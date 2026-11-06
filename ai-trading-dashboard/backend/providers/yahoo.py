"""Dati da Yahoo Finance (servizio NON ufficiale, senza chiave).

Comodo per iniziare, ma puo' smettere di funzionare o limitare le richieste
senza preavviso. Per un uso quotidiano e' preferibile Alpaca.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ..indicators import Bar
from .base import DataProvider, ProviderError

INTERVALS = {"1Min": "1m", "5Min": "5m", "15Min": "15m"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-trading-dashboard)"}


class YahooProvider(DataProvider):
    name = "yahoo"
    label = "Yahoo Finance"
    note = "Servizio non ufficiale: dati possibilmente in ritardo, può interrompersi."

    def __init__(self):
        self.client = httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True)

    def _chart(self, symbol: str, interval: str, start: datetime, end: Optional[datetime]) -> list[Bar]:
        params = {
            "interval": interval,
            "period1": int(start.timestamp()),
            "period2": int((end or self.now()).timestamp()),
            "includePrePost": "true",
        }
        try:
            r = self.client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params=params)
        except httpx.HTTPError as e:
            raise ProviderError(f"Yahoo non raggiungibile: {e}") from e
        if r.status_code == 429:
            raise ProviderError("Yahoo sta limitando le richieste: aumenta l'intervallo di aggiornamento.")
        if r.status_code >= 400:
            raise ProviderError(f"Errore Yahoo {r.status_code} per {symbol}")
        result = (r.json().get("chart") or {}).get("result") or []
        if not result:
            return []
        res = result[0]
        ts = res.get("timestamp") or []
        q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        bars = []
        for i, t in enumerate(ts):
            o, h, l, c, v = (q.get(k, [None] * len(ts))[i] for k in ("open", "high", "low", "close", "volume"))
            if None in (o, h, l, c):
                continue
            bars.append(Bar(int(t), float(o), float(h), float(l), float(c), float(v or 0)))
        return bars

    def get_bars(self, symbols, timeframe, start, end=None):
        interval = INTERVALS[timeframe]
        # Yahoo concede le candele da 1 minuto solo per gli ultimi ~7 giorni.
        if interval == "1m":
            start = max(start, self.now() - timedelta(days=7))
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(lambda s: self._chart(s, interval, start, end), symbols))
        return dict(zip(symbols, results))

    def _news_for(self, symbol: str) -> list[dict]:
        try:
            r = self.client.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": symbol, "newsCount": 10, "quotesCount": 0},
            )
            r.raise_for_status()
        except httpx.HTTPError:
            return []
        out = []
        for n in r.json().get("news", []):
            out.append(
                {
                    "id": n.get("uuid", ""),
                    "headline": n.get("title", ""),
                    "summary": "",
                    "url": n.get("link", ""),
                    "source": n.get("publisher", ""),
                    "created_at": int(n.get("providerPublishTime", 0)),
                    "symbols": n.get("relatedTickers") or [symbol],
                }
            )
        return out

    def get_news(self, symbols, start=None, limit=50):
        with ThreadPoolExecutor(max_workers=6) as ex:
            lists = list(ex.map(self._news_for, symbols))
        seen, items = set(), []
        for lst in lists:
            for n in lst:
                if n["id"] in seen:
                    continue
                if start is not None and n["created_at"] < start.timestamp():
                    continue
                seen.add(n["id"])
                items.append(n)
        items.sort(key=lambda n: n["created_at"], reverse=True)
        return items[:limit]

    def check(self):
        try:
            bars = self._chart("SPY", "5m", self.now() - timedelta(days=5), None)
        except ProviderError as e:
            return {"ok": False, "message": str(e)}
        if not bars:
            return {"ok": False, "message": "Yahoo ha risposto senza dati per SPY."}
        return {"ok": True, "message": f"Connesso a Yahoo. SPY ultimo prezzo: {bars[-1].c:.2f}"}
