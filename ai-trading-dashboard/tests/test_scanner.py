from datetime import date, datetime, timedelta

from backend import market
from backend.indicators import Bar
from backend.scanner import compute_row
from backend.storage import DEFAULT_SETTINGS

DAY = date(2026, 11, 6)
PREV = market.previous_trading_day(DAY)


def session(day, base, n_regular=78, vol=1000, step=0.0, pre=None):
    o, _ = market.regular_bounds(day)
    bars = []
    for i, (p, v) in enumerate(pre or []):
        bars.append(Bar(o - (len(pre) - i) * 300, p, p + 0.1, p - 0.1, p, v))
    for i in range(n_regular):
        p = base + step * i
        bars.append(Bar(o + i * 300, p, p + 0.2, p - 0.2, p, vol))
    return bars


def history(n_days=12, base=100.0):
    bars, d = [], PREV
    days = []
    for _ in range(n_days):
        days.append(d)
        d = market.previous_trading_day(d)
    for d in reversed(days):
        bars += session(d, base)
    return bars


def test_breakout_long_setup():
    # oggi: gap up, poi salita costante con volume triplo -> rottura ORH sopra VWAP
    today = session(DAY, 103.0, n_regular=24, vol=3000, step=0.1, pre=[(101.5, 500), (102.0, 800)])
    bars = history() + today
    now = market.at(DAY, market.REGULAR_OPEN) + timedelta(minutes=24 * 5)
    row = compute_row("TEST", bars, now, DEFAULT_SETTINGS)
    assert row["pdc"] == 100.0 and row["pdh"] == 100.2
    assert row["gap_pct"] == 3.0
    assert row["or_complete"] and row["orh"] == round(103.0 + 0.2 + 0.2, 2)
    assert 2.9 < row["rvol"] < 3.1
    assert row["above_vwap"] is True
    for sig in ("SETUP_LONG", "ORB_UP", "PDH_BREAK", "PMH_BREAK", "GAP_UP", "RVOL_HIGH", "HOD_NEAR"):
        assert sig in row["signals"], sig
    assert row["score"] > 0


def test_opening_range_not_ready_in_first_minutes():
    today = session(DAY, 100.0, n_regular=2)
    now = market.at(DAY, market.REGULAR_OPEN) + timedelta(minutes=10)
    row = compute_row("TEST", history() + today, now, DEFAULT_SETTINGS)
    assert row["or_complete"] is False and row["orh"] is None
    assert "ORB_UP" not in row["signals"]


def test_premarket_gap_uses_last_price():
    today = session(DAY, 0, n_regular=0, pre=[(95.0, 1000), (94.0, 1000)])
    now = market.at(DAY, market.REGULAR_OPEN) - timedelta(minutes=30)
    row = compute_row("TEST", history() + today, now, DEFAULT_SETTINGS)
    assert row["phase"] == "pre"
    assert row["gap_pct"] == -6.0
    assert "GAP_DOWN" in row["signals"] and "PDL_BREAK" in row["signals"]
    assert row["pml"] == 93.9


def test_relative_strength_vs_sector():
    today = session(DAY, 102.0, n_regular=12)
    now = market.at(DAY, market.REGULAR_OPEN) + timedelta(hours=1)
    row = compute_row("TEST", history() + today, now, DEFAULT_SETTINGS, bench_change=0.5)
    assert row["change_pct"] == 2.0 and row["rel_strength"] == 1.5
