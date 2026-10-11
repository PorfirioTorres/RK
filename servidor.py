"""Backend del asistente con personaje Live2D (versión 3).

Estructura de carpetas:
    servidor.py
    index.html
    modelo/            <- contenido de la carpeta "runtime" del modelo Live2D
    historial.json     <- se crea solo; guarda la conversación entre sesiones

Requisitos:
    pip install -r requirements.txt
    ollama pull qwen2.5:3b

Voz: usa edge-tts, que envía el texto de cada respuesta a un servicio online de
Microsoft para generar el audio (necesita internet; el modelo de lenguaje sigue siendo local).

Ejecutar (dentro de esta carpeta):
    uvicorn servidor:app --reload
Luego abre http://127.0.0.1:8000
"""

import json
import re
from pathlib import Path
from typing import Literal

import ollama
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import edge_tts
except ImportError:  # el chat funciona igual, solo sin voz
    edge_tts = None

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

# ---------- Configuración de la voz (edge-tts) ----------
# Otras voces en español: es-MX-JorgeNeural, es-ES-ElviraNeural, es-AR-ElenaNeural, es-CO-SalomeNeural
# Lista completa: en PowerShell ->  edge-tts --list-voices
VOZ = "en-US-AvaMultilingualNeural"
VOZ_VELOCIDAD = "+8%"   # "-10%" más lenta, "+20%" más rápida
VOZ_TONO = "+0Hz"       # "-10Hz" más grave, "+10Hz" más aguda

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


class TextoVoz(BaseModel):
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


@app.post("/voz")
async def voz(entrada: TextoVoz):
    """Convierte un texto en audio mp3 con edge-tts."""
    if edge_tts is None:
        raise HTTPException(503, "falta instalar edge-tts (pip install edge-tts)")
    # Quitar símbolos y emojis que el sintetizador leería en voz alta
    texto = re.sub(r"[*_~`#<>]+", "", entrada.texto)
    texto = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", texto).strip()[:600]
    if not texto:
        raise HTTPException(400, "texto vacío")
    try:
        comunicar = edge_tts.Communicate(texto, VOZ, rate=VOZ_VELOCIDAD, pitch=VOZ_TONO)
        audio = bytearray()
        async for trozo in comunicar.stream():
            if trozo["type"] == "audio":
                audio.extend(trozo["data"])
    except Exception as e:
        raise HTTPException(503, f"no pude generar la voz (¿hay internet?): {e}")
    if not audio:
        raise HTTPException(503, "el servicio de voz no devolvió audio")
    return Response(content=bytes(audio), media_type="audio/mpeg")


# Archivos del modelo Live2D (moc3, texturas, motions...)
app.mount("/modelo", StaticFiles(directory=CARPETA_MODELO), name="modelo")


@app.get("/")
def inicio():
    return FileResponse(BASE / "index.html")
