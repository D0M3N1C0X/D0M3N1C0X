from backend.indicators import Bar, aggregate, atr_daily, ema, macd, rsi, vwap


def test_ema_starts_with_sma_and_tracks_constant_series():
    vals = [10.0] * 30
    out = ema(vals, 9)
    assert out[7] is None
    assert out[8] == 10.0
    assert out[-1] == 10.0


def test_ema_weights_recent_prices():
    out = ema([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 3)
    assert out[2] == 2.0  # media semplice dei primi 3
    assert out[3] == 3.0  # 4*0.5 + 2*0.5
    assert out[-1] > 8.5


def test_rsi_extremes():
    up = [float(i) for i in range(1, 40)]
    down = list(reversed(up))
    assert rsi(up, 14)[-1] == 100.0
    assert rsi(down, 14)[-1] == 0.0
    assert rsi([5.0] * 20, 14)[-1] == 50.0


def test_rsi_known_value():
    # serie alternata simmetrica: guadagni e perdite medi uguali -> RSI ~ 50
    closes = [10, 11] * 20
    assert abs(rsi(closes, 14)[-1] - 50) < 5


def test_macd_zero_on_flat_series():
    line, sig, hist = macd([100.0] * 60)
    assert abs(line[-1]) < 1e-9 and abs(sig[-1]) < 1e-9 and abs(hist[-1]) < 1e-9
    assert line[24] is None and line[25] is not None


def test_vwap_volume_weighted():
    bars = [Bar(0, 10, 10, 10, 10, 100), Bar(60, 20, 20, 20, 20, 300)]
    out = vwap(bars)
    assert out[0] == 10
    assert out[1] == (10 * 100 + 20 * 300) / 400


def test_atr_daily():
    sessions = [(11, 9, 10), (12, 10, 11), (11, 8, 9)]
    # TR: max(2, 2, 0)=2 ; max(3, 2, 1)=3
    assert atr_daily(sessions) == 2.5


def test_aggregate_to_5_minutes():
    bars = [Bar(300 + i * 60, 10 + i, 11 + i, 9 + i, 10.5 + i, 10) for i in range(10)]
    out = aggregate(bars, 300)
    assert len(out) == 2
    first = out[0]
    assert (first.t, first.o, first.h, first.l, first.c, first.v) == (300, 10, 15, 9, 14.5, 50)
