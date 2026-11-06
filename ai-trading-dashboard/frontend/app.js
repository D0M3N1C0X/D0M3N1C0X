/* AI Momentum Desk - interfaccia. Nessuna build: JavaScript semplice. */
"use strict";

const LWC = window.LightweightCharts;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const S = {
  settings: null,
  meta: null,
  scan: null,
  journal: null,
  selected: null,
  tf: "5Min",
  sessions: 2,
  sort: { key: "score", dir: "abs" },
  prevSignals: null,
  prevPrices: new Map(),
  alerts: [],
  marketAt: 0,
  newsAll: false,
  lastNewsAt: 0,
  chartData: null,
  timer: null,
};

/* ---------------- utilità ---------------- */
const store = {
  get(k, d) { try { const v = localStorage.getItem("aimd." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("aimd." + k, JSON.stringify(v)); } catch { /* storage non disponibile */ } },
};

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  let data = {};
  try { data = await res.json(); } catch { /* risposta vuota */ }
  if (!res.ok) throw new Error(data.detail || `Errore ${res.status}`);
  return data;
}
const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body) });
const put = (p, body) => api(p, { method: "PUT", body: JSON.stringify(body) });

const nf2 = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf0 = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const price = (x) => (x == null ? "—" : nf2.format(x));
const pct = (x) => (x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + nf2.format(Math.abs(x)) + "%");
const eur = (x) => (x == null ? "—" : (x < 0 ? "−" : "") + nf2.format(Math.abs(x)) + " €");
const signed = (x) => (x == null ? "" : x > 0 ? "up" : x < 0 ? "down" : "");
const vol = (x) => (x >= 1e6 ? nf1.format(x / 1e6) + " M" : x >= 1e3 ? nf0.format(x / 1e3) + " K" : nf0.format(x || 0));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const timeFmt = (tz, withSec = false) => new Intl.DateTimeFormat("it-IT", { timeZone: tz, hour: "2-digit", minute: "2-digit", ...(withSec ? { second: "2-digit" } : {}) });
const romeTime = timeFmt("Europe/Rome", true);
const romeHM = timeFmt("Europe/Rome");
const nyHM = timeFmt("America/New_York");
const romeDayTime = new Intl.DateTimeFormat("it-IT", { timeZone: "Europe/Rome", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const utcDayTime = new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function signalInfo(code) {
  return (S.meta && S.meta.signals[code]) || { label: code, tone: "info", help: "" };
}

function toast(text, tone = "info", onClick) {
  const el = document.createElement("div");
  el.className = `toast ${tone}`;
  el.innerHTML = text;
  el.onclick = () => { el.remove(); if (onClick) onClick(); };
  $("#toasts").prepend(el);
  setTimeout(() => el.remove(), 9000);
  while ($("#toasts").children.length > 4) $("#toasts").lastChild.remove();
}

/* App desktop (pywebview): funzioni native esposte come window.pywebview.api */
const desktop = () => !!(window.pywebview && window.pywebview.api);
window.addEventListener("pywebviewready", async () => {
  document.documentElement.classList.add("desktop");
  try {
    const info = await window.pywebview.api.info();
    $("#desktop-data-path").textContent = info.data_dir;
    $("#desktop-data").hidden = false;
  } catch { /* ponte non disponibile */ }
});

let audioCtx = null;
document.addEventListener("click", () => { if (!audioCtx && window.AudioContext) audioCtx = new AudioContext(); }, { once: true });
function beep(tone) {
  if (!audioCtx || !S.settings?.alerts.sound) return;
  const o = audioCtx.createOscillator(), g = audioCtx.createGain();
  o.frequency.value = tone === "bear" ? 440 : 880;
  g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.15, audioCtx.currentTime + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.35);
  o.connect(g).connect(audioCtx.destination);
  o.start(); o.stop(audioCtx.currentTime + 0.4);
}

/* ---------------- tema ---------------- */
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  store.set("theme", t);
  if (chart) themeChart();
}
$("#theme-toggle").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

/* ---------------- schede ---------------- */
$$(".tab").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
function showView(v) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach((m) => m.classList.toggle("active", m.id === "view-" + v));
  if (v === "journal") { loadJournal(); const f = $("#journal-form"); if (!f.symbol.value && S.selected) f.symbol.value = S.selected; }
  if (v === "settings") fillSettings();
  store.set("view", v);
}

/* ---------------- intestazione ---------------- */
function renderHeader() {
  const m = S.scan?.market;
  if (!m) return;
  const el = $("#market");
  el.dataset.status = m.status;
  $(".status-label", el).textContent = m.label;
  const p = S.scan.provider;
  const badge = $("#provider-badge");
  badge.textContent = p.label;
  badge.title = p.note || "";
  badge.classList.toggle("demo", p.name === "demo");
  $("#bench").innerHTML = (S.scan.benchmarks || [])
    .map((b) => `<span class="bench-item"><b>${esc(b.symbol)}</b><span>${price(b.last)}</span><span class="${signed(b.change_pct)}">${pct(b.change_pct)}</span></span>`)
    .join("");
  $("#updated").textContent = "Aggiornato alle " + romeTime.format(new Date());
}

function tickClock() {
  const m = S.scan?.market;
  if (!m) return;
  const elapsed = (Date.now() - S.marketAt) / 1000;
  const serverNow = new Date(Date.parse(m.now_ny) + elapsed * 1000);
  const simulated = Math.abs(Date.parse(m.now_ny) - S.marketAt) > 120000;
  $("#clocks").textContent = `Roma ${romeHM.format(serverNow)} · New York ${nyHM.format(serverNow)}${simulated ? " (orario simulato)" : ""}`;
  let s = Math.max(0, Math.round(m.seconds_to_next - elapsed));
  const h = Math.floor(s / 3600), mi = Math.floor((s % 3600) / 60), se = s % 60;
  const left = h > 23 ? `${Math.floor(h / 24)} g ${h % 24} h` : h ? `${h} h ${mi} min` : `${mi} min ${String(se).padStart(2, "0")} s`;
  $("#countdown").textContent = `${m.next_event} tra ${left} (${m.next_event_rome})`;
}
setInterval(tickClock, 1000);

