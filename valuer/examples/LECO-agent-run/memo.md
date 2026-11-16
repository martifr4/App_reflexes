# LINCOLN ELECTRIC HOLDINGS INC (LECO): asset-based valuation

Run `LECO-2026-11-16-20261116T114926Z` | as of 2026-11-16 | balance sheet 2026-09-30 | last fiscal year end 2025-12-31  
Parameters `v001` hash `cb335f3241ce05c0` | engine `0.1.0` | model `claude-opus-5-5`

## Decision

**System verdict: PASS**

- Market cap is above the buy threshold (base reproduction value less the margin of safety).
- Market cap is above the low liquidation value, so the liquidation floor does not protect the price.
- Market cap is above base reproduction value.

| Measure | Value |
|---|---:|
| Market cap | $15,469.4m |
| Buy at or below (base reproduction value less 33.0% margin of safety) | $656.6m |
| Watch at or below (base reproduction value) | $980.1m |
| Low liquidation value (required for a buy) | -$1,113.9m |
| Margin of safety at the current price | -1,478.4% |

## Equity value

| | Low | Base | High |
|---|---:|---:|---:|
| Liquidation value | -$1,113.9m | -$699.9m | -$273.0m |
| Reproduction value | $157.6m | $980.1m | $1,818.6m |
| Liquidation value per share | -$20.37 | -$12.80 | -$4.99 |
| Reproduction value per share | $2.88 | $17.92 | $33.25 |

Liquidation value = tangible assets at sale haircuts minus all liabilities. Reproduction value = tangible assets at rebuild cost plus the selected intangible estimate minus all liabilities.

## Bear case

Written by an independent agent (`claude-opus-5-5`) that saw the valuation and the filings but not the analysts' work. The claims are the agent's opinion. Every quote and fact below was checked by code, and the scenario figures were computed by the engine.

The valuation already says PASS: the market price is far above both the liquidation and the reproduction value. The bear case is that even the base reproduction figure is too generous. Equipment is held near book while the company keeps consolidating plants and booking impairments, especially in International Welding. The intangible estimate gives credit for brand spending at a time when gross margin is shrinking because the company cannot fully pass on input costs. The deferred tax asset depends on a large valuation-allowance release that management says could reverse, and the bad-debt allowance was cut while receivables grew. The pension discount-rate risk and the asbestos docket, plus untaxed credit for the LIFO reserve, push the floor lower still, so the gap between price and assets is even wider than the base case shows.

| | Low | Base | High |
|---|---:|---:|---:|
| Reproduction value, as valued | $157.6m | $980.1m | $1,818.6m |
| Reproduction value, bear scenario | $157.6m | $836.2m | $1,818.6m |
| Liquidation value, as valued | -$1,113.9m | -$699.9m | -$273.0m |
| Liquidation value, bear scenario | -$1,113.9m | -$705.5m | -$273.0m |

Verdict in the bear scenario: **PASS**

| Parameter changed (base value) | As valued | Bear |
|---|---:|---:|
| `haircut.going_concern.equipment` | 0.9 | 0.8 |
| `intangible.brand_sga_share` | 0.2 | 0.15 |
| `haircut.going_concern.dta` | 0.8 | 0.6 |
| `haircut.going_concern.receivables` | 1 | 0.98 |
| `liability.pension_rate_shift` | 0 | 0.005 |

- **[medium] `haircut.going_concern.equipment`** Lincoln has rationalization plans in all three segments that consolidate manufacturing facilities, and impairment charges are rising in International Welding. Management also warns that more actions may follow. Machinery in plants that are being closed or merged is not worth close to its depreciated book value to a buyer rebuilding the business. Changes `haircut.going_concern.equipment`.
  > "The plans impacted headcount and included the consolidation of manufacturing facilities to better align with the cost structure, economic conditions and operating needs of the business." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:444`
- **[medium] `intangible.brand_sga_share`** The base case counts a fifth of SG&A as investment in brand and customer relationships. But gross margin fell in both the quarter and the year to date because input costs rose faster than prices, which points to limited pricing power. Brand capital that cannot protect margins should get a smaller share of overhead. Changes `intangible.brand_sga_share`.
  > "Gross profit as a percentage of sales decreased 1.9% and 1.1% for the three and nine months ended September 30, 2026, respectively, as compared to the same 2025 periods, driven by higher input costs." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:766`
