"""FastAPI app: chat API for the widget, the widget script, and demo pages.

Run: uvicorn app.main:app --reload   (from quoting_assistant/)
"""
from __future__ import annotations

import html
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from . import db  # noqa: E402  (after load_dotenv so DATA_DIR is honoured)
from .chat.dialog import MAX_FILE_BYTES, Assistant  # noqa: E402
from .chat.llm import get_llm  # noqa: E402
from .chat.texts import PROCESS  # noqa: E402
from .pricing.config import load_client_config  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Quoting assistant", docs_url="/api/docs")
# The widget is embedded on client websites, so the chat API answers any origin (no cookies).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
db.init()
assistant = Assistant(llm=get_llm())


class StartIn(BaseModel):
    lang: str | None = None


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _public(msgs: list[dict]) -> list[dict]:
    return [{"role": m["role"], "kind": m["kind"], "text": m["text"], "payload": m["payload"]} for m in msgs]


@app.get("/health")
def health():
    return {"ok": True, "mode": "claude" if assistant.llm else "offline"}


@app.get("/widget.js")
def widget_js():
    return FileResponse(STATIC / "widget.js", media_type="application/javascript")


@app.post("/api/{client_id}/conversations")
def start(client_id: str, body: StartIn):
    try:
        cid, msgs = assistant.start(client_id, body.lang)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "unknown client")
    cfg = load_client_config(client_id)
    return {"conversation_id": cid, "client_name": cfg.client.name, "lang": body.lang or cfg.client.default_language,
            "languages": cfg.client.languages, "messages": _public(msgs)}


@app.post("/api/conversations/{cid}/messages")
def message(cid: str, body: MessageIn):
    try:
        return {"messages": _public(assistant.on_message(cid, body.text))}
    except KeyError:
        raise HTTPException(404, "unknown conversation")


@app.post("/api/conversations/{cid}/files")
async def upload(cid: str, file: UploadFile = File(...)):
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        return {"messages": _public(assistant.on_file(cid, file.filename or "file", data))}
    except KeyError:
        raise HTTPException(404, "unknown conversation")


@app.get("/api/conversations/{cid}")
def history(cid: str):
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "unknown conversation")
    cfg = load_client_config(conv["client_id"])
    return {"lang": conv["state"]["lang"], "client_name": cfg.client.name, "messages": _public(db.get_messages(cid))}


# ---------------------------------------------------------------- demo pages
@app.get("/")
def root():
    return RedirectResponse("/demo")


@app.get("/demo")
def demo_page():
    return FileResponse(STATIC / "demo.html", media_type="text/html")


@app.get("/demo/samples/{name}")
def sample_file(name: str):
    path = ROOT / "samples" / Path(name).name
    if path.suffix != ".dxf" or not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/dxf", filename=path.name)


def _allowed(request: Request) -> bool:
    key = os.environ.get("DASHBOARD_KEY")
    if key:
        return request.query_params.get("key") == key
    return request.client is not None and request.client.host in ("127.0.0.1", "::1", "localhost", "testclient")


@app.get("/demo/sales", response_class=HTMLResponse)
def sales_view(request: Request, client: str = "demo_shop"):
    """What the sales team receives: requests ranked by priority and value. (Full dashboard: Milestone 4.)"""
    if not _allowed(request):
        raise HTTPException(403, "set DASHBOARD_KEY and pass ?key=")
    cfg = load_client_config(client)
    rows = []
    for lead in db.list_leads(client):
        s = lead["state"]
        est = lead["estimate"] or {}
        price = f"{est['low']:,.0f}–{est['high']:,.0f} €".replace(",", ".") if est.get("priced") else "—"
        files = ", ".join([p["name"] + ".dxf" for p in s.get("parts", [])] + s.get("unpriced_files", [])) or "—"
        contact = " · ".join(x for x in (s.get("email"), s.get("phone")) if x)
        procs = " + ".join(PROCESS.get(p, {}).get("es", p) for p in s.get("processes", []))
        rows.append(f"""<tr><td><span class="p p{lead['priority']}">{lead['priority']}</span></td>
          <td><b>{html.escape(s.get('company') or s.get('name') or '?')}</b><br><small>{html.escape(s.get('name') or '')}</small></td>
          <td>{html.escape(contact)}</td><td class="num">{price}</td>
          <td>{html.escape(lead['summary'])}<br><small>{html.escape(procs)} · {html.escape(files)}</small>
          {('<br><small>Preguntas: ' + html.escape(' | '.join(s.get('comments', []))) + '</small>') if s.get('comments') else ''}</td>
          <td>{lead['status']}</td><td><small>{lead['submitted_at'][:16].replace('T', ' ')} UTC</small></td></tr>""")
    body = "".join(rows) or '<tr><td colspan="7">Todavía no hay solicitudes.</td></tr>'
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Solicitudes · {html.escape(cfg.client.name)}</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1d232b;--muted:#5d6774;--line:#e2e6eb;--a:#0b7a4b;--b:#a46a00;--c:#6b7280}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12161b;--card:#1b2128;--ink:#e8ecf1;--muted:#9aa5b1;--line:#2b333d}}}}
body{{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}} h1{{font-size:22px;margin:0 0 4px}} p{{color:var(--muted);margin:0 0 16px}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;min-width:760px}} th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}} small{{color:var(--muted)}} .num{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.p{{display:inline-block;width:26px;height:26px;border-radius:50%;text-align:center;line-height:26px;font-weight:700;color:#fff}}
.pA{{background:var(--a)}} .pB{{background:var(--b)}} .pC{{background:var(--c)}}
</style></head><body><main>
<h1>Solicitudes de presupuesto · {html.escape(cfg.client.name)}</h1>
<p>Ordenadas por prioridad y valor estimado. Precios orientativos generados automáticamente: el presupuesto definitivo lo fija el equipo comercial.</p>
<div class="wrap"><table><thead><tr><th>Prio.</th><th>Cliente</th><th>Contacto</th><th>Estimación</th><th>Resumen</th><th>Estado</th><th>Recibida</th></tr></thead>
<tbody>{body}</tbody></table></div></main></body></html>"""
