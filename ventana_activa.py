"""Lógica para detectar la ventana activa y generar comentarios basados en la aplicación en uso."""
import win32gui
import re

# Mapeo de palabras clave en el título de la ventana -> Comentarios de Ryuko
# Formato: "palabra": { "en": "comentario", "es": "comentario" }
COMENTARIOS_APPS = {
    "chrome": {
        "en": "Still browsing the web? Try to be productive for once.",
        "es": "Todavía navegando por la web... intenta ser productivo por una vez."
    },
    "spotify": {
        "en": "Nice music. But I bet my taste is better.",
        "es": "Buena música. Pero apuesto a que mi gusto es mejor."
    },
    "visual studio code": {
        "en": "Coding again? Don't forget to sleep, programmer.",
        "es": "Programando otra vez... no te olvides de dormir, programador."
    },
    "notepad": {
        "en": "Writing notes in Notepad? How primitive.",
        "es": "Escribiendo notas en el Bloc de notas... qué primitivo."
    },
    "game": {
        "en": "Playing games? Fine, but don't come crying to me when you lose.",
        "es": "Jugando? Está bien, pero no vengas a llorarme cuando pierdas."
    },
    "discord": {
        "en": "Talking to friends? Don't ignore me too much.",
        "es": "Hablando con amigos... no me ignores demasiado."
    }
}

def obtener_ventana_activa() -> str:
    """Devuelve el título de la ventana que está actualmente en primer plano."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            return win32gui.GetWindowText(hwnd)
    except Exception:
        pass
    return ""

def obtener_comentario_app(titulo: str, idioma: str) -> str | None:
    """Busca si el título de la ventana coincide con alguna app conocida y devuelve un comentario."""
    if not titulo:
        return None

    titulo_low = titulo.lower()
    for app, textos in COMENTARIOS_APPS.items():
        if app in titulo_low:
            return textos.get(idioma)

    return None