- **[medium] `haircut.going_concern.dta`** The deferred tax asset is held at most of its book value, but that book value was lifted by a large valuation-allowance release in the latest fiscal year. Management says the amount it treats as realizable could be cut if its view of future taxable income changes. Reliance on a recent release argues for a deeper haircut. Changes `haircut.going_concern.dta`.
  > "The amount of net deferred tax assets considered realizable could be increased or reduced in the future if the Company’s assessment of future taxable income or tax planning strategies changes." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:567`
- **[low] `haircut.going_concern.receivables`** Gross receivables grew during the year while the allowance for doubtful accounts was cut sharply, so reserve coverage is thinner than at year end. Taking net receivables at full value assumes this lower reserve is enough. Changes `haircut.going_concern.receivables`.
  > "Accounts receivable (less allowance for doubtful accounts of $7,406 in 2026; $11,326 in 2025) 603,307 538,791" — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:112`
- **[low] `liability.pension_rate_shift`** The base case assumes no discount-rate risk on the pension and supplemental retirement obligations, even though the low case already prices a rate cut. A modest cut in the base is more prudent for unfunded and international plans. Changes `liability.pension_rate_shift`.
  Fact: `T2/CIK59527/pension_benefit_obligation/2025-12-31/0000059527-26-000006/8b72a0f2`
- **[low] `lifo_reserve`** In the reproduction lens the off-balance-sheet LIFO reserve is added at full value with no deferred tax, even though restating inventory to current cost would create taxable gains. Since the reserve keeps growing as input costs rise, this untaxed add-back inflates the base reproduction value.
  > "The excess of current cost over LIFO cost was $145,501 and $138,589 at September 30, 2026 and December 31, 2025, respectively." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:524`
- **[low] `other_liabilities`** The company remains a co-defendant in asbestos cases and faces product liability and health-and-safety claims, and no accrual or range of possible loss is disclosed. The valuation lists this as a gap, so any defence or settlement cost is a liability the model does not include.
  > "The Company is subject, from time to time, to a variety of civil and administrative proceedings arising out of its normal operations, including, without limitation, product liability claims, regulatory claims and health, safety and environmental claims." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:1010`

## Market value

| | |
|---|---:|
| Close on 2026-11-13 (yahoo) | $282.86 |
| Shares outstanding at 2026-09-30 | 54.16m |
| Dilution: treasury-stock method at the current price plus unvested awards (from footnotes) | 0.53m |
| Diluted shares | 54.69m |
| Market cap | $15,469.4m |

## Tangible assets

| Line | Book | Liq. low | Liq. base | Liq. high | Repro. low | Repro. base | Repro. high |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cash and equivalents | $283.2m | $283.2m | $283.2m | $283.2m | $283.2m | $283.2m | $283.2m |
| Receivables (net of allowance) | $603.3m | $452.5m | $512.8m | $573.1m | $573.1m | $603.3m | $603.3m |
| Inventory: finished goods | $369.6m | $184.8m | $240.2m | $295.7m | $332.6m | $369.6m | $369.6m |
| Inventory: work in process | $172.0m | $17.2m | $43.0m | $68.8m | $137.6m | $172.0m | $172.0m |
| Inventory: raw materials | $157.8m | $63.1m | $94.7m | $126.3m | $142.1m | $157.8m | $157.8m |
| LIFO reserve (off balance sheet) | $0.0m | $55.2m | $78.6m | $102.1m | $127.4m | $145.5m | $145.5m |
| Other current assets | $240.3m | $0.0m | $60.1m | $120.1m | $120.1m | $216.2m | $240.3m |
| PP&E: Land | $70.3m | $70.3m | $70.3m | $87.8m | $70.3m | $70.3m | $105.4m |
| PP&E: Buildings and improvements | $214.2m | $85.7m | $128.5m | $171.4m | $171.4m | $214.2m | $257.1m |
| PP&E: Machinery, equipment and other | $463.2m | $46.3m | $115.8m | $185.3m | $324.2m | $416.8m | $463.2m |
| Operating lease right-of-use assets | $57.7m | $0.0m | $0.0m | $14.4m | $57.7m | $57.7m | $57.7m |
| Goodwill | $886.0m | $0.0m | $0.0m | $0.0m | $0.0m | $0.0m | $0.0m |
| Book intangibles (excl. goodwill) | $250.4m | $0.0m | $0.0m | $0.0m | $0.0m | $0.0m | $0.0m |
| Deferred tax assets | $47.1m | $0.0m | $11.8m | $23.5m | $23.5m | $37.7m | $47.1m |
| Other non-current assets | $78.7m | $0.0m | $19.7m | $39.3m | $39.3m | $63.0m | $78.7m |
| **Total** | $3,893.6m | $1,258.2m | $1,658.7m | $2,091.1m | $2,402.5m | $2,807.2m | $2,980.7m |

