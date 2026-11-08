#!/bin/bash
# AI Momentum Desk - avvio per macOS (doppio clic) e Linux.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Scaricalo da https://www.python.org/downloads/ e riprova."
  read -r -p "Premi Invio per chiudere..."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Primo avvio: preparo l'ambiente (serve circa un minuto)..."
  python3 -m venv .venv || { echo "Impossibile creare l'ambiente Python."; read -r -p "Premi Invio..."; exit 1; }
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || {
  echo "Installazione dei componenti non riuscita: controlla la connessione a internet."
  read -r -p "Premi Invio per chiudere..."
  exit 1
}
python -m backend.run
