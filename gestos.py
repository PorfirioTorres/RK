"""Gestión de gestos y animaciones de Ryuko.
Permite disparar movimientos específicos basados en el estado o comandos."""
import random

# Mapeo de gestos disponibles en el modelo Live2D
# Estos nombres deben coincidir con los motions definidos en el modelo .moc3
GESTOS = {
    "saludar": "motion_wave",
    "estirarse": "motion_stretch",
    "bostezar": "motion_yawn",
    "enojada": "motion_angry",
    "pensativa": "motion_think",
    "feliz": "motion_happy"
}

def obtener_gesto_aleatorio() -> str | None:
    """Devuelve un gesto al azar para que Ryuko no parezca estática."""
    return random.choice(list(GESTOS.values()))

def interpretar_gesto(texto: str) -> str | None:
    """
    Detecta si el usuario pide un gesto específico.
    Ejemplos: 'wave to me', 'bosteza', 'salúdame'
    """
    import re
    t = texto.lower().strip()

    mapeo_comandos = {
        "saludar": [r"wave", r"saluda\w*"],
        "estirarse": [r"stretch", r"estira\w*"],
        "bostezar": [r"yawn", r"bosteza\w*"],
    }

    for gesto, patrones in mapeo_comandos.items():
        for p in patrones:
            if re.search(p, t, re.I):
                return GESTOS[gesto]

    return None