function renderBanners() {
  const out = [];
  const p = S.scan?.provider;
  if (p?.name === "demo") {
    out.push(`<div class="banner warn">⚠ <span><b>Modalità demo:</b> prezzi, volumi e notizie sono simulati. Per i dati reali collega Alpaca in <a href="#" data-goto="settings">Impostazioni › Fonte dati</a>.</span></div>`);
  }
  for (const e of S.scan?.errors || []) out.push(`<div class="banner error">✕ <span>${esc(e)}</span></div>`);
  const d = S.journal?.daily;
  if (d?.locked) out.push(`<div class="banner lock">⛔ <span>Stop giornaliero: ${d.reasons.map(esc).join(" ")} Per oggi è meglio fermarsi.</span></div>`);
  $("#banners").innerHTML = out.join("");
  $$("[data-goto]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); showView(a.dataset.goto); }));
}

/* ---------------- scanner ---------------- */
function renderGroupFilter() {
  const sel = $("#group-filter");
  const cur = sel.value || store.get("group", "*");
  sel.innerHTML = `<option value="*">Tutti i gruppi</option>` + S.settings.watchlist.map((g) => `<option>${esc(g.name)}</option>`).join("");
  sel.value = [...sel.options].some((o) => o.value === cur) ? cur : "*";
}
$("#group-filter").onchange = (e) => { store.set("group", e.target.value); renderScanner(); };
$("#only-signals").onchange = (e) => { store.set("onlySignals", e.target.checked); renderScanner(); };

$$("#scanner th[data-sort]").forEach((th) => {
  th.onclick = () => {
    const k = th.dataset.sort;
    if (S.sort.key === k) S.sort.dir = S.sort.dir === "desc" ? "asc" : "desc";
    else S.sort = { key: k, dir: k === "symbol" ? "asc" : "desc" };
    if (k === "score" && S.sort.dir === "asc") S.sort.dir = "abs";
    renderScanner();
  };
});

function sortedRows() {
  const g = $("#group-filter").value;
  const only = $("#only-signals").checked;
  let rows = (S.scan?.rows || []).filter((r) => (g === "*" || r.group === g) && (!only || r.signals.some((s) => s !== "NEWS")));
  const { key, dir } = S.sort;
  const val = (r) => (key === "score" && dir === "abs" ? Math.abs(r.score ?? 0) : r[key]);
  rows = rows.slice().sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    const c = typeof x === "string" ? x.localeCompare(y) : x - y;
    return dir === "asc" ? c : -c;
  });
  return rows;
}

function chipsHTML(signals, max = 1) {
  const extra = signals.length - max;
  const all = signals.map((c) => signalInfo(c).label).join(", ");
  return signals
    .slice(0, max)
    .map((c) => {
      const i = signalInfo(c);
      const setup = c.startsWith("SETUP") ? " setup" : "";
      return `<span class="chip ${i.tone}${setup}" title="${esc(i.help)}">${esc(i.label)}</span>`;
    })
    .join("") + (extra > 0 ? `<span class="chip" title="${esc(all)}">+${extra}</span>` : "");
}

function renderScanner() {
  $$("#scanner th").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === S.sort.key);
    th.classList.toggle("asc", th.dataset.sort === S.sort.key && S.sort.dir === "asc");
  });
  const thr = S.settings.scanner.rvol_threshold;
  const rows = sortedRows();
  const html = rows.map((r) => {
    const prev = S.prevPrices.get(r.symbol);
    const flash = prev != null && r.last != null && prev !== r.last ? (r.last > prev ? "flash-up" : "flash-down") : "";
    const vw = r.vwap_dist_pct == null ? "—" : `<span class="${signed(r.vwap_dist_pct)}">${r.vwap_dist_pct >= 0 ? "▲" : "▼"} ${pct(r.vwap_dist_pct)}</span>`;
    return `<tr data-sym="${esc(r.symbol)}" class="${r.symbol === S.selected ? "active" : ""}">
      <td class="sym-cell"><b>${esc(r.symbol)}</b><span class="muted">${esc(r.group || "")}${r.error ? " · " + esc(r.error) : ""}</span></td>
      <td class="num ${flash}">${price(r.last)}</td>
      <td class="num ${signed(r.change_pct)}">${pct(r.change_pct)}</td>
      <td class="num ${signed(r.gap_pct)}">${pct(r.gap_pct)}</td>
      <td class="num ${r.rvol != null && r.rvol >= thr ? "rvol-hot" : ""}">${r.rvol == null ? "—" : nf2.format(r.rvol) + "×"}</td>
      <td class="num">${vw}</td>
      <td class="num opt ${signed(r.rel_strength)}">${pct(r.rel_strength)}</td>
      <td><div class="chips">${chipsHTML(r.signals)}</div></td>
    </tr>`;
  });
  $("#scanner tbody").innerHTML = html.join("") || `<tr><td colspan="8" class="muted">Nessun titolo con questi filtri.</td></tr>`;
  $$("#scanner tbody tr[data-sym]").forEach((tr) => (tr.onclick = () => select(tr.dataset.sym)));
}

function rowFor(sym) {
  return (S.scan?.rows || []).concat(S.scan?.benchmarks || []).find((r) => r.symbol === sym);
}

