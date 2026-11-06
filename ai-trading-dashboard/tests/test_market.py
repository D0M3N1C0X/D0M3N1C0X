from datetime import date, datetime, timezone

from backend import market


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_holidays_and_weekends():
    assert not market.is_trading_day(date(2026, 11, 26))  # Thanksgiving
    assert not market.is_trading_day(date(2026, 11, 7))  # sabato
    assert market.is_trading_day(date(2026, 11, 6))
    assert market.previous_trading_day(date(2026, 11, 9)) == date(2026, 11, 6)


def test_status_and_rome_times():
    # 6 novembre 2026: USA ed Europa in ora solare -> apertura alle 15:30 italiane
    s = market.market_status(utc(2026, 11, 6, 15, 0))  # 10:00 NY
    assert s["status"] == "open"
    s = market.market_status(utc(2026, 11, 6, 12, 0))  # 07:00 NY
    assert s["status"] == "pre"
    assert s["next_event_rome"] == "06/11 15:30"
    s = market.market_status(utc(2026, 11, 7, 12, 0))  # sabato
    assert s["status"] == "closed"
    assert s["next_event_rome"] == "09/11 15:30"


def test_dst_mismatch_week_opens_1430_rome():
    # 30 ottobre 2026: Europa già in ora solare, USA ancora in ora legale
    s = market.market_status(utc(2026, 10, 30, 11, 0))
    assert s["next_event_rome"] == "30/10 14:30"


def test_session_date_rolls_back_before_premarket():
    assert market.session_date(utc(2026, 11, 9, 7, 0)) == date(2026, 11, 6)  # lunedì 02:00 NY
    assert market.session_date(utc(2026, 11, 9, 10, 0)) == date(2026, 11, 9)  # lunedì 05:00 NY
