"""Offline field extraction: regular expressions and keyword lists in CA/ES/EN/FR.

Used when no API key is set, and as a safety net next to Claude (emails and phones always
come from here). Returns a dict of field updates; never touches prices.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from ..pricing.config import ClientConfig

NUM = r"(\d+(?:[.,]\d+)?)"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s.-]{7,}\d)")
DIMS_RE = re.compile(NUM + r"\s*(?:mm)?\s*[x×*]\s*" + NUM + r"(?:\s*[x×*]\s*" + NUM + r")?\s*(mm|cm)?", re.I)
MM_RE = re.compile(NUM + r"\s*mm\b", re.I)
THICK_WORD_RE = re.compile(r"(?:gruix|grossor|espesor|espessor|grosor|thickness|thick|epaisseur|ep\.?|e\s*=|t\s*=)\s*(?:de|of|:|=)?\s*" + NUM, re.I)
QTY_RE = re.compile(r"(\d[\d.]*)\s*(?:u\b|uds?\b|unitats?|unidades?|units?|unites?|peces|peça|piezas?|pieces?|parts?|pcs|pzas?|ut\b|exemplars?|ejemplares?|brackets?|soportes?|suports?|plaques?|placas?|plates?|pletines?|bridas?|brides?|flanges?|escaires?|escuadras?|tapes?|tapas?|xapes?|chapas?)", re.I)
QTY_LOOSE_RE = re.compile(r"(\d[\d.]*)\s+(?:[a-zà-ÿ'·]+\s+){1,2}?(?:" + QTY_RE.pattern.split("(?:", 1)[1], re.I)
QTY_X_RE = re.compile(r"(?:\bx\s*(\d+)\b|\b(\d+)\s*x\b(?!\s*\d))", re.I)
HOLES_RE = re.compile(r"(\d+)\s*(?:forats?|agujeros?|holes?|trous?|taladros?|perforacions?|perforaciones?)", re.I)
HOLE_D_RE = re.compile(r"(?:ø|diametre|diametro|diameter|d\s*=)\s*" + NUM, re.I)
BENDS_RE = re.compile(r"(\d+)\s*(?:plecs?|plegs?|plegats?|pliegues?|plegados?|dobleces?|doblecs?|bends?|plis?)", re.I)
DAYS_RE = re.compile(r"(\d+)\s*(dies|dias|days|jours|setmanes|setmana|semanas?|weeks?|semaines?)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b")

PROCESS_WORDS = {
    "bending": ["pleg", "plec", "doblad", "doblar", "doblec", "bend", "plier", "pliage", "pli "],
    "welding": ["sold", "weld", "soud"],
    "machining": ["mecanitz", "mecaniz", "machin", "usinag", "fresa", "torn"],
    "laser": ["laser", "tall", "corte", "cortar", "cut", "decoup"],
}
FINISH_WORDS = {
    "galvanising": ["galvanitzat en calent", "galvanizado en caliente", "hot-dip", "hot dip", "galvanisation"],
    "powder_coating": ["pintura", "pintat", "pintad", "lacat", "lacad", "powder", "peinture", "thermolaqu", "epoxi"],
    "deburring": ["desbarb", "deburr", "ebavur"],
    "none": ["sense acabat", "sin acabado", "no finish", "en brut", "en bruto", "raw", "sans finition", "cap acabat", "ningun acabado", "ninguno", "cap", "no cal", "no hace falta", "none"],
}
NO_DRAWING_WORDS = ["no tinc plano", "no tinc planol", "sense planol", "no tengo plano", "sin plano",
                    "no drawing", "don't have a drawing", "pas de plan", "no tenim planol", "no tenemos plano"]
URGENT_WORDS = ["urgent", "urgente", "asap", "tan aviat com", "lo antes posible", "cuanto antes", "au plus vite"]
TOMORROW_WORDS = ["dema", "manana", "tomorrow", "demain"]
NEXT_WEEK_WORDS = ["setmana que ve", "proxima setmana", "semana que viene", "proxima semana", "next week", "semaine prochaine"]
PICKUP_WORDS = ["recoll", "recog", "pick up", "pickup", "collect", "retrait", "a taller", "al taller", "en taller"]
NAME_PATTERNS = [
    r"(?:em dic|soc|sóc|me llamo|soy|my name is|i am|i'm|je m'appelle|je suis)\s+([A-ZÀ-Ý][\wÀ-ÿ'·.-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'·.-]+){0,3})",
]
COMPANY_PATTERNS = [
    r"(?:de l'empresa|de la empresa|l'empresa|la empresa|empresa|company|from|de la societe|societe|entreprise)\s+([\wÀ-ÿ&'·.,-]+(?:\s+[\wÀ-ÿ&'·.-]+){0,4})",
    r"\b([A-ZÀ-Ý][\wÀ-ÿ&'·.-]*(?:\s+[A-ZÀ-Ý&][\wÀ-ÿ&'·.-]*){0,3}\s+(?:S\.?L\.?U?|S\.?A\.?|SARL|SAS|Ltd|GmbH))\b",
]
LANG_HINTS = {
    "ca": ["peces", "gruix", "necessito", "necessitem", "voldria", "planol", "amb", "dels", "quantes", "tinc", "acer", "xapa", "forats", "plecs", "bon dia", "gracies", "si us plau", "unes", "per a"],
    "es": ["piezas", "espesor", "necesito", "necesitamos", "quisiera", "plano", "con", "cuantas", "tengo", "acero", "chapa", "agujeros", "pliegues", "buenos dias", "gracias", "por favor", "unas", "para"],
    "en": ["pieces", "parts", "thickness", "need", "would like", "drawing", "with", "how many", "have", "steel", "sheet", "holes", "bends", "hello", "thanks", "please", "quote"],
    "fr": ["pieces", "epaisseur", "besoin", "voudrais", "plan", "avec", "combien", "acier", "tole", "trous", "plis", "bonjour", "merci", "devis", "nous"],
}


def fold(s: str) -> str:
    """Lowercase and strip accents, for keyword matching."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _business_days_until(target: date, today: date) -> int:
    days, d = 0, today
    while d < target:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def detect_language(text: str) -> str | None:
    f = f" {fold(text)} "
    scores = {lang: sum(1 for w in words if f" {w}" in f) for lang, words in LANG_HINTS.items()}
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    return best if ranked[0] >= 2 and ranked[0] > ranked[1] else None


