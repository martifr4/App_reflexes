/* Ojalá — ECB reference data.
 *
 * This is the ONLY file to touch when the ECB moves. Both the Spanish and the
 * English page read it: the moving tape at the top, the prize-pot estimate and
 * the "what a cut would do to the draw" line are all derived from these numbers.
 *
 * After a Governing Council decision:
 *   1. move `rates` into `previous`
 *   2. write the new levels into `rates`
 *   3. update `decided`, `effective` and `nextDecision`
 *   4. set `expectedNext` to whatever the market is pricing for that meeting
 *        (or null if you'd rather not show the what-if line)
 *
 * Demo figures. Dates are ISO, rates are percent per year.
 */
window.OJALA_ECB = {
  decided: '2026-09-10',        // Governing Council decision
  effective: '2026-09-16',      // date the new levels apply from
  nextDecision: '2026-10-29',   // next monetary policy meeting

  rates:    { deposit: 2.50, mro: 2.65, marginal: 2.90 },
  previous: { deposit: 2.75, mro: 2.90, marginal: 3.15 },

  expectedNext: 2.25,           // deposit rate the market prices for the next meeting

  pool: 20000000,               // € saved across everyone
  toPot: 0.80,                  // share of the yield that becomes prizes
  topPrize: 10000,              // the Ojalá Gordo
  syndicatePrize: 500,
  syndicateWinners: 10,
  pedreaPrize: 20               // the pedrea; its count flexes with the pot
};
