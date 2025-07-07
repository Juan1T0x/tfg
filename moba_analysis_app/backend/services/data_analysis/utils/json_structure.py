import json, sys
from pathlib import Path

# Script para imprimir la estructura de un JSON de timeline de Riot Games.

def main(json_path):
    try:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"❌ Error al decodificar el JSON: {e}")
    except FileNotFoundError:
        sys.exit(f"❌ El archivo '{json_path}' no existe.")
    except Exception as e:
        sys.exit(f"❌ Error inesperado: {e}")

    # Imprimimos el primer nivel de claves del JSON
    print("Primer nivel de claves:")
    for key in data.keys():
        print(f"- {key}")
    print("Claves de un frame:")
    for key in data.get("frames", [{}])[1].keys():
        print(f"- {key}")
    print("Claves de un event:") # Recorreremos todos los events del documento e imprimiremos todas las claves distintas
    events = set()
    for frame in data.get("frames", []):
        for event in frame.get("events", []):
            events.update(event.keys())
    for key in sorted(events):
        print(f"- {key}")


    # Para la clave type de events, imprimimos todos los valores distintos
    event_types = set()
    for frame in data.get("frames", []):
        for event in frame.get("events", []):
            event_types.add(event.get("type", "Desconocido"))
    print("Valores distintos de 'type' en events:")
    for event_type in sorted(event_types):
        print(f"- {event_type}")

    print("Claves de un participantFrames:") # Recorreremos todos los participantFrames del documento e imprimiremos todas las claves distintas
    participant_frames = set()
    for frame in data.get("frames", []):
        for participant_frame in frame.get("participantFrames", {}).values():
            participant_frames.update(participant_frame.keys())
    for key in sorted(participant_frames):
        print(f"- {key}")
        
    print("Valor del segundo timestamp:")
    print(data.get("frames", [{}])[1].get("timestamp", "No disponible"))
    
if __name__ == "__main__":
    main(sys.argv[1])