"""Control de música mediante simulación de teclas multimedia de Windows."""
import pyautogui

def ejecutar_accion(accion: str) -> bool:
    """
    Acciones: 'play_pause', 'next', 'prev', 'vol_up', 'vol_down', 'mute'
    """
    try:
        mapeo = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "prev": "prevtrack",
            "vol_up": "volumeup",
            "vol_down": "volumedown",
            "mute": "volumemute",
        }
        tecla = mapeo.get(accion)
        if tecla:
            pyautogui.press(tecla)
            return True
    except Exception:
        pass
    return False

def interpretar(texto: str):
    """
    Detecta órdenes de música.
    Ejemplos: 'pause the music', 'next song', 'sube el volumen'
    """
    import re
    t = texto.lower().strip()

    # Pausa / Play
    if re.search(r"\b(pause|play|stop|deten|para|continua)\b.*\b(music|song|cancion|audio)\b", t, re.I):
        return {"tipo": "musica", "accion": "play_pause"}

    # Siguiente / Anterior
    if re.search(r"\b(next|siguiente|skip)\b.*\b(song|music|cancion)\b", t, re.I):
        return {"tipo": "musica", "accion": "next"}
    if re.search(r"\b(previous|anterior|back)\b.*\b(song|music|cancion)\b", t, re.I):
        return {"tipo": "musica", "accion": "prev"}

    # Volumen
    if re.search(r"\b(up|sube|increase|más)\b.*\b(volume|volumen)\b", t, re.I):
        return {"tipo": "musica", "accion": "vol_up"}
    if re.search(r"\b(down|baja|decrease|menos)\b.*\b(volume|volumen)\b", t, re.I):
        return {"tipo": "musica", "accion": "vol_down"}
    if re.search(r"\b(mute|silencia)\b.*\b(volume|volumen)\b", t, re.I):
        return {"tipo": "musica", "accion": "mute"}

    return None

def texto_resultado(accion: str, exito: bool, idioma: str) -> str:
    mensajes = {
        "en": {
            "play_pause": "Music toggled.",
            "next": "Next song, coming up.",
            "prev": "Going back to the previous song.",
            "vol_up": "Volume increased.",
            "vol_down": "Volume decreased.",
            "mute": "Muted.",
        },
        "es": {
            "play_pause": "Música pausada o reanudada.",
            "next": "Siguiente canción.",
            "prev": "Canción anterior.",
            "vol_up": "Subí el volumen.",
            "vol_down": "Bajé el volumen.",
            "mute": "Silenciado.",
        }
    }
    return mensajes[idioma].get(accion, "Done.") if exito else "I couldn't do that."
