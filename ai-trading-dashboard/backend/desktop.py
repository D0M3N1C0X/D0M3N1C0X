"""App desktop: la dashboard in una finestra nativa, senza terminale né browser.

Usa pywebview (WebKit su Mac, Edge WebView2 su Windows). Il server della dashboard
gira in un thread interno su 127.0.0.1, su una porta libera.

Opzioni (per test e diagnostica):
  --selftest   avvia il server, controlla le API principali ed esce (0 = ok)
  AITD_SMOKE_OUT=<file>  apre la finestra, verifica che lo scanner si riempia,
                         scrive l'esito in <file> e chiude
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from . import storage
from .run import free_port

log = logging.getLogger("aimd.desktop")


def _setup_logging() -> Path:
    """Nell'app installata non c'è una console: tutto finisce in app.log nella cartella dati."""
    path = storage.data_dir() / "app.log"
    if storage.FROZEN or sys.stdout is None:
        f = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 (resta aperto per tutta l'esecuzione)
        sys.stdout = sys.stderr = f
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    return path


class ServerThread:
    """Il server FastAPI della dashboard, in un thread in background."""

    def __init__(self, port: int):
        import uvicorn

        from .main import app

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="dashboard-server", daemon=True)

    def start(self, timeout: float = 30) -> None:
        self.thread.start()
        deadline = time.time() + timeout
        while not self.server.started:
            if not self.thread.is_alive() or time.time() > deadline:
                raise RuntimeError("Il server della dashboard non è partito (vedi app.log).")
            time.sleep(0.05)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


class Bridge:
    """Funzioni del sistema chiamabili dalla pagina come window.pywebview.api.<nome>()."""

    def __init__(self) -> None:
        self._window = None  # assegnata dopo create_window (non esposta a JavaScript)

    def info(self) -> dict:
        return {"desktop": True, "platform": sys.platform, "data_dir": str(storage.data_dir())}

    def save_csv(self, filename: str, content: str) -> dict:
        import webview

        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=filename, file_types=("File CSV (*.csv)",)
        )
        if not result:
            return {"ok": False}
        path = result if isinstance(result, str) else result[0]
        # BOM UTF-8: Excel riconosce correttamente accenti e simbolo dell'euro
        Path(path).write_text(content, encoding="utf-8-sig")
        return {"ok": True, "path": str(path)}

    def notify(self, title: str, body: str) -> bool:
        """Notifica di sistema. Su Mac usa il Centro notifiche; altrove la pagina mostra il proprio avviso."""
        if sys.platform != "darwin":
            return False
        clean = lambda s: " ".join(str(s).split())[:200]  # noqa: E731
        script = (
            f"display notification {json.dumps(clean(body), ensure_ascii=False)} "
            f"with title {json.dumps(clean(title), ensure_ascii=False)}"
        )
        try:
            subprocess.Popen(["osascript", "-e", script])
            return True
        except OSError:
            return False

    def open_data_folder(self) -> str:
        path = str(storage.data_dir())
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
        return path


def selftest(base_url: str) -> int:
    """Verifica che il pacchetto contenga tutto: interfaccia, API e dati demo."""
    checks = {
        "pagina": base_url,
        "grafici": base_url + "vendor/lightweight-charts.standalone.production.js",
        "meta": base_url + "api/meta",
        "scanner": base_url + "api/scan",
        "grafico": base_url + "api/chart?symbol=NVDA&tf=5Min",
        "diario": base_url + "api/journal",
    }
    ok = True
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 127.0.0.1: mai tramite proxy
    for name, url in checks.items():
        try:
            with opener.open(url, timeout=60) as r:
                body = r.read()
            if name == "scanner":
                rows = json.loads(body)["rows"]
                assert rows and all(row["last"] for row in rows), "scanner vuoto"
            if name == "pagina":
                assert b"AI Momentum Desk" in body
            print(f"OK   {name}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"ERR  {name}: {e}")
    print("SELFTEST", "OK" if ok else "FALLITO")
    return 0 if ok else 1


def _smoke(window, out_path: str) -> None:
    """Test automatico della finestra: lo scanner deve mostrare dei titoli."""
    result = {"loaded": False, "rows": 0, "error": None}
    try:
        result["loaded"] = window.events.loaded.wait(60)
        for _ in range(60):
            time.sleep(1)
            n = window.evaluate_js("document.querySelectorAll('#scanner tbody tr[data-sym]').length")
            result["rows"] = int(n or 0)
            if result["rows"]:
                break
        result["bridge"] = bool(window.evaluate_js("!!(window.pywebview && window.pywebview.api)"))
    except Exception as e:  # noqa: BLE001
        result["error"] = repr(e)
    Path(out_path).write_text(json.dumps(result), encoding="utf-8")
    window.destroy()


def main() -> int:
    log_path = _setup_logging()
    log.info("Avvio %s (dati in %s)", storage.APP_NAME, storage.data_dir())
    port = free_port()
    server = ServerThread(port)
    server.start()
    url = f"http://127.0.0.1:{port}/"

    if "--selftest" in sys.argv:
        code = selftest(url)
        server.stop()
        return code

    try:
        import webview
    except ImportError:
        log.warning("pywebview non disponibile: apro la dashboard nel browser")
        webbrowser.open(url)
        try:
            server.thread.join()
        except KeyboardInterrupt:
            pass
        return 0

    bridge = Bridge()
    window = webview.create_window(
        storage.APP_NAME,
        url,
        js_api=bridge,
        width=1600,
        height=1000,
        min_size=(1000, 680),
        background_color="#0d0f12",
        text_select=True,
    )
    bridge._window = window
    smoke_out = os.environ.get("AITD_SMOKE_OUT")
    try:
        webview.start(
            _smoke if smoke_out else None,
            (window, smoke_out) if smoke_out else None,
            private_mode=False,  # conserva tema, titolo selezionato e preferenze della pagina
            storage_path=str(storage.data_dir() / "webview"),
        )
    except Exception:  # noqa: BLE001
        # Finestra nativa non disponibile (es. WebView2 mancante su Windows): ripiego sul browser.
        log.error("Finestra nativa non disponibile, apro il browser:\n%s", traceback.format_exc())
        webbrowser.open(url)
        server.thread.join()
    server.stop()
    log.info("Chiuso. Log: %s", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
