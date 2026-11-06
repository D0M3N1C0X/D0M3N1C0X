"""Dati di mercato da Alpaca (https://alpaca.markets).

Piano gratuito: feed IEX in tempo reale (una sola borsa: i volumi sono una frazione
di quelli consolidati), candele storiche e notizie (Benzinga).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from ..indicators import Bar
from .base import DataProvider, ProviderError

DATA_URL = "https://data.alpaca.markets"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


class AlpacaProvider(DataProvider):
    name = "alpaca"

    def __init__(self, key_id: str, secret: str, feed: str = "iex"):
        if not key_id or not secret:
            raise ProviderError("Mancano le chiavi API di Alpaca (Impostazioni > Fonte dati).")
        self.feed = feed or "iex"
        self.label = f"Alpaca ({self.feed.upper()})"
        self.note = (
            "Tempo reale dal feed IEX: i volumi sono parziali (una sola borsa)."
            if self.feed == "iex"
            else "Feed SIP consolidato."
        )
        self.client = httpx.Client(
            base_url=DATA_URL,
            headers={"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret},
            timeout=15,
        )

    def _get(self, path: str, params: dict) -> dict:
        try:
            r = self.client.get(path, params=params)
        except httpx.HTTPError as e:
            raise ProviderError(f"Alpaca non raggiungibile: {e}") from e
        if r.status_code in (401, 403):
            raise ProviderError("Alpaca ha rifiutato le chiavi API (controlla Key ID e Secret).")
        if r.status_code == 429:
            raise ProviderError("Troppe richieste ad Alpaca: aumenta l'intervallo di aggiornamento.")
        if r.status_code >= 400:
            raise ProviderError(f"Errore Alpaca {r.status_code}: {r.text[:200]}")
        return r.json()

    def get_bars(self, symbols, timeframe, start, end=None):
        out: dict[str, list[Bar]] = {s: [] for s in symbols}
        params = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": _iso(start),
            "limit": 10000,
            "feed": self.feed,
            "adjustment": "split",
            "sort": "asc",
        }
        if end is not None:
            params["end"] = _iso(end)
        for _ in range(50):  # paginazione
            data = self._get("/v2/stocks/bars", params)
            for sym, rows in (data.get("bars") or {}).items():
                out.setdefault(sym, []).extend(
                    Bar(_epoch(r["t"]), r["o"], r["h"], r["l"], r["c"], r["v"]) for r in rows
                )
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token
        for rows in out.values():
            rows.sort(key=lambda b: b.t)
        return out

    def get_last_prices(self, symbols):
        data = self._get("/v2/stocks/snapshots", {"symbols": ",".join(symbols), "feed": self.feed})
        snaps = data.get("snapshots", data) if isinstance(data, dict) else {}
        prices = {}
        for sym, snap in snaps.items():
            trade = (snap or {}).get("latestTrade") or {}
            if trade.get("p"):
                prices[sym] = float(trade["p"])
        return prices

    def get_news(self, symbols, start: Optional[datetime] = None, limit: int = 50):
        items: list[dict] = []
        params = {"symbols": ",".join(symbols), "limit": 50, "sort": "desc"}
        if start is not None:
            params["start"] = _iso(start)
        while len(items) < limit:
            data = self._get("/v1beta1/news", params)
            for n in data.get("news", []):
                items.append(
                    {
                        "id": str(n.get("id")),
                        "headline": n.get("headline", ""),
                        "summary": n.get("summary", ""),
                        "url": n.get("url", ""),
                        "source": n.get("source", ""),
                        "created_at": _epoch(n["created_at"]),
                        "symbols": n.get("symbols", []),
                    }
                )
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token
        return items[:limit]

    def check(self):
        try:
            prices = self.get_last_prices(["SPY"])
        except ProviderError as e:
            return {"ok": False, "message": str(e)}
        if not prices:
            return {"ok": False, "message": "Connesso, ma nessun prezzo ricevuto per SPY."}
        return {"ok": True, "message": f"Connesso ad Alpaca. SPY ultimo prezzo: {prices['SPY']:.2f}"}
