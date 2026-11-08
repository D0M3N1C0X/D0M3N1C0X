from .base import TF_SECONDS, DataProvider, ProviderError


def build_provider(cfg: dict) -> DataProvider:
    """Crea la fonte dati in base alla configurazione (config.env)."""
    name = (cfg.get("DATA_PROVIDER") or "demo").lower()
    if name == "alpaca":
        from .alpaca import AlpacaProvider

        return AlpacaProvider(cfg.get("ALPACA_KEY_ID", ""), cfg.get("ALPACA_SECRET_KEY", ""), cfg.get("ALPACA_FEED", "iex"))
    if name == "yahoo":
        from .yahoo import YahooProvider

        return YahooProvider()
    from .demo import DemoProvider

    return DemoProvider(speed=float(cfg.get("DEMO_SPEED") or 1))


__all__ = ["build_provider", "DataProvider", "ProviderError", "TF_SECONDS"]
