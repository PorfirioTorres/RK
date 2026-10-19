"""Control de aplicaciones, carpetas y sitios web mediante una lista permitida.
Permite abrir recursos del sistema de forma segura."""
import json
import subprocess
import webbrowser
from pathlib import Path

def cargar_permitidos(ruta_archivo: Path) -> dict:
    try:
        return json.loads(ruta_archivo.read_text(encoding="utf-8"))
    except Exception:
        return {"apps": {}, "folders": {}, "sites": {}}

def abrir_recurso(nombre: str, permitidos: dict) -> bool:
    # 1. Buscar en aplicaciones
    if nombre in permitidos["apps"]:
        try:
            subprocess.Popen(permitidos["apps"][nombre])
            return True
        except Exception:
            pass

    # 2. Buscar en carpetas
    if nombre in permitidos["folders"]:
        try:
            # 'explorer' abre la carpeta en Windows
            subprocess.Popen(f'explorer "{permitidos["folders"][nombre]}"')
            return True
        except Exception:
            pass

    # 3. Buscar en sitios web
    if nombre in permitidos["sites"]:
        try:
            webbrowser.open(permitidos["sites"][nombre])
            return True
        except Exception:
            pass

    return False

def interpretar(texto: str):
    """
    Detecta órdenes de abrir algo.
    Ejemplos: 'open chrome', 'abre mi carpeta de descargas', 'go to google'
    """
    import re
    t = texto.lower().strip()

    # Patrones: "open X", "abre X", "go to X", "lanza X"
    patron = re.compile(r"^\s*(?:open|abre|go\s+to|lanza|inicia)\s+(?P<recurso>.+)$", re.I)
    m = patron.search(t)
    if not m:
        return None

    recurso = m["recurso"].strip()
    # Limpiar palabras comunes como "the", "my", "mi"
    recurso = re.sub(r"\b(the|my|mi|la|el|una|un)\b", "", recurso).strip()

    return {"tipo": "abrir", "recurso": recurso}

def texto_resultado(exito: bool, recurso: str, idioma: str) -> str:
    if idioma == "en":
        return f"Done. I've opened {recurso} for you." if exito else f"Sorry, {recurso} is not in my allowed list."
    return f"Listo. He abierto {recurso}." if exito else f"Lo siento, {recurso} no está en mi lista de permitidos."
