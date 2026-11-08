"""Orari e calendario del mercato USA (NYSE/Nasdaq).

Tutti i calcoli interni usano l'ora di New York; la dashboard mostra l'ora italiana.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ROME = ZoneInfo("Europe/Rome")

PREMARKET_OPEN = time(4, 0)
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
AFTER_CLOSE = time(20, 0)
EARLY_CLOSE = time(13, 0)

# Festivita' NYSE (calendario indicativo: verificare sempre su nyse.com).
HOLIDAYS = {
    # 2025
    date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}

EARLY_CLOSES = {
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
    date(2026, 11, 27), date(2026, 12, 24),
    date(2027, 11, 26),
}


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def close_time(d: date) -> time:
    return EARLY_CLOSE if d in EARLY_CLOSES else REGULAR_CLOSE


def previous_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def session_date(now: datetime) -> date:
    """La sessione di riferimento: oggi se e' iniziato il premarket, altrimenti l'ultima."""
    ny = now.astimezone(NY)
    d = ny.date()
    if is_trading_day(d) and ny.time() >= PREMARKET_OPEN:
        return d
    return previous_trading_day(d)


def at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=NY)


def regular_bounds(d: date) -> tuple[int, int]:
    """Inizio/fine della sessione regolare come epoch secondi."""
    return int(at(d, REGULAR_OPEN).timestamp()), int(at(d, close_time(d)).timestamp())


def market_status(now: datetime) -> dict:
    ny = now.astimezone(NY)
    d, t = ny.date(), ny.time()
    if is_trading_day(d):
        close = close_time(d)
        if PREMARKET_OPEN <= t < REGULAR_OPEN:
            status, label, nxt, nxt_label = "pre", "Premarket", at(d, REGULAR_OPEN), "Apertura"
        elif REGULAR_OPEN <= t < close:
            status, label, nxt, nxt_label = "open", "Mercato aperto", at(d, close), "Chiusura"
        elif close <= t < AFTER_CLOSE:
            status, label = "after", "After-hours"
            nxt, nxt_label = at(next_trading_day(d), REGULAR_OPEN), "Apertura"
        elif t < PREMARKET_OPEN:
            status, label, nxt, nxt_label = "closed", "Chiuso", at(d, REGULAR_OPEN), "Apertura"
        else:
            status, label = "closed", "Chiuso"
            nxt, nxt_label = at(next_trading_day(d), REGULAR_OPEN), "Apertura"
    else:
        status, label = "closed", "Chiuso"
        nxt, nxt_label = at(next_trading_day(d), REGULAR_OPEN), "Apertura"
    return {
        "status": status,
        "label": label,
        "now_ny": ny.isoformat(),
        "now_rome": now.astimezone(ROME).isoformat(),
        "next_event": nxt_label,
        "next_event_at": int(nxt.timestamp()),
        "next_event_rome": nxt.astimezone(ROME).strftime("%d/%m %H:%M"),
        "seconds_to_next": int(nxt.timestamp() - now.timestamp()),
        "session_date": session_date(now).isoformat(),
    }


def ny_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, NY).date()


def rome_offset(ts: int) -> int:
    """Offset in secondi di Roma rispetto a UTC all'istante ts (gestisce l'ora legale)."""
    off = datetime.fromtimestamp(ts, ROME).utcoffset()
    return int(off.total_seconds()) if off else 0
