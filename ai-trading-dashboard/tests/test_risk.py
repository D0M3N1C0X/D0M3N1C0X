from datetime import date

from backend.risk import daily_status, journal_stats, position_size, trade_pnl


def test_position_size_long_limited_by_risk():
    r = position_size(capital_eur=10000, risk_pct=1, entry=50, stop=49, eurusd=1.0, max_position_pct=100)
    assert r["direction"] == "long"
    assert r["shares"] == 100  # 100 EUR di rischio / 1 $ per azione
    assert r["limited_by"] == "rischio"
    assert r["targets"][1]["price"] == 52  # 2R


def test_position_size_short_and_fx():
    r = position_size(capital_eur=10000, risk_pct=1, entry=100, stop=102, eurusd=1.2, max_position_pct=100)
    assert r["direction"] == "short"
    assert r["shares"] == 60  # 100 EUR = 120 $ / 2 $
    assert r["targets"][0]["price"] == 98


def test_position_size_capped_by_max_position():
    r = position_size(capital_eur=10000, risk_pct=1, entry=100, stop=99.9, eurusd=1.0, max_position_pct=25)
    assert r["shares"] == 25
    assert "dimensione" in r["limited_by"]


def test_commissions_reduce_size():
    r = position_size(capital_eur=10000, risk_pct=1, entry=50, stop=49, eurusd=1.0, commission_eur=10)
    assert r["shares"] == 80


def test_invalid_inputs():
    assert not position_size(10000, 1, 50, 50, 1.1)["ok"]
    assert not position_size(10000, 1, 0, 49, 1.1)["ok"]


def test_trade_pnl_and_r_multiple():
    t = {"side": "long", "qty": 100, "entry": 50, "exit": 52, "stop": 49, "eurusd": 1.0, "commission_eur": 1}
    assert trade_pnl(t) == {"pnl_usd": 200.0, "pnl_eur": 198.0, "r_multiple": 2.0}
    s = {"side": "short", "qty": 10, "entry": 100, "exit": 101, "stop": 102, "eurusd": 1.0, "commission_eur": 0}
    assert trade_pnl(s)["pnl_usd"] == -10.0 and trade_pnl(s)["r_multiple"] == -0.5
    assert trade_pnl({"side": "long", "qty": 1, "entry": 10, "exit": None})["pnl_eur"] is None


def test_daily_stop_locks():
    risk = {"capital_eur": 10000, "daily_loss_pct": 3, "max_trades_per_day": 0}
    trades = [{"date": "2026-11-06", "pnl_eur": -200}, {"date": "2026-11-06", "pnl_eur": -120}, {"date": "2026-11-05", "pnl_eur": -999}]
    d = daily_status(trades, risk, date(2026, 11, 6))
    assert d["pnl_eur"] == -320 and d["locked"] and d["used_pct"] == 100.0
    d = daily_status(trades[:1], risk, date(2026, 11, 6))
    assert not d["locked"] and d["remaining_eur"] == 100


def test_journal_stats():
    trades = [
        {"pnl_eur": 100, "r_multiple": 2, "setup": "ORB long"},
        {"pnl_eur": -50, "r_multiple": -1, "setup": "ORB long"},
        {"pnl_eur": None},
    ]
    s = journal_stats(trades)
    assert s["closed"] == 2 and s["win_rate"] == 50.0 and s["profit_factor"] == 2.0 and s["avg_r"] == 0.5
    assert s["by_setup"]["ORB long"]["pnl_eur"] == 50
