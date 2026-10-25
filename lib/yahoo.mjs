// Quotes and price bars from Yahoo Finance's chart endpoint, for visitors who
// haven't added a Finnhub key (and for every chart: Finnhub's free plan has none).
// Yahoo's endpoint is unofficial and may change or rate-limit without notice, so
// responses are cached at Vercel's edge and every failure is reported per symbol.

const RANGES = {
  '1d': { interval: '5m', ttl: 60 },
  '5d': { interval: '30m', ttl: 300 },
  '1mo': { interval: '1d', ttl: 3600 },
  '1y': { interval: '1d', ttl: 3600 },
};
// US tickers (AAPL, BRK-B) and Yahoo's exchange suffixes (000660.KS for SK hynix on KRX).
const SYMBOL = /^[A-Z0-9][A-Z0-9.\-]{0,11}$/;
const MAX_SYMBOLS = 30;

async function chart(symbol, range) {
  const { interval } = RANGES[range];
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}&includePrePost=false`;
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; tech-terminal)' },
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(res.status === 404 ? 'unknown symbol' : `Yahoo ${res.status}`);
  const r = (await res.json())?.chart?.result?.[0];
  if (!r?.meta?.regularMarketPrice) throw new Error('no data');

  const m = r.meta;
  const q = r.indicators?.quote?.[0] ?? {};
  const bars = [];
  (r.timestamp ?? []).forEach((t, i) => {
    if (q.close?.[i] != null) bars.push([t, round(q.close[i])]);
  });
  // chartPreviousClose is the close before the first bar, which is yesterday's
  // close only on the 1-day range.
  const prev = m.previousClose ?? m.chartPreviousClose;
  const price = m.regularMarketPrice;
  return {
    symbol,
    name: m.longName || m.shortName || symbol,
    exchange: m.fullExchangeName || m.exchangeName || '',
    currency: m.currency || 'USD',
    timezone: m.exchangeTimezoneName || 'America/New_York',
    price: round(price),
    prevClose: round(prev),
    change: round(price - prev),
    changePct: round(((price - prev) / prev) * 100),
    open: round(range === '1d' ? q.open?.find((v) => v != null) : null),
    high: round(m.regularMarketDayHigh),
    low: round(m.regularMarketDayLow),
    // Some exchanges (e.g. KRX) report 0 in the summary; fall back to the day's bars.
    volume: m.regularMarketVolume || (range === '1d' ? (q.volume ?? []).reduce((a, v) => a + (v || 0), 0) || null : null),
    time: m.regularMarketTime ?? null,
    bars,
  };
}

function round(v) {
  return v == null || Number.isNaN(v) ? null : Math.round(v * 100) / 100;
}

/** Handles ?symbols=AAPL,MSFT&range=1d and returns { status, headers, body }. */
export async function handle(params) {
  const range = RANGES[params.get('range')] ? params.get('range') : '1d';
  const symbols = [...new Set((params.get('symbols') || '').toUpperCase().split(',').map((s) => s.trim()).filter(Boolean))];
  if (!symbols.length || symbols.length > MAX_SYMBOLS || !symbols.every((s) => SYMBOL.test(s))) {
    return { status: 400, headers: {}, body: { error: `symbols: 1–${MAX_SYMBOLS} tickers like AAPL,MSFT` } };
  }
  const results = await Promise.allSettled(symbols.map((s) => chart(s, range)));
  const quotes = {}, errors = {};
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') quotes[symbols[i]] = r.value;
    else errors[symbols[i]] = r.reason?.message || 'failed';
  });
  const ttl = RANGES[range].ttl;
  return {
    status: Object.keys(quotes).length ? 200 : 502,
    headers: { 'Cache-Control': `public, s-maxage=${ttl}, stale-while-revalidate=${ttl * 5}` },
    body: { source: 'yahoo', range, fetchedAt: Date.now(), quotes, errors },
  };
}