/* ---------------- avvisi ---------------- */
function pushAlert(sym, text, tone) {
  const t = romeTime.format(new Date());
  S.alerts.unshift({ t, sym, text, tone });
  S.alerts = S.alerts.slice(0, 80);
  renderAlertLog();
  toast(`<b>${esc(sym)}</b> · ${esc(text)}`, tone, () => select(sym));
  beep(tone);
  if (S.settings.alerts.browser_notifications) {
    if (desktop()) window.pywebview.api.notify(`${sym}: ${text}`, "AI Momentum Desk").catch(() => {});
    else if ("Notification" in window && Notification.permission === "granted") {
      try { new Notification(`${sym}: ${text}`, { body: "AI Momentum Desk", tag: sym + text }); } catch { /* ignorato */ }
    }
  }
}

function renderAlertLog() {
  const ul = $("#alert-log");
  if (!S.alerts.length) { ul.innerHTML = `<li class="muted">Qui compaiono i nuovi segnali (rotture, setup) e gli avvisi di prezzo.</li>`; return; }
  ul.innerHTML = S.alerts.map((a) => `<li data-sym="${esc(a.sym)}"><span class="t">${a.t}</span><b>${esc(a.sym)}</b><span class="${a.tone === "bull" ? "up" : a.tone === "bear" ? "down" : ""}">${esc(a.text)}</span></li>`).join("");
  $$("#alert-log li[data-sym]").forEach((li) => (li.onclick = () => select(li.dataset.sym)));
}
$("#clear-alerts").onclick = () => { S.alerts = []; renderAlertLog(); };

function detectAlerts() {
  const rows = S.scan.rows.concat(S.scan.benchmarks || []);
  const enabled = new Set(S.settings.alerts.signals);
  const first = S.prevSignals === null;
  const next = new Map();
  for (const r of rows) {
    const cur = new Set(r.signals);
    next.set(r.symbol, cur);
    if (first) continue;
    const prev = S.prevSignals.get(r.symbol) || new Set();
    for (const c of cur) {
      if (!prev.has(c) && enabled.has(c)) {
        const i = signalInfo(c);
        pushAlert(r.symbol, `${i.label} a ${price(r.last)}`, i.tone);
      }
    }
  }
  S.prevSignals = next;

  // avvisi di prezzo
  let changed = false;
  for (const a of S.settings.price_alerts) {
    if (!a.active) continue;
    const r = rows.find((x) => x.symbol === a.symbol);
    if (!r || r.last == null) continue;
    if ((a.op === "above" && r.last >= a.price) || (a.op === "below" && r.last <= a.price)) {
      a.active = false;
      changed = true;
      pushAlert(a.symbol, `${a.op === "above" ? "ha superato" : "è sceso sotto"} ${price(a.price)} (ora ${price(r.last)})`, a.op === "above" ? "bull" : "bear");
    }
  }
  if (changed) savePriceAlerts();
}

function renderPriceAlerts() {
  const list = S.settings.price_alerts;
  $("#price-alerts").innerHTML = list
    .map((a) => `<li class="${a.active ? "" : "done"}"><span><b>${esc(a.symbol)}</b> ${a.op === "above" ? "supera" : "sotto"} ${price(a.price)}</span><button data-id="${a.id}" title="Elimina" aria-label="Elimina avviso">✕</button></li>`)
    .join("");
  $$("#price-alerts button").forEach((b) => (b.onclick = () => {
    S.settings.price_alerts = S.settings.price_alerts.filter((a) => a.id !== b.dataset.id);
    savePriceAlerts();
  }));
}
async function savePriceAlerts() {
  try { S.settings = await put("/api/settings", { price_alerts: S.settings.price_alerts }); } catch (e) { toast(esc(e.message), "bear"); }
  renderPriceAlerts();
}
$("#price-alert-form").onsubmit = (e) => {
  e.preventDefault();
  const p = parseFloat($("#pa-price").value);
  if (!S.selected || !(p > 0)) return toast("Seleziona un titolo e inserisci un prezzo.", "info");
  S.settings.price_alerts.push({ symbol: S.selected, op: $("#pa-op").value, price: p, active: true });
  $("#pa-price").value = "";
  savePriceAlerts();
};

/* ---------------- grafico ---------------- */
let chart, candle, volume, vwapS, vwapPool = [], ema9S, ema20S, rsiS, macdS, sigS, histS, markers;
let levelLines = [];
let rsiLines = [];

function initChart() {
  const el = $("#chart");
  chart = LWC.createChart(el, {
    autoSize: true,
    layout: { attributionLogo: true },
    timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 6 },
    crosshair: { mode: LWC.CrosshairMode.Normal },
    localization: { locale: "it-IT", priceFormatter: (p) => nf2.format(p), timeFormatter: (t) => utcDayTime.format(new Date(t * 1000)) },
  });
  candle = chart.addSeries(LWC.CandlestickSeries, {});
  volume = chart.addSeries(LWC.HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
  const line = (title, w) => ({ title, lineWidth: w, priceLineVisible: false, crosshairMarkerVisible: false, lastValueVisible: true });
  // Un tratto di VWAP per sessione (il VWAP riparte ogni giorno): l'ultimo porta l'etichetta.
  vwapPool = Array.from({ length: 6 }, () => chart.addSeries(LWC.LineSeries, { ...line("", 2), lastValueVisible: false }));
  vwapS = vwapPool[vwapPool.length - 1];
  vwapS.applyOptions({ title: "VWAP", lastValueVisible: true });
  ema9S = chart.addSeries(LWC.LineSeries, line("EMA 9", 1));
  ema20S = chart.addSeries(LWC.LineSeries, line("EMA 20", 1));
  rsiS = chart.addSeries(LWC.LineSeries, { ...line("RSI 14", 1), crosshairMarkerVisible: true }, 1);
  histS = chart.addSeries(LWC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 2);
  macdS = chart.addSeries(LWC.LineSeries, line("MACD", 1), 2);
  sigS = chart.addSeries(LWC.LineSeries, line("Segnale", 1), 2);
  const panes = chart.panes();
  panes[0].setStretchFactor(5);
  panes[1].setStretchFactor(1.3);
  panes[2].setStretchFactor(1.3);
  markers = LWC.createSeriesMarkers(candle, []);
  chart.subscribeCrosshairMove(updateLegend);
  themeChart();
}

