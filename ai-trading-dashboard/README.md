# AI Momentum Desk

Dashboard per il **day trading momentum/breakout** sui titoli legati all'intelligenza artificiale: chip, memorie, Big Tech e software AI.

![Dashboard](docs/dashboard.jpg)

*Nello screenshot: modalità demo, con dati simulati.*

## Cosa fa

| Area | Cosa trovi |
|---|---|
| **Scanner momentum** | Prezzo, variazione, gap d'apertura, **volume relativo (RVOL)**, distanza dal VWAP, forza relativa rispetto all'ETF dei semiconduttori (SMH) e segnali di rottura per ogni titolo della watchlist. Ordinato per forza del momentum. |
| **Grafico intraday** | Candele a 1, 5 e 15 minuti con VWAP, EMA 9/20, volumi, RSI e MACD. Le linee tratteggiate segnano i livelli chiave: range d'apertura (ORH/ORL), premarket (PMH/PML) e giorno precedente (PDH/PDL/PDC). |
| **Segnali e avvisi** | Rottura del range d'apertura, del massimo di ieri, del premarket e il *Setup long/short* completo (rottura + VWAP + volume + trend). Gli avvisi arrivano con suono e notifica, e puoi impostare avvisi su un prezzo. |
| **Notizie** | Notizie per titolo o per tutta la watchlist, con un sentiment indicativo (positivo, neutro o negativo) e le parole chiave che lo determinano. |
| **Rischio** | Calcolatore della posizione: rischi l'1% del conto (o la percentuale che scegli), inserisci entrata e stop, e la dashboard ti dice **quante azioni comprare**, con gli obiettivi a 1R, 2R e 3R. Il conto è in euro, i titoli in dollari: il cambio è gestito. |
| **Stop giornaliero** | Se la perdita del giorno raggiunge il limite (predefinito -3%), la dashboard te lo segnala in rosso. |
| **Diario trade** | Registri entrate e uscite e ottieni P&L in euro, multiplo di R, % di trade vincenti, profit factor e risultati per tipo di setup. Esportabile in CSV (si apre con Excel). |

Gli orari sono in **ora italiana**. La dashboard **non invia ordini**: gli ordini li inserisci tu su Directa.

---

## Installazione

Ci sono due modi per usarla:

| | **App installabile** (consigliata) | **Da cartella** |
|---|---|---|
| Come si apre | Icona nel Dock o nel menu Start, finestra propria | Doppio clic su `avvia.command` / `avvia.bat`, si apre nel browser |
| Serve Python | No | Sì |
| Sistemi | Mac con chip Apple (M1 e successivi), Windows 10/11 | Mac (anche Intel), Windows, Linux |

### A. App installabile

**1. Scarica l'app.** Su GitHub apri la scheda **Actions** del repository, poi il workflow **"AI Momentum Desk - app desktop"** e l'ultima esecuzione con la spunta verde. In fondo, nella sezione **Artifacts**, scarica:
- `AI-Momentum-Desk-macOS` per Mac
- `AI-Momentum-Desk-Windows` per Windows

GitHub lo scarica come zip che contiene un altro zip: estrai il primo, poi il secondo. Se è stata pubblicata una **Release**, puoi scaricare lo zip direttamente da lì.

**2. Installa e apri.**

**Mac:**
1. Trascina **AI Momentum Desk.app** nella cartella **Applicazioni**.
2. Al primo avvio macOS mostra un avviso, perché l'app non è firmata con un certificato Apple a pagamento. Premi **Fine**, poi apri **Impostazioni di Sistema → Privacy e sicurezza**, scorri in basso e premi **Apri comunque** accanto ad "AI Momentum Desk". Conferma con la password del Mac.

   In alternativa, dal Terminale:
   ```
   xattr -dr com.apple.quarantine "/Applications/AI Momentum Desk.app"
   ```
3. Dalla seconda volta si apre normalmente, anche dal Launchpad o dal Dock.