## Intangible assets (reproduction lens only)

| Method | Low | Base | High |
|---|---:|---:|---:|
| **A. Capitalised investment** | $270.0m | $511.7m | $927.2m |
| - Technology (capitalised R&D) | $163.8m | $230.2m | $318.3m |
| - Brand and customers (capitalised share of SG&A) | $106.2m | $281.5m | $608.9m |
| **B. Replacement cost** | $334.0m | $668.0m | $1,176.8m |
| - Technology (years of R&D) | $159.1m | $318.1m | $477.2m |
| - Brand and customers (years of SG&A) | $174.9m | $349.8m | $699.6m |
| **C. Relief from royalty** | $112.9m | $390.1m | $1,144.9m |
| **Used in the valuation** | $112.9m | $511.7m | $1,176.8m |

The three methods are not averaged. Rule per scenario: low uses `min` (here `relief_from_royalty`); base uses `lower_median` (here `capitalised_investment`); high uses `max` (here `replacement_cost`).

- A. Capitalised investment: SG&A is taken net of R&D, which this company reports inside SG&A.
- B. Replacement cost: SG&A is taken net of R&D, which this company reports inside SG&A.
- C. Relief from royalty: Revenue is held flat at the last fiscal year; no growth is assumed.

## Liabilities and prior claims

| Line | Book | Liq. low | Liq. base | Liq. high | Repro. low | Repro. base | Repro. high |
|---|---:|---:|---:|---:|---:|---:|---:|
| Debt | $1,150.0m | $1,150.0m | $1,150.0m | $1,150.0m | $1,150.0m | $1,150.0m | $1,150.0m |
| Operating lease liabilities | $58.0m | $58.0m | $58.0m | $58.0m | $58.0m | $58.0m | $58.0m |
| All other liabilities | $1,131.0m | $1,131.0m | $1,131.0m | $1,131.0m | $1,131.0m | $1,131.0m | $1,131.0m |
| Pension re-pricing at a lower discount rate | $0.0m | $11.3m | $0.0m | $0.0m | $11.3m | $0.0m | $0.0m |
| Unconditional purchase obligations | $0.0m | $7.7m | $0.0m | $0.0m | $7.7m | $0.0m | $0.0m |
| Tax on liquidation gains | $0.0m | $14.3m | $19.7m | $25.1m | $0.0m | $0.0m | $0.0m |
| **Total** | $2,338.9m | $2,372.2m | $2,358.6m | $2,364.0m | $2,357.8m | $2,338.9m | $2,338.9m |

## Line notes

- LIFO reserve (off balance sheet): Not carried on the balance sheet. Any liquidation gain is taxed in the liabilities section.
- Other current assets: Residual: everything not mapped to a line above.
- PP&E: Land: Split uses component detail at 2025-12-31. Land and construction in progress are not depreciated; accumulated depreciation is spread over buildings and equipment in proportion to gross cost.
- PP&E: Buildings and improvements: Split uses component detail at 2025-12-31. Land and construction in progress are not depreciated; accumulated depreciation is spread over buildings and equipment in proportion to gross cost.
- PP&E: Machinery, equipment and other: Split uses component detail at 2025-12-31. Land and construction in progress are not depreciated; accumulated depreciation is spread over buildings and equipment in proportion to gross cost.
- Book intangibles (excl. goodwill): Not in the latest balance sheet; uses the value at 2025-12-31.
- Deferred tax assets: Not in the latest balance sheet; uses the value at 2025-12-31.
- Other non-current assets: Residual: everything not mapped to a line above.
- Debt: Carrying amount, which is face value less small issue costs.
- All other liabilities: Residual: payables, accruals, pensions, deferred taxes and everything else, at the reported amount.
- Pension re-pricing at a lower discount rate: Read from the filing text by an agent and checked against that text by code.
- Unconditional purchase obligations: Read from the filing text by an agent and checked against that text by code.
- Tax on liquidation gains: Liquidation lens only.

