"""What agents are allowed to return. Their output is parsed into these models and then verified
by code (valuer.agents.verify) before anything reaches the fact store or a memo."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Scale = Literal["ones", "thousands", "millions", "billions"]

# key -> (unit, which analyst owns it, definition given to the agent)
EXTRACTION_KEYS: dict[str, tuple[str, str, str]] = {
    "options_outstanding": ("shares", "asset", "Number of stock options outstanding at period end."),
    "options_wavg_exercise_price": ("USD/shares", "asset", "Weighted-average exercise price of the options outstanding at period end."),
    "unvested_stock_awards": ("shares", "asset", "Unvested restricted stock, restricted stock units and performance share units outstanding at period end (the total across award types if the filing gives one; otherwise the largest single category, and say so in the note)."),
    "pension_benefit_obligation": ("USD", "liabilities", "Total projected benefit obligation of the defined benefit pension plans at period end (all plans, funded and unfunded)."),
    "contingent_possible_loss": ("USD", "liabilities", "Management's estimate of reasonably possible losses in excess of amounts accrued (litigation, environmental, tax). Use the top of the range if a range is given."),
    "guarantee_max_exposure": ("USD", "liabilities", "Maximum potential payments under guarantees of third-party obligations."),
    "purchase_obligations": ("USD", "liabilities", "Total unconditional purchase obligations or purchase commitments not recorded on the balance sheet."),
}


class Evidence(BaseModel):
    accession: str = Field(description="Accession number of the filing, as given by list_documents.")
    paragraph: int = Field(description="Paragraph number as shown by the search and read tools.")
    quote: str = Field(description="Text copied exactly from that one paragraph. One sentence or one table row.")


class Extraction(BaseModel):
    key: str = Field(description="One of the keys you were asked for.")
    status: Literal["found", "not_disclosed"]
    number_text: str | None = Field(default=None, description="The figure exactly as it appears inside the quote, e.g. '90,076'. Required when found.")
    add_number_texts: list[str] = Field(default_factory=list, description="Only when the filing gives the total in parts within the same table row (e.g. a U.S. column and a non-U.S. column): the further figures, exactly as printed in the same quote. Code adds them to number_text.")
    scale: Scale | None = Field(default=None, description="Units of the figures as presented in the filing. Required when found.")
    evidence: Evidence | None = Field(default=None, description="Where the figure is. Required when found.")
    scale_evidence: Evidence | None = Field(default=None, description="Where the filing states the scale (e.g. a heading saying 'in thousands'). Required for thousands, millions or billions unless the main quote itself says it.")
    note: str = Field(default="", description="One or two sentences: what was searched, or any caveat the owner should know before relying on the figure. No digits.")


class Observation(BaseModel):
    line: str = Field(description="Key of the valuation line or gap this bears on, or 'general'.")
    direction: Literal["lowers_value", "raises_value", "neutral"]
    statement: str = Field(description="What the filing shows and why it matters for this line, in one or two sentences. No digits.")
    evidence: Evidence


class AnalystReport(BaseModel):
    extractions: list[Extraction]
    observations: list[Observation]


class ParamOverride(BaseModel):
    param: str = Field(description="Parameter name exactly as listed in the valuation.")
    base: float = Field(description="The base-case value you would use instead.")


class Attack(BaseModel):
    target: str = Field(description="Line key, parameter name, or 'method'.")
    severity: Literal["high", "medium", "low"]
    claim: str = Field(description="Why the valuation is too high on this point. Two or three sentences. No digits.")
    evidence: Evidence | None = Field(default=None, description="A quote from a filing that supports the claim.")
    fact_id: str | None = Field(default=None, description="Alternatively, the id of a fact from the valuation or find_facts.")
    override: ParamOverride | None = Field(default=None, description="Optional: one parameter change that expresses this attack.")


class BearReport(BaseModel):
    summary: str = Field(description="The bear case in three or four sentences. No digits.")
    attacks: list[Attack]
