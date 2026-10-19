"""Lógica para el Modo Concentración y Ánimo según la hora.
Permite que Ryuko detecte si el usuario está en pantalla completa y ajuste su comportamiento."""
import time
from datetime import datetime
try:
    import win32gui
    import win32api
except ImportError:
    win32gui = None
    win32api = None

def es_hora_dormir() -> bool:
    """Retorna True si es madrugada (entre las 2 AM y las 7 AM)."""
    hora = datetime.now().hour
    return 2 <= hora < 7

def es_hora_animada() -> bool:
    """Retorna True si es tarde/noche (entre las 4 PM y las 10 PM)."""
    hora = datetime.now().hour
    return 16 <= hora < 22

def obtener_comentario_horario(idioma: str) -> str | None:
    """Devuelve un comentario basado en la hora actual."""
    hora = datetime.now().hour
    if 0 <= hora < 6:
        return "You're still awake? Go to sleep!" if idioma == "en" else "¡¿Sigues despierto?! ¡Vete a dormir!"
    if 23 <= hora <= 23:
        return "It's getting late... you should rest." if idioma == "en" else "Se está haciendo tarde... deberías descansar."
    return None

def detectar_pantalla_completa() -> bool:
    """
    Detecta si la ventana activa ocupa toda la pantalla.
    """
    if win32gui is None or win32api is None:
        return False

    try:
        # Obtener el handle de la ventana activa
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False

        # Obtener coordenadas de la ventana activa
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect

        # Obtener resolución de la pantalla
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)

        # Comprobar si la ventana cubre el área total de la pantalla
        # Se permite un pequeño margen de error por bordes invisibles
        return (x <= 0 and y <= 0 and
                (x2 - x) >= screen_width - 10 and
                (y2 - y) >= screen_height - 10)
    except Exception:
        return False