def match_material(text: str, cfg: ClientConfig) -> str | None:
    f = f" {fold(text)} "
    # galvanised sheet vs. hot-dip galvanising as a finish
    if any(w in f for w in FINISH_WORDS["galvanising"]):
        f = f.replace("galvan", "")
    best, best_len = None, 0
    for key, m in cfg.materials.items():
        for alias in m.aliases + [key]:
            a = fold(alias)
            if re.search(rf"(?<![\w.]){re.escape(a)}(?![\w])", f) and len(a) > best_len:
                best, best_len = key, len(a)
    return best


def extract(text: str, cfg: ClientConfig, asked: list[str] | None = None,
            today: date | None = None) -> dict:
    asked = asked or []
    today = today or date.today()
    out: dict = {}
    f = fold(text)
    stripped = text.strip()

    if m := EMAIL_RE.search(text):
        out["email"] = m.group(0)
    text_wo_email = EMAIL_RE.sub(" ", text)

    # dimensions first, so "200 x 150 mm" is not read as a thickness or a quantity
    dims = DIMS_RE.search(text_wo_email)
    rest = DIMS_RE.sub(" ", text_wo_email)
    if dims:
        k = 10.0 if (dims.group(4) or "").lower() == "cm" else 1.0
        a, b = _num(dims.group(1)) * k, _num(dims.group(2)) * k
        part = {"w": max(a, b), "h": min(a, b)}
        if dims.group(3):
            third = _num(dims.group(3)) * k
            if third <= 30:
                out["thickness_mm"] = third
        if hm := HOLES_RE.search(text_wo_email):
            part["holes"] = int(hm.group(1))
        if hd := HOLE_D_RE.search(text_wo_email):
            part["hole_d"] = _num(hd.group(1))
        out["described_part"] = part

    if m := PHONE_RE.search(rest):
        digits = re.sub(r"\D", "", m.group(0))
        if 9 <= len(digits) <= 13 and not MM_RE.search(m.group(0)):
            out["phone"] = m.group(0).strip()
            rest = rest.replace(m.group(0), " ")

    if m := THICK_WORD_RE.search(fold(rest)):
        out["thickness_mm"] = _num(m.group(1))
    elif "thickness_mm" not in out:
        for m in MM_RE.finditer(rest):
            v = _num(m.group(1))
            if 0.5 <= v <= 30:
                out["thickness_mm"] = v
                break

    if m := QTY_RE.search(rest):
        out["quantity"] = int(m.group(1).replace(".", ""))
    elif m := QTY_LOOSE_RE.search(rest):
        out["quantity"] = int(m.group(1).replace(".", ""))
    elif m := QTY_X_RE.search(rest):
        out["quantity"] = int(m.group(1) or m.group(2))

    if m := BENDS_RE.search(rest):
        out["bends_per_part"] = int(m.group(1))

    if mat := match_material(text, cfg):
        out["material"] = mat
    if m := re.search(r"\b(304l?|316l?|s235|s275|s355|5754|5083|6082|dc01|dx51d)\b", f):
        out["grade"] = m.group(1).upper()

    fw = fold(EMAIL_RE.sub(" ", text))
    procs = [p for p, words in PROCESS_WORDS.items() if any(re.search(rf"(?<!\w){re.escape(w)}", fw) for w in words)]
    if procs:
        out["processes"] = sorted(set(procs) | {"laser"}, key=["laser", "bending", "welding", "machining"].index)
    if "bends_per_part" in out:
        out.setdefault("processes", ["laser", "bending"])
        if "bending" not in out["processes"]:
            out["processes"].append("bending")

    for key, words in FINISH_WORDS.items():
        if key == "none" and "finish" not in asked and not any(w in f for w in words[:8]):
            continue
        if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", f) for w in words):
            out["finish"] = key
            break

    if any(w in f for w in NO_DRAWING_WORDS):
        out["no_drawing"] = True

    # deadline
    if m := DAYS_RE.search(f):
        n = int(m.group(1))
        unit = m.group(2)
        weeks = unit.startswith(("set", "sem", "week"))
        out["deadline_working_days"] = n * 5 if weeks else max(1, round(n * 5 / 7))  # calendar days
        out["deadline_text"] = m.group(0)
    elif any(w in f for w in URGENT_WORDS):
        out["deadline_working_days"], out["deadline_text"] = 2, "urgent"
    elif any(w in f for w in TOMORROW_WORDS):
        out["deadline_working_days"], out["deadline_text"] = 1, "tomorrow"
    elif any(w in f for w in NEXT_WEEK_WORDS):
        out["deadline_working_days"], out["deadline_text"] = 5, "next week"
    elif (m := DATE_RE.search(rest)) and not dims:
        try:
            d, mo = int(m.group(1)), int(m.group(2))
            y = int(m.group(3)) if m.group(3) else today.year
            y = y + 2000 if y < 100 else y
            target = date(y, mo, d)
            if target < today:
                target = date(y + 1, mo, d)
            out["deadline_working_days"] = _business_days_until(target, today)
            out["deadline_text"] = target.isoformat()
        except ValueError:
            pass

    for pat in NAME_PATTERNS:
        if m := re.search(pat, text, re.I):
            out["name"] = m.group(1).strip(" .,")
            break
    for pat in COMPANY_PATTERNS:
        if m := re.search(pat, text):
            out["company"] = m.group(1).strip(" .,")
            break

    # --- short answers to the question we just asked
    bare = re.fullmatch(r"\s*" + NUM + r"\s*(mm|u|uds|unitats|unidades|peces|piezas|pcs)?\s*\.?\s*", f)
    if bare and asked:
        v = _num(bare.group(1))
        for field in asked:
            if field == "thickness" and "thickness_mm" not in out and v <= 50:
                out["thickness_mm"] = v
                break
            if field == "quantity" and "quantity" not in out:
                out["quantity"] = int(v)
                break
            if field == "bends" and "bends_per_part" not in out:
                out["bends_per_part"] = int(v)
                break
    if "name" in asked and "name" not in out and not out.get("email") and not out.get("phone") and len(stripped) <= 80:
        parts = [p.strip() for p in re.split(r",|;| - | / |\bde\b|\bfrom\b", stripped, maxsplit=1)]
        if parts and 0 < len(parts[0].split()) <= 4:
            out["name"] = parts[0]
            if len(parts) > 1 and parts[1] and "company" not in out:
                out["company"] = parts[1]
    if "delivery" in asked and "delivery" not in out and len(stripped) <= 80:
        out["delivery"] = "pickup" if any(w in f for w in PICKUP_WORDS) else stripped
    if "deadline" in asked and "deadline_text" not in out and len(stripped) <= 60:
        out["deadline_text"] = stripped
    if "material" in asked and "material" not in out and len(stripped) <= 60 and not bare:
        out["material_text"] = stripped
    return out
