@echo off
REM AI Momentum Desk - avvio per Windows (doppio clic)
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3 non trovato. Scaricalo da https://www.python.org/downloads/
  echo Durante l'installazione spunta "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo Primo avvio: preparo l'ambiente, serve circa un minuto...
  %PY% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Installazione dei componenti non riuscita: controlla la connessione a internet.
  pause
  exit /b 1
)
python -m backend.run
pause