function themeChart() {
  const text = cssVar("--text-2"), border = cssVar("--border"), surf = cssVar("--surface-1");
  const up = cssVar("--up"), down = cssVar("--down");
  const grid = document.documentElement.dataset.theme === "dark" ? "rgba(255,255,255,0.045)" : "rgba(0,0,0,0.06)";
  chart.applyOptions({
    layout: { background: { type: "solid", color: surf }, textColor: text, fontSize: 11, panes: { separatorColor: border, separatorHoverColor: border } },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    rightPriceScale: { borderColor: border },
    timeScale: { borderColor: border },
  });
  candle.applyOptions({ upColor: up, downColor: down, borderUpColor: up, borderDownColor: down, wickUpColor: up, wickDownColor: down });
  vwapPool.forEach((sr) => sr.applyOptions({ color: cssVar("--series-vwap") }));
  ema9S.applyOptions({ color: cssVar("--series-ema9") });
  ema20S.applyOptions({ color: cssVar("--series-ema20") });
  rsiS.applyOptions({ color: cssVar("--series-ema9") });
  macdS.applyOptions({ color: cssVar("--series-ema9") });
  sigS.applyOptions({ color: cssVar("--series-vwap") });
  rsiLines.forEach((l) => rsiS.removePriceLine(l));
  rsiLines = [70, 30].map((p) => rsiS.createPriceLine({ price: p, color: cssVar("--muted"), lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, axisLabelVisible: true, title: "" }));
  if (S.chartData) setLevels(S.chartData.levels);
  updateLegend({});
}

function lastOf(arr) { return arr && arr.length ? arr[arr.length - 1] : null; }

function updateLegend(param) {
  const d = S.chartData;
  if (!d) { $("#chart-legend").innerHTML = ""; return; }
  let c, v, vw, e9, e20, t;
  if (param && param.time) {
    c = param.seriesData.get(candle);
    v = param.seriesData.get(volume)?.value;
    vw = vwapPool.map((sr) => param.seriesData.get(sr)?.value).find((x) => x != null);
    e9 = param.seriesData.get(ema9S)?.value;
    e20 = param.seriesData.get(ema20S)?.value;
    t = param.time;
  } else {
    c = lastOf(d.candles);
    v = lastOf(d.volume)?.value;
    vw = [...d.vwap].reverse().find((p) => p.value != null)?.value;
    e9 = lastOf(d.ema9)?.value;
    e20 = lastOf(d.ema20)?.value;
    t = c?.time;
  }
  if (!c) { $("#chart-legend").innerHTML = ""; return; }
  const cls = c.close >= c.open ? "up" : "down";
  const sw = (varName) => `<span class="sw" style="background:${cssVar(varName)}"></span>`;
  $("#chart-legend").innerHTML =
    `<span>${t ? utcDayTime.format(new Date(t * 1000)) : ""}</span>` +
    `<span>A <b class="${cls}">${price(c.open)}</b></span><span>Max <b class="${cls}">${price(c.high)}</b></span>` +
    `<span>Min <b class="${cls}">${price(c.low)}</b></span><span>C <b class="${cls}">${price(c.close)}</b></span>` +
    `<span>Vol ${vol(v)}</span>` +
    `<span>${sw("--series-vwap")}VWAP ${price(vw)}</span><span>${sw("--series-ema9")}EMA 9 ${price(e9)}</span><span>${sw("--series-ema20")}EMA 20 ${price(e20)}</span>`;
}

const LEVELS = [
  ["orh", "ORH", "--info"], ["orl", "ORL", "--info"],
  ["pmh", "PMH", "--warn"], ["pml", "PML", "--warn"],
  ["pdh", "PDH", "--muted"], ["pdl", "PDL", "--muted"], ["pdc", "PDC", "--muted"],
];
function setLevels(lv) {
  levelLines.forEach((l) => candle.removePriceLine(l));
  levelLines = [];
  if (!lv || !$("#show-levels").checked) return;
  for (const [k, title, col] of LEVELS) {
    if (lv[k] == null) continue;
    levelLines.push(candle.createPriceLine({ price: lv[k], color: cssVar(col), lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, axisLabelVisible: true, title }));
  }
}
$("#show-levels").onchange = () => S.chartData && setLevels(S.chartData.levels);

async function loadChart(reset = false) {
  if (!S.selected) return;
  const sym = S.selected;
  let d;
  try {
    d = await api(`/api/chart?symbol=${encodeURIComponent(sym)}&tf=${S.tf}&sessions=${S.sessions}`);
  } catch (e) {
    if (reset) toast(`Grafico ${esc(sym)}: ${esc(e.message)}`, "bear");
    return;
  }
  if (sym !== S.selected) return;
  S.chartData = d;
  $("#chart-empty").hidden = d.candles.length > 0;
  if (!d.candles.length) $("#chart-empty").textContent = "Nessun dato per questo titolo";
  candle.setData(d.candles);
  volume.setData(d.volume);
  setVwap(d.vwap);
  ema9S.setData(d.ema9);
  ema20S.setData(d.ema20);
  rsiS.setData(d.rsi);
  histS.setData(d.macd_hist);
  macdS.setData(d.macd);
  sigS.setData(d.macd_signal);
  markers.setMarkers(d.markers);
  setLevels(d.levels);
  if (reset) chart.timeScale().fitContent();
  updateLegend({});
  renderChartHead();
  renderLevels();
  renderStopButtons();
}

function setVwap(points) {
  const segs = [];
  let cur = [];
  for (const p of points) {
    if (p.value == null) { if (cur.length) segs.push(cur); cur = []; }
    else cur.push(p);
  }
  if (cur.length) segs.push(cur);
  const n = vwapPool.length;
  const recent = segs.slice(-n);
  // l'ultima sessione va sempre nella serie con l'etichetta (l'ultima del pool)
  vwapPool.forEach((sr, i) => sr.setData(recent[i - (n - recent.length)] || []));
}

