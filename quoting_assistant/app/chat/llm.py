"""Claude adapter: field extraction (cheap model) and reply wording (chat model).

The language model never sees or produces prices it could invent: prices come from the
pricing engine and are shown in a separate card. Replies that mention euro amounts are
discarded and replaced by the fixed templates.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from pathlib import Path

import anthropic

from .. import db
from ..pricing.config import ClientConfig

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"

# USD per million tokens (input, output). Keep in sync with Anthropic's price list.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
LANGUAGE_NAMES = {"ca": "Catalan", "es": "Spanish", "en": "English", "fr": "French"}
MONEY_RE = re.compile(r"(€|\beur\b|\beuros?\b|\d\s*€)", re.I)


def load_prompt(name: str, **values) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


def extraction_schema(cfg: ClientConfig) -> dict:
    s, n, i = {"type": "string"}, {"type": "number"}, {"type": "integer"}
    props = {
        "name": _nullable(s), "company": _nullable(s), "email": _nullable(s), "phone": _nullable(s),
        "material": _nullable({"type": "string", "enum": list(cfg.materials) + ["other"]}),
        "material_text": _nullable(s), "grade": _nullable(s),
        "thickness_mm": _nullable(n), "quantity": _nullable(i),
        "processes": _nullable({"type": "array", "items": {"type": "string", "enum": ["laser", "bending", "welding", "machining"]}}),
        "bends_per_part": _nullable(i),
        "finish": _nullable({"type": "string", "enum": sorted(set(cfg.finishes) | {"none"})}),
        "deadline_text": _nullable(s), "deadline_working_days": _nullable(n), "delivery": _nullable(s),
        "described_part": _nullable({
            "type": "object",
            "properties": {"w": n, "h": n, "holes": _nullable(i), "hole_d": _nullable(n)},
            "required": ["w", "h", "holes", "hole_d"], "additionalProperties": False}),
        "no_drawing": _nullable({"type": "boolean"}),
        "off_topic": {"type": "boolean"},
        "comment": _nullable(s),
    }
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


class ClaudeLLM:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model_chat = os.environ.get("MODEL_CHAT", "claude-sonnet-5-5")
        self.model_extract = os.environ.get("MODEL_EXTRACT", "claude-haiku-5-5")

    def _log(self, client_id: str, cid: str | None, purpose: str, model: str, usage) -> None:
        pin, pout = PRICES.get(model, (0.0, 0.0))
        inp = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cost = inp / 1e6 * pin + usage.output_tokens / 1e6 * pout
        db.log_usage(client_id, cid, purpose, model, inp, usage.output_tokens, round(cost, 6))

    # ------------------------------------------------------------------ extraction
    def extract(self, cfg: ClientConfig, cid: str | None, text: str, asked: list[str],
                pdf_b64: str | None = None) -> dict | None:
        system = load_prompt(
            "extract_fields", shop=cfg.client.name,
            materials=", ".join(f"{k} ({cfg.material_label(k, 'en')})" for k in cfg.materials),
            finishes=", ".join(sorted(set(cfg.finishes) | {"none"})),
            today=date.today().isoformat(), asked=", ".join(asked) or "nothing yet")
        content: list[dict] = []
        if pdf_b64:
            content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}})
        content.append({"type": "text", "text": text or "(see attached document)"})
        try:
            resp = self.client.messages.create(
                model=self.model_extract, max_tokens=2000, system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": extraction_schema(cfg)}},
            )
        except anthropic.APIConnectionError as e:
            log.warning("extract: connection error %s", e)
            return None
        except anthropic.APIStatusError as e:
            log.warning("extract: API error %s %s", e.status_code, e.message)
            return None
        self._log(cfg.client.id, cid, "extract", self.model_extract, resp.usage)
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None
        txt = next((b.text for b in resp.content if b.type == "text"), None)
        try:
            data = json.loads(txt) if txt else None
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        out = {k: v for k, v in data.items() if v not in (None, [], "")}
        if out.get("material") == "other":
            out.pop("material")
        return out

    # ------------------------------------------------------------------ reply wording
    def reply(self, cfg: ClientConfig, cid: str | None, lang: str, situation: dict,
              history: list[dict]) -> str | None:
        offered = ", ".join(cfg.client.processes_offered)
        system = load_prompt(
            "reply", shop=cfg.client.name, processes=offered,
            materials=", ".join(cfg.material_label(k, "en") for k in cfg.materials),
            max_sheet=" x ".join(f"{v:.0f}" for v in cfg.client.max_sheet_mm),
            language_name=LANGUAGE_NAMES.get(lang, "English"))
        messages = []
        for m in history[-8:]:
            if m["kind"] == "text" and m["text"]:
                messages.append({"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]})
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        messages.append({"role": "user", "content": "SITUATION (from our software, not from the customer):\n"
                         + json.dumps(situation, ensure_ascii=False)})
        # merge consecutive same-role turns
        merged: list[dict] = []
        for m in messages:
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n\n" + m["content"]
            else:
                merged.append(dict(m))
        try:
            resp = self.client.beta.messages.create(
                model=self.model_chat, max_tokens=2000, system=system, messages=merged,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        except anthropic.APIConnectionError as e:
            log.warning("reply: connection error %s", e)
            return None
        except anthropic.APIStatusError as e:
            log.warning("reply: API error %s %s", e.status_code, e.message)
            return None
        self._log(cfg.client.id, cid, "reply", self.model_chat, resp.usage)
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text or MONEY_RE.search(text):
            return None   # never let the model state a price: fall back to templates
        return text


def get_llm() -> ClaudeLLM | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return ClaudeLLM()
