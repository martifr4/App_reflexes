"""Per-client configuration: load and validate clients/<id>/config.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
CLIENTS_DIR = ROOT / "clients"


class OfficeHours(BaseModel):
    weekdays: list[int] = [0, 1, 2, 3, 4]
    start: str = "08:00"
    end: str = "17:00"
    timezone: str = "Europe/Madrid"


class ClientInfo(BaseModel):
    id: str
    name: str
    languages: list[str] = ["ca", "es", "en", "fr"]
    default_language: str = "ca"
    sales_email: str = ""
    office_hours: OfficeHours = OfficeHours()
    processes_offered: list[str] = ["laser"]
    max_sheet_mm: tuple[float, float] = (3000, 1500)
    sample_values: bool = False


class QuantityDiscount(BaseModel):
    from_: int = Field(alias="from")
    discount: float


class Rush(BaseModel):
    under_days: float
    surcharge: float


class Pricing(BaseModel):
    currency: str = "EUR"
    margin: float
    minimum_order: float = 0.0
    programming_per_part_type: float = 0.0
    material_basis: str = "bbox"
    bands: dict[str, tuple[float, float]]
    quantity_discounts: list[QuantityDiscount] = []
    rush: list[Rush] = []

    @field_validator("material_basis")
    @classmethod
    def _basis(cls, v: str) -> str:
        if v not in ("bbox", "net"):
            raise ValueError("material_basis must be 'bbox' or 'net'")
        return v


class Material(BaseModel):
    label: dict[str, str]
    aliases: list[str] = []
    density_kg_m3: float
    price_per_kg: float
    scrap_factor: float = 1.0
    cut_per_m: dict[float, float]
    pierce_each: dict[float, float]


class Bending(BaseModel):
    setup_per_part_type: float
    per_bend: dict[float, float]
    max_thickness_mm: float
    max_length_mm: float = 3000


class Welding(BaseModel):
    per_hour: float


class Finish(BaseModel):
    label: dict[str, str] = {}
    per_m2: float = 0.0
    per_kg: float = 0.0
    setup: float = 0.0
    sides: int = 1


class ClientConfig(BaseModel):
    client: ClientInfo
    pricing: Pricing
    materials: dict[str, Material]
    bending: Bending | None = None
    welding: Welding | None = None
    finishes: dict[str, Finish] = {}

    def material_label(self, key: str, lang: str) -> str:
        m = self.materials[key]
        return m.label.get(lang) or m.label.get("en") or key

    def finish_label(self, key: str, lang: str) -> str:
        f = self.finishes.get(key)
        if not f or not f.label:
            return key
        return f.label.get(lang) or f.label.get("en") or key


def load_config_file(path: Path) -> ClientConfig:
    with open(path, encoding="utf-8") as fh:
        return ClientConfig.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=64)
def load_client_config(client_id: str) -> ClientConfig:
    if not client_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid client id")
    path = CLIENTS_DIR / client_id / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no config for client {client_id!r}")
    return load_config_file(path)