function renderChartHead() {
  const r = rowFor(S.selected) || S.chartData?.levels;
  $("#chart-symbol").textContent = S.selected || "—";
  if (!r) return;
  $("#chart-price").textContent = price(r.last);
  const ch = $("#chart-change");
  ch.textContent = pct(r.change_pct);
  ch.className = "chg " + signed(r.change_pct);
  $("#chart-trend").textContent = r.trend === "up" ? "EMA 9 > EMA 20 (trend su)" : r.trend === "down" ? "EMA 9 < EMA 20 (trend giù)" : "";
}

function renderLevels() {
  const r = rowFor(S.selected) || S.chartData?.levels;
  if (!r) { $("#levels").innerHTML = ""; return; }
  const items = [
    ["VWAP", price(r.vwap)], ["Massimo", price(r.hod)], ["Minimo", price(r.lod)],
    ["ORH", r.or_complete ? price(r.orh) : "in formazione"], ["ORL", r.or_complete ? price(r.orl) : "—"],
    ["PMH", price(r.pmh)], ["PML", price(r.pml)], ["PDH", price(r.pdh)], ["PDL", price(r.pdl)], ["PDC", price(r.pdc)],
    ["ATR 14g", price(r.atr)], ["Range/ATR", r.range_atr_pct == null ? "—" : r.range_atr_pct + "%"],
    ["RVOL", r.rvol == null ? "—" : nf2.format(r.rvol) + "×"], ["RSI 5m", r.rsi == null ? "—" : nf1.format(r.rsi)], ["Volume", vol(r.volume)],
  ];
  $("#levels").innerHTML = items.map(([k, v]) => `<div class="level"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
}

$$("#tf-buttons button").forEach((b) => (b.onclick = () => {
  S.tf = b.dataset.tf;
  store.set("tf", S.tf);
  $$("#tf-buttons button").forEach((x) => x.classList.toggle("active", x === b));
  loadChart(true);
}));
$("#sessions").onchange = (e) => { S.sessions = +e.target.value; store.set("sessions", S.sessions); loadChart(true); };

/* ---------------- selezione ---------------- */
function select(sym) {
  if (!sym) return;
  showView("dashboard");
  const changed = sym !== S.selected;
  S.selected = sym;
  store.set("selected", sym);
  $$("#scanner tbody tr").forEach((tr) => tr.classList.toggle("active", tr.dataset.sym === sym));
  $("#calc-symbol").value = sym;
  if (changed) {
    const r = rowFor(sym);
    $("#calc-entry").value = r?.last ?? "";
    $("#calc-stop").value = "";
    $("#calc-result").innerHTML = `<p class="muted">Scegli uno stop: scrivilo o usa un livello qui sopra.</p>`;
  }
  renderChartHead();
  renderLevels();
  renderStopButtons();
  loadChart(changed);
  loadNews();
}

/* ---------------- rischio e calcolatore ---------------- */
function renderDaily() {
  const d = S.journal?.daily;
  if (!d) return;
  const r = S.settings.risk;
  $("#daily").innerHTML = `
    <div class="row"><span class="muted">P&amp;L di oggi</span><span class="big ${signed(d.pnl_eur)}">${eur(d.pnl_eur)}</span></div>
    <div class="meter ${d.used_pct >= 75 ? "danger" : ""}" title="Quota della perdita massima giornaliera già usata"><div style="width:${d.used_pct}%"></div></div>
    <div class="row small"><span class="muted">Limite perdita ${eur(d.max_loss_eur)} · usato ${nf0.format(d.used_pct)}%</span><span>Residuo ${eur(d.remaining_eur)}</span></div>
    <div class="row small" style="margin-top:6px"><span class="muted">Rischio per trade</span><span>${nf1.format(r.risk_pct)}% = ${eur(r.capital_eur * r.risk_pct / 100)}</span></div>`;
  $("#daily-trades").textContent = `${d.trades} trade oggi${d.trades ? ` · ${d.wins} ✓ ${d.losses} ✕` : ""}${d.open_trades ? ` · ${d.open_trades} aperti` : ""}`;
  $("#calc-capital").textContent = `Capitale ${eur(r.capital_eur)}`;
}

function renderStopButtons() {
  const r = rowFor(S.selected);
  const box = $("#stop-buttons");
  if (!r) { box.innerHTML = ""; return; }
  const opts = [["VWAP", r.vwap], ["ORL", r.orl], ["ORH", r.orh], ["Minimo", r.lod], ["Massimo", r.hod], ["PML", r.pml], ["PMH", r.pmh]].filter(([, v]) => v != null);
  box.innerHTML = opts.map(([k, v]) => `<button type="button" class="mini" data-v="${v}">${k} ${price(v)}</button>`).join("");
  $$("button", box).forEach((b) => (b.onclick = () => { $("#calc-stop").value = b.dataset.v; calc(); }));
}

$("#calc-use-last").onclick = () => { const r = rowFor(S.selected); if (r?.last) { $("#calc-entry").value = r.last; calc(); } };
let calcTimer;
$("#calc-entry").oninput = $("#calc-stop").oninput = () => { clearTimeout(calcTimer); calcTimer = setTimeout(calc, 200); };

async function calc() {
  const entry = parseFloat($("#calc-entry").value), stop = parseFloat($("#calc-stop").value);
  if (!(entry > 0) || !(stop > 0)) return;
  const r = rowFor(S.selected);
  let res;
  try { res = await post("/api/risk/position", { entry, stop, atr: r?.atr }); } catch (e) { return toast(esc(e.message), "bear"); }
  const box = $("#calc-result");
  if (!res.ok) { box.innerHTML = `<p class="down">${esc(res.error)}</p>`; return; }
  const locked = S.journal?.daily?.locked;
  box.innerHTML = `
    ${locked ? `<ul class="warnings"><li>Stop giornaliero raggiunto: valuta di non aprire altri trade oggi.</li></ul>` : ""}
    <div class="hero"><span class="n">${nf0.format(res.shares)}</span><span>azioni ${esc(S.selected)} <b class="${res.direction === "long" ? "up" : "down"}">${res.direction === "long" ? "LONG (acquisto)" : "SHORT (vendita)"}</b></span></div>
    <dl class="kv">
      <dt>Rischio</dt><dd>${eur(res.actual_risk_eur)} <span class="muted">/ max ${eur(res.risk_budget_eur)}</span></dd>
      <dt>Per azione</dt><dd>$ ${price(res.risk_per_share)} (${nf2.format(res.stop_pct)}%)</dd>
      <dt>Controvalore</dt><dd>$ ${price(res.position_value_usd)} ≈ ${eur(res.position_value_eur)}</dd>
      <dt>% capitale</dt><dd>${nf1.format(res.position_pct)}%</dd>
      <dt>Limitato da</dt><dd>${esc(res.limited_by)}</dd>
    </dl>
    <div class="targets">${res.targets.map((t) => `<div><span class="muted">${t.r}R</span><b>${price(t.price)}</b><span class="up">+${nf2.format(t.profit_eur)} €</span></div>`).join("")}</div>
    ${res.warnings.length ? `<ul class="warnings">${res.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    <div class="calc-actions"><button class="mini primary" id="calc-log" ${res.shares ? "" : "disabled"}>Registra come trade aperto</button></div>`;
  const btn = $("#calc-log");
  if (btn) btn.onclick = async () => {
    try {
      S.journal = await post("/api/journal", { symbol: S.selected, side: res.direction, qty: res.shares, entry, stop, setup: res.direction === "long" ? "ORB long" : "ORB short" });
      renderDaily(); renderBanners();
      toast(`Trade aperto registrato: ${esc(S.selected)} ${res.shares} azioni. Chiudilo dal Diario quando esci.`, "info");
    } catch (e) { toast(esc(e.message), "bear"); }
  };
}

/* ---------------- notizie ---------------- */
$("#news-all").onchange = (e) => { S.newsAll = e.target.checked; loadNews(); };
async function loadNews() {
  const q = S.newsAll || !S.selected ? "" : `?symbol=${encodeURIComponent(S.selected)}`;
  let d;
  try { d = await api("/api/news" + q); } catch (e) { $("#news").innerHTML = `<li class="muted">Notizie non disponibili: ${esc(e.message)}</li>`; return; }
  S.lastNewsAt = Date.now();
  const s = d.summary;
  const icon = (sc) => (sc > 0 ? "▲" : sc < 0 ? "▼" : "●");
  $("#news-summary").innerHTML = s.count
    ? `Sentiment ${S.newsAll ? "watchlist" : esc(S.selected || "")}: <b>${esc(s.label)}</b> <span class="muted">(${s.positive} ▲ · ${s.negative} ▼ su ${s.count} notizie, ultime 48 ore)</span>`
    : `<span class="muted">Nessuna notizia nelle ultime 48 ore.</span>`;
  const now = Date.now() / 1000;
  $("#news").innerHTML = d.items.map((n) => {
    const sc = n.sentiment.score;
    const cls = sc > 0 ? "pos" : sc < 0 ? "neg" : "neu";
    const title = n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.headline)}</a>` : esc(n.headline);
    const fresh = now - n.created_at < 3600 ? `<span class="fresh">Nuova</span>` : "";
    const syms = S.newsAll ? (n.symbols || []).slice(0, 4).map((x) => `<b>${esc(x)}</b>`).join(" ") : "";
    return `<li>${title}<div class="meta">${fresh}<span class="sent ${cls}" title="${n.sentiment.keywords.length ? "Parole chiave: " + esc(n.sentiment.keywords.join(", ")) : "Nessuna parola chiave"}">${icon(sc)} ${esc(n.sentiment.label)}</span>${syms}<span>${esc(n.source)}</span><span>${romeDayTime.format(new Date(n.created_at * 1000))}</span></div></li>`;
  }).join("");
}

/* ---------------- ciclo di aggiornamento ---------------- */
async function refresh() {
  clearTimeout(S.timer);
  try {
    const scan = await api("/api/scan");
    S.scan = scan;
    S.marketAt = Date.now();
    renderHeader();
    tickClock();
    renderScanner();
    detectAlerts();
    for (const r of scan.rows.concat(scan.benchmarks)) S.prevPrices.set(r.symbol, r.last);
    if (!S.selected && scan.rows.length) {
      const saved = store.get("selected", null);
      select(saved && rowFor(saved) ? saved : sortedRows()[0]?.symbol || scan.rows[0].symbol);
    }
    else if (S.selected) { renderChartHead(); renderLevels(); renderStopButtons(); loadChart(false); }
    if (Date.now() - S.lastNewsAt > 90000) loadNews();
  } catch (e) {
    S.scan = S.scan || null;
    $("#updated").textContent = "Aggiornamento non riuscito: " + e.message;
  }
  renderBanners();
  S.timer = setTimeout(refresh, (S.settings?.scanner.refresh_seconds || 15) * 1000);
}

async function loadJournal() {
  try { S.journal = await api("/api/journal"); } catch (e) { return toast(esc(e.message), "bear"); }
  renderDaily();
  renderJournal();
  renderBanners();
}

/* ---------------- diario ---------------- */
function renderJournal() {
  const j = S.journal;
  if (!j) return;
  const s = j.stats;
  const tiles = s.closed
    ? [
        ["P&L totale", `<span class="${signed(s.total_pnl_eur)}">${eur(s.total_pnl_eur)}</span>`],
        ["Trade chiusi", nf0.format(s.closed)],
        ["% vincenti", nf1.format(s.win_rate) + "%"],
        ["Media vincita", `<span class="up">${eur(s.avg_win_eur)}</span>`],
        ["Media perdita", `<span class="down">${eur(s.avg_loss_eur)}</span>`],
        ["Profit factor", s.profit_factor == null ? "—" : nf2.format(s.profit_factor)],
        ["R medio", s.avg_r == null ? "—" : nf2.format(s.avg_r) + " R"],
        ["P&L di oggi", `<span class="${signed(j.daily.pnl_eur)}">${eur(j.daily.pnl_eur)}</span>`],
      ]
    : [["Trade chiusi", "0"], ["P&L di oggi", eur(j.daily.pnl_eur)]];
  $("#journal-stats").innerHTML = tiles.map(([k, v]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");

  $("#journal-table tbody").innerHTML = j.trades.map((t) => {
    const open = t.exit == null;
    return `<tr data-id="${t.id}">
      <td>${esc(t.date.split("-").reverse().join("/"))} ${esc(t.time)}</td>
      <td><b>${esc(t.symbol)}</b></td>
      <td class="${t.side === "long" ? "up" : "down"}">${t.side === "long" ? "Long" : "Short"}</td>
      <td class="num">${nf0.format(t.qty)}</td>
      <td class="num">${price(t.entry)}</td>
      <td class="num">${price(t.stop)}</td>
      <td class="num">${open ? `<input type="number" step="0.01" placeholder="uscita" aria-label="Prezzo di uscita"> <button class="mini" data-act="close">Chiudi</button>` : price(t.exit)}</td>
      <td class="num ${signed(t.pnl_eur)}">${open ? `<span class="tag-open">APERTO</span>` : eur(t.pnl_eur)}</td>
      <td class="num">${t.r_multiple == null ? "—" : nf2.format(t.r_multiple)}</td>
      <td>${esc(t.setup)}</td>
      <td class="note" title="${esc(t.notes)}">${esc(t.notes)}</td>
      <td><button class="mini" data-act="del" title="Elimina" aria-label="Elimina trade">✕</button></td>
    </tr>`;
  }).join("") || `<tr><td colspan="12" class="muted">Nessun trade registrato.</td></tr>`;
  $$("#journal-table button").forEach((b) => (b.onclick = async () => {
    const id = b.closest("tr").dataset.id;
    try {
      if (b.dataset.act === "del") {
        if (!confirm("Eliminare questo trade dal diario?")) return;
        S.journal = await api(`/api/journal/${id}`, { method: "DELETE" });
      } else {
        const v = parseFloat(b.closest("td").querySelector("input").value);
        if (!(v > 0)) return toast("Inserisci il prezzo di uscita.", "info");
        S.journal = await put(`/api/journal/${id}`, { exit: v });
      }
      renderJournal(); renderDaily(); renderBanners();
    } catch (e) { toast(esc(e.message), "bear"); }
  }));

  $("#setup-table tbody").innerHTML = Object.entries(s.by_setup || {})
    .sort((a, b) => b[1].pnl_eur - a[1].pnl_eur)
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${v.trades}</td><td class="num">${v.wins}</td><td class="num ${signed(v.pnl_eur)}">${eur(v.pnl_eur)}</td></tr>`)
    .join("") || `<tr><td colspan="4" class="muted">Le statistiche per setup compaiono dopo i primi trade chiusi.</td></tr>`;
}

$("#export-csv").onclick = async (e) => {
  if (!desktop()) return; // nel browser basta il download normale
  e.preventDefault();
  try {
    const text = await (await fetch("/api/journal.csv")).text();
    const r = await window.pywebview.api.save_csv("diario-trade.csv", text);
    if (r.ok) toast(`Diario salvato in ${esc(r.path)}`, "info");
  } catch (err) { toast(esc(err.message || err), "bear"); }
};
$("#open-data").onclick = () => desktop() && window.pywebview.api.open_data_folder();

function resetJournalForm() {
  const f = $("#journal-form");
  f.reset();
  const now = new Date();
  const parts = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  f.date.value = parts;
  f.time.value = romeHM.format(now);
  f.commission_eur.value = S.settings?.risk.commission_eur ?? 0;
  if (S.selected) f.symbol.value = S.selected;
}
$("#journal-form").onsubmit = async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target).entries());
  body.symbol = body.symbol.toUpperCase();
  try {
    S.journal = await post("/api/journal", body);
    renderJournal(); renderDaily(); renderBanners();
    resetJournalForm();
    toast("Trade salvato nel diario.", "info");
  } catch (err) { toast(esc(err.message), "bear"); }
};

