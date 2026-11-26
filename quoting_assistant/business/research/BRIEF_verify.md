# Research brief: verify candidates (verification stage)

Read `BRIEF_identify.md` in this folder first: same product, ideal prospect, exclusions and data rules.
Another agent found the candidates in your input file(s). Your job is to check each one independently,
as if you didn't trust the first agent. Do not contact anyone or submit any form.

## For every candidate, check
1. **Exists and trades**: the website loads (or another live source shows recent activity); no sign of
   closure, insolvency (concurso de acreedores) or a takeover that changes who decides.
2. **Right kind of firm**: does subcontract metal work for other companies (not only own products, not only
   distribution). Note the main processes.
3. **Size**: within ~€1–30M revenue or ~5–150 staff. Give the source.
4. **Online quoting gap**: does the site already have instant online quotes, a configurator, a portal with
   drawing upload and price, or a strong WhatsApp + response-time promise? If instant quoting exists, reject.
   Otherwise describe the gap precisely (it will be quoted in a personalised email, so it must be true).
5. **Contact details**: open the page given in `email_source_url` and confirm the email is written there.
   If it is not, look for a published email on the company's own contact page or legal notice (avís legal).
   Never construct one. Confirm the phone the same way. A named contact counts only if the company or an
   official register publishes it.
6. **Not already ours**: not on the exclusion list, not a duplicate of another candidate (same domain or
   same group), not a subsidiary of an excluded firm.
7. **Language**: CA or ES, by the language the website is written in first.

## Output
Write a CSV at the path given in your task with the original columns plus:

verified,verify_notes,verified_email,verified_email_source,verified_fit

- verified: VERIFIED or REJECTED.
- verify_notes: one sentence: what you checked and any correction (or the reason for rejection).
- verified_email: the email you confirmed yourself (empty if none published).
- verified_fit: High / Medium-high / Medium / Medium-low after your checks.

Fix any wrong fields in place (town, size, gaps, language). End with a short summary: how many verified,
how many rejected and why, and how many verified firms have a confirmed published email.
