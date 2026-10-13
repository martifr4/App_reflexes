# Token Spread: working notes

Estimates what a GPU-hour earns serving LLM tokens at market API prices vs what it costs
(electricity → full owner cost → rent → token revenue). Method and formulas: `README.md`.
Latest written findings: `report.md`. Website: `site/index.html` (GitHub Pages).

## Pipeline (run from `token_spread/`)

```bash
pip install -r requirements.txt
python fetch/run_all.py     # OpenRouter prices, InferenceX throughput, Silicon Data rent, EIA/Eurostat power
python compute.py           # outputs/*.csv + dated snapshot in snapshots/
python report.py            # report.md + charts/*.png
python build_site.py        # site/index.html + site/artifact.html from site/template.html
node tests/check_engine.js  # in-browser engine must match compute.py (exit 1 on mismatch)
node tests/render_site.js   # headless Chromium: no console errors, no horizontal overflow
```

## Where things live

- `assumptions.yaml`: every assumption (models, GPUs, speed floor, utilization, mix, power,
  rental-firm costs). Never hardcode one elsewhere.
- `data/*.csv`: raw inputs; every row has `source_url`, `retrieved_date`, `estimate`, `notes`.
  Manually researched figures go in a CSV with a link (e.g. `data/rental_firm_sources.csv`).
  Never invent a figure; leave it empty and list it as a gap.
- `compute.py`: all calculations. `report.py`: markdown report. `build_site.py`: embeds data
  JSON into `site/template.html` (edit the template, never `index.html`).
- `site/template.html`: one self-contained page (vanilla JS + SVG, no libraries). The block
  between `ENGINE START` and `ENGINE END` mirrors `compute.py`. **Any formula change must be
  made in both**, plus a `python_*` record in `build_site.py` so the page footer and
  `tests/check_engine.js` can verify it.
- `.github/workflows/token-spread-daily.yml` (repo root): daily 06:17 UTC fetch → compute →
  report (Mondays) → build site → commit → GitHub Pages deploy (`ENABLE_PAGES=true`).

## Conventions

- Website: theme tokens on `:root` with dark variants; charts read colors from CSS classes;
  works at 390px width; tooltips via `bindTip`; numbers formatted with `fmtUSD/fmtX/fmtPct`.
- Plain, direct copy. Findings text is generated from data, not hardcoded numbers.
- Before pushing, run all six pipeline commands above and both tests.
- Rebuild locally with `GITHUB_REF_NAME=<default branch> python build_site.py` so the page's
  GitHub links point at the default branch (`claude/reflex-app-bugs-fmldxl`).
- The daily bot commits generated files to the default branch. When merging it into a
  feature branch, resolve conflicts in generated files by re-running the pipeline.
