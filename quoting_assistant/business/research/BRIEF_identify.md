# Research brief: find new prospects (identification stage)

## Who we are and what we sell
Martí Fernández-Real and Álvaro, a small Barcelona team. We install an AI quoting assistant on an
industrial firm's website and WhatsApp. It answers customers' requests for quotes at any hour (CA/ES/EN/FR),
collects the drawing (DXF/STEP/PDF), material, thickness, quantity and deadline, gives a rough price
from the firm's own rates, and sends the request to the firm's sales team ranked by € value.
Offer: free trial of a few weeks, no commitment.

## Ideal prospect
- Metal subcontractor ("subcontractació metal·lúrgica / calderería / mecanizado a terceros") in Catalonia:
  laser cutting (sheet or tube), bending/folding, punching, waterjet, plasma/oxy-fuel, welding,
  boilermaking (calderería fina), CNC machining or turning for third parties, tube bending.
- Revenue roughly €1–20M, or 5–150 staff. Many small, varied requests for quotes (job shop).
- Weak online quoting: no drawing upload, no instant estimate, no WhatsApp, no response-time promise,
  old website. Note exactly what you see.

## Exclude
- Firms already contacted or reserved (and their group companies):
  R&G Metal Shaping, Metalgama, Inoxtop/Qualinox, Initube, Curvat, Laser Barberà/Ferros Barberà, Inoxlaser,
  Egarlaser, Laser 7, Mecanitzats Parés, CMQUEL, Ferros Planes, TMT Tubulares, Recam Làser (and its group),
  Proceinox 90, Mecanizados CMS, Laser Mimar, Deluq Numèrics, Mafesa/Mafesa Làser, Fab Laser,
  Talleres ECI, Laserpenta, Laser Goded, GTlaser, Grupo Semesa.
- Big groups (> ~€30M revenue or > ~150 staff), pure steel distributors with no processing, firms that
  only make their own products (no subcontracting), firms that are closed or in insolvency.
- Firms that already offer instant online quotes or an online configurator/portal (Nexafab, Xometry-style,
  own "pressupost online" with upload and price). Mention any you find in your summary as competitors/benchmarks, but don't list them as candidates.

## Data rules (legal, non-negotiable)
- Only contact details the company publishes itself (its own website), or that it published in an
  official or industry directory (ACCIÓ "Catalonia Industry Suppliers", Interempresas, Cambra de Comerç,
  Registro Mercantil / BORME for director names). Record the exact URL where you found each email.
- Never guess or construct an email address (no "info@domain" unless you saw it written). If no email is
  published, leave it empty and say so; a published phone alone is fine.
- No personal data from LinkedIn or other social networks, no data-broker lists.
- Do not contact anyone, submit forms or sign up for anything. Research only.

## How to work
- Use web search and fetch the company websites (home, services, contact page). Directory listings
  (ACCIÓ, Interempresas, Kompass, Páginas Amarillas, einforma/axesor public snippets for size) help find firms.
- Prefer quality over quantity: a firm that clearly fits with a verified email beats three vague ones.
- If a site fails to load, note it and move on.

## Output
Write a CSV (UTF-8, comma-separated, quoted where needed) at the path given in your task, with exactly
these columns:

company,town,comarca,website,email_published,email_source_url,phone_published,named_contact_published,named_contact_source,what_they_do,processes,quoting_gaps_seen,why_theyd_buy,size,size_source,language,fit,fit_reason,evidence_urls,notes

- processes: semicolon-separated from laser;tube_laser;bending;punching;waterjet;plasma;welding;boilermaking;machining;turning;tube_bending;finishing
- language: CA if the website is mainly in Catalan (or Catalan-first), ES otherwise.
- fit: High / Medium-high / Medium / Medium-low (High = job shop, many small RFQs, mid size, weak online quoting).
- Keep text fields short (one sentence each), in English.

End with a short summary: how many candidates, how many with a published email, the strongest 5, and any
competitors with online quoting you came across.
