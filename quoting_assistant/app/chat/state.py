"""What we know about one quote request, and what to ask next."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..pricing.engine import PartGeometry, QuoteRequest

# Asked in this order; at most two per turn. "Optional" fields are asked once, then skipped.
SPEC_FIELDS = ["drawing", "material", "thickness", "quantity", "bends"]
OPTIONAL_SPEC = ["deadline", "finish"]
CONTACT_FIELDS = ["name", "contact"]
OPTIONAL_CONTACT = ["delivery"]


@dataclass
class IntakeState:
    lang: str = "ca"
    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    material: str | None = None          # config key
    material_text: str | None = None     # what the customer wrote, if not recognised
    grade: str | None = None
    thickness_mm: float | None = None
    quantity: int | None = None
    processes: list[str] = field(default_factory=lambda: ["laser"])
    bends_per_part: int | None = None
    finish: str | None = None            # config key or "none"
    deadline_text: str | None = None
    deadline_working_days: float | None = None
    delivery: str | None = None
    no_drawing: bool = False             # customer said they have no drawing
    described_part: dict | None = None   # {"w":..,"h":..,"holes":..,"hole_d":..}
    parts: list[dict] = field(default_factory=list)       # PartGeometry as dicts
    unpriced_files: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    asked: list[str] = field(default_factory=list)        # fields asked in the last turn
    asked_once: list[str] = field(default_factory=list)
    estimate_shown: bool = False
    last_estimate_point: float | None = None
    handed_off: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "IntakeState":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    # ------------------------------------------------------------------ geometry
    def geometry(self) -> list[PartGeometry]:
        parts = [PartGeometry(**p) for p in self.parts]
        if not parts and self.described_part:
            d = self.described_part
            w, h = float(d["w"]), float(d["h"])
            holes = int(d.get("holes") or 0)
            hole_d = float(d.get("hole_d") or 10)
            parts.append(PartGeometry(
                name="described", cut_length_mm=2 * (w + h) + holes * 3.14159 * hole_d,
                pierces=1 + holes, bbox_w_mm=w, bbox_h_mm=h,
                area_mm2=w * h - holes * 3.14159 * hole_d ** 2 / 4, source="described"))
        return parts

    def quote_request(self) -> QuoteRequest:
        return QuoteRequest(
            material=self.material, thickness_mm=self.thickness_mm, quantity=self.quantity,
            parts=self.geometry(), processes=self.processes, bends_per_part=self.bends_per_part,
            finish=self.finish, deadline_working_days=self.deadline_working_days,
            unpriced_files=self.unpriced_files)

    # ------------------------------------------------------------------ what's missing
    def has_drawing_info(self) -> bool:
        return bool(self.parts or self.described_part)

    def needs_bends(self) -> bool:
        if "bending" not in self.processes or self.bends_per_part is not None:
            return False
        parts = self.geometry()
        return not parts or any(p.bends is None for p in parts)

    def missing_spec(self) -> list[str]:
        out = []
        if not self.has_drawing_info():
            out.append("drawing")
        if not self.material:
            out.append("material")
        if not self.thickness_mm:
            out.append("thickness")
        if not self.quantity:
            out.append("quantity")
        if self.needs_bends():
            out.append("bends")
        return out

    def can_price(self) -> bool:
        return not [f for f in self.missing_spec() if f != "bends"]

    def missing_contact(self) -> list[str]:
        out = []
        if not self.name:
            out.append("name")
        if not (self.email or self.phone):
            out.append("contact")
        return out

    def lead_label(self) -> str:
        who = self.company or self.name or self.email or self.phone or "?"
        return who
