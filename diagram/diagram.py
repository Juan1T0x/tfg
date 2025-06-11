from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom                 # iconos personalizados
from diagrams.generic.database import SQL          # cilindro genérico de BD
from diagrams.onprem.compute import Server

#
#  NOTA: coloca flutter.png, opencv.png, leaguepedia.png, riot.png y youtube.png
#        en el mismo directorio que este script.
#

with Diagram("Moba Analysis – Arquitectura", direction="LR", show=False):
    # -------- Frontend (icono Flutter) --------------------------------------
    frontend = Custom("Flutter Web\n:8080", "./flutter.png")

    # -------- Backend -------------------------------------------------------
    with Cluster("Backend (Python)\n:8888  –   WebSocket"):
        # ── Módulos que hablan con APIs externas ────────────────────────────
        with Cluster("API Bridges"):
            riot_api   = Server("Riot_API")
            league_api = Server("Leaguepedia_API")

        # ── BBDD (cilindro) -------------------------------------------------
        sqlite_db = SQL("SQLite\nDB")        # cilindro genérico

        # ── Pipeline de vídeo ----------------------------------------------
        with Cluster("Video Pipeline"):
            video_proc   = Server("Video_Process")
            champ_detect = Custom("Champion_Detection", "./opencv.png")
            game_detect  = Custom("Game_Detection", "./opencv.png")

    # -------- APIs externas (iconos custom) ---------------------------------
    riot_ext   = Custom("Riot Games API",   "./riot.png")
    league_ext = Custom("Leaguepedia API",  "./leaguepedia.png")
    youtube    = Custom("YouTube",          "./youtube.png")

    # ================== FLUJOS PRINCIPALES ==================================

    # Frontend ⇄ Backend
    frontend >> Edge(label="WebSocket") >> video_proc
    champ_detect >> Edge(label="GameState") >> frontend
    game_detect  >> Edge(label="GameState") >> frontend

    # Frontend → YouTube (carga de vídeos)
    frontend >> Edge(style="dotted", label="video URL") >> youtube
    youtube  >> Edge(style="dotted", label="stream")    >> video_proc

    # Video pipeline
    video_proc  >> Edge(label="frames") >> champ_detect
    video_proc  >> Edge(label="frames") >> game_detect

    # Módulos de API → SQLite
    riot_api   >> sqlite_db
    league_api >> sqlite_db

    # API calls hacia fuera
    riot_api   >> Edge(style="dotted", label="HTTPS") >> riot_ext
    league_api >> Edge(style="dotted", label="HTTPS") >> league_ext
