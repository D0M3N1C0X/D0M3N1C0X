"""Server locale della dashboard (FastAPI). Avvio: python -m backend.run"""
from __future__ import annotations

import csv
import io
import re
import threading
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import market, risk, sentiment, storage
from .chart import build_chart
from .providers import ProviderError, build_provider
from .providers.demo import DemoProvider
from .scanner import SIGNALS, Scanner

SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
VERSION = "0.2.0"

app = FastAPI(title="AI Momentum Desk", version=VERSION)


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.provider_error: Optional[str] = None
        self.reload()

    def reload(self):
        cfg = storage.load_env()
        try:
            provider = build_provider(cfg)
            self.provider_error = None
        except ProviderError as e:
            provider = DemoProvider()
            self.provider_error = f"{e} Uso i dati demo nel frattempo."
        self.provider = provider
        self.scanner = Scanner(provider)


state = State()


def _symbol(s: str) -> str:
    s = (s or "").strip().upper()
    if not SYMBOL.match(s):
        raise HTTPException(400, f"Simbolo non valido: {s!r}")
    return s


@app.exception_handler(ProviderError)
def _provider_error(_, exc: ProviderError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# ---- informazioni generali -------------------------------------------------
@app.get("/api/meta")
def meta():
    return {
        "version": VERSION,
        "signals": {k: {"label": v[0], "tone": v[1], "help": v[2]} for k, v in SIGNALS.items()},
        "provider": state.provider.info(),
        "provider_error": state.provider_error,
        "market": market.market_status(state.provider.now()),
    }


# ---- scanner, grafico, notizie ---------------------------------------------
@app.get("/api/scan")
def scan():
    result = state.scanner.scan(storage.load_settings())
    if state.provider_error:
        result["errors"].insert(0, state.provider_error)
    return result


@app.get("/api/chart")
def chart(symbol: str, tf: str = "5Min", sessions: int = 2):
    try:
        data = build_chart(state.provider, _symbol(symbol), tf, sessions)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    last = state.scanner.last_result
    row = next((r for r in (last or {}).get("rows", []) + (last or {}).get("benchmarks", []) if r["symbol"] == data["symbol"]), None)
    if row is None:
        from .scanner import compute_row

        settings = storage.load_settings()
        now, bars = state.scanner.bars_for([data["symbol"]], settings)
        row = compute_row(data["symbol"], bars.get(data["symbol"], []), now, settings)
    data["levels"] = row
    return data


@app.get("/api/news")
def news(symbol: Optional[str] = None, hours: int = 48):
    settings = storage.load_settings()
    symbols = [_symbol(symbol)] if symbol else sorted({s for g in settings["watchlist"] for s in g["symbols"]})
    since = datetime.fromtimestamp(state.provider.now().timestamp() - hours * 3600, market.NY)
    items = [sentiment.annotate(n) for n in state.provider.get_news(symbols, start=since, limit=50)]
    return {"items": items, "summary": sentiment.summarize(items)}


# ---- impostazioni ------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    return storage.load_settings()


@app.put("/api/settings")
def put_settings(payload: dict = Body(...)):
    current = storage.load_settings()
    if "watchlist" in payload:
        groups = []
        for g in payload["watchlist"]:
            syms = list(dict.fromkeys(_symbol(s) for s in g.get("symbols", []) if str(s).strip()))
            name = str(g.get("name", "")).strip()[:40] or "Gruppo"
            groups.append({"name": name, "symbols": syms})
        payload["watchlist"] = groups
    for key in ("benchmarks",):
        if key in payload:
            payload[key] = [_symbol(s) for s in payload[key]]
    if "sector_benchmark" in payload:
        payload["sector_benchmark"] = _symbol(payload["sector_benchmark"])
    if "price_alerts" in payload:
        alerts = []
        for a in payload["price_alerts"]:
            alerts.append(
                {
                    "id": a.get("id") or uuid.uuid4().hex[:8],
                    "symbol": _symbol(a["symbol"]),
                    "op": "above" if a.get("op") != "below" else "below",
                    "price": float(a["price"]),
                    "active": bool(a.get("active", True)),
                }
            )
        payload["price_alerts"] = alerts
    current.update({k: v for k, v in payload.items() if k in storage.DEFAULT_SETTINGS})
    return storage.save_settings(current)


# ---- fonte dati --------------------------------------------------------------
def _masked(cfg: dict) -> dict:
    key = cfg.get("ALPACA_KEY_ID", "")
    return {
        "DATA_PROVIDER": cfg.get("DATA_PROVIDER", "demo"),
        "ALPACA_FEED": cfg.get("ALPACA_FEED", "iex"),
        "ALPACA_KEY_ID": (key[:4] + "..." + key[-2:]) if len(key) > 6 else ("impostata" if key else ""),
        "has_secret": bool(cfg.get("ALPACA_SECRET_KEY")),
    }


@app.get("/api/provider")
def get_provider():
    return {"config": _masked(storage.load_env()), "info": state.provider.info(), "error": state.provider_error}


@app.post("/api/provider")
def set_provider(payload: dict = Body(...)):
    cfg = storage.load_env()
    name = str(payload.get("DATA_PROVIDER", cfg.get("DATA_PROVIDER", "demo"))).lower()
    if name not in ("demo", "alpaca", "yahoo"):
        raise HTTPException(400, "Fonte dati non valida")
    cfg["DATA_PROVIDER"] = name
    for k in ("ALPACA_KEY_ID", "ALPACA_SECRET_KEY"):
        v = str(payload.get(k) or "").strip()
        if v:  # campo vuoto = mantieni la chiave gia' salvata
            cfg[k] = v
    if payload.get("ALPACA_FEED") in ("iex", "sip"):
        cfg["ALPACA_FEED"] = payload["ALPACA_FEED"]
    storage.save_env(cfg)
    with state.lock:
        state.reload()
    check = state.provider.check() if not state.provider_error else {"ok": False, "message": state.provider_error}
    return {"config": _masked(cfg), "info": state.provider.info(), "check": check}


@app.post("/api/provider/test")
def test_provider():
    return state.provider.check()


@app.get("/api/fx")
def fx():
    """Cambio EUR/USD di riferimento BCE (aggiornato una volta al giorno)."""
    try:
        r = httpx.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=10)
        r.raise_for_status()
        m = re.search(r"currency=['\"]USD['\"]\s+rate=['\"]([0-9.]+)['\"]", r.text)
        d = re.search(r"time=['\"]([0-9-]+)['\"]", r.text)
        if not m:
            raise ValueError("cambio USD non trovato")
        return {"ok": True, "eurusd": float(m.group(1)), "date": d.group(1) if d else None, "source": "BCE"}
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "message": f"Cambio non disponibile ({e}). Inseriscilo a mano."}


