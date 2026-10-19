"""Gestión del portapapeles: permite leer el texto copiado para procesarlo con el modelo.
Se integra en el flujo de respuesta del servidor."""
import pyperclip

def obtener_texto_copiado() -> str:
    """Lee el contenido actual del portapapeles."""
    try:
        texto = pyperclip.paste()
        return texto.strip() if texto else ""
    except Exception:
        return ""

def interpretar(texto: str):
    """
    Detecta si el usuario quiere que Ryuko analice el portapapeles.
    Ejemplos: 'explain what I copied', 'traduce lo que copié', 'what is this in my clipboard?'
    """
    import re
    t = texto.lower().strip()

    # Patrones: "lo que copié", "portapapeles", "clipboard"
    patrones = [
        r"\b(explain|explícame|resume|summarize)\b.*\b(copied|copié|clipboard|portapapeles)\b",
        r"\b(translate|traduce)\b.*\b(copied|copié|clipboard|portapapeles)\b",
        r"\b(what is|qué es)\b.*\b(copied|copié|clipboard|portapapeles)\b",
        r"\b(clipboard|portapapeles)\b.*\b(read|lee|analiza|explain|explica)\b",
    ]

    for p in patrones:
        if re.search(p, t, re.I):
            return {"tipo": "portapapeles", "accion": "analizar"}

    return None
