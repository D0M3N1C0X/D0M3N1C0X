"""Salvataggio locale: impostazioni, diario dei trade e chiavi API.

Tutto resta sul tuo computer.
- Versione da cartella (avvia.command / avvia.bat): nella cartella del progetto,
  in config.env e data/.
- App installata: nella cartella dati dell'utente
  (Mac: ~/Library/Application Support/AI Momentum Desk,
   Windows: %APPDATA%\\AI Momentum Desk).

File:
- config.env      fonte dati e chiavi API (non va mai condiviso)
- settings.json   watchlist, rischio, scanner, avvisi
- journal.json    diario dei trade
"""
from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path

APP_NAME = "AI Momentum Desk"
# Nell'app installata (PyInstaller) i file dell'interfaccia stanno in sys._MEIPASS.
FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
_lock = threading.Lock()


def user_data_dir() -> Path:
    """Cartella dati standard del sistema operativo per l'app installata."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "ai-momentum-desk"


def data_dir() -> Path:
    default = user_data_dir() if FROZEN else ROOT / "data"
    d = Path(os.environ.get("AITD_DATA_DIR") or default)
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    default = data_dir() / "config.env" if FROZEN else ROOT / "config.env"
    return Path(os.environ.get("AITD_CONFIG") or default)


DEFAULT_SETTINGS = {
    "watchlist": [
        {"name": "Chip e hardware", "symbols": ["NVDA", "AMD", "AVGO", "TSM", "MRVL", "ARM", "MU", "SMCI"]},
        {"name": "Memorie e storage", "symbols": ["SNDK", "WDC", "STX"]},
        {"name": "Big Tech AI", "symbols": ["MSFT", "GOOGL", "META", "AMZN", "AAPL"]},
        {"name": "Software AI", "symbols": ["PLTR", "SNOW", "AI", "PATH", "SOUN", "BBAI"]},
    ],
    "benchmarks": ["SPY", "QQQ", "SMH"],
    "sector_benchmark": "SMH",
    "risk": {
        "capital_eur": 10000.0,
        "risk_pct": 1.0,
        "daily_loss_pct": 3.0,
        "max_position_pct": 25.0,
        "max_trades_per_day": 0,
        "eurusd": 1.15,
        "commission_eur": 0.0,
    },
    "scanner": {
        "or_minutes": 15,
        "rvol_threshold": 2.0,
        "gap_threshold": 3.0,
        "rvol_days": 10,
        "refresh_seconds": 15,
    },
    "alerts": {
        "sound": True,
        "browser_notifications": False,
        "signals": ["SETUP_LONG", "SETUP_SHORT", "ORB_UP", "ORB_DOWN", "PDH_BREAK", "PDL_BREAK", "PMH_BREAK"],
    },
    "price_alerts": [],
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(default)


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_settings() -> dict:
    with _lock:
        return _merge(DEFAULT_SETTINGS, _read_json(data_dir() / "settings.json", {}))


def save_settings(settings: dict) -> dict:
    merged = _merge(DEFAULT_SETTINGS, settings)
    with _lock:
        _write_json(data_dir() / "settings.json", merged)
    return merged


def load_journal() -> list[dict]:
    with _lock:
        return _read_json(data_dir() / "journal.json", [])


def save_journal(trades: list[dict]) -> None:
    with _lock:
        _write_json(data_dir() / "journal.json", trades)


def load_env() -> dict:
    cfg: dict[str, str] = {}
    try:
        for line in config_path().read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    # Le variabili d'ambiente hanno la precedenza sul file.
    for k in ("DATA_PROVIDER", "ALPACA_KEY_ID", "ALPACA_SECRET_KEY", "ALPACA_FEED", "DEMO_SPEED"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def save_env(cfg: dict) -> None:
    lines = [
        "# Configurazione locale della dashboard. NON condividere questo file: contiene le chiavi API.",
        "# DATA_PROVIDER: demo | alpaca | yahoo",
    ]
    for k in ("DATA_PROVIDER", "ALPACA_KEY_ID", "ALPACA_SECRET_KEY", "ALPACA_FEED", "DEMO_SPEED"):
        if cfg.get(k) not in (None, ""):
            lines.append(f"{k}={cfg[k]}")
    with _lock:
        config_path().write_text("\n".join(lines) + "\n", encoding="utf-8")