## Analyst findings

Observations from agents that read the filings. The statements are the agents' reading; each quote was checked by code against the filing text.

### Asset analyst (`claude-opus-5-5`)

- **[lowers value] Cash and equivalents:** Most of the reported cash at the quarter end is held by international subsidiaries. During the quarter the company booked a tax charge on foreign earnings it may bring home, so not all of this cash would reach shareholders at face value.
  > "As of September 30, 2026, the Company had cash of $283,237, of which $179,018 was held by international subsidiaries." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:946`
- **[raises value] LIFO reserve (off balance sheet):** Only part of inventory, mostly in the U.S., is on LIFO. The LIFO reserve grew over the year after a LIFO charge caused by rising input costs, so the book value of that inventory is below what it would cost to replace today. This supports the engine adding the reserve back.
  > "At December 31, 2025 and 2024, approximately 38% and 35% of total inventories, respectively, were valued using the LIFO method." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:991`
- **[neutral] Goodwill:** Goodwill comes from a series of recent bolt-on acquisitions in automation and mining services (Alloy Steel, Vanair, Inrotech, RedViking). It is purchase premium, not something that could be sold, so zero value in both lenses is right. It also shows the reproduction intangibles include bought capabilities, not only ones built internally.
  > "(2) Decreases to Americas Welding reflects Vanair and RedViking purchase accounting adjustments. Additions to International Welding reflect goodwill recognized in the acquisition of Alloy Steel." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1134`
- **[lowers value] PP&E: Machinery, equipment and other:** Rationalization plans in all three segments include consolidating manufacturing facilities, and impairment charges continue into the current year, mostly in International Welding. Some equipment and buildings may be worth less than book, which supports the liquidation haircuts.
  > "The plans impacted headcount and included the consolidation of manufacturing facilities to better align with the cost structure, economic conditions and operating needs of the business." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:444`
- **[neutral] General:** The company is a long-standing co-defendant in asbestos cases over welding consumables, and the claimants mostly seek unspecified sums. The filing gives no estimate of reasonably possible loss, so this gap cannot be filled, although past outcomes have been mostly dismissals or defence wins.
  > "The asbestos claimants seek compensatory and punitive damages, in most cases for unspecified sums." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:263`

### Liabilities analyst (`claude-opus-5-5`)

- **[lowers value] General:** Reserves cover only identified or asserted claims and no range of possible loss is given, so litigation exposure beyond the accruals inside other liabilities can't be measured.
  > "Moreover, reserves only cover identified and/or asserted claims." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1817`
- **[neutral] General:** Asbestos claims are still open but have been shrinking, and the company's long record of dismissals and defense verdicts suggests a small exposure. Damages sought are unspecified, though.
  > "As of September 30, 2026, the Company was a co-defendant in cases alleging asbestos induced illness involving claims by approximately 367 plaintiffs, which is a net decrease of 334 claims from those previously reported." — `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt:1011`
- **[neutral] Pension re-pricing at a lower discount rate:** Both plan groups are underfunded, and the U.S. plans have no assets at all. The net deficit is already in the balance sheet's other liabilities, so only a change in assumptions would add to the liability, and the plans are small next to the company's size.
  > "Funded status at end of year (7,300) (31,438) (7,862) (30,830)" — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1456`
- **[neutral] All other liabilities:** Trade payables include amounts owed to a bank under a supplier financing programme with long invoice terms. The amount is already on the balance sheet, but it is closer to debt than an ordinary payable.
  > "At December 31, 2025 and 2024, Trade accounts payable included $25,709 and $29,164, respectively, payable to suppliers that have elected to participate in the supplier financing program." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1820`
- **[neutral] Debt:** The revolving credit facility has a maximum net leverage covenant and a minimum interest coverage covenant. The company was in compliance, and the reported debt is well inside these limits, so a covenant-driven acceleration seems unlikely.
  > "The financial covenants consist of a maximum net leverage ratio of 3.5x EBITDA and a minimum interest coverage ratio of 2.5x EBITDA." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1352`
- **[lowers value] General:** The company warns that indemnities it gives when selling businesses may be hard to quantify and could be material. No amount is disclosed, so this is an unmeasured exposure.
  > "Sellers typically retain certain liabilities or indemnify buyers for certain matters." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:154`
