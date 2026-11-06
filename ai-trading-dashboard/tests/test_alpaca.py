"""Verifica la lettura delle risposte di Alpaca con un server finto (nessuna rete)."""
from datetime import datetime, timezone

import httpx
import pytest

from backend.providers.alpaca import DATA_URL, AlpacaProvider
from backend.providers.base import ProviderError


def make(handler):
    p = AlpacaProvider("KEY", "SECRET")
    p.client = httpx.Client(base_url=DATA_URL, transport=httpx.MockTransport(handler), headers=p.client.headers)
    return p


def test_bars_pagination_and_headers():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        assert req.headers["APCA-API-KEY-ID"] == "KEY"
        assert req.url.params["feed"] == "iex" and req.url.params["timeframe"] == "5Min"
        if "page_token" not in req.url.params:
            return httpx.Response(200, json={"bars": {"NVDA": [{"t": "2026-11-06T14:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]}, "next_page_token": "abc"})
        return httpx.Response(200, json={"bars": {"NVDA": [{"t": "2026-11-06T14:35:00Z", "o": 1.5, "h": 2, "l": 1, "c": 1.8, "v": 50}], "AMD": []}, "next_page_token": None})

    p = make(handler)
    out = p.get_bars(["NVDA", "AMD"], "5Min", datetime(2026, 11, 6, tzinfo=timezone.utc))
    assert len(calls) == 2
    assert [b.c for b in out["NVDA"]] == [1.5, 1.8]
    assert out["NVDA"][0].t == int(datetime(2026, 11, 6, 14, 30, tzinfo=timezone.utc).timestamp())
    assert out["AMD"] == []


def test_snapshots_both_shapes():
    p = make(lambda r: httpx.Response(200, json={"NVDA": {"latestTrade": {"p": 190.5}}}))
    assert p.get_last_prices(["NVDA"]) == {"NVDA": 190.5}
    p = make(lambda r: httpx.Response(200, json={"snapshots": {"AMD": {"latestTrade": {"p": 150.25}}}}))
    assert p.get_last_prices(["AMD"]) == {"AMD": 150.25}


def test_news_parsing():
    item = {"id": 1, "headline": "NVDA beats", "summary": "", "url": "https://x", "source": "benzinga", "created_at": "2026-11-06T12:00:00Z", "symbols": ["NVDA"]}
    p = make(lambda r: httpx.Response(200, json={"news": [item], "next_page_token": None}))
    n = p.get_news(["NVDA"])
    assert n[0]["headline"] == "NVDA beats" and n[0]["symbols"] == ["NVDA"] and n[0]["id"] == "1"


def test_bad_keys_give_readable_error():
    p = make(lambda r: httpx.Response(403, json={"message": "forbidden"}))
    with pytest.raises(ProviderError, match="chiavi"):
        p.get_last_prices(["SPY"])
    assert not p.check()["ok"]


def test_missing_keys():
    with pytest.raises(ProviderError):
        AlpacaProvider("", "")