/* ---------------- impostazioni ---------------- */
function msg(id, text, ok = true) { const el = $(id); el.textContent = text; el.className = "form-msg " + (ok ? "ok" : "err"); }

async function fillSettings() {
  const st = S.settings;
  try {
    const p = await api("/api/provider");
    const f = $("#provider-form");
    f.DATA_PROVIDER.value = p.config.DATA_PROVIDER;
    f.ALPACA_FEED.value = p.config.ALPACA_FEED;
    f.ALPACA_KEY_ID.value = "";
    f.ALPACA_KEY_ID.placeholder = p.config.ALPACA_KEY_ID ? `salvata: ${p.config.ALPACA_KEY_ID} (lascia vuoto per non cambiarla)` : "es. PK…";
    f.ALPACA_SECRET_KEY.placeholder = p.config.has_secret ? "salvata (lascia vuoto per non cambiarla)" : "incollala qui";
    if (p.error) msg("#provider-msg", p.error, false);
  } catch (e) { msg("#provider-msg", e.message, false); }

  renderWatchlistEditor();
  $("#benchmarks").value = st.benchmarks.join(", ");
  $("#sector-benchmark").value = st.sector_benchmark;
  const rf = $("#risk-form");
  for (const [k, v] of Object.entries(st.risk)) if (rf[k]) rf[k].value = v;
  const sf = $("#scanner-form");
  for (const [k, v] of Object.entries(st.scanner)) if (sf[k]) sf[k].value = v;
  sf.sound.checked = st.alerts.sound;
  sf.browser_notifications.checked = st.alerts.browser_notifications;
  $("#signal-checks").innerHTML = Object.entries(S.meta.signals)
    .map(([c, i]) => `<label class="check" title="${esc(i.help)}"><input type="checkbox" value="${c}" ${st.alerts.signals.includes(c) ? "checked" : ""}> ${esc(i.label)}</label>`)
    .join("");
}

