#!/usr/bin/env node
// Favicon set + 1200×630 share image for Tech Terminal.
//
//   npm i --no-save puppeteer-core@23.11.1
//   npm run dev &                  # the share image uses the running app's fonts and /api/yahoo
//   node scripts/brand/make.mjs [http://localhost:3000/]
//
// Needs Google Chrome at CHROME_PATH (default: the macOS app path).
// Outputs (committed): public/icon.svg, public/favicon.ico, public/favicon-32.png,
// public/apple-touch-icon.png, public/og.png

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const pub = path.join(root, 'public');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const url = process.argv[2] || 'http://localhost:3000/';

// An amber terminal tile with a prompt and a rising line.
const ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#000"/>
  <rect x="3" y="3" width="58" height="58" rx="10" fill="none" stroke="#ffa028" stroke-width="3"/>
  <path d="M14 22 L24 30 L14 38" fill="none" stroke="#ffa028" stroke-width="5" stroke-linecap="square"/>
  <path d="M28 46 L36 38 L42 42 L52 28" fill="none" stroke="#4af626" stroke-width="4.5" stroke-linejoin="round" stroke-linecap="round"/>
</svg>`;

const ALIAS = { SKHY: 'SK hynix (ADR)', TSM: 'TSMC (ADR)', NVDA: 'NVIDIA', GOOGL: 'Alphabet', AAPL: 'Apple', MSFT: 'Microsoft' };

function spark(bars, prev, w, h) {
  const ys = bars.map((b) => b[1]).concat(prev);
  const lo = Math.min(...ys), hi = Math.max(...ys), k = (v) => h - 2 - ((v - lo) / (hi - lo || 1)) * (h - 4);
  const pts = bars.map((b, i) => `${((i / (bars.length - 1)) * w).toFixed(1)},${k(b[1]).toFixed(1)}`).join(' ');
  const up = bars.at(-1)[1] >= prev;
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><line x1="0" x2="${w}" y1="${k(prev)}" y2="${k(prev)}" stroke="#555" stroke-dasharray="2 3"/><polyline points="${pts}" fill="none" stroke="${up ? '#4af626' : '#ff3b30'}" stroke-width="1.6"/></svg>`;
}

function poster(rows, base) {
  const fmt = (v) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const tr = rows.map((q) => {
    const c = q.changePct >= 0 ? 'u' : 'd';
    return `<tr><td><b>${q.symbol}</b><i>${ALIAS[q.symbol] || q.name}</i></td><td>${fmt(q.price)}</td><td class="${c}">${q.changePct >= 0 ? '+' : ''}${fmt(q.changePct)}%</td><td>${spark(q.bars, q.prevClose, 120, 30)}</td></tr>`;
  }).join('');
  const tape = rows.map((q) => `<span><b>${q.symbol}</b> ${fmt(q.price)} <em class="${q.changePct >= 0 ? 'u' : 'd'}">${q.changePct >= 0 ? '▲' : '▼'}${fmt(Math.abs(q.changePct))}%</em></span>`).join('');
  return `<!doctype html><base href="${base}"><style>
  @font-face{font-family:P;font-weight:400;src:url(/fonts/ibm-plex-mono-400.woff2)}
  @font-face{font-family:P;font-weight:600;src:url(/fonts/ibm-plex-mono-600.woff2)}
  *{margin:0;box-sizing:border-box}
  body{width:1200px;height:630px;overflow:hidden;background:#000;color:#e8e2d6;font:16px/1.35 P,monospace;position:relative}
  body:before{content:"";position:absolute;inset:0;background:radial-gradient(ellipse at 20% 40%,#2a1a05 0,transparent 60%)}
  .u{color:#4af626}.d{color:#ff3b30}
  .tape{position:absolute;top:0;left:0;right:0;height:44px;border-bottom:1px solid #262626;background:#111;display:flex;align-items:center;white-space:nowrap;overflow:hidden;color:#8a8174;font-size:17px}
  .tape .tag{background:#ffa028;color:#000;font-weight:600;height:100%;display:flex;align-items:center;padding:0 16px;margin-right:22px;letter-spacing:.04em}
  .tape span{margin-right:30px}.tape b{color:#e8e2d6;font-weight:600}.tape em{font-style:normal}
  .left{position:absolute;left:64px;top:104px;width:520px}
  .k{color:#ffa028;font-size:16px;letter-spacing:.14em}
  h1{font-weight:600;font-size:84px;line-height:.98;color:#ffa028;margin:18px 0 26px;letter-spacing:-.01em;text-shadow:0 0 30px #ffa02855}
  h1 span{display:block}
  .tl{font-size:27px;line-height:1.3;color:#e8e2d6}
  .sub{margin-top:16px;color:#8a8174;font-size:17px;line-height:1.5}
  .url{position:absolute;left:64px;bottom:52px;color:#ffa028;font-size:22px;font-weight:600;border:1.5px solid #8a560f;padding:8px 16px}
  .url:before{content:"> ";color:#8a560f}
  .panel{position:absolute;right:56px;top:92px;width:540px;border:1px solid #333;background:#0b0b0b;box-shadow:0 0 0 1px #000,0 20px 60px #000}
  .ph{display:flex;justify-content:space-between;background:#111;color:#ffa028;font-weight:600;padding:9px 16px;border-bottom:1px solid #262626;font-size:15px}
  .ph em{font-style:normal;color:#8a8174;font-weight:400}
  table{width:100%;border-collapse:collapse}
  td{padding:8px 16px;border-bottom:1px solid #1a1a1a;text-align:right;font-size:19px;white-space:nowrap}
  tr:last-child td{border-bottom:0}
  td:first-child{text-align:left}td b{color:#ffa028;font-weight:600;display:block}td i{font-style:normal;color:#8a8174;font-size:13px}
  td svg{display:block;margin-left:auto}
  .keys{display:flex;gap:6px;padding:10px 12px;border-top:1px solid #262626;background:#111}
  .keys span{background:#1e1e1e;border:1px solid #333;padding:4px 9px;font-size:13px}.keys b{color:#ffa028;margin-right:6px}
  </style>
  <div class="tape"><div class="tag">TECH TERMINAL</div>${tape}${tape}</div>
  <div class="left">
    <div class="k">BIG TECH · LIVE BOARD</div>
    <h1><span>TECH</span><span>TERMINAL</span></h1>
    <p class="tl">Big tech stocks on a<br>trading-terminal board.</p>
    <p class="sub">Live quotes · sparklines · 1D–1Y charts<br>Bring your own Finnhub key, never stored</p>
  </div>
  <div class="url">techterminal.vercel.app</div>
  <div class="panel"><div class="ph">WATCHLIST <em>1D</em></div><table>${tr}</table>
  <div class="keys"><span><b>F1</b>HELP</span><span><b>F2</b>SORT</span><span><b>F3</b>RANGE</span><span><b>F6</b>KEY</span></div></div>`;
}