- Searched for `contingent_possible_loss` and found none disclosed. Searched the contingencies note of the annual report and the legal proceedings section of the latest quarterly report. The company says a range of possible losses often cannot be made and gives no estimate of reasonably possible losses above amounts accrued.
- Searched for `guarantee_max_exposure` and found none disclosed. Searched for guarantees, indemnities and off-balance-sheet arrangements. The filing mentions only letters of credit backing the company's own obligations and possible divestiture indemnities, with no maximum exposure stated.

## Figures read from filing text

These figures are not in the structured data. An agent located them; code parsed the figure from the quote, applied the stated scale and confirmed the quote against the filing. Open the cited file at the cited line to check.

- **`options_outstanding`** = 0.62m at 2025-12-31 (`T2/CIK59527/options_outstanding/2025-12-31/0000059527-26-000006/3d33d656`)
  > "Balance at end of year 621,683 150.63" — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1371`
  Agent's caveat: Taken from the stock option activity table in the annual report's stock plans note, as of the fiscal year end. The September quarterly report does not restate the option table, so options exercised during the year are not reflected. Share counts in this table are in ones.
- **`options_wavg_exercise_price`** = $150.63 at 2025-12-31 (`T2/CIK59527/options_wavg_exercise_price/2025-12-31/0000059527-26-000006/ccfd0f71`)
  > "Balance at end of year 621,683 150.63" — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1371`
  Agent's caveat: Weighted-average exercise price in dollars per share, from the same row of the annual report's option activity table at fiscal year end.
- **`pension_benefit_obligation`** = $94.1m at 2025-12-31 (`T2/CIK59527/pension_benefit_obligation/2025-12-31/0000059527-26-000006/8b72a0f2`)
  > "Benefit obligations at end of year 7,300 86,779 7,862 85,372" — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1446`
  The value is a sum, added by code, of figures the agent marked in this row: `7,300 + 86,779`.
  Agent's caveat: The U.S. and non-U.S. columns for the latest fiscal year end are added. The U.S. plans hold no assets. The quarterly reports do not restate the obligation.
- **`purchase_obligations`** = $76.5m at 2025-12-31 (`T2/CIK59527/purchase_obligations/2025-12-31/0000059527-26-000006/2a04621b`)
  > "As of December 31, 2025, the Company had total purchase commitments of $76,500, which includes $76,348 in current liabilities." — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:511`
  Agent's caveat: The wording says almost the whole amount sits in current liabilities. That may mean it is already on the balance sheet, or the company may just mean it is due within a year. Check before adding it as an extra liability, because it could be double-counted.
- **`unvested_stock_awards`** = 0.24m at 2025-12-31 (`T2/CIK59527/unvested_stock_awards/2025-12-31/0000059527-26-000006/57cae412`)
  > "Balance at end of year 241,774 210.59" — `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt:1414`
  Agent's caveat: Combined balance of RSUs and PSUs from the annual report's activity table at fiscal year end. The filing also says a separate group of vested but deferred units under the executive deferred compensation plan count in diluted shares, and it is not clear whether this table includes them. No newer figure appears in the quarterly reports.

## Sensitivity

Base equity value when one parameter is moved to its own low or high setting and all others stay at base. Largest swings first.

| Parameter | Repro. at low | Repro. at high | Liq. at low | Liq. at high |
|---|---:|---:|---:|---:|
| `intangible.selection` | $858.5m | $1,136.3m | -$699.9m | -$699.9m |
| `intangible.brand_sga_share` | $858.5m | $1,120.8m | -$699.9m | -$699.9m |
| `intangible.brand_life_years` | $910.9m | $1,104.5m | -$699.9m | -$699.9m |
| `intangible.royalty_rate` | $980.1m | $1,136.3m | -$699.9m | -$699.9m |
| `intangible.rd_life_years` | $913.7m | $1,068.2m | -$699.9m | -$699.9m |
| `haircut.going_concern.equipment` | $887.4m | $1,026.4m | -$699.9m | -$699.9m |
| `haircut.liquidation.equipment` | $980.1m | $980.1m | -$769.4m | -$630.4m |
| `haircut.liquidation.inventory_fg` | $980.1m | $980.1m | -$764.0m | -$635.8m |
| `haircut.liquidation.receivables` | $980.1m | $980.1m | -$760.2m | -$639.6m |
| `haircut.liquidation.other_current` | $980.1m | $980.1m | -$760.0m | -$639.8m |
| `haircut.going_concern.other_current` | $884.0m | $1,004.1m | -$699.9m | -$699.9m |
| `haircut.going_concern.buildings` | $937.2m | $1,022.9m | -$699.9m | -$699.9m |

