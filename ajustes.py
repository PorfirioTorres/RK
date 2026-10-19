"""Gestión de ajustes y respaldos del sistema.
Permite guardar configuraciones globales y realizar copias de seguridad de los datos del usuario."""
import json
import shutil
import os
from pathlib import Path
from datetime import datetime

def cargar_ajustes(ruta: Path) -> dict:
    """Carga los ajustes desde el archivo settings.json."""
    try:
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        pass
    # Ajustes por defecto
    return {
        "idioma": "en",
        "volumen": 1.0,
        "voz_estilo": "neutral",
        "reacciones_activas": True
    }

def guardar_ajustes(ruta: Path, ajustes: dict):
    """Guarda los ajustes en el archivo settings.json."""
    try:
        ruta.write_text(json.dumps(ajustes, indent=1, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False

def crear_respaldo(carpeta_datos: Path, carpeta_destino: Path) -> list[str]:
    """
    Copia los archivos JSON críticos a una carpeta de respaldo con fecha.
    Retorna la lista de archivos respaldados.
    """
    archivos_criticos = ["memoria.json", "notas.json", "recordatorios.json", "historial.json"]
    respaldados = []

    try:
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_respaldo = carpeta_destino / f"backup_{fecha}"
        ruta_respaldo.mkdir(parents=True, exist_ok=True)

        for archivo in archivos_criticos:
            ruta_orig = carpeta_datos / archivo
            if ruta_orig.exists():
                shutil.copy(ruta_orig, ruta_respaldo / archivo)
                respaldados.append(archivo)

        return respaldados
    except Exception as e:
        print(f"Error creando respaldo: {e}")
        return []
