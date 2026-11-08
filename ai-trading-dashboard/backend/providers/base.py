from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..indicators import Bar

TF_SECONDS = {"1Min": 60, "5Min": 300, "15Min": 900}


class ProviderError(Exception):
    """Errore leggibile da mostrare all'utente."""


class DataProvider:
    name = "base"
    label = "Base"
    note = ""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_bars(
        self, symbols: list[str], timeframe: str, start: datetime, end: Optional[datetime] = None
    ) -> dict[str, list[Bar]]:
        raise NotImplementedError

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        """Ultimo prezzo scambiato. Se il provider non lo offre si usa l'ultima candela."""
        return {}

    def get_news(self, symbols: list[str], start: Optional[datetime] = None, limit: int = 50) -> list[dict]:
        """Lista di notizie: id, headline, summary, url, source, created_at (epoch), symbols."""
        return []

    def check(self) -> dict:
        """Verifica la connessione. Ritorna {ok, message}."""
        return {"ok": True, "message": "OK"}

    def info(self) -> dict:
        return {"name": self.name, "label": self.label, "note": self.note}