## Gaps

Items this run could not measure from the fact store. They are left out of the numbers above.

- `contingent_possible`: An estimate of reasonably possible losses: An analyst agent searched the current filings and found none disclosed. Code cannot verify an absence, so check this yourself if it matters.
- `guarantees`: A maximum guarantee exposure: An analyst agent searched the current filings and found none disclosed. Code cannot verify an absence, so check this yourself if it matters.
- `dilution_strike`: Options are valued at their average exercise price, which understates dilution when some grants are in the money and others are not. Convertibles are not included.

## Parameters used

Overrides applied: `company:LECO`

| Parameter | Low | Base | High |
|---|---:|---:|---:|
| `decision.buy_requires_liquidation_floor` | 1 | 1 | 1 |
| `decision.margin_of_safety` | 0.33 | 0.33 | 0.33 |
| `haircut.going_concern.book_intangibles` | 0 | 0 | 0 |
| `haircut.going_concern.buildings` | 0.8 | 1 | 1.2 |
| `haircut.going_concern.cash` | 1 | 1 | 1 |
| `haircut.going_concern.dta` | 0.5 | 0.8 | 1 |
| `haircut.going_concern.equipment` | 0.7 | 0.9 | 1 |
| `haircut.going_concern.goodwill` | 0 | 0 | 0 |
| `haircut.going_concern.inventory_fg` | 0.9 | 1 | 1 |
| `haircut.going_concern.inventory_rm` | 0.9 | 1 | 1 |
| `haircut.going_concern.inventory_wip` | 0.8 | 1 | 1 |
| `haircut.going_concern.land` | 1 | 1 | 1.5 |
| `haircut.going_concern.other_current` | 0.5 | 0.9 | 1 |
| `haircut.going_concern.other_noncurrent` | 0.5 | 0.8 | 1 |
| `haircut.going_concern.receivables` | 0.95 | 1 | 1 |
| `haircut.going_concern.rou` | 1 | 1 | 1 |
| `haircut.liquidation.book_intangibles` | 0 | 0 | 0 |
| `haircut.liquidation.buildings` | 0.4 | 0.6 | 0.8 |
| `haircut.liquidation.cash` | 1 | 1 | 1 |
| `haircut.liquidation.dta` | 0 | 0.25 | 0.5 |
| `haircut.liquidation.equipment` | 0.1 | 0.25 | 0.4 |
| `haircut.liquidation.goodwill` | 0 | 0 | 0 |
| `haircut.liquidation.inventory_fg` | 0.5 | 0.65 | 0.8 |
| `haircut.liquidation.inventory_rm` | 0.4 | 0.6 | 0.8 |
| `haircut.liquidation.inventory_wip` | 0.1 | 0.25 | 0.4 |
| `haircut.liquidation.land` | 1 | 1 | 1.25 |
| `haircut.liquidation.other_current` | 0 | 0.25 | 0.5 |
| `haircut.liquidation.other_noncurrent` | 0 | 0.25 | 0.5 |
| `haircut.liquidation.receivables` | 0.75 | 0.85 | 0.95 |
| `haircut.liquidation.rou` | 0 | 0 | 0.25 |
| `intangible.brand_life_years` | 2 | 3 | 5 |
| `intangible.brand_sga_share` | 0.1 | 0.2 | 0.3 |
| `intangible.rd_life_years` | 3 | 5 | 8 |
| `intangible.replacement_avg_years` | 3 | 3 | 3 |
| `intangible.replacement_rd_years` | 2 | 4 | 6 |
| `intangible.replacement_sga_years` | 0.25 | 0.5 | 1 |
| `intangible.royalty_discount_rate` | 0.12 | 0.1 | 0.08 |
| `intangible.royalty_life_years` | 5 | 10 | 15 |
| `intangible.royalty_rate` | 0.01 | 0.02 | 0.04 |
| `intangible.selection` | `min` | `lower_median` | `max` |
| `intangible.sga_includes_rd` | 1 | 1 | 1 |
| `liability.pension_duration_years` | 12 | 12 | 12 |
| `liability.pension_rate_shift` | 0.01 | 0 | 0 |
| `liability.purchase_obligation_fraction` | 0.1 | 0 | 0 |
| `mapping.residual_tolerance` | 0.005 | 0.005 | 0.005 |
| `market.max_price_stale_days` | 7 | 7 | 7 |
| `tax.rate` | 0.26 | 0.25 | 0.21 |

