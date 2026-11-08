"""Scanner momentum/breakout: livelli chiave, volume relativo e segnali per ogni titolo."""
from __future__ import annotations

import threading
import time as _time
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from . import market
from .indicators import Bar, atr_daily, ema, rsi, vwap
from .providers import DataProvider, ProviderError

BAR = 300  # lo scanner lavora su candele da 5 minuti

# codice: (etichetta, tono, spiegazione)
SIGNALS = {
    "SETUP_LONG": ("Setup long", "bull", "Rottura del massimo d'apertura sopra VWAP, con volume relativo alto ed EMA 9 sopra EMA 20."),
    "SETUP_SHORT": ("Setup short", "bear", "Rottura del minimo d'apertura sotto VWAP, con volume relativo alto ed EMA 9 sotto EMA 20."),
    "ORB_UP": ("Rottura ORH", "bull", "Prezzo sopra il massimo del range di apertura (Opening Range High)."),
    "ORB_DOWN": ("Rottura ORL", "bear", "Prezzo sotto il minimo del range di apertura (Opening Range Low)."),
    "PDH_BREAK": ("Sopra PDH", "bull", "Prezzo sopra il massimo di ieri (Previous Day High)."),
    "PDL_BREAK": ("Sotto PDL", "bear", "Prezzo sotto il minimo di ieri (Previous Day Low)."),
    "PMH_BREAK": ("Sopra PMH", "bull", "Prezzo sopra il massimo del premarket."),
    "PML_BREAK": ("Sotto PML", "bear", "Prezzo sotto il minimo del premarket."),
    "HOD_NEAR": ("Al massimo", "bull", "Entro lo 0,2% dal massimo della giornata."),
    "LOD_NEAR": ("Al minimo", "bear", "Entro lo 0,2% dal minimo della giornata."),
    "GAP_UP": ("Gap up", "bull", "Apertura sopra la chiusura di ieri oltre la soglia impostata."),
    "GAP_DOWN": ("Gap down", "bear", "Apertura sotto la chiusura di ieri oltre la soglia impostata."),
    "RVOL_HIGH": ("Volume alto", "info", "Volume relativo sopra la soglia: c'è più interesse del solito."),
    "NEWS": ("News", "info", "Notizie uscite dalla chiusura di ieri: possibile catalizzatore."),
}


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or not b:
        return None
    return (a / b - 1) * 100


def _r(x: Optional[float], n: int = 2) -> Optional[float]:
    return None if x is None else round(x, n)


def group_by_day(bars: list[Bar]) -> dict[date, list[Bar]]:
    out: dict[date, list[Bar]] = defaultdict(list)
    for b in bars:
        out[market.ny_date(b.t)].append(b)
    return out


def split_session(bars: list[Bar], day: date) -> tuple[list[Bar], list[Bar], list[Bar]]:
    """(premarket, regolare, after-hours) per la giornata."""
    o, c = market.regular_bounds(day)
    pre = [b for b in bars if b.t < o]
    reg = [b for b in bars if o <= b.t < c]
    post = [b for b in bars if b.t >= c]
    return pre, reg, post


def _cum_volume(bars: list[Bar], start_ts: int, elapsed: float, bar_seconds: int = BAR) -> float:
    """Volume cumulato nei primi `elapsed` secondi da start_ts (pro-rata sull'ultima candela)."""
    total = 0.0
    for b in bars:
        off = b.t - start_ts
        if off >= elapsed:
            break
        total += b.v * min(1.0, max(0.0, (elapsed - off) / bar_seconds))
    return total