function ico(pngs) {
  const header = Buffer.alloc(6 + 16 * pngs.length);
  header.writeUInt16LE(0, 0); header.writeUInt16LE(1, 2); header.writeUInt16LE(pngs.length, 4);
  let offset = header.length;
  pngs.forEach(({ size, buf }, i) => {
    const o = 6 + 16 * i;
    header.writeUInt8(size, o); header.writeUInt8(size, o + 1);
    header.writeUInt16LE(1, o + 4); header.writeUInt16LE(32, o + 6);
    header.writeUInt32LE(buf.length, o + 8); header.writeUInt32LE(offset, o + 12);
    offset += buf.length;
  });
  return Buffer.concat([header, ...pngs.map((p) => p.buf)]);
}

const browser = await puppeteer.launch({ executablePath: chrome, headless: true });
try {
  fs.writeFileSync(path.join(pub, 'icon.svg'), ICON);
  const page = await browser.newPage();
  const png = async (size) => {
    await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 });
    await page.setContent(`<style>*{margin:0}svg{display:block;width:${size}px;height:${size}px}</style>${ICON}`);
    return page.screenshot({ omitBackground: size !== 180 }); // apple-touch must be opaque
  };
  const [p16, p32, p48, p180] = [await png(16), await png(32), await png(48), await png(180)];
  fs.writeFileSync(path.join(pub, 'favicon-32.png'), p32);
  fs.writeFileSync(path.join(pub, 'apple-touch-icon.png'), p180);
  fs.writeFileSync(path.join(pub, 'favicon.ico'), ico([{ size: 16, buf: p16 }, { size: 32, buf: p32 }, { size: 48, buf: p48 }]));
  console.log('wrote public/icon.svg, favicon-32.png, apple-touch-icon.png, favicon.ico');

  // Share image: a poster in the app's own look (title, tagline, URL) beside a
  // watchlist drawn from the running app's /api/yahoo at the time of the run.
  const syms = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'SKHY', 'TSM'];
  const res = await fetch(new URL(`/api/yahoo?symbols=${syms.join(',')}&range=1d`, url));
  const { quotes } = await res.json();
  await page.setViewport({ width: 1200, height: 630, deviceScaleFactor: 1 });
  await page.setContent(poster(syms.map((s) => quotes[s]).filter(Boolean), url), { waitUntil: 'networkidle0' });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(pub, 'og.png') });
  console.log('wrote public/og.png');
} finally {
  await browser.close();
}
