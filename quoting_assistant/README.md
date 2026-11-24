# Quoting assistant for industrial SMEs

An AI chat that metal subcontractors put on their website (and later on WhatsApp). It answers
customers at any hour in Catalan, Spanish, English or French, reads the DXF drawing, gives an
**indicative price from the firm's own rates** and passes the request to sales, ranked by value.

Project context and rules: `CLAUDE.md`. Business documents: `business/`.

## Run it on your laptop

Needs Python 3.11 or newer.

```bash
cd quoting_assistant
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/demo.

- **Offline mode** (no `ANTHROPIC_API_KEY` in `.env`): the conversation is rule-based with fixed
  wording. No internet needed, which is the safest choice for a demo at a prospect's office.
- **Claude mode** (key set): `claude-haiku-5-5` reads each message into fields and
  `claude-sonnet-5-5` writes the replies. Prices still come only from the pricing engine. If Claude
  writes any euro amount, the reply is thrown away and the fixed wording is used instead. Token
  costs are logged per client in the `llm_usage` table.

## The 3-minute demo

Before the meeting: run the server, open http://127.0.0.1:8000/demo, and keep
http://127.0.0.1:8000/demo/sales open in a second tab. Download `escaire_plegat.dxf` from the
yellow bar. If you rehearsed in the same browser, clear the site data first (or switch the
chat's language selector, which starts a new conversation).

1. **(0:00) The problem.** "A request comes in at 21:00. Today it waits until tomorrow. Your
   competitors (Laserpenta, for example) already quote online."
2. **(0:30) The customer's side.** Click "Demanin pressupost". Point out that the assistant says
   it is an AI. Type:
   > Bon dia, necessitem 50 escaires d'acer de 2 mm, tallats i plegats

   It asks only for what's missing: the drawing.
3. **(1:00) The drawing.** Attach `escaire_plegat.dxf`. It reads the size, cut length, holes
   and bend line, and shows an **indicative range marked "pending review"**, calculated with
   *their* rates (these are sample rates for now).
4. **(1:45) Urgency.** Type `En 3 dies, sense acabat`. The price updates with the rush
   surcharge. Then `Joan Puig, Metalls Puig SL` and `joan@exemple.cat`.
5. **(2:15) The sales side.** Switch to the second tab and refresh: the request is ranked
   (A/B/C) with value, contact, file and a one-line summary. "Your team calls the best ones
   first. The final quote is always yours."
6. **(2:40) The offer.** One week of setup with their rates, 3–4 weeks live, free, no
   commitment.

To demo in Spanish, switch the chat's language selector to ES and type
`Buenos días, necesitamos 50 escuadras de acero de 2 mm, cortadas y plegadas`.

## Add the widget to a website

One line before `</body>`:

```html
<script src="https://YOUR-HOST/widget.js" data-client="demo_shop" data-lang="ca"
        data-color="#0b5cad" data-privacy-url="https://client.example/privacitat" async></script>
```

A button on the site can open the chat with `window.QuoteAssistant.open()`.

## How it is built

| Part | File | Notes |
|---|---|---|
| Client rates | `clients/<id>/config.yaml` | Materials (€/kg, density, scrap), cutting €/m and pierce € by thickness, bending, welding, finishes, margin, minimum order, quantity discounts, rush |
| Pricing engine | `app/pricing/engine.py` | Deterministic. Returns low/high, confidence, notes, breakdown. Won't price without material, thickness, quantity and geometry |
| DXF reader | `app/pricing/dxf.py` | ezdxf: cut length, pierces, bounding box, net area, bend lines (layer BEND/PLEG/DOBL), units, blocks, gaps |
| Conversation | `app/chat/dialog.py` | Asks only what's missing, at most two things per turn; same code for web and (later) WhatsApp |
| Wording | `app/chat/texts.py`, `prompts/` | CA/ES always in the formal plural |
| Lead ranking | `app/scoring.py` | First version (A/B/C); Milestone 3 refines it |
| Storage | `app/db.py` | SQLite, `client_id` on every row, uploads in `data/uploads/<client>/<conversation>/` |
| Widget | `app/static/widget.js` | Vanilla JS in a shadow DOM, so the client's CSS can't break it |

**Data retention:** `python -c "from app import db; print(db.purge_older_than(12))"` deletes
conversations untouched for 12 months, including their files. Schedule it daily in production.

**Sales view access:** `/demo/sales` opens only from localhost unless `DASHBOARD_KEY` is set in
`.env` (then use `/demo/sales?key=...`). The real client dashboard, with login, is Milestone 4.

## Not done yet (by milestone)

- M2: onboarding questionnaire (CA/ES) that produces `config.yaml`; trial checklist.
- M3: WhatsApp (Meta Cloud API adapter), email to sales, better lead scoring.
- M4: client dashboard with statuses and trial metrics; end-of-trial report.
- Before the first live client: EU hosting, HTTPS, rate limiting on the chat API, privacy
  notice template, and a data processing agreement (DPA) with the client.
