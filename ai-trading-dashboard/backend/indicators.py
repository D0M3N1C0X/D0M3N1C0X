"""Indicatori tecnici. Funzioni pure su liste, facili da testare."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class Bar:
    t: int  # epoch secondi (UTC), inizio della candela
    o: float
    h: float
    l: float
    c: float
    v: float


def ema(values: Sequence[float], period: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: Sequence[float], period: int = 14) -> list[Optional[float]]:
    """RSI di Wilder."""
    out: list[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / period, losses / period

    def value(g: float, l: float) -> float:
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100 - 100 / (1 + g / l)

    out[period] = value(avg_g, avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
        out[i] = value(avg_g, avg_l)
    return out


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """Ritorna (linea MACD, linea segnale, istogramma)."""
    ef, es = ema(closes, fast), ema(closes, slow)
    line: list[Optional[float]] = [
        (a - b) if a is not None and b is not None else None for a, b in zip(ef, es)
    ]
    first = next((i for i, v in enumerate(line) if v is not None), None)
    sig: list[Optional[float]] = [None] * len(closes)
    if first is not None:
        sub = ema([v for v in line[first:]], signal)  # type: ignore[misc]
        for j, v in enumerate(sub):
            sig[first + j] = v
    hist = [(a - b) if a is not None and b is not None else None for a, b in zip(line, sig)]
    return line, sig, hist


def vwap(bars: Sequence[Bar]) -> list[Optional[float]]:
    """VWAP cumulativo sulle candele passate (tipicamente: solo la sessione regolare)."""
    out: list[Optional[float]] = []
    pv = vol = 0.0
    for b in bars:
        tp = (b.h + b.l + b.c) / 3
        pv += tp * b.v
        vol += b.v
        out.append(pv / vol if vol > 0 else None)
    return out


def atr_daily(sessions: Sequence[tuple[float, float, float]], period: int = 14) -> Optional[float]:
    """ATR semplice su sessioni (high, low, close) in ordine cronologico."""
    if len(sessions) < 2:
        return None
    trs = []
    for i in range(1, len(sessions)):
        h, l, _ = sessions[i]
        pc = sessions[i - 1][2]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    trs = trs[-period:]
    return sum(trs) / len(trs)


def aggregate(bars: Sequence[Bar], seconds: int) -> list[Bar]:
    """Aggrega candele (es. da 1 minuto a 5 minuti), allineate all'epoch."""
    out: list[Bar] = []
    cur: Optional[Bar] = None
    for b in bars:
        bucket = b.t - (b.t % seconds)
        if cur is None or cur.t != bucket:
            if cur is not None:
                out.append(cur)
            cur = Bar(bucket, b.o, b.h, b.l, b.c, b.v)
        else:
            cur.h = max(cur.h, b.h)
            cur.l = min(cur.l, b.l)
            cur.c = b.c
            cur.v += b.v
    if cur is not None:
        out.append(cur)
    return out
