import sys
from pathlib import Path

from backend import desktop, storage
from backend.run import free_port


def test_installed_app_uses_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("AITD_DATA_DIR")
    monkeypatch.delenv("AITD_CONFIG")
    monkeypatch.setattr(storage, "FROZEN", True)
    monkeypatch.setattr(storage, "user_data_dir", lambda: tmp_path / "AI Momentum Desk")
    assert storage.data_dir() == tmp_path / "AI Momentum Desk"
    assert storage.config_path() == tmp_path / "AI Momentum Desk" / "config.env"


def test_user_data_dir_per_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert storage.user_data_dir() == Path.home() / "Library" / "Application Support" / "AI Momentum Desk"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "C:/Users/x/AppData/Roaming")
    assert storage.user_data_dir() == Path("C:/Users/x/AppData/Roaming") / "AI Momentum Desk"


def test_server_thread_and_selftest():
    port = free_port(8890)
    srv = desktop.ServerThread(port)
    srv.start()
    try:
        assert desktop.selftest(f"http://127.0.0.1:{port}/") == 0
    finally:
        srv.stop()
    assert not srv.thread.is_alive()


def test_bridge_info_and_notify(monkeypatch):
    b = desktop.Bridge()
    assert b.info()["desktop"] is True
    monkeypatch.setattr(sys, "platform", "win32")
    assert b.notify("NVDA", "Rottura ORH") is False
