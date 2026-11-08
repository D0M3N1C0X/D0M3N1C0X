"""Calcolo della dimensione della posizione e del rischio giornaliero.

Il conto e' in euro (come su Directa), i titoli USA sono in dollari: si converte con EUR/USD.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Optional


def position_size(
    capital_eur: float,
    risk_pct: float,
    entry: float,
    stop: float,
    eurusd: float,
    max_position_pct: float = 100.0,
    commission_eur: float = 0.0,
    atr: Optional[float] = None,
) -> dict:
    """Quante azioni comprare (o vendere allo scoperto) per rischiare al massimo `risk_pct` del capitale."""
    warnings: list[str] = []
    if capital_eur <= 0 or entry <= 0 or stop <= 0 or eurusd <= 0:
        return {"ok": False, "error": "Inserisci capitale, prezzo di entrata, stop e cambio EUR/USD maggiori di zero."}
    if entry == stop:
        return {"ok": False, "error": "Lo stop deve essere diverso dal prezzo di entrata."}

    direction = "long" if stop < entry else "short"
    risk_per_share = abs(entry - stop)
    risk_budget_eur = capital_eur * risk_pct / 100
    # Le commissioni (entrata + uscita) riducono il rischio disponibile per il prezzo.
    budget_for_price_eur = max(0.0, risk_budget_eur - 2 * commission_eur)
    budget_usd = budget_for_price_eur * eurusd

    shares_by_risk = math.floor(budget_usd / risk_per_share) if risk_per_share > 0 else 0
    max_value_usd = capital_eur * max_position_pct / 100 * eurusd
    shares_by_size = math.floor(max_value_usd / entry)
    shares = max(0, min(shares_by_risk, shares_by_size))
    limited_by = "rischio" if shares_by_risk <= shares_by_size else "dimensione massima della posizione"

    if shares == 0:
        warnings.append("Con questi parametri non puoi comprare nemmeno un'azione: stop troppo largo o rischio troppo basso.")
    stop_pct = risk_per_share / entry * 100
    if stop_pct < 0.15:
        warnings.append("Stop molto stretto (meno dello 0,15%): rischi di essere stoppato dal semplice rumore del prezzo.")
    if atr and risk_per_share > atr * 0.5:
        warnings.append("Lo stop supera metà dell'ATR giornaliero: per un day trade è molto largo.")
    if shares_by_size < shares_by_risk:
        warnings.append("La posizione è limitata dalla dimensione massima, non dal rischio.")

    value_usd = shares * entry
    actual_risk_eur = shares * risk_per_share / eurusd + 2 * commission_eur if shares else 0.0
    sign = 1 if direction == "long" else -1
    targets = [
        {"r": r, "price": round(entry + sign * r * risk_per_share, 2), "profit_eur": round(shares * r * risk_per_share / eurusd - 2 * commission_eur, 2)}
        for r in (1, 2, 3)
    ]
    return {
        "ok": True,
        "direction": direction,
        "shares": shares,
        "risk_per_share": round(risk_per_share, 4),
        "stop_pct": round(stop_pct, 2),
        "risk_budget_eur": round(risk_budget_eur, 2),
        "actual_risk_eur": round(actual_risk_eur, 2),
        "position_value_usd": round(value_usd, 2),
        "position_value_eur": round(value_usd / eurusd, 2),
        "position_pct": round(value_usd / eurusd / capital_eur * 100, 1),
        "limited_by": limited_by,
        "targets": targets,
        "warnings": warnings,
    }


def trade_pnl(trade: dict) -> dict:
    """P&L in dollari, in euro (al netto commissioni) e multiplo di R di un trade chiuso."""
    entry, exit_, qty = trade.get("entry"), trade.get("exit"), trade.get("qty")
    if entry in (None, "") or exit_ in (None, "") or not qty:
        return {"pnl_usd": None, "pnl_eur": None, "r_multiple": None}
    sign = 1 if trade.get("side", "long") == "long" else -1
    pnl_usd = (float(exit_) - float(entry)) * float(qty) * sign
    fx = float(trade.get("eurusd") or 1) or 1
    pnl_eur = pnl_usd / fx - 2 * float(trade.get("commission_eur") or 0)
    r = None
    stop = trade.get("stop")
    if stop not in (None, "") and float(stop) != float(entry):
        r = (float(exit_) - float(entry)) * sign / abs(float(entry) - float(stop))
    return {"pnl_usd": round(pnl_usd, 2), "pnl_eur": round(pnl_eur, 2), "r_multiple": None if r is None else round(r, 2)}


def daily_status(trades: list[dict], risk: dict, today: date) -> dict:
    """P&L del giorno e controllo dello stop giornaliero."""
    todays = [t for t in trades if t.get("date") == today.isoformat()]
    closed = [t for t in todays if t.get("pnl_eur") is not None]
    pnl = round(sum(t["pnl_eur"] for t in closed), 2)
    max_loss = round(float(risk["capital_eur"]) * float(risk["daily_loss_pct"]) / 100, 2)
    max_trades = int(risk.get("max_trades_per_day") or 0)
    reasons = []
    if pnl <= -max_loss:
        reasons.append(f"Hai raggiunto la perdita massima giornaliera ({max_loss:.0f} EUR).")
    if max_trades and len(todays) >= max_trades:
        reasons.append(f"Hai raggiunto il numero massimo di trade per oggi ({max_trades}).")
    wins = [t for t in closed if t["pnl_eur"] > 0]
    return {
        "date": today.isoformat(),
        "pnl_eur": pnl,
        "max_loss_eur": max_loss,
        "remaining_eur": round(max_loss + pnl, 2) if pnl < 0 else max_loss,
        "trades": len(todays),
        "open_trades": len(todays) - len(closed),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "locked": bool(reasons),
        "reasons": reasons,
        "used_pct": round(min(100.0, max(0.0, -pnl / max_loss * 100)) if max_loss else 0.0, 1),
    }


def journal_stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("pnl_eur") is not None]
    if not closed:
        return {"closed": 0}
    wins = [t["pnl_eur"] for t in closed if t["pnl_eur"] > 0]
    losses = [t["pnl_eur"] for t in closed if t["pnl_eur"] <= 0]
    rs = [t["r_multiple"] for t in closed if t.get("r_multiple") is not None]
    by_setup: dict[str, dict] = {}
    for t in closed:
        s = by_setup.setdefault(t.get("setup") or "Altro", {"trades": 0, "pnl_eur": 0.0, "wins": 0})
        s["trades"] += 1
        s["pnl_eur"] = round(s["pnl_eur"] + t["pnl_eur"], 2)
        s["wins"] += 1 if t["pnl_eur"] > 0 else 0
    return {
        "closed": len(closed),
        "total_pnl_eur": round(sum(t["pnl_eur"] for t in closed), 2),
        "win_rate": round(len(wins) / len(closed) * 100, 1),
        "avg_win_eur": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss_eur": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
        "by_setup": by_setup,
    }
