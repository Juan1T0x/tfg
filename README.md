MOBA Analysis App
=================

The project is an end-to-end toolkit that **scrapes live-game data from League of Legends VODs, stores / visualises the results, and serves them through a REST API plus a Flutter web UI**.

moba_analysis_app/
├── backend ← FastAPI service + computer-vision & data-science pipeline
└── frontend ← Flutter web client that consumes the REST API

---------------------------------------------------------------------------
1 · Backend (FastAPI + Python)
---------------------------------------------------------------------------

WHAT IT DOES
* Downloads YouTube (or generic) videos with *yt-dlp* and extracts frames via FFmpeg.
* Detects champions, health / mana bars and HUD statistics in real time.
* Builds a live **game-state timeline** and writes it as JSON.
* Generates gold / CS-difference plots and positional heat-maps.
* Persists and exposes everything through a clean, versioned REST API.
* Ships with automatic Riot-API synchronisation (patch versions, champions, images).

PREREQUISITES
* Python 3.11 or newer
* FFmpeg available in your `PATH`
* (Recommended) a *virtual environment* to isolate dependencies.

INSTALLATION
```bash
# from the repo root
cd backend

# 1) create & activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\Activate.ps1     # PowerShell / Windows

# 2) install third-party libraries
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

RUNNING THE SERVER
```bash
python main.py --reload
```
* --reload enables auto-reloading during development.
* API root: http://localhost:8888
* Interactive OpenAPI docs: http://localhost:8888/docs

---------------------------------------------------------------------------
2 · Frontend (Flutter)
---------------------------------------------------------------------------

The web client consumes the FastAPI endpoints and offers a clean UI for:
* Triggering video-analysis pipelines.
* Browsing match timelines and visualisations.
* Displaying champion & patch information pulled from the backend.

REQUIREMENTS
* Flutter SDK (stable channel) installed and in your PATH.

RUNNING THE WEB APP
```bash
cd frontend
flutter pub get

# Default (random port assigned by Flutter)
flutter run -d web-server

# Custom port, e.g. 8080
flutter run -d web-server --web-port 8080
```
Open the printed URL (e.g. http://localhost:8080/#/) in your browser.
Make sure the backend is already running on port 8888; the frontend expects it there by default.

---------------------------------------------------------------------------
3 · Putting it all together
---------------------------------------------------------------------------

1. Start the backend
```bash
python main.py --reload
```
2. Start the Flutter web server
```bash
flutter run -d web-server
```
3. Browse to the frontend URL and enjoy the app
