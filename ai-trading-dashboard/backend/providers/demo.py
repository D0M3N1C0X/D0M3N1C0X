"""Dati SIMULATI per provare la dashboard senza chiavi API.

Prezzi, volumi e notizie sono inventati (random walk deterministico per titolo e giorno):
non corrispondono al mercato reale. Fuori dall'orario di borsa l'orologio demo
"riproduce" l'ultima sessione dalle 10:00 di New York, cosi' i segnali si muovono.
"""
from __future__ import annotations

import hashlib
import math
import random
import time as _time
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from .. import market
from ..indicators import Bar, aggregate
from .base import TF_SECONDS, DataProvider

# Livelli di partenza indicativi, solo per dare scale di prezzo plausibili.
BASE = {
    "NVDA": (180, 0.030, 2.2e8), "AMD": (160, 0.034, 5e7), "AVGO": (330, 0.028, 2.5e7),
    "TSM": (270, 0.024, 1.5e7), "MRVL": (85, 0.036, 1.8e7), "ARM": (150, 0.038, 6e6),
    "MU": (190, 0.034, 2.5e7), "SMCI": (45, 0.050, 3e7), "SNDK": (120, 0.045, 8e6),
    "WDC": (95, 0.032, 9e6), "STX": (210, 0.030, 4e6), "MSFT": (510, 0.016, 2e7),
    "GOOGL": (250, 0.020, 3e7), "META": (720, 0.022, 1.2e7), "AMZN": (225, 0.020, 4e7),
    "AAPL": (255, 0.016, 5e7), "PLTR": (180, 0.040, 6e7), "SNOW": (230, 0.034, 5e6),
    "AI": (22, 0.045, 6e6), "PATH": (13, 0.040, 1.5e7), "SOUN": (15, 0.060, 4e7),
    "BBAI": (6, 0.065, 3e7), "SMH": (310, 0.020, 6e6), "SPY": (670, 0.010, 7e7),
    "QQQ": (600, 0.012, 4e7),
}
HISTORY_SESSIONS = 30

HEADLINES_POS = [
    "{s} beats estimates as AI demand surges",
    "Analyst upgrades {s}, raises price target on data center growth",
    "{s} announces record AI partnership deal",
    "{s} shares rally after strong guidance",
    "{s} expands AI chip supply agreement",
]
HEADLINES_NEG = [
    "{s} falls after guidance cut",
    "Analyst downgrades {s} on valuation concerns",
    "{s} faces probe over export restrictions",
    "{s} slumps as AI spending fears weigh",
]
HEADLINES_NEU = [
    "{s} to present at technology conference next week",
    "What to watch for {s} ahead of earnings",
    "{s} files quarterly report",
]


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _volume_profile(minute: int) -> float:
    """Profilo a U del volume nella sessione regolare (minuto 0..389)."""
    x = minute / 389
    return 0.55 + 2.4 * (1 - x) ** 6 + 1.3 * x**8


