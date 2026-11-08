"""Avvia la dashboard e la apre nel browser. Uso: python -m backend.run"""
from __future__ import annotations

import os
import socket
import threading
import webbrowser

import uvicorn


def free_port(start: int = 8765) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("Nessuna porta libera tra 8765 e 8784.")


def main() -> None:
    port = int(os.environ.get("PORT") or free_port())
    url = f"http://127.0.0.1:{port}"
    print("\n  AI Momentum Desk")
    print(f"  Dashboard: {url}")
    print("  Per chiudere: chiudi questa finestra oppure premi Ctrl+C\n")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    # Solo 127.0.0.1: la dashboard è raggiungibile unicamente da questo computer.
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
