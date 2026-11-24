from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import db
from app.chat.dialog import Assistant
from app.chat.llm import ClaudeLLM, extraction_schema
from app.chat.rules import detect_language, extract
from app.pricing.config import load_client_config

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db.init()


@pytest.fixture
def cfg():
    return load_client_config("demo_shop")


def texts(msgs):
    return " ".join(m["text"] or "" for m in msgs)


# ---------------------------------------------------------------- extraction rules
def test_extract_catalan_request(cfg):
    u = extract("Necessito 50 peces d'inoxidable 304 de 3 mm, tall i plegat amb 2 plecs, per d'aquí 2 setmanes",
                cfg, today=date(2026, 11, 24))
    assert u["material"] == "stainless_304" and u["thickness_mm"] == 3 and u["quantity"] == 50
    assert u["bends_per_part"] == 2 and "bending" in u["processes"] and u["deadline_working_days"] == 10


def test_extract_spanish_described_part(cfg):
    u = extract("200 piezas de 200x150 mm con 4 agujeros en chapa galvanizada de 1,5mm", cfg)
    assert u["described_part"] == {"w": 200, "h": 150, "holes": 4}
    assert u["thickness_mm"] == 1.5 and u["quantity"] == 200 and u["material"] == "galvanised"


def test_short_answers_fill_the_field_just_asked(cfg):
    assert extract("3", cfg, ["thickness"]) == {"thickness_mm": 3}
    assert extract("120", cfg, ["quantity"]) == {"quantity": 120}
    u = extract("Joan Puig, Metalls Puig SL", cfg, ["name", "contact"])
    assert u["name"] == "Joan Puig" and u["company"] == "Metalls Puig SL" and "processes" not in u


def test_contact_details(cfg):
    u = extract("joan@metallspuig.example o 938 123 456", cfg, ["contact"])
    assert u["email"] == "joan@metallspuig.example" and u["phone"] == "938 123 456"


def test_language_detection():
    assert detect_language("Bon dia, necessito peces d'acer amb forats") == "ca"
    assert detect_language("Buenos días, necesito piezas de acero con agujeros") == "es"
    assert detect_language("Hello, I need steel parts with holes, please") == "en"
    assert detect_language("ok") is None


# ---------------------------------------------------------------- conversation flow (offline)
def test_full_conversation_offline():
    a = Assistant()
    cid, first = a.start("demo_shop", "ca")
    assert "intel·ligència artificial" in first[0]["text"]          # AI Act art. 50 disclosure
    r = a.on_message(cid, "Necessitem 50 escaires d'acer de 2 mm, tallats i plegats")
    assert "plànol" in texts(r)                                      # asks for the drawing only
    r = a.on_file(cid, "escaire_plegat.dxf", (SAMPLES / "escaire_plegat.dxf").read_bytes())
    card = next(m for m in r if m["kind"] == "estimate")["payload"]
    assert card["low"] < card["high"] and "pendent de revisió" in card["title"]
    assert card["sample_values"] is True
    a.on_message(cid, "En 2 setmanes, sense acabat")
    a.on_message(cid, "Joan Puig, Metalls Puig SL")
    r = a.on_message(cid, "joan@metallspuig.example")
    assert "equip comercial" in texts(r)
    leads = db.list_leads("demo_shop")
    assert len(leads) == 1 and leads[0]["priority"] in "ABC" and leads[0]["value_eur"] > 0
    assert leads[0]["state"]["handed_off"] is True


def test_never_prices_without_enough_information():
    a = Assistant()
    cid, _ = a.start("demo_shop", "es")
    r = a.on_message(cid, "Hola, quería información para unas piezas de acero")
    assert not any(m["kind"] == "estimate" for m in r)
    assert "€" not in texts(r)


