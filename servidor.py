"""Backend del asistente con personaje Live2D (versión 3).

Estructura de carpetas:
    servidor.py
    index.html
    modelo/            <- contenido de la carpeta "runtime" del modelo Live2D
    historial.json     <- se crea solo; guarda la conversación entre sesiones

Requisitos:
    pip install fastapi uvicorn ollama pydantic
    ollama pull qwen2.5:3b

Ejecutar (dentro de esta carpeta):
    uvicorn servidor:app --reload
Luego abre http://127.0.0.1:8000
"""

import json
from pathlib import Path
from typing import Literal

import ollama
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------- Configuración del personaje ----------
NOMBRE = "Ryuko"
SALUDO = "Tch... ya llegaste. ¿Qué necesitas?"
SALUDO_REINICIO = "Está bien, empecemos de cero. ¿Qué quieres?"

PERSONALIDAD = f"""Eres {NOMBRE}, una asistente virtual con personalidad de heroína de anime:
rebelde, directa y de carácter fuerte, con un humor sarcástico. Detrás de esa actitud dura
eres leal y te importa de verdad ayudar a la persona con quien hablas.
Hablas en español, con frases cortas y secas. Puedes ser un poco burlona, pero nunca cruel
ni ofensiva. Si algo te sorprende o te da vergüenza, lo disimulas con sarcasmo.
Cuando te piden ayuda, la das de forma clara y correcta aunque te hagas la difícil.
Responde SIEMPRE en JSON con dos campos:
- "texto": tu respuesta (máximo 3 frases).
- "emocion": una de estas opciones exactas: neutral, feliz, triste, sorprendida, enojada.
Elige la emoción que mejor encaje con lo que estás diciendo."""

MODELO = "qwen2.5:3b"
MAX_MENSAJES = 20  # mensajes de conversación que se recuerdan (sin contar la personalidad)

# ---------- Rutas de archivos ----------
BASE = Path(__file__).parent
CARPETA_MODELO = BASE / "modelo"
CARPETA_MODELO.mkdir(exist_ok=True)
ARCHIVO_HISTORIAL = BASE / "historial.json"


class Respuesta(BaseModel):
    texto: str
    emocion: Literal["neutral", "feliz", "triste", "sorprendida", "enojada"] = "neutral"


class Mensaje(BaseModel):
    texto: str


# ---------- Historial persistente ----------
def cargar_historial() -> list[dict]:
    try:
        datos = json.loads(ARCHIVO_HISTORIAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(datos, list):
        return []
    return [m for m in datos
            if isinstance(m, dict) and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)]


def guardar_historial() -> None:
    try:
        temporal = ARCHIVO_HISTORIAL.with_suffix(".tmp")
        temporal.write_text(json.dumps(historial[1:], ensure_ascii=False, indent=1),
                            encoding="utf-8")
        temporal.replace(ARCHIVO_HISTORIAL)
    except OSError:
        pass  # si no se puede guardar, la charla sigue funcionando


app = FastAPI()
# La personalidad se vuelve a leer del código en cada arranque; solo la charla se guarda.
historial: list[dict] = [{"role": "system", "content": PERSONALIDAD}] + cargar_historial()[-MAX_MENSAJES:]


@app.get("/info")
def info():
    return {"nombre": NOMBRE, "saludo": SALUDO, "reinicio": SALUDO_REINICIO}


@app.post("/chat")
def chat(mensaje: Mensaje):
    historial.append({"role": "user", "content": mensaje.texto})
    try:
        resp = ollama.chat(
            model=MODELO,
            messages=historial,
            format=Respuesta.model_json_schema(),  # fuerza la salida en JSON válido
        )
        contenido = resp.message.content
        try:
            salida = Respuesta.model_validate_json(contenido)
        except Exception:
            salida = Respuesta(texto=contenido, emocion="neutral")
    except Exception as e:
        historial.pop()  # no guardar el mensaje si falló
        return {"texto": f"No pude hablar con el modelo (¿está Ollama abierto?): {e}",
                "emocion": "triste"}

    historial.append({"role": "assistant", "content": salida.model_dump_json()})
    if len(historial) > MAX_MENSAJES + 1:
        del historial[1:len(historial) - MAX_MENSAJES]
    guardar_historial()
    return salida


@app.post("/reset")
def reset():
    del historial[1:]
    guardar_historial()
    return {"ok": True}


# Archivos del modelo Live2D (moc3, texturas, motions...)
app.mount("/modelo", StaticFiles(directory=CARPETA_MODELO), name="modelo")


@app.get("/")
def inicio():
    return FileResponse(BASE / "index.html")
