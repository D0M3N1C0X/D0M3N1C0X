"""Punto di ingresso dell'app desktop (usato da PyInstaller). Avvio manuale: python desktop_main.py"""
import sys

from backend.desktop import main

if __name__ == "__main__":
    sys.exit(main())