def test_step_file_goes_to_technician_and_lead_is_still_captured():
    a = Assistant()
    cid, _ = a.start("demo_shop", "es")
    a.on_file(cid, "soporte.step", b"ISO-10303-21; fake")
    r = a.on_message(cid, "acero 4 mm, 30 piezas")
    assert "técnico" in texts(r) and not any(m["kind"] == "estimate" for m in r)
    a.on_message(cid, "en 2 semanas, sin acabado")
    a.on_message(cid, "Ana Soler, Talleres Soler SL")
    a.on_message(cid, "ana@soler.example")
    lead = db.list_leads("demo_shop")[0]
    assert lead["value_eur"] is None and "revisar" in lead["summary"]


def test_rejects_unknown_file_types():
    a = Assistant()
    cid, _ = a.start("demo_shop", "ca")
    r = a.on_file(cid, "virus.exe", b"MZ")
    assert "no s'admet" in texts(r)


def test_question_is_noted_for_sales_offline():
    a = Assistant()
    cid, _ = a.start("demo_shop", "es")
    r = a.on_message(cid, "¿Hacéis también corte por agua?")
    assert "pregunta" in texts(r)
    assert db.get_conversation(cid)["state"]["comments"]


# ---------------------------------------------------------------- HTTP API
def test_api_round_trip():
    from app.main import app
    c = TestClient(app)
    assert c.get("/health").json()["mode"] == "offline"
    assert c.get("/widget.js").status_code == 200
    d = c.post("/api/demo_shop/conversations", json={"lang": "en"}).json()
    cid = d["conversation_id"]
    assert "AI system" in d["messages"][0]["text"]
    c.post(f"/api/conversations/{cid}/messages", json={"text": "100 flanges, stainless 304, 6 mm"})
    with open(SAMPLES / "brida_160.dxf", "rb") as fh:
        r = c.post(f"/api/conversations/{cid}/files", files={"file": ("brida_160.dxf", fh)}).json()
    assert any(m["kind"] == "estimate" for m in r["messages"])
    assert c.get(f"/api/conversations/{cid}").json()["client_name"] == "Taller Demo SL"
    assert c.post("/api/nope/conversations", json={}).status_code == 404
    assert c.get("/demo/sales").status_code == 200


# ---------------------------------------------------------------- Claude adapter (mocked, no network)
def _resp(text, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20))


class FakeMessages:
    def __init__(self, text):
        self.text, self.calls = text, []

    def create(self, **kw):
        self.calls.append(kw)
        return _resp(self.text)


def make_llm(text):
    llm = ClaudeLLM(api_key="test")
    fake = FakeMessages(text)
    llm.client = SimpleNamespace(messages=fake, beta=SimpleNamespace(messages=fake))
    return llm, fake


def test_extraction_schema_is_strict(cfg):
    s = extraction_schema(cfg)
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])


def test_claude_reply_with_a_price_is_discarded(cfg):
    llm, fake = make_llm("El preu és de 120 € per peça.")
    assert llm.reply(cfg, None, "ca", {"this_turn": []}, []) is None
    call = fake.calls[0]
    assert call["model"] == "claude-sonnet-5-5" and call["fallbacks"] == "default"
    assert "formal plural" in call["system"]


def test_claude_reply_used_and_cost_logged(cfg):
    llm, _ = make_llm("Gràcies. Quin gruix té la xapa?")
    assert llm.reply(cfg, "c1", "ca", {"this_turn": []}, []) == "Gràcies. Quin gruix té la xapa?"
    assert db.usage_by_client()[0]["cost_usd"] > 0


def test_claude_extraction_parsed_and_merged(cfg):
    llm, fake = make_llm('{"material": "aluminium", "thickness_mm": 4, "quantity": null, "off_topic": false, "comment": null}')
    out = llm.extract(cfg, None, "alu de 4", ["material"])
    assert out == {"material": "aluminium", "thickness_mm": 4, "off_topic": False}
    assert fake.calls[0]["model"] == "claude-haiku-5-5"
    assert fake.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_assistant_falls_back_to_templates_when_claude_states_prices():
    llm, _ = make_llm("Són 99 €.")
    llm.extract = lambda *a, **k: {}
    a = Assistant(llm=llm)
    cid, _ = a.start("demo_shop", "es")
    r = a.on_message(cid, "50 piezas de acero de 3 mm")
    assert "99 €" not in texts(r) and "plano" in texts(r)
