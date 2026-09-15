# Ojalá — demo site

Prize-linked savings for Spain: you save, your money stays yours, and the interest
everyone's savings earn is pooled into a monthly draw. Same idea as UK Premium Bonds.

Two pages, one shared engine:

| File | What it is |
|---|---|
| `index.html` | Spanish page (`lang="es"`) |
| `en.html` | English page (`lang="en"`) |
| `assets/ecb-data.js` | **The rates. The only file you edit when the ECB moves.** |
| `assets/ojala.js` | Shared behaviour: the moving tape, the simulator, the countdown, the drum |
| `assets/ojala.css` | Shared styles |

No build step and no dependencies. Open `index.html` in a browser, or serve the
folder (`python3 -m http.server` from `ojala/`) and visit `/` or `/en.html`.

## The moving tape

The strip across the top scrolls the current ECB position and what it means for
the next draw. Every line is generated from `assets/ecb-data.js` — nothing in it
is typed by hand:

1. Deposit facility, with the size and direction of the last move (`▼ 25 bp`,
   `▲ 50 bp` or `unchanged`) and the date it took effect
2. Main refinancing and marginal lending rates
3. This month's pot, and how much the last move added to or took off it
4. What that pot buys: the Gordo, the syndicate prizes, and the pedrea
5. What 25 bp is worth — in euros of pot, and in pedrea prizes
6. What €100 of savings hands to the pot in a year
7. The next Governing Council date, days away, and the pot if the market is right
8. The next draw, days away
9. The point of the whole thing: rates move, your savings don't

It scrolls at a fixed ~55 px/s whatever the content length, pauses on the button
(it is the only moving thing on the page, so it needs one), and under
`prefers-reduced-motion` it stops moving and becomes a plain scrollable strip.
The day counts refresh every minute while the page is open.

## Updating after an ECB decision

Edit `assets/ecb-data.js` only:

1. Move `rates` into `previous`
2. Write the new levels into `rates`
3. Update `decided`, `effective` and `nextDecision`
4. Set `expectedNext` to what the market is pricing for that meeting, or `null`
   to drop the what-if line

Both languages follow. The tape rewrites itself — a cut reads "menos que" /
"less than", a hike "más que" / "more than", no change "sin cambios" /
"unchanged" — and so does the rest of the page.

## What else moves with the rate

Anything marked `data-ojala="…"` in the HTML is filled in by `ojala.js`, so a new
rate level flows through the whole page instead of leaving stale numbers behind:

`pot` · `prizes` · `pedrea` · `pedreaTotal` · `syndicateTotal` · `topPrize` ·
`rateDeposit` · `potRate` · `yield100` · `yield1000` · `split` · `per100Pot` ·
`per100Rest` · `per100Net` · `per100Giveup` · `stepBp` · `stepPot` ·
`stepPrizes` · `yearsAny` · `yearsGordo` · `poolM` · `entriesM` · `drawMonth`

The prize structure is deliberate: the €10,000 Gordo and the ten €500 syndicate
prizes are fixed, and the pedrea absorbs the rate. When the ECB cuts, fewer
people win €20 — the headline prize doesn't shrink and nobody's savings move.
The number in the HTML is a fallback for the no-JS case; JavaScript overwrites it.

The draw is the first Monday of the month at 09:00, and rolls to next month once
this month's has passed.

## Figures

Demo numbers throughout — the rates, the €20M pool, the winners' names and the
prize counts derived from them are illustrative, not an offer or a forecast.
Ojalá is not a credit institution and is not affiliated with Loterías y Apuestas
del Estado, ONCE or NS&I.
