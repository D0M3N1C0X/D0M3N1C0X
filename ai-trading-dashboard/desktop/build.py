"""Costruisce l'app installabile con PyInstaller.

Uso (dalla cartella ai-trading-dashboard, sul sistema di destinazione):
    pip install -r requirements-desktop.txt
    python desktop/build.py

Risultato:
    Mac      dist/AI Momentum Desk.app
    Windows  dist/AI Momentum Desk/AI Momentum Desk.exe
PyInstaller non fa compilazioni incrociate: l'app per Mac si costruisce su un Mac,
quella per Windows su Windows (lo fa in automatico GitHub Actions).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
APP = "AI Momentum Desk"
VERSION = "0.2.0"


def main() -> None:
    os.chdir(ROOT)
    icon = ROOT / "desktop" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    args = [
        str(ROOT / "desktop_main.py"),
        "--name", APP,
        "--windowed",  # niente finestra del terminale
        "--noconfirm",
        "--clean",
        "--icon", str(icon),
        "--add-data", f"{ROOT / 'frontend'}{os.pathsep}frontend",
        "--collect-submodules", "backend",
        "--collect-submodules", "uvicorn",
        # moduli non usati che PyInstaller trascinerebbe se presenti nell'ambiente
        *[a for m in ("numpy", "PIL", "tkinter", "yaml", "matplotlib", "pandas", "pytest") for a in ("--exclude-module", m)],
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "io.github.d0m3n1c0x.aimomentumdesk"]
    PyInstaller.__main__.run(args)

    if sys.platform == "darwin":
        # versione mostrata in "Informazioni su" e nel Finder
        import plistlib

        plist = ROOT / "dist" / f"{APP}.app" / "Contents" / "Info.plist"
        data = plistlib.loads(plist.read_bytes())
        data.update(
            {
                "CFBundleShortVersionString": VERSION,
                "CFBundleVersion": VERSION,
                "NSHighResolutionCapable": True,
                "LSApplicationCategoryType": "public.app-category.finance",
                "NSHumanReadableCopyright": "Strumento di analisi, non consulenza finanziaria.",
            }
        )
        plist.write_bytes(plistlib.dumps(data))
        # la modifica di Info.plist invalida la firma ad-hoc: la rifacciamo
        os.system(f'codesign --force --deep --sign - "{ROOT / "dist" / (APP + ".app")}"')
    print(f"\nApp creata in {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
