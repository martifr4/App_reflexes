# Quoting assistant: working notes

AI quoting assistant and lead generation for industrial SMEs around Barcelona.
This folder is self-contained inside the `App_reflexes` repo (siblings: the Expo reflex app at the
repo root and `token_spread/`; don't touch them). Run every command from `quoting_assistant/`.

## How to run (kept current)

```bash
pip install -r requirements.txt
cp .env.example .env              # add ANTHROPIC_API_KEY to use Claude; leave empty for offline mode
python -m pytest -q               # all tests
python samples/make_samples.py    # regenerate the 3 sample DXF parts
uvicorn app.main:app --reload     # demo at http://127.0.0.1:8000/demo
```

## Where things live

- `app/pricing/`: deterministic pricing engine (`engine.py`) and DXF geometry (`dxf.py`). Never
  let the language model produce a price.
- `app/chat/`: intake state, offline rule-based extractor, Claude adapter. `app/main.py`: FastAPI.
- `app/static/widget.js`: the embeddable one-`<script>` chat widget. `app/static/demo.html`: a
  fake client website used for demos.
- `clients/<client_id>/config.yaml`: per-client pricing rules and bot settings.
- `prompts/`: all language-model prompts. `samples/`: sample DXF parts and their generator.
- `business/`: prospects, pricing/P&L, legal notes, client-facing templates (CA + ES).

---

## 1. The business in one paragraph

Industrial SMEs around Barcelona, starting with metal subcontractors, lose orders because they take hours or days to answer requests for quotes. We install an **AI assistant on their website and WhatsApp** that:
- answers each customer immediately, at any hour, in Catalan, Spanish, English or French;
- collects the drawing (DXF/STEP/PDF), material, thickness, quantity and deadline;
- gives a **rough price** using the firm's own pricing rules;
- sends the request to the firm's sales team, **ranked by € value**, so they call the best ones first.

The firm always sets the final quote. An optional add-on is **lead generation**: we run Meta/Google ads on the client's own ad account. We charge a setup fee plus a monthly fee, possibly with a bonus per qualified lead. The client pays the ad spend directly, so we carry no cash risk.

The offer to prospects is a **free trial for a few weeks**: about 1 week of setup, then 3–4 weeks live. After that they decide whether to pay.

## 2. Who we are and how we talk to clients

- Martí Fernández-Real, +34 650 288 339, martifrg@gmail.com. Based in Barcelona, with a friend as co-founder. We are a young local team, eager to help, and we offer in-person visits.
- Client communication is in Catalan or Spanish, always in the formal plural ("vostès" / "ustedes"), never "tu", "usted" or "vostè".
- In Catalan, don't write "com treballen avui" when you mean how they work; write "com treballen". The same goes for Spanish ("cómo trabajan", not "cómo trabajan hoy").
- Martí is fluent in both languages. Write client-facing text carefully and check the spelling.

## 3. Status as of 24 Nov 2026

- On 23 Nov 2026 we emailed 20 metal subcontractors around Barcelona (list in section 7). The emails were tailored to each firm, offered the free trial, and asked whether they're interested, with more information by email, phone or in person.
- The prospect tracker, with columns for phone, quoting gaps, fit and status, is at https://claude.ai/artifact/4EHf7bVJvkSKFgK3EJGyb1 (a Claude Sheet). Mirror it in `business/prospects.csv` and keep the statuses updated when Martí reports replies.
- Next sectors to prospect: **packaging and printing**, then **freight and logistics**.
- Benchmark for the pitch: **Laserpenta** (La Llagosta) already offers online quotes through Nexafab and a 24-hour express service. So the pitch can truthfully say "your competitors already quote online".

## 4. Legal and platform rules (hard constraints)

Not legal advice. Flag anything doubtful rather than guessing.
- **Cold email (LSSI art. 21):** commercial email needs prior consent, even business-to-business. From now on: phone first, get a yes, then email. Every email includes an opt-out line, and we honour opt-outs immediately.
- **Cold calls (Ley 11/2022, art. 66.1.b):** calling individuals for sales requires their prior consent. Calling a company's published switchboard to speak to the business is the normal B2B route, but keep a log.
- **GDPR:** use only contact details that companies publish themselves. No scraping of social networks, no data-broker lists, no guessed email addresses. (The French regulator fined KASPR €240k in 2024 for scraping contacts, and Meta sues scrapers.)
- **EU AI Act art. 50 (applies from 2 Aug 2026):** the assistant must tell users clearly that they're talking to an AI.
- **WhatsApp Business API:** since 15 Jan 2026 Meta bans general-purpose AI chatbots, but bots that do a specific business task are allowed. Keep the assistant strictly to quoting, order intake and customer service for the client's business. Use the official Cloud API through a business solution provider, and approved message templates for anything we send first.
- **Lead generation:** each lead form must name the specific client the person is contacting, and the person must submit it themselves. Never resell leads to several buyers. **Avoid household energy switching** entirely: Spain's Real Decreto 88/2026 bans unsolicited sales calls, and the CNMC says generic consent clauses on third-party websites aren't valid.
- **Prices:** the bot's estimate is always labelled "orientative / pending review". The binding quote comes from a human at the firm.

## 5. Product requirements (MVP)

**Channels**
- An embeddable web chat widget: one `<script>` tag the client pastes into their site.
- WhatsApp through the Meta Cloud API. Build an adapter interface, so a Twilio adapter can be swapped in later.
- An email notification to the sales team, with an optional WhatsApp ping to the sales manager.

**Intake flow** (multilingual, configurable per client)
- Collect: name, company, email or phone, files (DXF, DWG, STEP, PDF, images), material and grade, thickness, quantity, process (laser, bending, welding, machining…), finish, deadline and delivery location.
- Ask only for what's missing, in plain language.
- Never invent a price when there's too little information. Say a technician will review it.

**Pricing engine** (deterministic code, never the language model)
- Read a per-client YAML config with:
  - material €/kg or €/m², density and scrap factor;
  - cutting €/m by material and thickness, plus a cost per pierce;
  - bending € per bend and setup;
  - welding €/hour;
  - minimum order, quantity discounts, margin and rush surcharge.
- Parse DXF files (with `ezdxf`) for cut length, number of pierces, bounding box and area.
- Return a price range (low/high), a confidence level and the assumptions used.
- For STEP/PDF/images in the MVP, extract what's possible, mark the quote "needs review" and still capture the lead.

**Lead scoring**
- Score on estimated € value, quantity, repeat potential, how complete the information is and how urgent it is.
- Output a priority label (A/B/C) and a one-line summary for the sales team.

**Dashboard** (simple, for the client)
- Show the lead list sorted by priority, with conversation, files, estimate and status (new / contacted / quoted / won / lost).
- Show trial metrics: leads captured, share received outside office hours, median response time, estimated value of the pipeline, and quotes won.

**Language model use**
- Use the Claude API for conversation and for extracting fields from free text and PDFs: `claude-sonnet-5-5` by default, `claude-haiku-5-5` for cheap steps.
- Keep prompts in `/prompts`. Log token costs per client.

**Hosting and data**
- Host in an EU region, with data separated per client and a retention policy (for example, delete chats after 12 months unless the client asks otherwise).
- Provide a privacy notice template the client can link to.

## 6. Milestones

1. **Demo (first)**
   - Repo skeleton (Python + FastAPI + SQLite to start).
   - The pricing engine with a sample config for a generic laser and bending shop, plus tests.
   - DXF parsing tested on 3 generated sample parts.
   - The web chat widget running locally against the engine.
   - Goal: a 3-minute demo Martí can show a prospect on his laptop.
2. **Onboarding kit:** a questionnaire (in Catalan and Spanish) that turns a client's rates into the YAML config within 1 week, and a checklist for the trial setup.
3. **WhatsApp channel**, the email notification to sales, and lead scoring.
4. **Client dashboard and trial metrics**, plus a one-page end-of-trial report generated automatically.
5. **Ads add-on:**
   - a landing page template per client;
   - Meta lead-form settings with consent naming that client;
   - tracking of cost per lead and cost per qualified lead;
   - a simple calculator for cost per lead, pricing and margin.
6. **Sales operations:**
   - a prospect tracker;
   - reply templates in Catalan and Spanish (formal plural);
   - phone call scripts for the consent-first approach;
   - prospect lists for packaging/printing and freight/logistics, built from company-published contacts only.

## 7. Prospects already emailed (23 Nov 2026)

| # | Company | Town | Email | Language | Fit |
|---|---|---|---|---|---|
| 1 | R&G Metal Shaping | Vic | info@rgmetalshaping.com | ES | High |
| 2 | Metalgama | Sant Feliu de Llobregat | comercial@metalgama.com | ES | High |
| 3 | Inoxtop (Qualinox) | Manresa | inoxtop@inoxtop.com | ES | High |
| 4 | Initube | Lliçà de Vall | info@initube.es | ES | High |
| 5 | Curvat | Martorelles | curvat@curvat.es | CA | High |
| 6 | Laser Barberà | Barberà del Vallès | fb@laserbarbera.com | CA | High |
| 7 | Inoxlaser | Centelles | inoxlaser@inoxlaser.com | CA | High |
| 8 | Egarlaser | Terrassa | egarlaser@egarlaser.com | ES | Medium-high |
| 9 | Laser 7 | Santpedor | admin@laser-7.com | CA | Medium-high |
| 10 | Mecanitzats Parés | Sant Esteve Sesrovires | comercial@mecanitzatspares.com | CA | Medium-high |
| 11 | CMQUEL | Canovelles | info@cmquel.com | ES | Medium |
| 12 | Ferros Planes | Martorelles | comercial@ferrosplanes.com | CA | Medium |
| 13 | TMT Tubulares | Granollers | tmt@tmtubulares.com | ES | Medium |
| 14 | Recam Làser | Caldes de Montbui | recamlaser@recamlaser.com | CA | Medium |
| 15 | Proceinox90 | Ripollet | administracion@proceinox90.com | ES | Medium |
| 16 | Mecanizados CMS | Castellar del Vallès | mecanizadoscms@gmail.com | ES | Medium |
| 17 | Laser Mimar | Parets del Vallès | comercial@lasermimar.com | ES | Medium |
| 18 | Deluq Numèrics | Torrelles de Llobregat | dn@deluq-numerics.cat | CA | Medium-low |
| 19 | Mafesa (Mafesa Làser) | Vic | mafesa@mafesa.com | CA | Medium-low |
| 20 | Fab Laser | Badalona | fablaser@fablaser.es | ES | Medium-low |

Reserves, not contacted: Talleres ECI (already has file upload, WhatsApp and a 24-hour reply promise), Laserpenta (benchmark), Laser Goded (too big), GTlaser (Rubí), Grupo Semesa.

## 8. Commercial model (first draft, to refine with Martí)

- **Trial:** free for a few weeks with no commitment. We remove everything if they don't continue.
- **Assistant:**
  - one-off setup fee;
  - monthly fee per client;
  - a higher tier for multiple languages, extra processes or ERP/CRM integration.
- **Ads add-on:**
  - setup fee plus a monthly management fee;
  - an optional bonus per qualified lead;
  - the ad spend goes on the client's card.
- Pricing options and a simple P&L live in `business/pricing.md`. Prices must be easy to change, and it shows the break-even point (clients needed to cover API, hosting and WhatsApp costs plus our time).
- Target: industrial SMEs with €1–20M revenue and many small, varied requests for quotes. Avoid household consumer niches.

## Working rules

- Explain choices briefly, then build. Prefer simple, boring technology Martí can maintain.
- Work in small steps; run the code after each one and show it works; commit each step with a clear message.
- Keep the business documents (sections 7–8) as up-to-date Markdown/CSV in `business/`.
- Never put secrets in the repo: use `.env` and `.env.example`.
- Never send emails, WhatsApp messages or anything public without Martí's explicit OK in the chat.
- Client-facing text: always give both the Catalan and Spanish versions, in the formal plural.
- Decisions taken (24 Nov 2026): project lives in this subfolder; the chat uses Claude when
  `ANTHROPIC_API_KEY` is set and falls back to an offline rule-based intake otherwise; the sample
  shop ("Taller Demo SL") uses plausible made-up rates, labelled as sample values.
