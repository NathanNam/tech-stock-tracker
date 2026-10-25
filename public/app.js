// Tech Terminal. Quotes come from Finnhub when the visitor pastes their own key
// (kept in memory only, sent only to Finnhub), otherwise from Yahoo Finance via
// /api/yahoo. Charts, sparklines and volume always use Yahoo: Finnhub's free plan
// has no price history, and it covers US listings only.

const DEFAULT_LIST = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'AVGO', 'TSM', 'SKHY', 'TSLA', 'SPCX', 'ORCL'];
const INDEXES = ['SPY', 'QQQ'];
const MAX_LIST = 25;
// Short display names (Yahoo's long names don't fit the row); non-US listings get a label too.
const ALIAS = {
  TSM: { name: 'TSMC (ADR)' }, SKHY: { name: 'SK hynix (ADR)' }, SPCX: { name: 'SpaceX' },
  GOOGL: { name: 'Alphabet' }, META: { name: 'Meta Platforms' }, AVGO: { name: 'Broadcom' },
  '000660.KS': { label: 'SK HYNIX KS', name: 'SK hynix · KRX 000660' },
};
const SORTS = ['pct', 'chg', 'last', 'vol', 'mcap', 'sym'];
const sorts = () => (Object.values(state.mcap).some(Boolean) ? SORTS : SORTS.filter((k) => k !== 'mcap'));
const RANGES = ['1d', '5d', '1mo', '1y'];
const RANGE_LABEL = { '1d': '1D', '5d': '5D', '1mo': '1M', '1y': '1Y' };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

const state = {
  list: store.get('tt.list', DEFAULT_LIST),
  sel: null,
  sort: store.get('tt.sort', 'pct'),
  range: '1d',
  quotes: {},      // symbol → merged quote
  history: {},     // `${symbol}|${range}` → { at, bars, prevClose }
  mcap: {},        // symbol → market cap in USD (Finnhub profile2)
  key: null,       // Finnhub key: memory only, never persisted
  lastUpdate: null,
  errors: {},
};
state.sel = state.list[0];

const label = (s) => ALIAS[s]?.label || s;
const isUS = (s) => !s.includes('.') || /^[A-Z]+\.[A-Z]$/.test(s); // BRK.B yes, 000660.KS no

