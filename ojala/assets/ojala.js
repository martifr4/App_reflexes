/* Ojalá — shared behaviour for the Spanish and English demo pages.
 * Language is read from <html lang>; all copy lives in STRINGS below. */
(function(){
'use strict';

var ES     = (document.documentElement.lang || 'es').slice(0,2) === 'es';
var LOCALE = ES ? 'es-ES' : 'en-GB';
var R      = window.OJALA_ECB;

/* ---------- formatting ---------- */
var nf0  = new Intl.NumberFormat(LOCALE, {useGrouping:'always'});
var cur0 = new Intl.NumberFormat(LOCALE, {style:'currency', currency:'EUR', maximumFractionDigits:0, useGrouping:'always'});
var pct2 = new Intl.NumberFormat(LOCALE, {style:'percent', minimumFractionDigits:2});
var cur2 = new Intl.NumberFormat(LOCALE, {style:'currency', currency:'EUR', minimumFractionDigits:2});
var dayMonth = new Intl.DateTimeFormat(LOCALE, {day:'numeric', month:'short'});
var longDate = new Intl.DateTimeFormat(LOCALE, {weekday:'long', day:'numeric', month:'long', year:'numeric'});
var monthName = new Intl.DateTimeFormat(LOCALE, {month:'long'});

function fmtN(n){ return nf0.format(Math.round(n)); }
function fmtEUR(n){ return cur0.format(Math.round(n)); }
function fmtPct(p){ return pct2.format(p/100); }
function cap(s){ return s.charAt(0).toUpperCase() + s.slice(1); }
function iso(d){ return new Date(d + 'T00:00:00'); }
function daysUntil(date){ return Math.max(0, Math.ceil((date - Date.now()) / 86400000)); }

/* ---------- copy ---------- */
var STRINGS = ES ? {
  tapeLabel:'Tipos del BCE y su efecto en el próximo sorteo',
  pause:'Pausar', play:'Reanudar',
  ecb:'BCE', deposit:'Facilidad de depósito', mro:'Op. principales', marginal:'Facilidad marginal',
  since:function(d){ return 'desde el ' + d; },
  unchanged:'sin cambios',
  potNow:function(m){ return 'Bote de ' + m; },          // octubre, en minúscula
  potDelta:function(amount, up, prev){
    return up ? amount + ' más que con el ' + prev : amount + ' menos que con el ' + prev;
  },
  potSame:'igual que el mes pasado',
  breakdown:function(total, gordo, syn, synN, pedrea, pedreaN){
    return total + ' premios este mes: 1 × ' + gordo + ', ' + synN + ' × ' + syn + ' y ' + pedreaN + ' × ' + pedrea;
  },
  sensitivity:function(bp, money, prizes){
    return 'Cada ' + bp + ' pb del BCE mueve ' + money + ' del bote: ' + prizes + ' premios de la pedrea';
  },
  per100:function(money){ return 'Cada 100 € ahorrados ceden ' + money + ' al año al bote. Y siguen siendo tuyos'; },
  nextMeeting:function(date, days){ return 'Próxima decisión del BCE: ' + date + ', en ' + days; },
  whatIf:function(rate, pot, up){ return (up ? 'Si sube al ' : 'Si baja al ') + rate + ', el bote sería de ' + pot; },
  drawIn:function(date, days){ return 'Próximo sorteo: ' + date + ', dentro de ' + days; },
  days:function(n){ return n === 1 ? '1 día' : n + ' días'; },
  closer:'Los tipos se mueven. Tu ahorro, no.',
  oneIn:'1 de ',
  spinning:'Girando el bombo…', again:'Volver a simular',
  gordo:'Gordo', syndicate:'Peña', pedrea:'Pedrea', winners:'ganadores',
  names:['Lucía G., Valencia','Pablo M., Madrid','Carmen S., Málaga','Iker A., Donostia','Marta V., Zaragoza','Álvaro T., Murcia','Rosa P., A Coruña','Hugo D., Sevilla'],
  penas:['Peña "El Bar de Paco", Cádiz','Peña "Oficina 3B", Barcelona','Peña "Las de yoga", Valladolid','Peña "Los del martes", Bilbao']
} : {
  tapeLabel:'ECB rates and what they do to the next draw',
  pause:'Pause', play:'Play',
  ecb:'ECB', deposit:'Deposit facility', mro:'Main refinancing', marginal:'Marginal lending',
  since:function(d){ return 'since ' + d; },
  unchanged:'unchanged',
  potNow:function(m){ return cap(m) + ' pot'; },
  potDelta:function(amount, up, prev){
    return amount + (up ? ' more' : ' less') + ' than at ' + prev;
  },
  potSame:'same as last month',
  breakdown:function(total, gordo, syn, synN, pedrea, pedreaN){
    return total + ' prizes this month: 1 × ' + gordo + ', ' + synN + ' × ' + syn + ' and ' + pedreaN + ' × ' + pedrea;
  },
  sensitivity:function(bp, money, prizes){
    return 'Every ' + bp + ' bp from the ECB moves ' + money + ' of pot: ' + prizes + ' pedrea prizes';
  },
  per100:function(money){ return 'Every €100 saved hands ' + money + ' a year to the pot. And stays yours'; },
  nextMeeting:function(date, days){ return 'Next ECB decision: ' + date + ', in ' + days; },
  whatIf:function(rate, pot, up){ return (up ? 'A rise to ' : 'A cut to ') + rate + ' would make the pot ' + pot; },
  drawIn:function(date, days){ return 'Next draw: ' + date + ', in ' + days; },
  days:function(n){ return n === 1 ? '1 day' : n + ' days'; },
  closer:'Rates move. Your savings don’t.',
  oneIn:'1 in ',
  spinning:'Spinning the drum…', again:'Simulate again',
  gordo:'Gordo', syndicate:'Syndicate', pedrea:'Pedrea', winners:'winners',
  names:['Lucía G., Valencia','Pablo M., Madrid','Carmen S., Málaga','Iker A., Donostia','Marta V., Zaragoza','Álvaro T., Murcia','Rosa P., A Coruña','Hugo D., Seville'],
  penas:['"El Bar de Paco" syndicate, Cádiz','"Oficina 3B" syndicate, Barcelona','"Las de yoga" syndicate, Valladolid','"Los del martes" syndicate, Bilbao']
};
var T = STRINGS;

/* ---------- the draw: first Monday of the month, 09:00 ---------- */
function firstMonday(year, month){
  var d = new Date(year, month, 1, 9, 0, 0);
  while (d.getDay() !== 1) d.setDate(d.getDate() + 1);
  return d;
}
function nextDraw(){
  var now = new Date();
  var d = firstMonday(now.getFullYear(), now.getMonth());
  if (d - now <= 0) d = firstMonday(now.getFullYear(), now.getMonth() + 1);
  return d;
}
var target = nextDraw();

/* ---------- ECB rate → pot → prizes ---------- */
function potExact(rate){
  // €pool at `rate` a year, `toPot` of it to prizes, split over 12 months
  return R.pool * (rate/100) * R.toPot / 12;
}
function potFor(rate){            // headline figure, to the nearest €1,000
  return Math.round(potExact(rate) / 1000) * 1000;
}
function round100(n){ return Math.round(n / 100) * 100; }
function prizesFor(pot){
  var fixed = R.topPrize + R.syndicatePrize * R.syndicateWinners;
  var pedrea = Math.max(0, Math.floor((pot - fixed) / R.pedreaPrize));
  return { pedrea: pedrea, total: 1 + R.syndicateWinners + pedrea };
}

var pot       = potFor(R.rates.deposit);
var potPrev   = potFor(R.previous.deposit);
var deltaBp   = Math.round((R.rates.deposit - R.previous.deposit) * 100);
var breakdown = prizesFor(pot);
var step      = 25; // basis points: the ECB's usual stride
// deltas come off the unrounded pot, so "moved €3,300" and "€3,300 per 25 bp" agree
var deltaPot  = round100(Math.abs(potExact(R.rates.deposit) - potExact(R.previous.deposit)));
var stepPot   = round100(potExact(step/100));
var stepPrz   = Math.round(stepPot / R.pedreaPrize);
var entries   = R.pool / 10;   // one entry per €10 saved

/* ---------- figures on the page that follow the rate ----------
 * Anything marked <span data-ojala="key"> is filled from the numbers above, so
 * a new ECB level moves the pot, the prize table and the draw odds together. */
(function(){
  var nf1 = new Intl.NumberFormat(LOCALE, {maximumFractionDigits:1});
  var yield100 = 100 * (R.rates.deposit/100);          // what €100 earns in a year
  var toPot100 = yield100 * R.toPot;                   // the part that becomes prizes
  var rest100  = yield100 - toPot100;                  // bank + Ojalá
  var pMonth   = 1 - Math.pow(1 - 100/entries, breakdown.total);   // with 100 entries

  var VALUES = {
    rateDeposit:    fmtPct(R.rates.deposit),
    potRate:        fmtPct(R.rates.deposit * R.toPot),
    pot:            fmtEUR(pot),
    prizes:         fmtN(breakdown.total),
    pedrea:         fmtN(breakdown.pedrea),
    pedreaPrize:    fmtEUR(R.pedreaPrize),
    pedreaTotal:    fmtEUR(breakdown.pedrea * R.pedreaPrize),
    topPrize:       fmtEUR(R.topPrize),
    syndicatePrize: fmtEUR(R.syndicatePrize),
    syndicateN:     fmtN(R.syndicateWinners),
    syndicateTotal: fmtEUR(R.syndicatePrize * R.syndicateWinners),
    poolM:          fmtN(R.pool / 1000000),
    entriesM:       fmtN(entries / 1000000),
    drawMonth:      monthName.format(target),
    yield100:       cur2.format(yield100),
    yield1000:      fmtEUR(yield100 * 10),
    split:          cur2.format(toPot100) + ' · ' + cur2.format(rest100/2) + ' · ' + cur2.format(rest100/2),
    per100Pot:      cur2.format(toPot100),
    per100Rest:     cur2.format(rest100),
    per100Half:     cur2.format(rest100/2),
    per100Net:      cur2.format(toPot100 * 0.81),       // after the 19 % withholding
    per100Giveup:   cur2.format(yield100 - toPot100 * 0.81),
    stepBp:         fmtN(step),
    stepPot:        fmtEUR(stepPot),
    stepPrizes:     fmtN(stepPrz),
    yearsAny:       nf1.format(1 / (12 * pMonth)),
    yearsGordo:     fmtN(entries / 100 / 12)
  };

  [].forEach.call(document.querySelectorAll('[data-ojala]'), function(el){
    var v = VALUES[el.dataset.ojala];
    if (v != null) el.textContent = v;
  });
})();

/* ---------- the moving tape ---------- */
(function(){
  var tape = document.getElementById('ecbTape');
  if (!tape || !R) return;

  var effective = iso(R.effective), meeting = iso(R.nextDecision);
  var dir  = deltaBp > 0 ? 'up' : deltaBp < 0 ? 'down' : 'flat';
  var arrow = deltaBp > 0 ? '▲' : deltaBp < 0 ? '▼' : '=';
  var move = deltaBp === 0
    ? T.unchanged
    : arrow + ' ' + Math.abs(deltaBp) + (ES ? ' pb' : ' bp');

  var live = function(id, text){ return '<span data-live="' + id + '">' + text + '</span>'; };

  var items = [
    { cls:'lead', html:
      '<span class="k">' + T.ecb + ' · ' + T.deposit + '</span><b>' + fmtPct(R.rates.deposit) + '</b>' +
      '<span class="' + dir + '">' + move + '</span>' +
      '<span>' + T.since(dayMonth.format(effective)) + '</span>' },

    { html: '<span class="k">' + T.mro + '</span><b>' + fmtPct(R.rates.mro) + '</b>' +
            '<span class="k">' + T.marginal + '</span><b>' + fmtPct(R.rates.marginal) + '</b>' },

    { html: '<span class="k">' + T.potNow(monthName.format(target)) + '</span>' +
            '<span class="pot">≈ ' + fmtEUR(pot) + '</span>' +
            '<span class="' + dir + '">' + (deltaBp === 0
              ? T.potSame
              : T.potDelta(fmtEUR(deltaPot), pot > potPrev, fmtPct(R.previous.deposit))) + '</span>' },

    { html: T.breakdown(fmtN(breakdown.total), fmtEUR(R.topPrize), fmtEUR(R.syndicatePrize),
                        R.syndicateWinners, fmtEUR(R.pedreaPrize), fmtN(breakdown.pedrea)) },

    { html: T.sensitivity(step, '≈ ' + fmtEUR(stepPot), '≈ ' + fmtN(stepPrz)) },

    { html: T.per100(cur2.format(100 * (R.rates.deposit/100) * R.toPot)) },

    { html: T.nextMeeting(dayMonth.format(meeting), live('meeting', T.days(daysUntil(meeting)))) },

    { html: T.drawIn(dayMonth.format(target), live('draw', T.days(daysUntil(target)))) },

    { cls:'lead', html: T.closer }
  ];

  if (R.expectedNext != null && R.expectedNext !== R.rates.deposit){
    items.splice(7, 0, { html: T.whatIf(fmtPct(R.expectedNext),
                                       '≈ ' + fmtEUR(potFor(R.expectedNext)),
                                       R.expectedNext > R.rates.deposit) });
  }

  var one = items.map(function(i){
    return '<li class="' + (i.cls || '') + '">' + i.html + '</li>';
  }).join('');

  var track = tape.querySelector('.tape-track');
  track.innerHTML = '<ul class="tape-run">' + one + '</ul>';

  // repeat the set until it covers the viewport, then clone it once for a seamless loop
  var runWidth = track.firstElementChild.getBoundingClientRect().width;
  var copies = Math.max(1, Math.ceil(tape.getBoundingClientRect().width / Math.max(runWidth, 1)));
  var set = one.repeat(copies);
  track.innerHTML = '<ul class="tape-run">' + set + '</ul>' +
                    '<ul class="tape-run" aria-hidden="true">' + set + '</ul>';
  track.style.setProperty('--tape-duration', Math.round(runWidth * copies / 55) + 's');

  var btn = tape.querySelector('.tape-pause');
  if (btn){
    var ICON = {
      pause: '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true" fill="currentColor"><rect x="1.5" y="1" width="3" height="10" rx="1"/><rect x="7.5" y="1" width="3" height="10" rx="1"/></svg>',
      play:  '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true" fill="currentColor"><path d="M2.5 1.2 10.5 6l-8 4.8z"/></svg>'
    };
    var label = function(paused){
      btn.innerHTML = (paused ? ICON.play : ICON.pause) +
                      '<span class="tape-pause-word">' + (paused ? T.play : T.pause) + '</span>';
      btn.setAttribute('aria-label', paused ? T.play : T.pause);
    };
    label(false);
    btn.addEventListener('click', function(){
      var paused = tape.dataset.paused === 'true';
      tape.dataset.paused = String(!paused);
      btn.setAttribute('aria-pressed', String(!paused));
      label(!paused);
    });
  }

  // keep the countdowns honest while the page stays open
  function refresh(){
    var values = { meeting: T.days(daysUntil(meeting)), draw: T.days(daysUntil(target)) };
    Object.keys(values).forEach(function(k){
      [].forEach.call(track.querySelectorAll('[data-live="' + k + '"]'), function(el){
        el.textContent = values[k];
      });
    });
  }
  setInterval(refresh, 60000);
})();

/* ---------- simulator ---------- */
(function(){
  var POOL_ENTRIES = entries, PRIZES = breakdown.total;
  var weekly = document.getElementById('weekly'), initial = document.getElementById('initial');
  if (!weekly || !initial) return;
  var chips = [].slice.call(document.querySelectorAll('.chip'));
  var months = 12;

  function calc(){
    var w = +weekly.value, init = +initial.value;
    var saved = init + w * (52/12) * months;
    var entries = Math.floor(saved / 10);
    var pMonth = 1 - Math.pow(1 - entries / POOL_ENTRIES, PRIZES);
    // average entries over the year ≈ half of final for a growing balance
    var avgEntries = Math.max(1, init/10 + (entries - init/10)/2);
    var pAvg = 1 - Math.pow(1 - avgEntries / POOL_ENTRIES, PRIZES);
    var pYear = 1 - Math.pow(1 - pAvg, Math.min(months, 12));
    document.getElementById('weeklyOut').textContent  = fmtEUR(w);
    document.getElementById('initialOut').textContent = fmtEUR(init);
    document.getElementById('saved').textContent      = fmtEUR(saved);
    document.getElementById('entries').textContent    = fmtN(entries);
    document.getElementById('odds').textContent       = entries ? T.oneIn + fmtN(1/pMonth) : '—';
    document.getElementById('oddsYear').textContent   = entries ? T.oneIn + fmtN(1/pYear) : '—';
  }
  weekly.addEventListener('input', calc);
  initial.addEventListener('input', calc);
  chips.forEach(function(c){
    c.addEventListener('click', function(){
      chips.forEach(function(x){ x.setAttribute('aria-pressed','false'); });
      c.setAttribute('aria-pressed','true');
      months = +c.dataset.months;
      calc();
    });
  });
  calc();
})();

/* ---------- countdown ---------- */
(function(){
  var dEl = document.getElementById('cd-d');
  if (!dEl) return;
  var label = longDate.format(target);
  document.getElementById('nextDate').textContent = (ES ? cap(label) : label) + ' · 9:00';
  function tick(){
    var ms = Math.max(0, target - Date.now());
    document.getElementById('cd-d').textContent = String(Math.floor(ms/86400000));
    document.getElementById('cd-h').textContent = String(Math.floor(ms/3600000)%24).padStart(2,'0');
    document.getElementById('cd-m').textContent = String(Math.floor(ms/60000)%60).padStart(2,'0');
  }
  tick();
  setInterval(tick, 30000);
})();

/* ---------- demo draw ---------- */
(function(){
  var btn = document.getElementById('demoDraw');
  if (!btn) return;
  btn.addEventListener('click', function(){
    var label = btn.textContent;
    btn.disabled = true;
    btn.textContent = T.spinning;
    window.OJALA_SPIN && window.OJALA_SPIN();
    setTimeout(function(){
      var log = document.getElementById('drawLog');
      var month = cap(monthName.format(target));
      var pick = function(a){ return a[Math.floor(Math.random()*a.length)]; };
      log.innerHTML =
        '<div><span>' + month + ' · ' + T.gordo + '</span><span class="mono win">' + pick(T.names) + ' · ' + fmtEUR(R.topPrize) + '</span></div>' +
        '<div><span>' + month + ' · ' + T.syndicate + '</span><span class="mono">' + pick(T.penas) + ' · ' + fmtEUR(R.syndicatePrize) + '</span></div>' +
        '<div><span>' + month + ' · ' + T.pedrea + '</span><span class="mono">' + fmtN(breakdown.pedrea) + ' ' + T.winners + ' · ' + fmtEUR(R.pedreaPrize) + '</span></div>';
      btn.disabled = false;
      btn.textContent = T.again || label;
      var s = document.getElementById('serial');
      if (s) s.textContent = [0,0,0].map(function(){
        return String(Math.floor(Math.random()*100)).padStart(2,'0');
      }).join(' ');
    }, 1800);
  });
})();

/* ---------- waitlist ---------- */
(function(){
  var form = document.getElementById('waitlist');
  if (!form) return;
  form.addEventListener('submit', function(e){
    e.preventDefault();
    form.hidden = true;
    document.getElementById('waitOk').hidden = false;
  });
})();

/* ---------- bombo (drum) ---------- */
(function(){
  var cv = document.getElementById('bombo');
  if (!cv) return;
  var ctx = cv.getContext('2d');
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var css = function(k){ return getComputedStyle(document.documentElement).getPropertyValue(k).trim(); };
  var N = 34, RAD = 190, C = 220;
  var balls = Array.from({length:N}, function(_, i){
    return {
      a: Math.random()*Math.PI*2, r: 40 + Math.random()*130, v: (Math.random()-.5)*.02,
      n: String(Math.floor(Math.random()*100)).padStart(2,'0'), s: 15 + Math.random()*6,
      hot: i % 9 === 0
    };
  });
  var rot = 0, spinBoost = 0;
  window.OJALA_SPIN = function(){ spinBoost = 1; };

  function draw(){
    var hope = css('--hope'), ink = css('--ink'), line = css('--line'),
        ticket = css('--ticket'), coral = css('--coral');
    ctx.clearRect(0,0,440,440);
    ctx.save(); ctx.translate(C,C);
    ctx.beginPath(); ctx.arc(0,0,RAD,0,Math.PI*2); ctx.fillStyle = ticket; ctx.fill();
    ctx.lineWidth = 10; ctx.strokeStyle = line; ctx.stroke();
    ctx.save(); ctx.rotate(rot);
    ctx.strokeStyle = line; ctx.lineWidth = 2; ctx.globalAlpha = .6;
    for (var i=0;i<8;i++){
      ctx.beginPath(); ctx.moveTo(0,0);
      ctx.lineTo(RAD*Math.cos(i*Math.PI/4), RAD*Math.sin(i*Math.PI/4)); ctx.stroke();
    }
    ctx.restore(); ctx.globalAlpha = 1;
    balls.forEach(function(b){
      var x = b.r*Math.cos(b.a), y = b.r*Math.sin(b.a);
      ctx.beginPath(); ctx.arc(x,y,b.s,0,Math.PI*2);
      ctx.fillStyle = b.hot ? hope : ticket; ctx.fill();
      ctx.lineWidth = 1.5; ctx.strokeStyle = b.hot ? hope : ink;
      ctx.globalAlpha = b.hot ? 1 : .55; ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillStyle = b.hot ? '#fff' : ink;
      ctx.font = '500 ' + Math.round(b.s*.8) + 'px "DM Mono", monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(b.n, x, y+1);
    });
    ctx.beginPath(); ctx.arc(0,0,9,0,Math.PI*2); ctx.fillStyle = coral; ctx.fill();
    ctx.restore();
    ctx.strokeStyle = line; ctx.lineWidth = 10; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(C-70,430); ctx.lineTo(C+70,430); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(C,C+RAD+5); ctx.lineTo(C,430); ctx.stroke();
  }
  function step(){
    var speed = .006 + spinBoost*.09;
    rot += speed;
    balls.forEach(function(b){
      b.a += b.v + speed*(.6 + b.r/400);
      b.r += (Math.random()-.5)*(1 + spinBoost*10);
      b.r = Math.max(30, Math.min(RAD-22, b.r));
    });
    if (spinBoost > 0) spinBoost = Math.max(0, spinBoost - .012);
    draw();
    requestAnimationFrame(step);
  }
  draw();
  if (!reduce) requestAnimationFrame(step);
  new MutationObserver(draw).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});
})();

})();
