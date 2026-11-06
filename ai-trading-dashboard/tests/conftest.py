import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Ogni test usa una cartella dati vuota e la modalità demo."""
    monkeypatch.setenv("AITD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AITD_CONFIG", str(tmp_path / "config.env"))
    monkeypatch.setenv("DATA_PROVIDER", "demo")
    yield