def compute_row(
    symbol: str,
    bars: list[Bar],
    now: datetime,
    settings: dict,
    last_price: Optional[float] = None,
    bench_change: Optional[float] = None,
) -> dict:
    sc = settings["scanner"]
    now_ts = int(now.timestamp())
    today = market.session_date(now)
    days = group_by_day(bars)
    prior = sorted(d for d in days if d < today and split_session(days[d], d)[1])
    pre, reg, post = split_session(days.get(today, []), today)
    open_ts, close_ts = market.regular_bounds(today)

    row: dict = {"symbol": symbol, "session": today.isoformat()}
    prev_reg = split_session(days[prior[-1]], prior[-1])[1] if prior else []
    pdh = max(b.h for b in prev_reg) if prev_reg else None
    pdl = min(b.l for b in prev_reg) if prev_reg else None
    pdc = prev_reg[-1].c if prev_reg else None

    today_bars = pre + reg + post
    last = last_price or (today_bars[-1].c if today_bars else pdc)
    phase = "pre" if now_ts < open_ts else "regular" if now_ts < close_ts else "post"

    day_open = reg[0].o if reg else None
    gap = _pct(day_open if day_open is not None else last, pdc)
    change = _pct(last, pdc)

    vw = vwap(reg)[-1] if reg else None
    hod = max([b.h for b in reg] + ([last] if phase == "regular" and last else [])) if reg else None
    lod = min([b.l for b in reg] + ([last] if phase == "regular" and last else [])) if reg else None
    pmh = max(b.h for b in pre) if pre else None
    pml = min(b.l for b in pre) if pre else None

    or_end = open_ts + int(sc["or_minutes"]) * 60
    or_bars = [b for b in reg if b.t < or_end]
    or_complete = bool(or_bars) and now_ts >= or_end
    orh = max(b.h for b in or_bars) if or_complete else None
    orl = min(b.l for b in or_bars) if or_complete else None

    # Volume relativo: volume di oggi fino a quest'ora vs media degli ultimi N giorni alla stessa ora.
    rvol = None
    lookback = prior[-int(sc["rvol_days"]):]
    if phase == "pre":
        start_today = int(market.at(today, market.PREMARKET_OPEN).timestamp())
        elapsed = now_ts - start_today
        today_vol = sum(b.v for b in pre)
        hist = [
            _cum_volume(split_session(days[d], d)[0], int(market.at(d, market.PREMARKET_OPEN).timestamp()), elapsed)
            for d in lookback
        ]
    else:
        elapsed = min(now_ts, close_ts) - open_ts
        today_vol = sum(b.v for b in reg)
        hist = [_cum_volume(split_session(days[d], d)[1], market.regular_bounds(d)[0], elapsed) for d in lookback]
    hist = [h for h in hist if h > 0]
    if hist and today_vol:
        rvol = today_vol / (sum(hist) / len(hist))

    sessions_hlc = []
    for d in prior[-15:]:
        r = split_session(days[d], d)[1]
        sessions_hlc.append((max(b.h for b in r), min(b.l for b in r), r[-1].c))
    atr = atr_daily(sessions_hlc, 14)

    closes = [b.c for b in bars[-300:]]
    if closes and last:
        closes[-1] = last
    e9, e20 = ema(closes, 9), ema(closes, 20)
    ema9, ema20 = (e9[-1] if e9 else None), (e20[-1] if e20 else None)
    rsi14 = rsi(closes, 14)[-1] if closes else None

    above_vwap = (last > vw) if (vw and last) else None
    thr = float(sc["rvol_threshold"])

    sig: list[str] = []
    if last is not None:
        if phase != "pre":
            if orh is not None and last > orh:
                sig.append("ORB_UP")
            if orl is not None and last < orl:
                sig.append("ORB_DOWN")
            if pmh is not None and last > pmh:
                sig.append("PMH_BREAK")
            if pml is not None and last < pml:
                sig.append("PML_BREAK")
            if hod and last >= hod * 0.998:
                sig.append("HOD_NEAR")
            elif lod and last <= lod * 1.002:
                sig.append("LOD_NEAR")
        if pdh is not None and last > pdh:
            sig.append("PDH_BREAK")
        if pdl is not None and last < pdl:
            sig.append("PDL_BREAK")
    if gap is not None and gap >= float(sc["gap_threshold"]):
        sig.append("GAP_UP")
    if gap is not None and gap <= -float(sc["gap_threshold"]):
        sig.append("GAP_DOWN")
    if rvol is not None and rvol >= thr:
        sig.append("RVOL_HIGH")
    trend_up = ema9 is not None and ema20 is not None and ema9 > ema20
    trend_dn = ema9 is not None and ema20 is not None and ema9 < ema20
    strong_vol = rvol is not None and rvol >= thr
    if "ORB_UP" in sig and above_vwap and strong_vol and trend_up:
        sig.insert(0, "SETUP_LONG")
    if "ORB_DOWN" in sig and above_vwap is False and strong_vol and trend_dn:
        sig.insert(0, "SETUP_SHORT")

    bull = sum(1 for s in sig if SIGNALS[s][1] == "bull")
    bear = sum(1 for s in sig if SIGNALS[s][1] == "bear")
    score = None
    if change is not None:
        score = change * min(max(rvol or 1.0, 0.5), 5.0) + 0.5 * (bull - bear)

    row.update(
        {
            "phase": phase,
            "last": _r(last),
            "change_pct": _r(change),
            "gap_pct": _r(gap),
            "open": _r(day_open),
            "volume": int(today_vol) if today_vol else 0,
            "rvol": _r(rvol),
            "vwap": _r(vw),
            "vwap_dist_pct": _r(_pct(last, vw)),
            "above_vwap": above_vwap,
            "hod": _r(hod), "lod": _r(lod),
            "pdh": _r(pdh), "pdl": _r(pdl), "pdc": _r(pdc),
            "pmh": _r(pmh), "pml": _r(pml),
            "orh": _r(orh), "orl": _r(orl), "or_complete": or_complete,
            "atr": _r(atr),
            "range_atr_pct": _r((hod - lod) / atr * 100 if (atr and hod and lod) else None, 0),
            "ema9": _r(ema9), "ema20": _r(ema20),
            "trend": "up" if trend_up else "down" if trend_dn else None,
            "rsi": _r(rsi14, 1),
            "rel_strength": _r(change - bench_change if (change is not None and bench_change is not None) else None),
            "signals": sig,
            "score": _r(score),
            "updated": int(today_bars[-1].t) if today_bars else None,
        }
    )
    return row