# ---- rischio -----------------------------------------------------------------
@app.post("/api/risk/position")
def position(payload: dict = Body(...)):
    r = storage.load_settings()["risk"]

    def num(key, default=None):
        v = payload.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    return risk.position_size(
        capital_eur=num("capital_eur", r["capital_eur"]),
        risk_pct=num("risk_pct", r["risk_pct"]),
        entry=num("entry"),
        stop=num("stop"),
        eurusd=num("eurusd", r["eurusd"]),
        max_position_pct=num("max_position_pct", r["max_position_pct"]),
        commission_eur=num("commission_eur", r["commission_eur"]),
        atr=num("atr") or None,
    )


# ---- diario dei trade ----------------------------------------------------------
TRADE_FIELDS = ("date", "time", "symbol", "side", "qty", "entry", "exit", "stop", "setup", "notes", "commission_eur", "eurusd")


def _clean_trade(payload: dict, existing: Optional[dict] = None) -> dict:
    t = dict(existing or {})
    for k in TRADE_FIELDS:
        if k in payload:
            t[k] = payload[k]
    t["symbol"] = _symbol(t.get("symbol", ""))
    t["side"] = "short" if t.get("side") == "short" else "long"
    for k in ("qty", "entry", "exit", "stop", "commission_eur", "eurusd"):
        v = t.get(k)
        t[k] = None if v in (None, "") else float(v)
    if not t.get("qty") or not t.get("entry"):
        raise HTTPException(400, "Servono almeno quantità e prezzo di entrata.")
    now = datetime.now(market.ROME)
    t.setdefault("date", now.date().isoformat())
    t["date"] = t["date"] or now.date().isoformat()
    t["time"] = t.get("time") or now.strftime("%H:%M")
    if t.get("eurusd") is None:
        t["eurusd"] = storage.load_settings()["risk"]["eurusd"]
    if t.get("commission_eur") is None:
        t["commission_eur"] = storage.load_settings()["risk"]["commission_eur"]
    t["notes"] = str(t.get("notes") or "")[:2000]
    t["setup"] = str(t.get("setup") or "Altro")[:60]
    t.update(risk.trade_pnl(t))
    return t


def _journal_response():
    trades = storage.load_journal()
    settings = storage.load_settings()
    today = datetime.now(market.ROME).date()
    trades_sorted = sorted(trades, key=lambda t: (t.get("date", ""), t.get("time", "")), reverse=True)
    return {
        "trades": trades_sorted,
        "stats": risk.journal_stats(trades),
        "daily": risk.daily_status(trades, settings["risk"], today),
    }


@app.get("/api/journal")
def journal():
    return _journal_response()


@app.post("/api/journal")
def add_trade(payload: dict = Body(...)):
    trades = storage.load_journal()
    t = _clean_trade(payload)
    t["id"] = uuid.uuid4().hex[:10]
    trades.append(t)
    storage.save_journal(trades)
    return _journal_response()


@app.put("/api/journal/{trade_id}")
def update_trade(trade_id: str, payload: dict = Body(...)):
    trades = storage.load_journal()
    for i, t in enumerate(trades):
        if t.get("id") == trade_id:
            trades[i] = _clean_trade(payload, t)
            storage.save_journal(trades)
            return _journal_response()
    raise HTTPException(404, "Trade non trovato")


@app.delete("/api/journal/{trade_id}")
def delete_trade(trade_id: str):
    trades = [t for t in storage.load_journal() if t.get("id") != trade_id]
    storage.save_journal(trades)
    return _journal_response()


@app.get("/api/journal.csv")
def journal_csv():
    buf = io.StringIO()
    cols = ["date", "time", "symbol", "side", "qty", "entry", "exit", "stop", "setup", "pnl_usd", "pnl_eur", "r_multiple", "commission_eur", "eurusd", "notes"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", delimiter=";")
    w.writeheader()
    for t in sorted(storage.load_journal(), key=lambda t: (t.get("date", ""), t.get("time", ""))):
        w.writerow(t)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=diario-trade.csv"},
    )


app.mount("/", StaticFiles(directory=str(storage.ROOT / "frontend"), html=True), name="frontend")