**Windows:**
1. Sposta la cartella **AI Momentum Desk** dove preferisci (per esempio in Documenti) e apri **AI Momentum Desk.exe**. Per comodità, fai clic destro e scegli **Aggiungi a Start** o **Crea collegamento**.
2. Se compare "Windows ha protetto il PC", premi **Ulteriori informazioni → Esegui comunque**. Succede perché l'app non è firmata digitalmente.
3. La finestra usa Microsoft Edge WebView2, già presente in Windows 10 e 11 aggiornati.

**Dove sono i tuoi dati.** L'app salva impostazioni, diario e chiavi nella cartella dati del sistema:
- **Mac:** `~/Library/Application Support/AI Momentum Desk`
- **Windows:** `%APPDATA%\AI Momentum Desk`

In **Impostazioni** c'è il pulsante **Apri cartella dati**. Se usavi già la versione da cartella, copia lì dentro `config.env` e i file `settings.json` e `journal.json` della cartella `data/`. Aggiornando l'app i dati restano dove sono.

Nell'app le notifiche degli avvisi arrivano nel **Centro notifiche** del Mac. Su Windows compaiono nella finestra, con il suono.

### B. Da cartella (con Python)

1. **Installa Python 3** da **https://www.python.org/downloads/**. Su Windows spunta **"Add python.exe to PATH"** durante l'installazione.
2. **Scarica il progetto:** su GitHub premi **Code → Download ZIP**, estrai e apri la cartella `ai-trading-dashboard`.
3. **Avvia:**
   - **Mac:** doppio clic su **`avvia.command`**. Se macOS lo blocca, fai clic destro, scegli **Apri** e conferma.
   - **Windows:** doppio clic su **`avvia.bat`**.
   - **Linux:** `./avvia.sh`

Il primo avvio richiede circa un minuto, poi il browser si apre su `http://127.0.0.1:8765`. **Lascia aperta la finestra nera** finché usi la dashboard.

All'inizio, in entrambi i casi, la dashboard è in **modalità demo** con dati simulati, così puoi provare tutto subito.

---

## Collegare i dati reali (Alpaca, gratuito)

Alpaca offre gratuitamente prezzi in tempo reale, grafici e notizie sulle azioni USA.

1. Crea un account gratuito su **https://alpaca.markets**. Basta il conto **Paper Trading** (simulato): non devi depositare soldi.
2. Nel pannello di Alpaca cerca la sezione **API Keys** e genera una nuova chiave. Ottieni due codici: **API Key ID** e **Secret Key**. Copia subito la Secret, perché Alpaca la mostra una sola volta.
3. Nella dashboard vai in **Impostazioni → Fonte dati**:
   - Fonte: **Alpaca**
   - incolla **API Key ID** e **Secret Key**
   - Feed: **IEX (gratuito)**
   - premi **Salva e collega**. Se compare "Connesso ad Alpaca", hai finito.

> **Da sapere:** con il feed gratuito IEX i volumi arrivano da una sola borsa, quindi sono più bassi di quelli che vedi su Directa. Il **volume relativo resta affidabile**, perché confronta numeri della stessa fonte. Per i volumi completi serve il feed SIP, a pagamento.

Le chiavi restano **solo sul tuo computer**, nel file `config.env`. Non condividerlo e non caricarlo su GitHub (è già escluso).

**Alternativa senza registrazione:** in Impostazioni puoi scegliere **Yahoo Finance**. Non serve nessuna chiave, ma è un servizio non ufficiale: i dati possono essere in ritardo e a volte smette di funzionare.

---

## Come usarla in una giornata di trading

| Ora italiana | Cosa fare |
|---|---|
| **10:00 – 15:30** premarket | Guarda lo scanner: titoli con **gap** e **RVOL** alto, più le **notizie**. Sono i candidati del giorno. Imposta avvisi di prezzo sui livelli chiave. |
| **15:30 – 15:45** | Lascia formare il **range d'apertura** (15 minuti, modificabile). Non inseguire le prime candele. |
| **Dalle 15:45** | Aspetta il segnale **Setup long/short**, oppure la rottura di ORH/PDH/PMH con volume. Nel calcolatore usa i pulsanti dei livelli (VWAP, ORL…) come stop: la dashboard ti dice quante azioni comprare. Inserisci l'ordine su Directa. |
| **Dopo l'uscita** | Chiudi il trade nel **Diario**. Se compare il blocco dello **stop giornaliero**, per oggi hai finito. |
| **22:00** | Chiusura. Rileggi il diario: quali setup funzionano davvero per te? |

