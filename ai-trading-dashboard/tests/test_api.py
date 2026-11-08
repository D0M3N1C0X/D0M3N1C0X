from fastapi.testclient import TestClient


def client():
    from backend.main import app, state

    state.reload()
    return TestClient(app)


def test_scan_chart_news_in_demo():
    c = client()
    d = c.get("/api/scan").json()
    assert d["provider"]["name"] == "demo"
    assert len(d["rows"]) == 22 and {b["symbol"] for b in d["benchmarks"]} == {"SPY", "QQQ", "SMH"}
    assert all(r["last"] for r in d["rows"])
    ch = c.get("/api/chart", params={"symbol": "NVDA", "tf": "5Min"}).json()
    assert ch["candles"] and ch["rsi"] and ch["levels"]["symbol"] == "NVDA"
    assert c.get("/api/chart", params={"symbol": "NVDA", "tf": "2Min"}).status_code == 400
    assert c.get("/api/chart", params={"symbol": "../etc"}).status_code == 400
    n = c.get("/api/news").json()
    assert "summary" in n


def test_settings_and_watchlist_validation():
    c = client()
    s = c.get("/api/settings").json()
    s["watchlist"] = [{"name": "Test", "symbols": ["nvda", "NVDA", "mrvl"]}]
    r = c.put("/api/settings", json={"watchlist": s["watchlist"]}).json()
    assert r["watchlist"] == [{"name": "Test", "symbols": ["NVDA", "MRVL"]}]
    assert c.put("/api/settings", json={"watchlist": [{"name": "x", "symbols": ["<script>"]}]}).status_code == 400


def test_journal_flow_and_csv():
    c = client()
    j = c.post("/api/journal", json={"symbol": "nvda", "side": "long", "qty": 10, "entry": 100, "stop": 99}).json()
    t = j["trades"][0]
    assert t["symbol"] == "NVDA" and t["pnl_eur"] is None and j["daily"]["open_trades"] == 1
    j = c.put(f"/api/journal/{t['id']}", json={"exit": 102}).json()
    assert j["trades"][0]["r_multiple"] == 2.0 and j["stats"]["closed"] == 1
    csv = c.get("/api/journal.csv").text
    assert csv.startswith("date;time;symbol") and "NVDA" in csv
    j = c.delete(f"/api/journal/{t['id']}").json()
    assert j["trades"] == []


def test_risk_endpoint():
    c = client()
    r = c.post("/api/risk/position", json={"entry": 50, "stop": 49, "eurusd": 1}).json()
    assert r["ok"] and r["shares"] == 50  # limitato dal 25% di posizione massima (2500/50)


def test_provider_switch_without_keys_falls_back_to_demo(monkeypatch):
    monkeypatch.delenv("DATA_PROVIDER")
    c = client()
    r = c.post("/api/provider", json={"DATA_PROVIDER": "alpaca"}).json()
    assert r["info"]["name"] == "demo" and not r["check"]["ok"]
    assert "chiavi" in r["check"]["message"]
    r = c.post("/api/provider", json={"DATA_PROVIDER": "demo"}).json()
    assert r["check"]["ok"]
