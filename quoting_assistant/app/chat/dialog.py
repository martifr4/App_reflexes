"""Conversation flow. Channel-independent: the web widget and (later) WhatsApp call the same
`Assistant` methods.

Order of a conversation:
1. drawing / material / thickness / quantity (at most two questions per turn)
2. number of bends, if bending is requested and the drawing has no bend lines
3. indicative price card + deadline and finish (asked once)
4. contact name, company, email or phone
5. hand-off to sales (lead saved and ranked) + delivery location (asked once)
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

from .. import db
from ..pricing.config import ClientConfig, load_client_config
from ..pricing.dxf import parse_dxf
from ..pricing.engine import Estimate, estimate
from ..scoring import score_lead
from . import rules
from .llm import ClaudeLLM
from .state import OPTIONAL_SPEC, IntakeState
from .texts import CONFIDENCE, LANGS, render_note, t

ALLOWED_EXT = {".dxf", ".dwg", ".step", ".stp", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_BYTES = 20 * 1024 * 1024
ASK_KEYS = {"drawing": "ask_drawing", "material": "ask_material", "thickness": "ask_thickness",
            "quantity": "ask_quantity", "bends": "ask_bends", "deadline": "ask_deadline",
            "finish": "ask_finish", "name": "ask_name", "contact": "ask_contact", "delivery": "ask_delivery"}


def fmt_eur(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


class Assistant:
    def __init__(self, llm: ClaudeLLM | None = None):
        self.llm = llm

    # ------------------------------------------------------------------ public API
    def start(self, client_id: str, lang: str | None = None, channel: str = "web") -> tuple[str, list[dict]]:
        cfg = load_client_config(client_id)
        lang = lang if lang in cfg.client.languages else cfg.client.default_language
        state = IntakeState(lang=lang)
        cid = db.create_conversation(client_id, state.to_dict(), channel)
        msg = db.add_message(cid, "assistant", t("greeting", lang, shop=cfg.client.name))
        return cid, [msg]

    def on_message(self, cid: str, text: str) -> list[dict]:
        conv, cfg, state = self._load(cid)
        text = text.strip()[:4000]
        db.add_message(cid, "user", text)
        detected = rules.detect_language(text)
        if detected and detected in cfg.client.languages:
            state.lang = detected

        updates = rules.extract(text, cfg, state.asked)
        off_topic = False
        if self.llm:
            llm_updates = self.llm.extract(cfg, cid, text, state.asked)
            if llm_updates:
                off_topic = bool(llm_updates.pop("off_topic", False))
                for k, v in llm_updates.items():
                    if k in ("email", "phone") and k in updates:
                        continue          # regex wins for contact details
                    updates[k] = v
        meaningful = {k for k, v in updates.items()
                      if k != "processes" or set(v) - set(state.processes)}
        question_only = not self.llm and "?" in text and not meaningful
        self._apply(state, updates)
        events = [{"type": "off_topic"}] if off_topic and not meaningful else []
        if question_only:
            state.comments.append(text)          # the sales team will answer it
            events.append({"type": "question_noted"})
        return self._turn(cid, conv, cfg, state, events, text)

    def on_file(self, cid: str, filename: str, data: bytes) -> list[dict]:
        conv, cfg, state = self._load(cid)
        safe = re.sub(r"[^\w.\- ]", "_", Path(filename).name)[:120] or "file"
        ext = Path(safe).suffix.lower()
        db.add_message(cid, "user", safe, kind="file")
        if ext not in ALLOWED_EXT or len(data) > MAX_FILE_BYTES:
            msg = db.add_message(cid, "assistant", t("file_rejected", state.lang))
            return [msg]
        path = db.upload_dir(conv["client_id"], cid) / f"{len(state.parts) + len(state.unpriced_files)}_{safe}"
        path.write_bytes(data)
        events: list[dict] = []
        parsed = None
        if ext == ".dxf":
            try:
                g = parse_dxf(path, name=Path(safe).stem)
                state.parts.append(g.__dict__)
                parsed = g.__dict__
                events.append({"type": "file_read", "file": safe, "w": g.bbox_w_mm, "h": g.bbox_h_mm,
                               "cut_m": round(g.cut_length_mm / 1000, 2), "pierces": g.pierces, "bends": g.bends})
                if g.bends:
                    if "bending" not in state.processes:
                        state.processes.append("bending")
            except Exception:  # noqa: BLE001 - any unreadable DXF goes to a human
                state.unpriced_files.append(safe)
                events.append({"type": "file_error", "file": safe})
        else:
            state.unpriced_files.append(safe)
            events.append({"type": "file_other", "file": safe})
            if ext == ".pdf" and self.llm:
                upd = self.llm.extract(cfg, cid, "", state.asked, pdf_b64=base64.b64encode(data).decode())
                if upd:
                    upd.pop("off_topic", None)
                    self._apply(state, upd)
        db.add_file(cid, conv["client_id"], safe, path, ext.lstrip("."), parsed)
        return self._turn(cid, conv, cfg, state, events, f"[file: {safe}]")

    # ------------------------------------------------------------------ internals
    def _load(self, cid: str):
        conv = db.get_conversation(cid)
        if not conv:
            raise KeyError(cid)
        cfg = load_client_config(conv["client_id"])
        return conv, cfg, IntakeState.from_dict(conv["state"])

    @staticmethod
    def _apply(state: IntakeState, upd: dict) -> None:
        for k, v in upd.items():
            if k == "processes":
                for p in v:
                    if p not in state.processes:
                        state.processes.append(p)
            elif k == "comment":
                if v and v not in state.comments:
                    state.comments.append(v)
            elif k == "material" and v:
                state.material, state.material_text = v, None
            elif k in state.__dataclass_fields__ and v not in (None, ""):
                setattr(state, k, v)
        if upd.get("bends_per_part") is not None and "bending" not in state.processes:
            state.processes.append("bending")

    def _plan(self, state: IntakeState) -> tuple[str, list[str]]:
        hard = [f for f in state.missing_spec() if f != "bends"]
        if "drawing" in hard and state.unpriced_files:
            hard.remove("drawing")       # a STEP/PDF came in: a technician will measure it
        if hard:
            return "spec", hard[:2]
        if state.needs_bends() and "bends" not in state.asked_once:
            return "spec", ["bends"]
        optional = [f for f in OPTIONAL_SPEC if f not in state.asked_once
                    and not (state.deadline_text if f == "deadline" else state.finish)]
        if optional:
            return "spec", optional
        contact = state.missing_contact()
        if contact:
            return "contact", contact
        return "done", []

    def _estimate(self, cfg: ClientConfig, state: IntakeState) -> Estimate | None:
        return estimate(cfg, state.quote_request()) if state.can_price() else None

    def _card(self, cfg: ClientConfig, est: Estimate, lang: str) -> dict:
        notes = [n for n in (render_note(n.__dict__, lang) for n in est.notes) if n]
        return {
            "title": t("card_title", lang), "currency": est.currency,
            "low": est.low, "high": est.high, "low_fmt": fmt_eur(est.low), "high_fmt": fmt_eur(est.high),
            "per_unit": est.per_unit_point, "per_unit_label": t("per_unit", lang),
            "confidence": est.confidence, "confidence_label": f"{t('confidence', lang)}: {CONFIDENCE[est.confidence][lang]}",
            "needs_review": est.needs_review, "notes": notes, "sample_values": cfg.client.sample_values,
        }

    def _turn(self, cid: str, conv: dict, cfg: ClientConfig, state: IntakeState,
              events: list[dict], user_text: str) -> list[dict]:
        lang = state.lang if state.lang in LANGS else "en"
        shop = cfg.client.name
        est = self._estimate(cfg, state)
        card = None
        if est and est.priced:
            if not state.estimate_shown or abs((state.last_estimate_point or 0) - est.point) > 0.005:
                events.append({"type": "estimate", "updated": state.estimate_shown,
                               "low": est.low, "high": est.high})
                card = self._card(cfg, est, lang)
                state.estimate_shown = True
                state.last_estimate_point = est.point
        elif est is not None or (not state.has_drawing_info() and state.unpriced_files
                                 and not [f for f in state.missing_spec() if f not in ("drawing", "bends")]):
            if "_no_price" not in state.asked_once:
                events.append({"type": "no_price"})
                state.asked_once.append("_no_price")

        phase, ask = self._plan(state)
        if phase == "done" and not state.handed_off:
            state.handed_off = True
            events.append({"type": "handoff", "name": state.name or ""})
            if not state.delivery and "delivery" not in state.asked_once:
                ask = ["delivery"]
        elif phase == "done" and not events:
            events.append({"type": "after_handoff"})
        if state.email or state.phone:
            lead = score_lead(cfg, state, est)
            db.upsert_lead(cid, conv["client_id"], lead["priority"], lead["value_eur"], lead["summary"],
                           est.to_dict() if est else None)

        state.asked = ask
        for f in ask:
            if f in ("deadline", "finish", "bends", "delivery") and f not in state.asked_once:
                state.asked_once.append(f)

        text = None
        if self.llm:
            situation = {
                "customer_wrote": user_text,
                "known": self._known(cfg, state),
                "this_turn": events,
                "questions_to_ask": [{"field": f, "suggested_wording": t(ASK_KEYS[f], lang)} for f in ask],
            }
            text = self.llm.reply(cfg, cid, lang, situation, db.get_messages(cid))
        if not text:
            text = self._template_reply(events, ask, lang, shop)
        out = [db.add_message(cid, "assistant", text)]
        if card:
            out.append(db.add_message(cid, "assistant", None, kind="estimate", payload=card))
        db.save_state(cid, state.to_dict())
        return out

    @staticmethod
    def _known(cfg: ClientConfig, s: IntakeState) -> dict:
        return {k: v for k, v in {
            "material": cfg.material_label(s.material, "en") if s.material else s.material_text,
            "thickness_mm": s.thickness_mm, "quantity": s.quantity, "processes": s.processes,
            "bends_per_part": s.bends_per_part, "finish": s.finish, "deadline": s.deadline_text,
            "drawings_read": [p["name"] for p in s.parts], "files_for_technician": s.unpriced_files,
            "name": s.name, "company": s.company, "has_contact": bool(s.email or s.phone),
            "delivery": s.delivery, "request_sent_to_sales": s.handed_off,
        }.items() if v not in (None, [], False)}

    @staticmethod
    def _template_reply(events: list[dict], ask: list[str], lang: str, shop: str) -> str:
        parts = []
        for e in events:
            k = e["type"]
            if k == "file_read":
                bends = t("file_dxf_bends", lang, n=e["bends"]) if e.get("bends") else ""
                parts.append(t("file_dxf", lang, file=e["file"], w=f"{e['w']:g}", h=f"{e['h']:g}",
                               cut=f"{e['cut_m']:g}".replace(".", "," if lang in ("ca", "es", "fr") else "."),
                               pierces=e["pierces"], bends=bends))
            elif k in ("file_other", "file_error"):
                parts.append(t(k, lang, file=e["file"]))
            elif k == "estimate":
                key = "estimate_updated" if e["updated"] else "estimate_intro"
                parts.append(t(key, lang, low=fmt_eur(e["low"]), high=fmt_eur(e["high"]), shop=shop))
            elif k == "no_price":
                parts.append(t("no_price", lang, shop=shop))
            elif k == "handoff":
                txt = t("handoff", lang, name=e["name"], shop=shop)
                parts.append(txt.replace(", .", ".").replace(" ,", ","))
            elif k == "after_handoff":
                parts.append(t("after_handoff", lang))
            elif k == "question_noted":
                parts.append(t("question_noted", lang))
            elif k == "off_topic":
                parts.append(t("off_topic", lang, shop=shop))
        parts += [t(ASK_KEYS[f], lang) for f in ask]
        return " ".join(parts) if parts else t("after_handoff", lang)
