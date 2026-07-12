# Options & Trading — A One-Hour Course

An elegant LaTeX **Beamer** slide deck (~20 slides, 16:9) for a one-hour
recorded lecture on trading, options, pricing, the Greeks, and risk
management. Mathematically precise but deliberately light — designed to be
narrated over video.

## Contents

`options-trading-course.tex` — the full deck. Structure:

| # | Slide | Part |
|---|-------|------|
| 1 | Title | — |
| 2 | Roadmap | — |
| 3 | What is trading? | I — Foundations |
| 4 | Stocks: a share of a company | I |
| 5 | The price as a stochastic process (GBM) | I |
| 6 | Risk, return, and volatility | I |
| 7 | What is an option? (calls & puts) | II — Options |
| 8 | Payoffs at expiry | II |
| 9 | What an option is worth (intrinsic + time value) | II |
| 10 | Black–Scholes in one slide | II |
| 11 | The Greeks: overview table | III — The Greeks |
| 12 | Delta: exposure to the underlying | III |
| 13 | Delta hedging / dynamic replication | III |
| 14 | Gamma, Theta, Vega | III |
| 15 | Implied volatility and the smile | III |
| 16 | Strategies I: protective put & covered call | IV — Strategies & Risk |
| 17 | Strategies II: vertical spreads | IV |
| 18 | Strategies III: straddles & strangles | IV |
| 19 | Managing risk with the Greeks | IV |
| 20 | Key takeaways | — |

## Build

Requires a standard TeX Live install (packages: `beamer`, `tikz`,
`pgfplots`, `mathtools`, `booktabs`, `xcolor` — all in
`texlive-latex-recommended` + `texlive-pictures` + `texlive-latex-extra`).
No external theme packages are needed; the theme is self-contained.

```sh
latexmk -pdf options-trading-course.tex     # recommended
# or, run 2–3 times so TikZ/pgfplots settle:
pdflatex options-trading-course.tex
```

Clean build artifacts with `latexmk -C`.

## Design notes

- The theme is a flat, "metropolis-inspired" look built only from stock
  Beamer, so it compiles anywhere. Palette and frame-title rule are defined
  at the top of the `.tex` file — tweak the `\definecolor` block to rebrand.
- All charts (price paths, return densities, payoff diagrams, delta curve,
  volatility smile) are drawn in TikZ/pgfplots — vector, editable, no image
  assets.
- Colour convention: **blue** = primary / the position you hold, **orange**
  = the other side of a trade, **green** = profit, **red** = loss.

## Speaking to time (~60 min)

Roughly 3 minutes per slide leaves room for the two math-heavy slides
(GBM, Black–Scholes) and the four strategy slides, which deserve more.
Suggested pacing: Part I ~12 min, Part II ~18 min, Part III ~16 min,
Part IV ~14 min.

> Educational material only — not investment advice.