// ---- formatting --------------------------------------------------------------------
function money(v, cur = 'USD') {
  if (v == null || v === 0) return '—';
  const dp = cur === 'KRW' || cur === 'JPY' ? 0 : 2;
  return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
const signed = (v, cur) => (v == null ? '—' : (v > 0 ? '+' : '') + money(v, cur));
const pct = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(2) + '%');
const cls = (v) => (v > 0 ? 'u' : v < 0 ? 'd' : '');
function big(v) {
  if (!v) return '—';
  for (const [n, s] of [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']]) if (v >= n) return (v / n).toFixed(v >= n * 100 ? 0 : v >= n * 10 ? 1 : 2) + s;
  return String(v);
}
const etFmt = (opts) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', ...opts });
const tzFmt = (tz, opts) => new Intl.DateTimeFormat('en-US', { timeZone: tz, ...opts });

// ---- market clock (NYSE regular hours; holidays and early closes for 2026–27) ---------
const HOLIDAYS = new Set(['2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
  '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24']);
const EARLY = new Set(['2026-11-27', '2026-12-24', '2027-11-26']);
function market(now = new Date()) {
  const p = Object.fromEntries(etFmt({ year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short', hourCycle: 'h23' })
    .formatToParts(now).map((x) => [x.type, x.value]));
  const day = `${p.year}-${p.month}-${p.day}`, mins = +p.hour * 60 + +p.minute;
  const close = EARLY.has(day) ? 13 * 60 : 16 * 60;
  if (p.weekday === 'Sat' || p.weekday === 'Sun' || HOLIDAYS.has(day)) return { open: false, text: 'MARKET CLOSED' };
  if (mins < 9 * 60 + 30) return { open: false, text: mins >= 4 * 60 ? 'PRE-MARKET' : 'MARKET CLOSED' };
  if (mins >= close) return { open: false, text: mins < 20 * 60 ? 'AFTER HOURS' : 'MARKET CLOSED' };
  return { open: true, text: 'MARKET OPEN' };
}
function tickClock() {
  $('clock').textContent = etFmt({ hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(new Date());
  const m = market();
  $('mkt').textContent = m.text;
  $('mkt').className = m.open ? 'u' : 'm';
}

// ---- data --------------------------------------------------------------------------
async function yahoo(symbols, range) {
  const res = await fetch(`/api/yahoo?range=${range}&symbols=${symbols.map(encodeURIComponent).join(',')}`);
  if (!res.ok && res.status !== 502) throw new Error(`Yahoo: HTTP ${res.status}`);
  return res.json();
}

async function finnhub(path, key) {
  const res = await fetch(`https://finnhub.io/api/v1/${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(key)}`);
  if (res.status === 401 || res.status === 403) throw Object.assign(new Error('key rejected'), { auth: true });
  if (res.status === 429) throw new Error('Finnhub rate limit');
  if (!res.ok) throw new Error(`Finnhub: HTTP ${res.status}`);
  return res.json();
}

async function refresh() {
  const symbols = [...new Set([...state.list, ...INDEXES])];
  let y;
  try {
    y = await yahoo(symbols, '1d');
  } catch (e) {
    $('src').innerHTML = `SOURCE: <b>offline</b> · ${esc(e.message)}`;
    return;
  }
  state.errors = y.errors || {};
  for (const [s, q] of Object.entries(y.quotes)) {
    state.quotes[s] = { ...q, source: 'yahoo' };
    state.history[`${s}|1d`] = { at: Date.now(), bars: q.bars, prevClose: q.prevClose };
  }

  if (state.key) {
    const us = symbols.filter(isUS);
    const results = await Promise.allSettled(us.map((s) => finnhub(`quote?symbol=${encodeURIComponent(s)}`, state.key)));
    results.forEach((r, i) => {
      const s = us[i], q = state.quotes[s];
      if (r.status === 'rejected') { if (r.reason?.auth) dropKey('Finnhub rejected the key; back to Yahoo.'); return; }
      const f = r.value;
      if (!f || !f.c) return; // Finnhub returns zeros for symbols it doesn't cover
      state.quotes[s] = { ...(q || { symbol: s, name: s, currency: 'USD', bars: [] }), price: f.c, change: f.d, changePct: f.dp, high: f.h, low: f.l, open: f.o, prevClose: f.pc, time: f.t, source: 'finnhub' };
    });
    const need = state.list.filter((s) => isUS(s) && state.mcap[s] === undefined);
    await Promise.allSettled(need.map(async (s) => {
      const p = await finnhub(`stock/profile2?symbol=${encodeURIComponent(s)}`, state.key);
      state.mcap[s] = p?.marketCapitalization ? p.marketCapitalization * 1e6 : null;
    }));
  }
  state.lastUpdate = new Date();
  render();
  if (state.range !== '1d') loadChart();
}

function dropKey(msg) {
  state.key = null;
  for (const q of Object.values(state.quotes)) q.source = 'yahoo';
  flash(msg);
}

// ---- rendering ---------------------------------------------------------------------
let prevPrice = {};
function sortedList() {
  const q = state.quotes, k = state.sort;
  const val = (s) => ({ pct: q[s]?.changePct, chg: q[s]?.change, last: q[s]?.price, vol: q[s]?.volume, mcap: state.mcap[s], sym: label(s) })[k];
  return [...state.list].sort((a, b) => {
    if (k === 'sym') return label(a).localeCompare(label(b));
    return (val(b) ?? -Infinity) - (val(a) ?? -Infinity);
  });
}

function sparkline(bars, prev, up) {
  if (!bars?.length) return '';
  const ys = bars.map((b) => b[1]), lo = Math.min(...ys, prev ?? Infinity), hi = Math.max(...ys, prev ?? -Infinity);
  const x = (i) => (i / Math.max(1, bars.length - 1)) * 84, y = (v) => 21 - ((v - lo) / (hi - lo || 1)) * 20;
  const pts = ys.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const base = prev != null ? `<line x1="0" x2="84" y1="${y(prev).toFixed(1)}" y2="${y(prev).toFixed(1)}" stroke="#333" stroke-dasharray="2 2"/>` : '';
  return `<svg class="spark" viewBox="0 0 84 22" aria-hidden="true">${base}<polyline fill="none" stroke="${up ? '#4af626' : '#ff3b30'}" stroke-width="1.2" points="${pts}"/></svg>`;
}

function render() {
  const q = state.quotes;
  // rows
  $('rows').innerHTML = sortedList().map((s) => {
    const r = q[s];
    if (!r) {
      const err = state.errors[s];
      return `<tr class="err${s === state.sel ? ' sel' : ''}" data-s="${esc(s)}"><td><span class="sym">${esc(label(s))}</span><span class="nm">${err ? esc(err) : 'loading…'}</span></td><td colspan="6"></td></tr>`;
    }
    const was = prevPrice[s], f = was == null || r.price === was ? '' : r.price > was ? 'fu' : 'fd';
    const name = ALIAS[s]?.name || r.name;
    return `<tr data-s="${esc(s)}" class="${s === state.sel ? 'sel' : ''}">
      <td><span class="sym">${esc(label(s))}</span><span class="nm">${esc(name)}</span></td>
      <td class="${f}">${money(r.price, r.currency)}</td>
      <td class="hide-xs ${cls(r.change)}">${signed(r.change, r.currency)}</td>
      <td class="${cls(r.changePct)}">${pct(r.changePct)}</td>
      <td class="hide-sm">${big(r.volume)}</td>
      <td class="hide-sm cap">${big(state.mcap[s])}</td>
      <td>${sparkline(r.bars, r.prevClose, r.change >= 0)}</td></tr>`;
  }).join('');
  prevPrice = Object.fromEntries(Object.entries(q).map(([s, r]) => [s, r.price]));

  $('lhint').textContent = `${state.list.length} SECURITIES · SORT: ${state.sort.toUpperCase()} ▼`;
  document.body.classList.toggle('nocap', !Object.values(state.mcap).some(Boolean)); // market caps come from Finnhub
  document.querySelectorAll('th button').forEach((b) => b.classList.toggle('on', b.dataset.sort === state.sort));

  // index strip
  for (const s of INDEXES) {
    const r = q[s];
    $(s.toLowerCase()).innerHTML = r ? `${money(r.price)} <small class="${cls(r.changePct)}">${pct(r.changePct)}</small>` : '—';
  }
  const have = state.list.filter((s) => q[s]);
  $('adv').innerHTML = have.length ? `${have.filter((s) => q[s].change > 0).length} <small class="m">of ${have.length}</small>` : '—';
  $('upd').textContent = state.lastUpdate ? etFmt({ hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(state.lastUpdate) + ' ET' : '—';

  // tape (doubled for a seamless loop)
  const tape = state.list.filter((s) => q[s]).map((s) => {
    const r = q[s];
    return `<span><b>${esc(label(s))}</b> ${money(r.price, r.currency)} <em class="${cls(r.changePct)}">${r.changePct >= 0 ? '▲' : '▼'}${Math.abs(r.changePct ?? 0).toFixed(2)}%</em></span>`;
  }).join('');
  $('tape').innerHTML = tape + tape;

  // source line
  const fin = Object.values(q).some((r) => r.source === 'finnhub');
  $('src').innerHTML = state.key
    ? `SOURCE: <b>FINNHUB</b> (your key, this tab only)${fin ? '' : ' · waiting'} · charts, volume${state.list.some((s) => !isUS(s)) ? ' &amp; non-US' : ''}: Yahoo Finance`
    : `SOURCE: <b>YAHOO FINANCE</b> (unofficial) · <button id="src-key" style="color:var(--amber);text-decoration:underline">use your Finnhub key</button>`;
  $('src-key')?.addEventListener('click', openKey);

  renderChartHeader();
  if (state.range === '1d') drawChart();
}

function renderChartHeader() {
  const s = state.sel, r = state.quotes[s];
  $('c-sym').textContent = label(s || '—');
  if (!r) { $('c-px').textContent = ''; $('c-chg').textContent = ''; $('c-name').textContent = state.errors[s] || ''; $('stats').innerHTML = ''; return; }
  $('c-px').textContent = money(r.price, r.currency);
  $('c-chg').className = cls(r.change);
  $('c-chg').textContent = `${signed(r.change, r.currency)} (${pct(r.changePct)})`;
  $('c-name').textContent = `${(ALIAS[s]?.name || r.name).toUpperCase()} · ${r.exchange} · ${r.currency}`;
  const st = [['OPEN', money(r.open, r.currency)], ['HIGH', money(r.high, r.currency)], ['LOW', money(r.low, r.currency)], ['PREV', money(r.prevClose, r.currency)], ['VOL', big(r.volume)], ...(state.mcap[s] ? [['MCAP', big(state.mcap[s])]] : [])];
  $('stats').innerHTML = st.map(([k, v]) => `<div><span>${k}</span>${v}</div>`).join('');
}

// ---- chart -------------------------------------------------------------------------
const W = 560, H = 260, PAD = { l: 4, r: 62, t: 10, b: 22 };
// Axis prices: compact for big numbers (won-priced stocks) so labels fit the margin.
const axis = (v, cur) => (Math.abs(v) >= 1e5 ? big(v) : money(v, cur));
let plotted = null;

async function loadChart() {
  const s = state.sel, key = `${s}|${state.range}`, h = state.history[key];
  const ttl = state.range === '5d' ? 5 * 60e3 : 60 * 60e3;
  if (state.range !== '1d' && (!h || Date.now() - h.at > ttl)) {
    drawChart('loading…');
    try {
      const y = await yahoo([s], state.range);
      const q = y.quotes[s];
      if (q) state.history[key] = { at: Date.now(), bars: q.bars, prevClose: null };
    } catch {}
  }
  if (s === state.sel) drawChart();
}

function drawChart(message) {
  const s = state.sel, h = state.history[`${s}|${state.range}`], r = state.quotes[s];
  const svg = $('svg');
  plotted = null;
  if (message || !h?.bars?.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" fill="#8a8174" font-size="12" text-anchor="middle">${esc(message || (r ? 'no chart data' : 'loading…'))}</text>`;
    return;
  }
  const bars = h.bars, cur = r?.currency || 'USD', tz = r?.timezone || 'America/New_York';
  const prev = state.range === '1d' ? h.prevClose : null;
  const ys = bars.map((b) => b[1]);
  let lo = Math.min(...ys, prev ?? Infinity), hi = Math.max(...ys, prev ?? -Infinity);
  const padY = (hi - lo) * 0.08 || 1; lo -= padY; hi += padY;
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const x = (i) => PAD.l + (i / Math.max(1, bars.length - 1)) * iw;
  const y = (v) => PAD.t + (1 - (v - lo) / (hi - lo)) * ih;
  const up = ys[ys.length - 1] >= (prev ?? ys[0]);
  const color = up ? '#4af626' : '#ff3b30';

  let g = '';
  for (let i = 0; i <= 4; i++) {
    const v = lo + ((hi - lo) * i) / 4, yy = y(v).toFixed(1);
    g += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${yy}" y2="${yy}" stroke="#1c1c1c"/><text x="${W - PAD.r + 6}" y="${(+yy + 4).toFixed(1)}" fill="#8a8174">${axis(v, cur)}</text>`;
  }
  // x labels: about five, as times (1D/5D) or dates
  const fmt = state.range === '1d' ? tzFmt(tz, { hour: 'numeric', minute: '2-digit' })
    : state.range === '5d' ? tzFmt(tz, { weekday: 'short' })
    : tzFmt(tz, { month: 'short', day: 'numeric' });
  const step = Math.max(1, Math.floor(bars.length / 5));
  let lastLbl = '';
  for (let i = 0; i < bars.length; i += step) {
    const t = fmt.format(new Date(bars[i][0] * 1000));
    if (t === lastLbl) continue; lastLbl = t;
    g += `<text x="${x(i).toFixed(1)}" y="${H - 6}" fill="#8a8174" text-anchor="${i === 0 ? 'start' : 'middle'}">${t}</text>`;
  }
  if (prev != null) g += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y(prev).toFixed(1)}" y2="${y(prev).toFixed(1)}" stroke="#5b544a" stroke-dasharray="3 3"/>`;
  const pts = ys.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = `${PAD.l},${(PAD.t + ih).toFixed(1)} ${pts} ${x(ys.length - 1).toFixed(1)},${(PAD.t + ih).toFixed(1)}`;
  g += `<defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".18"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
  g += `<polygon points="${area}" fill="url(#fill)"/><polyline fill="none" stroke="${color}" stroke-width="1.6" points="${pts}"/>`;
  g += `<line id="xh" y1="${PAD.t}" y2="${PAD.t + ih}" stroke="#8a560f" visibility="hidden"/><circle id="xd" r="3" fill="#ffa028" visibility="hidden"/>`;
  svg.innerHTML = g;
  plotted = { bars, x, y, tz };
}

function hover(e) {
  if (!plotted) return;
  const rect = $('svg').getBoundingClientRect();
  const px = ((e.clientX - rect.left) / rect.width) * W;
  const { bars, x, y, tz } = plotted;
  const i = Math.max(0, Math.min(bars.length - 1, Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (bars.length - 1))));
  const [t, v] = bars[i], xx = x(i), yy = y(v);
  const xh = $('xh'), xd = $('xd'), tip = $('tip');
  xh.setAttribute('x1', xx); xh.setAttribute('x2', xx); xh.setAttribute('visibility', 'visible');
  xd.setAttribute('cx', xx); xd.setAttribute('cy', yy); xd.setAttribute('visibility', 'visible');
  const when = tzFmt(tz, state.range === '1d' || state.range === '5d' ? { weekday: 'short', hour: 'numeric', minute: '2-digit' } : { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(t * 1000));
  tip.textContent = `${when} · ${money(v, state.quotes[state.sel]?.currency)}`;
  tip.style.left = `${(xx / W) * 100}%`;
  tip.hidden = false;
}
function unhover() {
  $('tip').hidden = true;
  $('xh')?.setAttribute('visibility', 'hidden');
  $('xd')?.setAttribute('visibility', 'hidden');
}

// ---- actions -----------------------------------------------------------------------
function select(s) {
  state.sel = s;
  render();
  loadChart();
}
function setRange(r) {
  state.range = r;
  document.querySelectorAll('.rng button').forEach((b) => b.classList.toggle('on', b.dataset.range === r));
  loadChart();
}
function setSort(k) {
  state.sort = k; store.set('tt.sort', k); render();
}
function saveList() { store.set('tt.list', state.list); }

async function addTicker(s) {
  if (state.list.includes(s)) return select(s);
  if (state.list.length >= MAX_LIST) return flash(`Watchlist is full (${MAX_LIST}). DEL a ticker first.`);
  flash(`Looking up ${s}…`);
  try {
    const y = await yahoo([s], '1d');
    if (!y.quotes[s]) return flash(`${s}: ${y.errors?.[s] || 'not found'}`);
    state.list.push(s); saveList();
    state.quotes[s] = { ...y.quotes[s], source: 'yahoo' };
    state.history[`${s}|1d`] = { at: Date.now(), bars: y.quotes[s].bars, prevClose: y.quotes[s].prevClose };
    flash(`Added ${label(s)}.`);
    select(s);
    if (state.key) refresh();
  } catch (e) { flash(e.message); }
}
function removeTicker(s) {
  if (!state.list.includes(s)) return flash(`${s} isn't on the watchlist.`);
  state.list = state.list.filter((x) => x !== s); saveList();
  if (state.sel === s) state.sel = state.list[0];
  flash(`Removed ${label(s)}.`);
  render(); loadChart();
}

let flashTimer;
function flash(msg) {
  const c = $('cmd');
  c.value = ''; c.placeholder = msg;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => { c.placeholder = 'Ticker <GO> · HELP'; }, 4000);
}

// Aliases typed at the command line → real symbols.
const TYPED = { HYNIX: 'SKHY', 'SK HYNIX': 'SKHY', SKHYNIX: 'SKHY', SPACEX: 'SPCX', TSMC: 'TSM', '000660': '000660.KS' };
function run(raw) {
  let t = raw.toUpperCase().replace(/<?\s*GO\s*>?$/, '').trim();
  if (!t) return;
  const [cmd, ...rest] = t.split(/\s+/), arg = TYPED[rest.join(' ')] || rest.join('');
  if (cmd === 'HELP' || t === '?') return $('dlg-help').showModal();
  if (cmd === 'KEY') return openKey();
  if (cmd === 'RESET') { state.list = [...DEFAULT_LIST]; saveList(); state.sel = state.list[0]; flash('Watchlist reset.'); return refresh(); }
  if (cmd === 'REFRESH') return refresh();
  if ((cmd === 'DEL' || cmd === 'RM' || cmd === 'REMOVE') && arg) return removeTicker(arg);
  if (cmd === 'SORT' && SORTS.includes(arg.toLowerCase())) return setSort(arg.toLowerCase());
  const r = { '1D': '1d', '5D': '5d', '1M': '1mo', '1Y': '1y' }[t];
  if (r) return setRange(r);
  const sym = TYPED[t] || t.replace(/\s+/g, '');
  if (!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(sym)) return flash(`Unknown command: ${t}. Type HELP.`);
  addTicker(sym);
}

// ---- Finnhub key dialog (the key lives only in state.key) ---------------------------
function openKey() {
  $('key-in').value = '';
  $('key-msg').textContent = state.key ? 'A key is in use for this tab.' : '';
  $('dlg-key').showModal();
  $('key-in').focus();
}
$('key-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const k = $('key-in').value.trim();
  if (!k) return;
  $('key-msg').textContent = 'Checking key…';
  try {
    const q = await finnhub('quote?symbol=AAPL', k);
    if (!q?.c) throw new Error('no data for AAPL');
    state.key = k;
    $('key-in').value = '';
    $('dlg-key').close();
    flash('Finnhub key in use for this tab.');
    refresh();
  } catch (err) {
    $('key-msg').innerHTML = `<span class="d">${err.auth ? 'Finnhub rejected that key.' : esc(err.message)}</span>`;
  }
});
$('key-cancel').addEventListener('click', () => $('dlg-key').close());
$('key-clear').addEventListener('click', () => { state.key = null; $('dlg-key').close(); flash('Using Yahoo Finance.'); refresh(); });
$('help-close').addEventListener('click', () => $('dlg-help').close());

// ---- wiring ------------------------------------------------------------------------
$('cmd').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); run(e.target.value); e.target.value = ''; }
  if (e.key === 'Escape') e.target.blur();
});
$('rows').addEventListener('click', (e) => { const tr = e.target.closest('tr[data-s]'); if (tr) select(tr.dataset.s); });
document.querySelectorAll('th button').forEach((b) => b.addEventListener('click', () => setSort(b.dataset.sort)));
document.querySelectorAll('.rng button').forEach((b) => b.addEventListener('click', () => setRange(b.dataset.range)));
const F = {
  help: () => $('dlg-help').showModal(),
  sort: () => { const l = sorts(); setSort(l[(l.indexOf(state.sort) + 1) % l.length]); },
  range: () => setRange(RANGES[(RANGES.indexOf(state.range) + 1) % RANGES.length]),
  add: () => { $('cmd').focus(); flash('Type a ticker and press Enter'); },
  refresh: () => refresh(),
  key: openKey,
};
document.querySelectorAll('.fkeys button').forEach((b) => b.addEventListener('click', () => F[b.dataset.f]()));
document.addEventListener('keydown', (e) => {
  if (document.querySelector('dialog[open]')) return;
  const fk = { F1: 'help', F2: 'sort', F3: 'range', F4: 'add', F5: 'refresh', F6: 'key' }[e.key];
  if (fk) { e.preventDefault(); return F[fk](); }
  if (e.target === $('cmd') || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === '/') { e.preventDefault(); return $('cmd').focus(); }
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const l = sortedList(), i = l.indexOf(state.sel);
    select(l[(i + (e.key === 'ArrowDown' ? 1 : -1) + l.length) % l.length]);
  }
});
$('plot').addEventListener('pointermove', hover);
$('plot').addEventListener('pointerleave', unhover);

// Refresh every minute while US markets are open (or a non-US listing is on the list), every 5 otherwise.
function schedule() {
  const open = market().open || state.list.some((s) => !isUS(s));
  setTimeout(async () => { if (!document.hidden) await refresh(); schedule(); }, open ? 60e3 : 300e3);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && Date.now() - (state.lastUpdate || 0) > 60e3) refresh(); });

tickClock(); setInterval(tickClock, 1000);
render();
refresh().then(() => loadChart());
schedule();
