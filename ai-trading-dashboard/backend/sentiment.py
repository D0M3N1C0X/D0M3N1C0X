"""Sentiment indicativo dei titoli delle notizie (in inglese), basato su parole chiave.

E' volutamente semplice e trasparente: per ogni notizia mostra le parole che hanno
determinato il punteggio. Non sostituisce la lettura della notizia.
"""
from __future__ import annotations

import re

POSITIVE = {
    "beat": 2, "beats": 2, "tops": 2, "surge": 2, "surges": 2, "soar": 2, "soars": 2, "jump": 1, "jumps": 1,
    "rally": 1, "rallies": 1, "record": 1, "upgrade": 2, "upgrades": 2, "upgraded": 2, "raise": 1, "raises": 1,
    "raised": 1, "boost": 1, "boosts": 1, "strong": 1, "stronger": 1, "growth": 1, "partnership": 1, "partner": 1,
    "deal": 1, "contract": 1, "wins": 1, "win": 1, "approval": 1, "approved": 1, "buyback": 2, "outperform": 2,
    "bullish": 2, "expands": 1, "expand": 1, "expansion": 1, "launch": 1, "launches": 1, "gain": 1, "gains": 1,
    "higher": 1, "exceeds": 2, "accelerates": 1, "demand": 1, "breakthrough": 2, "overweight": 1, "buy": 1,
    "climbs": 1, "rises": 1, "optimistic": 1, "profit": 1, "investment": 1, "invests": 1,
}
NEGATIVE = {
    "miss": 2, "misses": 2, "missed": 2, "plunge": 2, "plunges": 2, "tumble": 2, "tumbles": 2, "fall": 1, "falls": 1,
    "drop": 1, "drops": 1, "slump": 2, "slumps": 2, "sink": 1, "sinks": 1, "downgrade": 2, "downgrades": 2,
    "downgraded": 2, "cut": 1, "cuts": 1, "weak": 1, "weaker": 1, "lawsuit": 2, "sues": 2, "probe": 2,
    "investigation": 2, "ban": 2, "bans": 2, "restriction": 1, "restrictions": 2, "tariff": 1, "tariffs": 1,
    "delay": 1, "delays": 1, "delayed": 1, "recall": 2, "bearish": 2, "selloff": 2, "sell-off": 2, "warning": 2,
    "warns": 2, "layoffs": 1, "fraud": 3, "short": 1, "resigns": 1, "loss": 1, "losses": 1, "lower": 1,
    "concerns": 1, "fears": 1, "underperform": 2, "underweight": 1, "sell": 1, "decline": 1, "declines": 1,
    "halt": 2, "halted": 2, "dilution": 2, "offering": 1, "bubble": 1, "slowdown": 1,
}
NEGATIONS = {"not", "no", "never", "without", "fails", "despite"}
WORD = re.compile(r"[a-z][a-z\-']*")


def score_text(text: str) -> dict:
    words = WORD.findall((text or "").lower())
    score = 0
    hits: list[str] = []
    for i, w in enumerate(words):
        val = POSITIVE.get(w, 0) - NEGATIVE.get(w, 0)
        if not val:
            continue
        if any(p in NEGATIONS for p in words[max(0, i - 2): i]):
            val = -val
        score += val
        hits.append(w)
    if score >= 2:
        label = "positivo"
    elif score <= -2:
        label = "negativo"
    elif score == 1:
        label = "leggermente positivo"
    elif score == -1:
        label = "leggermente negativo"
    else:
        label = "neutro"
    return {"score": score, "label": label, "keywords": hits}


def annotate(item: dict) -> dict:
    s = score_text(item.get("headline", "") + ". " + item.get("headline", "") + ". " + (item.get("summary") or ""))
    # il titolo pesa il doppio del sommario
    return {**item, "sentiment": s}


def summarize(items: list[dict]) -> dict:
    if not items:
        return {"count": 0, "label": "nessuna notizia", "score": 0}
    total = sum(i["sentiment"]["score"] for i in items)
    pos = sum(1 for i in items if i["sentiment"]["score"] > 0)
    neg = sum(1 for i in items if i["sentiment"]["score"] < 0)
    avg = total / len(items)
    label = "positivo" if avg >= 1 else "negativo" if avg <= -1 else "misto/neutro"
    return {"count": len(items), "positive": pos, "negative": neg, "score": round(avg, 2), "label": label}
