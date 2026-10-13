// Checks that the website's in-browser engine (site/index.html) reproduces compute.py.
// Usage (from token_spread/): node tests/check_engine.js   -> exits 1 on any mismatch
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'site/index.html'), 'utf8');
const D = JSON.parse(html.match(/<script id="ts-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const CFG = D.config, MODELS = CFG.models, GPUS = CFG.gpus;
const src = html.match(/\/\* =+ ENGINE START[\s\S]*?=+ \*\/([\s\S]*?)\/\* =+ ENGINE END/)[1];
const ENGINE = eval(src + '; ENGINE');
const BASE = { util: CFG.utilization_base, ratio: CFG.io_ratio_base, floor: CFG.interactivity_floor_tok_s_per_user,
  price: CFG.price_statistic, rental: CFG.rental_base_series, spec: CFG.allow_speculative_decoding, multi: CFG.allow_disaggregated_multinode };
const P = CFG.power ? { region: CFG.power.base_region, pue: CFG.power.pue_base, lf: CFG.power.load_factor } : null;
const RF = CFG.rental_firm;
const F = RF ? { capex: RF.capex_usd_per_gpu, capexMult: 1, years: RF.depreciation_years, rate: RF.cost_of_capital,
  colo: RF.colocation_usd_per_kw_month, ops: RF.ops_usd_per_gpu_hour, occ: RF.occupancy_base } : null;
const close = (a, b, tol = 1e-6) => (isNaN(a) && isNaN(b)) || Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));
const caseOf = (m, g, p) => ENGINE.cases().find(c => c.m.key === m && c.gpu === g && c.prec === p);
let bad = 0, n = 0;
const check = (ok, msg) => { n++; if (!ok) { bad++; console.log('MISMATCH', msg); } };
for (const p of D.python_summary) { const r = ENGINE.evaluate(caseOf(p.m, p.gpu, p.prec), BASE); check(close(r.rev, p.revenue) && close(r.sratio, p.ratio), `spread ${p.m} ${p.gpu} ${p.prec}`); }
const sens = fs.readFileSync(path.join(root, 'outputs/sensitivity.csv'), 'utf8').trim().split('\n'); const hdr = sens.shift().split(',');
for (const line of sens) { const o = Object.fromEntries(hdr.map((k, i) => [k, line.split(',')[i]])); if (o.op_point !== 'floor') continue;
  const c = ENGINE.cases().find(c => c.m.key === o.model && c.gpu === o.gpu && c.prec === o.precision && c.kind === 'base');
  check(close(ENGINE.evaluate(c, BASE, +o.io_ratio, +o.utilization).sratio, +o.spread_ratio), `sensitivity ${line}`); }
const po = new Set([...(CFG.closed_models || []), ...(CFG.price_only_open_models || [])].map(c => c.key));
for (const p of D.python_breakeven || []) { const rent = ENGINE.rental(p.gpu, BASE.rental).base;
  const price = po.has(p.m) ? ENGINE.closedPrice(p.m, BASE.ratio).list : ENGINE.evaluate(ENGINE.cases().find(c => c.m.key === p.m && c.gpu === p.gpu && c.kind === 'base'), BASE).price;
  check(close(ENGINE.breakeven(rent, price, BASE.util), p.be), `breakeven ${p.m} ${p.gpu}`); }
for (const p of D.python_power || []) { const r = ENGINE.evaluate(caseOf(p.m, p.gpu, p.prec), BASE);
  check(close(ENGINE.kwhPerHour(p.gpu, P) * ENGINE.elecPrice(P.region), p.power) && close(ENGINE.measuredPower(r.tf), p.mw == null ? NaN : p.mw), `power ${p.m} ${p.gpu}`); }
if (F) {
  for (const p of D.python_firm || []) { const c = ENGINE.firmCosts(p.gpu, F, P), pp = ENGINE.firmPnl(c, ENGINE.rental(p.gpu, BASE.rental).base, F.occ);
    check(close(pp.full, p.full) && close(pp.profit, p.profit), `firm ${p.gpu}`); }
  for (const p of D.python_split || []) { const r = ENGINE.evaluate(caseOf(p.m, p.gpu, p.prec), BASE), c = ENGINE.firmCosts(p.gpu, F, P), pp = ENGINE.firmPnl(c, r.R.base, F.occ);
    check(close(r.R.base - pp.full / F.occ, p.landlord) && close(r.rev - pp.full, p.integrated), `split ${p.m} ${p.gpu}`); }
  if (D.python_ranking) { const rk = ENGINE.ranking(BASE, F, P);
    check(rk.length === D.python_ranking.length, `ranking length ${rk.length} vs ${D.python_ranking.length}`);
    for (const p of D.python_ranking) { const r = rk.find(x => x.key === p.m);
      check(r && r.gpu === p.gpu && close(r.rev, p.revenue) && close(r.profit, p.profit), `ranking ${p.m}`); } }
}
console.log(`${n - bad}/${n} checks match compute.py`);
process.exit(bad ? 1 : 0);