## Documents

The raw files behind this run. Paths are relative to the `raw` folder of the data directory.

| Document | Local copy |
|---|---|
| [SEC filing index and company profile (SIC code, fiscal year end)](https://data.sec.gov/submissions/CIK0000059527.json) | `LECO/sec/submissions.2026-11-16.json` |
| [Every XBRL-tagged fact the company has filed; source of the XBRL fact store](https://data.sec.gov/api/xbrl/companyfacts/CIK0000059527.json) | `LECO/sec/companyfacts.2026-11-16.json` |
| [10-K for the period ending 2025-12-31, filed 2026-02-25, as filed](https://www.sec.gov/Archives/edgar/data/59527/000005952726000006/leco-20251231x10k.htm) | `LECO/filings/0000059527-26-000006/leco-20251231x10k.htm` |
| 10-K for the period ending 2025-12-31, filed 2026-02-25, as plain text; line numbers are the paragraph numbers in citations | `LECO/filings/0000059527-26-000006/leco-20251231x10k.txt` |
| [10-Q for the period ending 2026-03-31, filed 2026-04-30, as filed](https://www.sec.gov/Archives/edgar/data/59527/000005952726000012/leco-20260331x10q.htm) | `LECO/filings/0000059527-26-000012/leco-20260331x10q.htm` |
| 10-Q for the period ending 2026-03-31, filed 2026-04-30, as plain text; line numbers are the paragraph numbers in citations | `LECO/filings/0000059527-26-000012/leco-20260331x10q.txt` |
| [10-Q for the period ending 2026-06-30, filed 2026-07-30, as filed](https://www.sec.gov/Archives/edgar/data/59527/000005952726000022/leco-20260630x10q.htm) | `LECO/filings/0000059527-26-000022/leco-20260630x10q.htm` |
| 10-Q for the period ending 2026-06-30, filed 2026-07-30, as plain text; line numbers are the paragraph numbers in citations | `LECO/filings/0000059527-26-000022/leco-20260630x10q.txt` |
| [10-Q for the period ending 2026-09-30, filed 2026-10-27, as filed](https://www.sec.gov/Archives/edgar/data/59527/000005952726000027/leco-20260930x10q.htm) | `LECO/filings/0000059527-26-000027/leco-20260930x10q.htm` |
| 10-Q for the period ending 2026-09-30, filed 2026-10-27, as plain text; line numbers are the paragraph numbers in citations | `LECO/filings/0000059527-26-000027/leco-20260930x10q.txt` |
| [Daily closes stored from yahoo; append-only, earlier rows never change](https://query1.finance.yahoo.com/v8/finance/chart/LECO) | `LECO/prices/yahoo.csv` |

## Facts used

Price: `PX/LECO/2026-11-13/yahoo`

| Fact | Value | Form | Filed |
|---|---:|---|---|
| `CIK59527/dei:EntityCommonStockSharesOutstanding/shares/2026-09-30/0000059527-26-000027` | 54.16m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:AccountsReceivableNetCurrent/USD/2026-09-30/0000059527-26-000027` | $603.3m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:Assets/USD/2026-09-30/0000059527-26-000027` | $3,893.6m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:AssetsCurrent/USD/2026-09-30/0000059527-26-000027` | $1,826.2m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:BuildingsAndImprovementsGross/USD/2025-12-31/0000059527-26-000006` | $499.5m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:CashAndCashEquivalentsAtCarryingValue/USD/2026-09-30/0000059527-26-000027` | $283.2m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:DebtLongtermAndShorttermCombinedAmount/USD/2026-09-30/0000059527-26-000027` | $1,150.0m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:DeferredIncomeTaxAssetsNet/USD/2025-12-31/0000059527-26-000006` | $47.1m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:ExcessOfReplacementOrCurrentCostsOverStatedLIFOValue/USD/2026-09-30/0000059527-26-000027` | $145.5m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:Goodwill/USD/2026-09-30/0000059527-26-000027` | $886.0m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:IntangibleAssetsNetExcludingGoodwill/USD/2025-12-31/0000059527-26-000006` | $250.4m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:InventoryFinishedGoodsNetOfReserves/USD/2026-09-30/0000059527-26-000027` | $369.6m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:InventoryNet/USD/2026-09-30/0000059527-26-000027` | $699.4m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:InventoryRawMaterialsNetOfReserves/USD/2026-09-30/0000059527-26-000027` | $157.8m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:InventoryWorkInProcessNetOfReserves/USD/2026-09-30/0000059527-26-000027` | $172.0m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:Land/USD/2025-12-31/0000059527-26-000006` | $66.0m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:Liabilities/USD/2026-09-30/0000059527-26-000027` | $2,338.9m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:OperatingLeaseLiability/USD/2026-09-30/0000059527-26-000027` | $58.0m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:OperatingLeaseRightOfUseAsset/USD/2026-09-30/0000059527-26-000027` | $57.7m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:PropertyPlantAndEquipmentGross/USD/2025-12-31/0000059527-26-000006` | $1,645.6m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:PropertyPlantAndEquipmentNet/USD/2025-12-31/0000059527-26-000027` | $702.8m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:PropertyPlantAndEquipmentNet/USD/2026-09-30/0000059527-26-000027` | $747.6m | 10-Q | 2026-10-27 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2018-01-01..2018-12-31/0000059527-21-000008` | $54.2m | 10-K | 2021-02-19 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2019-01-01..2019-12-31/0000059527-22-000006` | $56.8m | 10-K | 2022-02-18 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2020-01-01..2020-12-31/0000059527-23-000004` | $51.4m | 10-K | 2023-02-21 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2021-01-01..2021-12-31/0000059527-24-000008` | $56.0m | 10-K | 2024-02-27 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2022-01-01..2022-12-31/0000059527-25-000006` | $63.2m | 10-K | 2025-02-26 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2023-01-01..2023-12-31/0000059527-26-000006` | $71.2m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2024-01-01..2024-12-31/0000059527-26-000006` | $81.8m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:ResearchAndDevelopmentExpense/USD/2025-01-01..2025-12-31/0000059527-26-000006` | $85.5m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax/USD/2025-01-01..2025-12-31/0000059527-26-000006` | $4,233.0m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:SellingGeneralAndAdministrativeExpense/USD/2021-01-01..2021-12-31/0000059527-24-000008` | $597.1m | 10-K | 2024-02-27 |
| `CIK59527/us-gaap:SellingGeneralAndAdministrativeExpense/USD/2022-01-01..2022-12-31/0000059527-25-000006` | $656.6m | 10-K | 2025-02-26 |
| `CIK59527/us-gaap:SellingGeneralAndAdministrativeExpense/USD/2023-01-01..2023-12-31/0000059527-26-000006` | $758.9m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:SellingGeneralAndAdministrativeExpense/USD/2024-01-01..2024-12-31/0000059527-26-000006` | $780.6m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:SellingGeneralAndAdministrativeExpense/USD/2025-01-01..2025-12-31/0000059527-26-000006` | $798.0m | 10-K | 2026-02-25 |
| `CIK59527/us-gaap:WeightedAverageNumberDilutedSharesOutstandingAdjustment/shares/2026-07-01..2026-09-30/0000059527-26-000027` | 0.47m | 10-Q | 2026-10-27 |
| `T2/CIK59527/contingent_possible_loss/2025-12-31/0000059527-26-000006/f99e8b38` | none disclosed | 10-K | 2026-02-25 |
| `T2/CIK59527/guarantee_max_exposure/2025-12-31/0000059527-26-000006/f99e8b38` | none disclosed | 10-K | 2026-02-25 |
| `T2/CIK59527/options_outstanding/2025-12-31/0000059527-26-000006/3d33d656` | 0.62m | 10-K | 2026-02-25 |
| `T2/CIK59527/options_wavg_exercise_price/2025-12-31/0000059527-26-000006/ccfd0f71` | $150.63 | 10-K | 2026-02-25 |
| `T2/CIK59527/pension_benefit_obligation/2025-12-31/0000059527-26-000006/8b72a0f2` | $94.1m | 10-K | 2026-02-25 |
| `T2/CIK59527/purchase_obligations/2025-12-31/0000059527-26-000006/2a04621b` | $76.5m | 10-K | 2026-02-25 |
| `T2/CIK59527/unvested_stock_awards/2025-12-31/0000059527-26-000006/57cae412` | 0.24m | 10-K | 2026-02-25 |