class DemoProvider(DataProvider):
    name = "demo"
    label = "Demo (dati simulati)"
    note = "Dati inventati per provare la dashboard: non usarli per fare trading."

    def __init__(self, speed: float = 1.0):
        self.speed = speed
        self.started = _time.time()
        self._cache: dict[tuple[str, str], list[Bar]] = {}

    # ---- orologio -----------------------------------------------------------
    def now(self) -> datetime:
        real = datetime.now(timezone.utc)
        ny = real.astimezone(market.NY)
        d = ny.date()
        if market.is_trading_day(d) and market.REGULAR_OPEN <= ny.time() < market.close_time(d):
            return real
        # Fuori orario: riproduce l'ultima sessione regolare a partire dalle 10:00 NY.
        if market.is_trading_day(d) and ny.time() >= market.close_time(d):
            day = d
        else:
            day = market.previous_trading_day(d)
        start = market.at(day, time(10, 0))
        elapsed = (_time.time() - self.started) * self.speed
        close = market.at(day, market.close_time(day))
        sim = min(start + timedelta(seconds=elapsed), close - timedelta(seconds=1))
        return sim.astimezone(timezone.utc)

    # ---- generazione --------------------------------------------------------
    def _sessions(self, last_day) -> list:
        days = [last_day]
        while len(days) < HISTORY_SESSIONS:
            days.append(market.previous_trading_day(days[-1]))
        return list(reversed(days))

    def _minute_bars(self, symbol: str, day) -> list[Bar]:
        key = (symbol, day.isoformat())
        if key in self._cache:
            return self._cache[key]
        # Calcola la catena di sessioni fino a 'day' (prezzi continui tra i giorni).
        days = self._sessions(day)
        base, vol, adv = BASE.get(symbol, (50 + _seed(symbol) % 200, 0.03, 5e6))
        rng0 = random.Random(_seed(symbol, "chain", days[0]))
        price = base * (0.85 + 0.3 * rng0.random())
        result: list[Bar] = []
        for dday in days:
            k = (symbol, dday.isoformat())
            if k in self._cache:
                bars = self._cache[k]
                price = bars_last_regular_close(bars, dday) or price
                result = bars
                continue
            rng = random.Random(_seed(symbol, dday))
            momentum_day = rng.random() < 0.18
            direction = 1 if rng.random() < 0.55 else -1
            gap = rng.gauss(0, vol * 0.35) + (direction * vol * rng.uniform(0.6, 1.6) if momentum_day else 0)
            drift = (direction * vol * rng.uniform(0.4, 1.2) if momentum_day else rng.gauss(0, vol * 0.25)) / 390
            day_adv = adv * (rng.uniform(1.8, 3.5) if momentum_day else rng.uniform(0.7, 1.25))
            sigma = vol / math.sqrt(390) * (1.25 if momentum_day else 1.0)
            bars = []
            open_ts = int(market.at(dday, market.REGULAR_OPEN).timestamp())
            close_ts = int(market.at(dday, market.close_time(dday)).timestamp())
            pre_start = open_ts - 90 * 60  # premarket simulato dalle 8:00
            post_end = close_ts + 60 * 60
            p = price
            pre_target = price * (1 + gap)
            n_pre = (open_ts - pre_start) // 60
            for i in range(n_pre):  # premarket: converge verso il gap
                t = pre_start + i * 60
                o = p
                p = p + (pre_target - p) * 0.04 + p * rng.gauss(0, sigma * 0.6)
                h, l = max(o, p) * (1 + abs(rng.gauss(0, sigma * 0.3))), min(o, p) * (1 - abs(rng.gauss(0, sigma * 0.3)))
                v = day_adv * 0.0004 * (2.5 if momentum_day else 1) * rng.uniform(0.3, 1.7)
                bars.append(Bar(t, round(o, 2), round(h, 2), round(l, 2), round(p, 2), round(v)))
            n_reg = (close_ts - open_ts) // 60
            for i in range(n_reg):
                t = open_ts + i * 60
                o = p
                shock = rng.gauss(0, sigma * (1.8 if i < 15 else 1.0))
                p = max(0.5, p * (1 + drift + shock))
                wick = abs(rng.gauss(0, sigma * 0.5))
                h, l = max(o, p) * (1 + wick), min(o, p) * (1 - wick)
                v = day_adv / 390 * _volume_profile(i) * rng.uniform(0.5, 1.6) * (1 + 8 * abs(shock))
                bars.append(Bar(t, round(o, 2), round(h, 2), round(l, 2), round(p, 2), round(v)))
            regular_close = p
            for i in range(int((post_end - close_ts) // 60)):  # after-hours
                t = close_ts + i * 60
                o = p
                p = p * (1 + rng.gauss(0, sigma * 0.4))
                h, l = max(o, p), min(o, p)
                v = day_adv * 0.0002 * rng.uniform(0.3, 1.7)
                bars.append(Bar(t, round(o, 2), round(h, 2), round(l, 2), round(p, 2), round(v)))
            self._cache[k] = bars
            price = regular_close
            result = bars
        return result

    def get_bars(self, symbols, timeframe, start, end=None):
        now_ts = int(self.now().timestamp())
        end_ts = min(int(end.timestamp()), now_ts) if end else now_ts
        start_ts = int(start.timestamp())
        last_day = market.session_date(datetime.fromtimestamp(end_ts, timezone.utc))
        days = [d for d in self._sessions(last_day) if market.at(d, market.AFTER_CLOSE).timestamp() >= start_ts]
        out = {}
        for s in symbols:
            rows: list[Bar] = []
            for d in days:
                rows.extend(b for b in self._minute_bars(s, d) if start_ts <= b.t and b.t + 60 <= end_ts)
            out[s] = aggregate(rows, TF_SECONDS[timeframe]) if timeframe != "1Min" else [
                Bar(b.t, b.o, b.h, b.l, b.c, b.v) for b in rows
            ]
        return out

    def get_news(self, symbols, start=None, limit=50):
        now = self.now()
        day = market.session_date(now)
        items = []
        for s in symbols:
            rng = random.Random(_seed(s, "news", day))
            for j in range(rng.randint(0, 3)):
                kind = rng.random()
                pool = HEADLINES_POS if kind < 0.45 else HEADLINES_NEG if kind < 0.75 else HEADLINES_NEU
                created = market.at(day, time(7, 0)).timestamp() + rng.randint(0, 8 * 3600)
                if created > now.timestamp():
                    continue
                items.append(
                    {
                        "id": f"demo-{s}-{day}-{j}",
                        "headline": "[DEMO] " + rng.choice(pool).format(s=s),
                        "summary": "Notizia simulata per la modalità demo.",
                        "url": "",
                        "source": "Demo",
                        "created_at": int(created),
                        "symbols": [s],
                    }
                )
        if start is not None:
            items = [n for n in items if n["created_at"] >= start.timestamp()]
        items.sort(key=lambda n: n["created_at"], reverse=True)
        return items[:limit]

    def check(self):
        return {"ok": True, "message": "Modalità demo attiva: i dati sono simulati."}


def bars_last_regular_close(bars: list[Bar], day) -> Optional[float]:
    _, close_ts = market.regular_bounds(day)
    reg = [b for b in bars if b.t < close_ts]
    return reg[-1].c if reg else None