class Scanner:
    """Scarica i dati con cache e calcola le righe dello scanner."""

    def __init__(self, provider: DataProvider):
        self.provider = provider
        self._lock = threading.Lock()
        self._hist: dict = {}
        self._today: dict = {}
        self._news: dict = {}
        self.last_result: Optional[dict] = None

    def _history(self, symbols: list[str], day: date) -> dict[str, list[Bar]]:
        key = (day, tuple(symbols))
        if key not in self._hist:
            self._hist = {
                key: self.provider.get_bars(
                    symbols, "5Min", market.at(day - timedelta(days=24), time(0)), market.at(day, time(0))
                )
            }
        return self._hist[key]

    def _today_bars(self, symbols: list[str], day: date, ttl: float) -> dict[str, list[Bar]]:
        key = (day, tuple(symbols))
        hit = self._today.get(key)
        if hit and _time.time() - hit[0] < ttl:
            return hit[1]
        data = self.provider.get_bars(symbols, "5Min", market.at(day, time(0)))
        self._today = {key: (_time.time(), data)}
        return data

    def news(self, symbols: list[str], since: datetime, ttl: float = 90) -> list[dict]:
        key = tuple(symbols)
        hit = self._news.get(key)
        if hit and _time.time() - hit[0] < ttl:
            return hit[1]
        items = self.provider.get_news(symbols, start=since, limit=100)
        self._news[key] = (_time.time(), items)
        return items

    def bars_for(self, symbols: list[str], settings: dict) -> tuple[datetime, dict[str, list[Bar]]]:
        now = self.provider.now()
        day = market.session_date(now)
        ttl = max(4.0, float(settings["scanner"]["refresh_seconds"]) - 1)
        hist = self._history(symbols, day)
        today = self._today_bars(symbols, day, ttl)
        merged = {s: (hist.get(s) or []) + (today.get(s) or []) for s in symbols}
        return now, merged

    def scan(self, settings: dict) -> dict:
        groups = settings["watchlist"]
        watch = [s for g in groups for s in g["symbols"]]
        benches = list(dict.fromkeys(settings["benchmarks"] + [settings["sector_benchmark"]]))
        symbols = sorted(set(watch) | set(benches))
        errors: list[str] = []
        with self._lock:
            now, bars = self.bars_for(symbols, settings)
            try:
                prices = self.provider.get_last_prices(symbols)
            except ProviderError as e:
                prices = {}
                errors.append(str(e))
            day = market.session_date(now)
            since = market.at(market.previous_trading_day(day), market.REGULAR_CLOSE)
            try:
                news = self.news([s for s in symbols if s in watch], since)
            except ProviderError as e:
                news = []
                errors.append(f"Notizie non disponibili: {e}")

        news_count: dict[str, int] = defaultdict(int)
        for n in news:
            for s in n.get("symbols", []):
                news_count[s] += 1

        bench_rows = {s: compute_row(s, bars.get(s, []), now, settings, prices.get(s)) for s in benches}
        sector_chg = bench_rows.get(settings["sector_benchmark"], {}).get("change_pct")
        rows = []
        seen = set()
        for g in groups:
            for s in g["symbols"]:
                if s in seen:
                    continue
                seen.add(s)
                row = compute_row(s, bars.get(s, []), now, settings, prices.get(s), sector_chg)
                row["group"] = g["name"]
                row["news_count"] = news_count.get(s, 0)
                if row["news_count"]:
                    row["signals"].append("NEWS")
                if not bars.get(s):
                    row["error"] = "Nessun dato ricevuto"
                rows.append(row)
        result = {
            "generated_at": int(_time.time()),
            "market": market.market_status(now),
            "provider": self.provider.info(),
            "rows": rows,
            "benchmarks": [bench_rows[s] for s in settings["benchmarks"] if s in bench_rows],
            "errors": errors,
        }
        self.last_result = result
        return result