function renderWatchlistEditor(groups = S.settings.watchlist) {
  $("#watchlist-editor").innerHTML = groups
    .map((g, i) => `<div class="group-edit" data-i="${i}"><input class="g-name" value="${esc(g.name)}" aria-label="Nome gruppo"><input class="g-syms" value="${esc(g.symbols.join(", "))}" aria-label="Titoli del gruppo" placeholder="NVDA, AMD, …"><button class="mini" data-del="${i}" title="Elimina gruppo">✕</button></div>`)
    .join("");
  $$("#watchlist-editor [data-del]").forEach((b) => (b.onclick = () => {
    const gs = readWatchlistEditor();
    gs.splice(+b.dataset.del, 1);
    renderWatchlistEditor(gs);
  }));
}
function readWatchlistEditor() {
  return $$("#watchlist-editor .group-edit").map((row) => ({
    name: $(".g-name", row).value.trim(),
    symbols: $(".g-syms", row).value.split(/[\s,;]+/).map((s) => s.trim().toUpperCase()).filter(Boolean),
  }));
}
$("#add-group").onclick = () => renderWatchlistEditor([...readWatchlistEditor(), { name: "Nuovo gruppo", symbols: [] }]);

async function saveSettings(patch, msgId) {
  try {
    S.settings = await put("/api/settings", patch);
    msg(msgId, "Salvato.");
    renderGroupFilter();
    renderPriceAlerts();
    S.prevSignals = null;
    refresh();
    loadJournal();
  } catch (e) { msg(msgId, e.message, false); }
}