Quando gli orari legali di USA ed Europa non coincidono (alcune settimane in marzo e tra ottobre e novembre), il mercato apre alle 14:30 italiane. La dashboard lo gestisce in automatico.

La scheda **Guida** della dashboard spiega ogni colonna, livello e segnale.

---

## Impostazioni principali

Si cambiano dalla scheda **Impostazioni**, senza toccare codice:

- **Watchlist:** gruppi di titoli modificabili. All'inizio: chip (NVDA, AMD, AVGO, TSM, MRVL, ARM, MU, SMCI), memorie (SNDK, WDC, STX), Big Tech (MSFT, GOOGL, META, AMZN, AAPL) e software AI (PLTR, SNOW, AI, PATH, SOUN, BBAI).
- **Rischio:** capitale in €, rischio per trade (1%), perdita massima giornaliera (3%), posizione massima (25% del capitale), commissioni Directa per ordine, cambio EUR/USD (con aggiornamento dalla BCE).
- **Scanner:** durata del range d'apertura (5, 15 o 30 minuti), soglie di RVOL e di gap, frequenza di aggiornamento.
- **Avvisi:** quali segnali fanno suonare l'avviso, notifiche del browser.

---

## Privacy e sicurezza

- La dashboard gira **solo sul tuo computer**: è raggiungibile solo dall'indirizzo `127.0.0.1` e nessun altro dispositivo in rete può aprirla.
- Impostazioni, diario e chiavi sono salvati sul tuo computer: nella cartella del progetto (`data/` e `config.env`, esclusi da Git) oppure, nell'app, nella cartella dati del sistema.
- Le uniche connessioni esterne sono verso la fonte dati che scegli e, se premi "Aggiorna (BCE)", verso la Banca Centrale Europea per il cambio.

---

## Prossimi passi (app completa)

- Firma digitale delle app (certificato Apple Developer e Windows), così non compaiono gli avvisi di sicurezza al primo avvio.
- Versione per Mac Intel.
- Integrazione con **Directa** tramite la piattaforma Darwin, da valutare sulla documentazione ufficiale delle API Directa.
- Grafico giornaliero e multi-giorno, heatmap del settore AI, calendario delle trimestrali.
- Statistiche del diario per fascia oraria e per titolo, con grafico dell'equity.

---

## Per sviluppatori

```
backend/            server Python (FastAPI)
  main.py           API: /api/scan, /api/chart, /api/news, /api/journal, /api/settings, ...
  scanner.py        livelli, RVOL e segnali momentum
  indicators.py     EMA, RSI, MACD, VWAP, ATR
  risk.py           dimensionamento della posizione, stop giornaliero, statistiche
  sentiment.py      sentiment delle notizie per parole chiave
  market.py         orari e festività NYSE, fusi orari
  providers/        alpaca.py, yahoo.py, demo.py (dati simulati)
frontend/           HTML/CSS/JS senza build; grafici con TradingView Lightweight Charts (Apache 2.0)
  desktop.py        app desktop: finestra nativa (pywebview) + server in background
desktop/            build.py (PyInstaller), icone, make_icons.py
desktop_main.py     punto di ingresso dell'app
tests/              test automatici (pytest)
```

Per costruire l'app sul proprio computer (quella per Mac si costruisce su un Mac, quella per Windows su Windows):

```
pip install -r requirements-desktop.txt
python desktop/build.py              # crea dist/AI Momentum Desk(.app)
python desktop_main.py --selftest    # verifica server e API senza aprire la finestra
```

Il workflow `.github/workflows/desktop-app.yml` fa tutto questo in automatico, su Mac e su Windows, a ogni modifica.

Per eseguire i test:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

---

> **Avvertenza.** Questo è uno strumento di analisi, non un consiglio di investimento. I segnali sono regole tecniche automatiche e non garantiscono risultati. Il day trading è ad alto rischio e può comportare la perdita del capitale. Le decisioni di trading restano tue.
