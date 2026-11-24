"""Lead scoring (first version; Milestone 3 refines it).

Score 0-100 from estimated value, quantity, completeness and urgency, then A/B/C.
Thresholds are per-client defaults that can move to config.yaml once a trial gives real data.
"""
from __future__ import annotations

from .chat.state import IntakeState
from .chat.texts import PROCESS
from .pricing.config import ClientConfig
from .pricing.engine import Estimate


def score_lead(cfg: ClientConfig, s: IntakeState, est: Estimate | None) -> dict:
    value = est.point if est and est.priced else None
    score = 0.0
    if value:
        score += min(50, value / 3000 * 50)              # value: full marks at 3,000 €
    if s.quantity:
        score += min(15, s.quantity / 500 * 15)           # volume hints at repeat work
    complete = sum(bool(x) for x in (s.material, s.thickness_mm, s.quantity, s.parts or s.described_part,
                                     s.name, s.company, s.email or s.phone))
    score += complete / 7 * 20
    if s.deadline_working_days is not None and s.deadline_working_days <= 5:
        score += 10                                       # urgent buyers decide fast
    if s.company:
        score += 5
    priority = "A" if score >= 55 else "B" if score >= 30 else "C"

    bits = [s.company or s.name or "?"]
    if s.quantity:
        bits.append(f"{s.quantity} u")
    if s.material:
        bits.append(cfg.material_label(s.material, "es") + (f" {s.thickness_mm:g} mm" if s.thickness_mm else ""))
    bits.append(" + ".join(PROCESS.get(p, {}).get("es", p) for p in s.processes))
    if est and est.priced:
        bits.append(f"{est.low:,.0f}–{est.high:,.0f} €".replace(",", "."))
        if est.needs_review:
            bits.append("revisar")
    else:
        bits.append("sin precio: revisar")
    if s.deadline_text:
        bits.append(f"plazo: {s.deadline_text}")
    return {"priority": priority, "score": round(score), "value_eur": value, "summary": " · ".join(bits)}