$("#save-watchlist").onclick = () => saveSettings({
  watchlist: readWatchlistEditor().filter((g) => g.symbols.length),
  benchmarks: $("#benchmarks").value.split(/[\s,;]+/).map((s) => s.trim().toUpperCase()).filter(Boolean),
  sector_benchmark: $("#sector-benchmark").value.trim().toUpperCase() || "SMH",
}, "#watchlist-msg");

$("#risk-form").onsubmit = (e) => {
  e.preventDefault();
  const risk = {};
  for (const [k, v] of new FormData(e.target).entries()) risk[k] = parseFloat(v) || 0;
  saveSettings({ risk }, "#risk-msg");
};
$("#fx-update").onclick = async () => {
  const r = await api("/api/fx").catch((e) => ({ ok: false, message: e.message }));
  if (r.ok) { $("#risk-form").eurusd.value = r.eurusd; msg("#risk-msg", `Cambio BCE del ${r.date}: ${r.eurusd}. Ricorda di salvare.`); }
  else msg("#risk-msg", r.message, false);
};

$("#scanner-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const scanner = {};
  for (const k of ["or_minutes", "rvol_threshold", "gap_threshold", "rvol_days", "refresh_seconds"]) scanner[k] = parseFloat(f[k].value);
  const alerts = {
    sound: f.sound.checked,
    browser_notifications: f.browser_notifications.checked,
    signals: $$("#signal-checks input:checked").map((i) => i.value),
  };
  if (alerts.browser_notifications && !desktop() && "Notification" in window && Notification.permission === "default") {
    await Notification.requestPermission();
  }
  saveSettings({ scanner, alerts }, "#scanner-msg");
};

$("#provider-form").onsubmit = async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target).entries());
  msg("#provider-msg", "Collegamento in corso…");
  try {
    const r = await post("/api/provider", body);
    msg("#provider-msg", r.check.message, r.check.ok);
    S.prevSignals = null;
    S.meta = await api("/api/meta");
    refresh();
    fillSettings();
    if (r.check.ok) msg("#provider-msg", r.check.message, true);
  } catch (err) { msg("#provider-msg", err.message, false); }
};
$("#provider-test").onclick = async () => {
  msg("#provider-msg", "Verifica in corso…");
  const r = await post("/api/provider/test", {}).catch((e) => ({ ok: false, message: e.message }));
  msg("#provider-msg", r.message, r.ok);
};

/* ---------------- guida ---------------- */
function renderGuide() {
  $("#guide-signals").innerHTML = Object.values(S.meta.signals).map((i) => `<dt><span class="chip ${i.tone}">${esc(i.label)}</span></dt><dd>${esc(i.help)}</dd>`).join("");
}

/* ---------------- avvio ---------------- */
async function start() {
  setTheme(store.get("theme", "dark"));
  S.tf = store.get("tf", "5Min");
  S.sessions = store.get("sessions", 2);
  $$("#tf-buttons button").forEach((x) => x.classList.toggle("active", x.dataset.tf === S.tf));
  $("#sessions").value = String(S.sessions);
  $("#only-signals").checked = store.get("onlySignals", false);
  initChart();
  try {
    [S.meta, S.settings] = await Promise.all([api("/api/meta"), api("/api/settings")]);
  } catch (e) {
    $("#banners").innerHTML = `<div class="banner error">✕ Il server della dashboard non risponde (${esc(e.message)}). È ancora aperta la finestra di avvio?</div>`;
    return;
  }
  renderGroupFilter();
  renderPriceAlerts();
  renderGuide();
  resetJournalForm();
  await loadJournal();
  await refresh();
  const v = store.get("view", "dashboard");
  if (v !== "dashboard") showView(v);
}
start();
