"""Dati per il grafico: candele, volumi e indicatori, con orari spostati sull'ora italiana."""
from __future__ import annotations

from datetime import time

from . import market
from .indicators import ema, macd, rsi, vwap
from .providers import TF_SECONDS, DataProvider
from .scanner import group_by_day, split_session


def build_chart(provider: DataProvider, symbol: str, timeframe: str, sessions: int = 2) -> dict:
    if timeframe not in TF_SECONDS:
        raise ValueError("Timeframe non valido")
    sessions = max(1, min(5, sessions))
    now = provider.now()
    day = market.session_date(now)
    first = day
    for _ in range(sessions):  # una sessione in piu' per "scaldare" EMA, RSI e MACD
        first = market.previous_trading_day(first)
    display_from = market.at(market.next_trading_day(first), time(0)).timestamp()
    bars = provider.get_bars([symbol], timeframe, market.at(first, time(0))).get(symbol, [])

    closes = [b.c for b in bars]
    e9, e20, r14 = ema(closes, 9), ema(closes, 20), rsi(closes, 14)
    m_line, m_sig, m_hist = macd(closes)

    # VWAP calcolato separatamente per ogni sessione regolare
    vw_by_t: dict[int, float] = {}
    for d, day_bars in group_by_day(bars).items():
        _, reg, _ = split_session(day_bars, d)
        for b, v in zip(reg, vwap(reg)):
            if v is not None:
                vw_by_t[b.t] = v

    out = {k: [] for k in ("candles", "volume", "vwap", "ema9", "ema20", "rsi", "macd", "macd_signal", "macd_hist")}
    markers = []
    orb_up_done: set = set()
    orb_dn_done: set = set()
    or_ranges: dict = {}
    for i, b in enumerate(bars):
        if b.t < display_from:
            continue
        t = b.t + market.rome_offset(b.t)
        d = market.ny_date(b.t)
        o_ts, c_ts = market.regular_bounds(d)
        extended = not (o_ts <= b.t < c_ts)
        up = b.c >= b.o
        candle = {"time": t, "open": b.o, "high": b.h, "low": b.l, "close": b.c}
        if extended:
            col = "rgba(38,166,154,0.35)" if up else "rgba(239,83,80,0.35)"
            candle.update(color=col, wickColor=col, borderColor=col)
        out["candles"].append(candle)
        out["volume"].append(
            {"time": t, "value": b.v, "color": ("rgba(38,166,154,0.45)" if up else "rgba(239,83,80,0.45)")}
        )
        if b.t in vw_by_t:
            out["vwap"].append({"time": t, "value": round(vw_by_t[b.t], 4)})
        else:  # punto vuoto: la linea si interrompe tra una sessione e l'altra
            out["vwap"].append({"time": t})
        for key, series in (("ema9", e9), ("ema20", e20), ("rsi", r14), ("macd", m_line), ("macd_signal", m_sig)):
            if series[i] is not None:
                out[key].append({"time": t, "value": round(series[i], 4)})
        if m_hist[i] is not None:
            out["macd_hist"].append(
                {"time": t, "value": round(m_hist[i], 4), "color": "#26a69a" if m_hist[i] >= 0 else "#ef5350"}
            )

        # Marcatori: prima chiusura oltre il range d'apertura (15 minuti) di ogni sessione
        if not extended:
            rng = or_ranges.setdefault(d, {"h": None, "l": None, "end": o_ts + 15 * 60})
            if b.t < rng["end"]:
                rng["h"] = b.h if rng["h"] is None else max(rng["h"], b.h)
                rng["l"] = b.l if rng["l"] is None else min(rng["l"], b.l)
            elif rng["h"] is not None:
                if d not in orb_up_done and b.c > rng["h"]:
                    orb_up_done.add(d)
                    markers.append({"time": t, "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "ORB"})
                if d not in orb_dn_done and b.c < rng["l"]:
                    orb_dn_done.add(d)
                    markers.append({"time": t, "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "ORB"})

    # Sfondo delle fasce orarie: inizio delle sessioni regolari (per separare i giorni)
    session_starts = []
    for d in sorted({market.ny_date(b.t) for b in bars if b.t >= display_from}):
        o_ts, _ = market.regular_bounds(d)
        session_starts.append(o_ts + market.rome_offset(o_ts))

    out.update(
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "markers": markers,
            "session_starts": session_starts,
            "provider": provider.info(),
        }
    )
    return out
