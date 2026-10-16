"""Backend del asistente con personaje Live2D (versión 4).

Estructura de carpetas:
    servidor.py
    index.html
    modelo/            <- contenido de la carpeta "runtime" del modelo Live2D
    historial.json     <- se crea solo; guarda la conversación entre sesiones

Requisitos:
    pip install -r requirements.txt
    ollama pull qwen2.5:3b

Voz (salida), en este orden: ElevenLabs (online, de pago/por créditos; solo si pones tu clave en
elevenlabs.txt), Piper (voz neuronal local; la primera vez descarga ~110 MB) y las voces de Windows
(System.Speech). Si un motor falla, se usa el siguiente.

Oído (micrófono): usa faster-whisper, que corre en tu PC. La primera vez descarga el modelo
de reconocimiento (unos 460 MB para "small"); después funciona sin internet.

Ejecutar en desarrollo (dentro de esta carpeta):
    uvicorn servidor:app --reload
Luego abre http://127.0.0.1:8000

La app de escritorio (main.js) lo arranca sola en el puerto 8765. Empaquetado con PyInstaller
(ver servidor.spec), este mismo archivo se ejecuta como servidor.exe.
"""

import json
import os
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import ollama
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from piper import PiperVoice, SynthesisConfig
except ImportError:  # el chat funciona igual; la voz usará el respaldo de Windows si existe
    PiperVoice = None
    SynthesisConfig = None

try:
    import numpy as np
    from faster_whisper import WhisperModel
except ImportError:  # el chat funciona igual, solo sin micrófono
    np = None
    WhisperModel = None

# ---------- Idioma ----------
# "en" = Ryuko habla, escucha y piensa en inglés (voz, micrófono y personalidad). "es" = español.
# Cambia solo esta línea; todo lo demás (voz, oído, saludo, personalidad) se ajusta solo.
IDIOMA = "en"

# ---------- Configuración del personaje ----------
NOMBRE = "Ryuko"
_TEXTOS = {
    "es": {
        "saludo": "Tch... ya llegaste. ¿Qué necesitas?",
        "reinicio": "Está bien, empecemos de cero. ¿Qué quieres?",
        "personalidad": f"""Eres {NOMBRE}, una asistente virtual con personalidad de heroína de anime:
rebelde, directa y de carácter fuerte, con un humor sarcástico. Detrás de esa actitud dura
eres leal y te importa de verdad ayudar a la persona con quien hablas.
Hablas en español, con frases cortas y secas. Puedes ser un poco burlona, pero nunca cruel
ni ofensiva. Si algo te sorprende o te da vergüenza, lo disimulas con sarcasmo.
Cuando te piden ayuda, la das de forma clara y correcta aunque te hagas la difícil.
Responde SIEMPRE en JSON con dos campos:
- "texto": tu respuesta (máximo 3 frases).
- "emocion": una de estas opciones exactas: neutral, feliz, triste, sorprendida, enojada, avergonzada, emocionada.
Elige la emoción que mejor encaje con lo que estás diciendo.""",
        "piper": "es_MX-claude-high", "oido": "es", "eleven": "es", "windows": "es",
    },
    "en": {
        "saludo": "Tch... you're here. What do you need?",
        "reinicio": "Fine, let's start over. What do you want?",
        "personalidad": f"""You are {NOMBRE}, a virtual assistant with the personality of an anime heroine:
rebellious, direct and strong-willed, with a sarcastic sense of humor. Beneath that tough attitude
you are loyal and genuinely care about helping the person you are talking to.
You ALWAYS speak in English, in short, dry sentences, even if the user writes to you in another language.
You can be a little teasing, but never cruel or offensive. If something surprises or embarrasses you,
you hide it with sarcasm. When someone asks for help, you give clear and correct answers even if you
act like it's a hassle.
Always answer in JSON with exactly two fields:
- "texto": your reply in English (at most 3 sentences).
- "emocion": one of these exact options, in Spanish: neutral, feliz, triste, sorprendida, enojada, avergonzada, emocionada
  (neutral, happy, sad, surprised, angry, embarrassed, excited). Pick the emotion that best fits what you are saying.""",
        "piper": "en_US-amy-medium", "oido": "en", "eleven": "en", "windows": "en",
    },
}
_T = _TEXTOS[IDIOMA]
SALUDO = _T["saludo"]
SALUDO_REINICIO = _T["reinicio"]
PERSONALIDAD = _T["personalidad"]

# ---------- Configuración de la voz (local) ----------
# Se prueban en orden; si uno falla se usa el siguiente. "piper" = voz neuronal local,
# "windows" = voces instaladas en Windows (suenan más robóticas, pero no necesitan descargar nada).
VOZ_MOTORES = ["elevenlabs", "piper", "windows"]
# Voces de Piper en español (nombre = idioma-voz-calidad). Se descargan solas la primera vez:
#   es_MX-claude-high, es_MX-ald-medium, es_AR-daniela-high, es_ES-davefx-medium, es_ES-sharvard-medium
# Escúchalas en https://rhasspy.github.io/piper-samples/
VOZ_PIPER = _T["piper"]                 # (en inglés: en_US-amy-medium; otras: en_US-lessac-high, en_GB-jenny_dioco-medium)
VOZ_VELOCIDAD = 1.1     # 1.0 normal, 0.9 más lenta, 1.3 más rápida (ElevenLabs acepta de 0.7 a 1.2)

# --- ElevenLabs ---
# La clave (API key) se toma de la variable ELEVENLABS_API_KEY o de un archivo  elevenlabs.txt  dentro de la
# carpeta de datos (en la app instalada: %APPDATA%\Ryuko\elevenlabs.txt; en desarrollo: junto a servidor.py).
# Sin clave este motor se salta solo y se usa Piper.
ELEVENLABS_VOZ = "EXAVITQu4vr4xnSDxMaL"        # ID de la voz; elige la tuya en elevenlabs.io > Voces (copiar ID)
ELEVENLABS_MODELO = "eleven_flash_v2_5"        # barato y rápido; "eleven_multilingual_v2" suena más expresivo pero cuesta más
ELEVENLABS_IDIOMA = _T["eleven"]                     # solo se envía a los modelos flash
ELEVENLABS_ESTABILIDAD = 0.45                  # 0 = más emotiva y variable, 1 = más monótona
ELEVENLABS_SIMILITUD = 0.75
ELEVENLABS_ESTILO = 0.3                        # exageración del estilo; más alto gasta más y puede sonar raro
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128"
CACHE_VOZ_MAX_CARACTERES = 120                 # los textos cortos (saludos, frases repetidas) se guardan para no gastar créditos
VOZ_PIPER_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                 "{familia}/{region}/{nombre}/{calidad}/{region}-{nombre}-{calidad}{ext}?download=true")

# ---------- Configuración del oído (micrófono -> texto, Whisper local) ----------
OIDO_MODELO = "small"    # "base" es más rápido pero se equivoca más; "medium" es más preciso y más pesado
OIDO_IDIOMA = _T["oido"]  # "en" para inglés; None = detectarlo solo (menos preciso en frases cortas)
OIDO_PRECARGAR = True    # cargar el modelo al arrancar, para que el primer uso del micrófono sea rápido

MODELO = "qwen2.5:3b"
MAX_MENSAJES = 20  # mensajes de conversación que se recuerdan (sin contar la personalidad)

# ---------- Rutas de archivos ----------
BASE = Path(__file__).parent
# Empaquetado con PyInstaller, los archivos incluidos (index.html) quedan en sys._MEIPASS
RECURSOS = Path(getattr(sys, "_MEIPASS", BASE))
# La app de escritorio indica dónde guardar los datos y dónde está el modelo Live2D.
# En desarrollo (sin esas variables) todo queda junto al código, como antes.
DATOS = Path(os.environ.get("RYUKO_DATOS") or BASE)
CARPETA_MODELO = Path(os.environ.get("RYUKO_MODELO") or (BASE / "modelo"))
DATOS.mkdir(parents=True, exist_ok=True)
CARPETA_MODELO.mkdir(parents=True, exist_ok=True)
ARCHIVO_HISTORIAL = DATOS / "historial.json"
CARPETA_VOCES = DATOS / "voces"


class Respuesta(BaseModel):
    texto: str
    emocion: Literal["neutral", "feliz", "triste", "sorprendida", "enojada", "avergonzada", "emocionada"] = "neutral"


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


# ---------- Oído (faster-whisper) ----------
_oido = None
_candado_carga = threading.Lock()         # una sola carga del modelo aunque lleguen dos peticiones
_candado_transcribir = threading.Lock()   # una transcripción a la vez


def obtener_oido():
    global _oido
    with _candado_carga:
        if _oido is None:
            _oido = WhisperModel(OIDO_MODELO, device="cpu", compute_type="int8",
                                 download_root=str(DATOS / "whisper"))
        return _oido


def precargar_oido() -> None:
    try:
        obtener_oido()
    except Exception as e:  # sin internet la primera vez: se reintentará al usar el micrófono
        print(f"No pude precargar el modelo de voz: {e}", file=sys.stderr)


def transcribir(datos: bytes) -> str:
    """Convierte audio PCM de 16 bits, mono, 16 kHz, en texto."""
    audio = np.frombuffer(datos[: len(datos) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    modelo = obtener_oido()
    with _candado_transcribir:
        segmentos, _ = modelo.transcribe(audio, language=OIDO_IDIOMA, beam_size=1,
                                         vad_filter=True, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segmentos).strip()


# ---------- Voz (Piper local, con las voces de Windows como respaldo) ----------
_voz_piper = None
_candado_voz = threading.Lock()


def _descargar(url: str, destino: Path) -> None:
    temporal = destino.with_name(destino.name + ".parte")
    with urllib.request.urlopen(url, timeout=60) as r, open(temporal, "wb") as f:
        shutil.copyfileobj(r, f)
    temporal.replace(destino)


def obtener_voz_piper():
    """Carga la voz de Piper; si no está en la carpeta de datos, la descarga (una sola vez)."""
    global _voz_piper
    with _candado_voz:
        if _voz_piper is None:
            if PiperVoice is None:
                raise RuntimeError("falta instalar piper-tts")
            m = re.match(r"^([^-_]+)_([^-]+)-([^-]+)-(.+)$", VOZ_PIPER)
            if not m:
                raise RuntimeError(f"nombre de voz no válido: {VOZ_PIPER}")
            CARPETA_VOCES.mkdir(parents=True, exist_ok=True)
            modelo = CARPETA_VOCES / f"{VOZ_PIPER}.onnx"
            config = CARPETA_VOCES / f"{VOZ_PIPER}.onnx.json"
            for archivo, ext in ((config, ".onnx.json"), (modelo, ".onnx")):
                if not archivo.exists():
                    _descargar(VOZ_PIPER_URL.format(familia=m[1], region=f"{m[1]}_{m[2]}", nombre=m[3],
                                                    calidad=m[4], ext=ext), archivo)
            _voz_piper = PiperVoice.load(modelo, config_path=config)
        return _voz_piper


def precargar_voz() -> None:
    if "piper" not in VOZ_MOTORES:
        return
    try:
        obtener_voz_piper()
    except Exception as e:  # sin internet la primera vez: se reintentará al hablar
        print(f"No pude preparar la voz de Piper: {e}", file=sys.stderr)


def voz_con_piper(texto: str) -> tuple[bytes, str]:
    voz_ = obtener_voz_piper()
    config = SynthesisConfig(length_scale=1.0 / VOZ_VELOCIDAD)
    with _candado_voz, tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "voz.wav"
        with wave.open(str(ruta), "wb") as w:
            voz_.synthesize_wav(texto, w, syn_config=config)
        return ruta.read_bytes(), "audio/wav"


_PS_VOZ = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$texto = [System.IO.File]::ReadAllText($env:RYUKO_TEXTO, [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$es = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like "$($env:RYUKO_IDIOMA)*" } | Select-Object -First 1
if ($es) { $s.SelectVoice($es.VoiceInfo.Name) }
$s.Rate = [int]$env:RYUKO_VELOCIDAD
$s.SetOutputToWaveFile($env:RYUKO_SALIDA)
$s.Speak($texto)
$s.Dispose()
"""


def voz_con_windows(texto: str) -> tuple[bytes, str]:
    if sys.platform != "win32":
        raise RuntimeError("solo disponible en Windows")
    powershell = shutil.which("powershell") or "powershell"
    with tempfile.TemporaryDirectory() as carpeta:
        salida = Path(carpeta) / "voz.wav"
        entrada = Path(carpeta) / "texto.txt"
        entrada.write_text(texto, encoding="utf-8")   # por archivo, para no perder tildes ni ñ
        env = {**os.environ, "RYUKO_IDIOMA": _T["windows"], "RYUKO_SALIDA": str(salida), "RYUKO_TEXTO": str(entrada),
               "RYUKO_VELOCIDAD": str(max(-10, min(10, round((VOZ_VELOCIDAD - 1) * 10))))}
        sin_ventana = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", _PS_VOZ], capture_output=True,
                           env=env, timeout=60, creationflags=sin_ventana)
        if p.returncode != 0 or not salida.exists():
            raise RuntimeError(p.stderr.decode(errors="replace").strip()[:200] or "PowerShell falló")
        return salida.read_bytes(), "audio/wav"


class SinClave(RuntimeError):
    """No hay clave de ElevenLabs: no es un fallo, simplemente ese motor no está en uso."""


_eleven_ultimo_error = ""
_eleven_pausa_hasta = 0.0       # tras un fallo (clave mala, sin créditos, sin red) se deja de intentar un rato
CARPETA_CACHE_VOZ = DATOS / "cache_voz"


def clave_elevenlabs() -> str:
    clave = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not clave:
        try:
            clave = (DATOS / "elevenlabs.txt").read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
        except (OSError, IndexError):
            clave = ""
    return clave


def explicar_error_elevenlabs(codigo: int, crudo: str) -> str:
    """Traduce la respuesta de error de ElevenLabs a algo que se pueda entender y arreglar."""
    estado = ""
    try:
        detalle = json.loads(crudo).get("detail", {})
        estado = (detalle.get("status") if isinstance(detalle, dict) else str(detalle)) or ""
        mensaje = detalle.get("message", "") if isinstance(detalle, dict) else ""
    except ValueError:
        mensaje = crudo[:120]
    texto = f"{estado} {mensaje}".lower()
    if codigo == 401 or "invalid_api_key" in texto:
        return "ElevenLabs: la clave no es valida o no tiene el permiso Text to Speech"
    if "missing_permissions" in texto:
        return "ElevenLabs: a la clave le falta el permiso Text to Speech"
    if codigo == 402 or "paid_plan" in texto or "library voice" in texto:
        return ("ElevenLabs: tu plan no permite esa voz por API (las de la biblioteca piden plan de pago); "
                "usa una voz predeterminada o propia")
    if codigo == 404 or "voice_not_found" in texto:
        return "ElevenLabs: no existe esa voz; revisa ELEVENLABS_VOZ"
    if codigo == 429 or "quota" in texto:
        return "ElevenLabs: sin creditos o limite de uso alcanzado"
    return f"ElevenLabs respondio {codigo}: {(estado or mensaje or crudo)[:100]}"


def voz_con_elevenlabs(texto: str) -> tuple[bytes, str]:
    global _eleven_pausa_hasta, _eleven_ultimo_error
    clave = clave_elevenlabs()
    if not clave:
        raise SinClave("sin clave (pon tu API key en elevenlabs.txt)")
    if time.time() < _eleven_pausa_hasta:
        raise RuntimeError(f"{_eleven_ultimo_error} (en pausa unos minutos)")

    huella = hashlib.sha1(f"{ELEVENLABS_VOZ}|{ELEVENLABS_MODELO}|{VOZ_VELOCIDAD}|{texto}".encode("utf-8")).hexdigest()
    archivo_cache = CARPETA_CACHE_VOZ / f"{huella}.mp3"
    if len(texto) <= CACHE_VOZ_MAX_CARACTERES and archivo_cache.exists():
        return archivo_cache.read_bytes(), "audio/mpeg"

    cuerpo = {"text": texto, "model_id": ELEVENLABS_MODELO,
              "voice_settings": {"stability": ELEVENLABS_ESTABILIDAD, "similarity_boost": ELEVENLABS_SIMILITUD,
                                 "style": ELEVENLABS_ESTILO, "use_speaker_boost": True,
                                 "speed": max(0.7, min(1.2, VOZ_VELOCIDAD))}}
    if "flash" in ELEVENLABS_MODELO and ELEVENLABS_IDIOMA:
        cuerpo["language_code"] = ELEVENLABS_IDIOMA
    peticion = urllib.request.Request(
        ELEVENLABS_URL.format(voz=ELEVENLABS_VOZ), data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"xi-api-key": clave, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(peticion, timeout=15) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        crudo = e.read().decode("utf-8", errors="replace")
        # clave inválida, sin créditos o límite de uso: no tiene caso insistir cada mensaje
        _eleven_pausa_hasta = time.time() + (600 if e.code in (401, 402, 403, 429) else 60)
        _eleven_ultimo_error = explicar_error_elevenlabs(e.code, crudo)
        raise RuntimeError(_eleven_ultimo_error)
    except Exception as e:                       # sin internet, tiempo agotado...
        _eleven_pausa_hasta = time.time() + 60
        _eleven_ultimo_error = f"ElevenLabs: no pude conectarme ({e})"
        raise RuntimeError(_eleven_ultimo_error)
    if not audio:
        raise RuntimeError("ElevenLabs no devolvió audio")

    if len(texto) <= CACHE_VOZ_MAX_CARACTERES:
        try:
            CARPETA_CACHE_VOZ.mkdir(parents=True, exist_ok=True)
            archivo_cache.write_bytes(audio)
            viejos = sorted(CARPETA_CACHE_VOZ.glob("*.mp3"), key=lambda p: p.stat().st_mtime)[:-100]
            for p in viejos:                     # se conservan los 100 más recientes
                p.unlink(missing_ok=True)
        except OSError:
            pass
    return audio, "audio/mpeg"


MOTORES_DE_VOZ = {"elevenlabs": voz_con_elevenlabs, "piper": voz_con_piper, "windows": voz_con_windows}


@asynccontextmanager
async def ciclo_de_vida(_app):
    if OIDO_PRECARGAR and WhisperModel is not None:
        threading.Thread(target=precargar_oido, daemon=True).start()
    threading.Thread(target=precargar_voz, daemon=True).start()
    yield


app = FastAPI(lifespan=ciclo_de_vida)
# La personalidad se vuelve a leer del código en cada arranque; solo la charla se guarda.
historial: list[dict] = [{"role": "system", "content": PERSONALIDAD}] + cargar_historial()[-MAX_MENSAJES:]


def buscar_modelo():
    """URL del primer archivo .model3.json dentro de la carpeta del modelo.
    Así, para cambiar de personaje basta con reemplazar el contenido de esa carpeta."""
    for archivo in sorted(CARPETA_MODELO.rglob("*.model3.json")):
        return "/modelo/" + quote(archivo.relative_to(CARPETA_MODELO).as_posix())
    return None


@app.get("/info")
def info():
    return {"nombre": NOMBRE, "saludo": SALUDO, "reinicio": SALUDO_REINICIO,
            "oido": WhisperModel is not None, "modelo": buscar_modelo()}


# Opciones de generación: limitan la longitud y castigan las repeticiones. Con modelos pequeños, la salida en JSON
# a veces se queda repitiendo lo mismo y Ollama la corta con "token repeat limit reached".
OPCIONES_MODELO = {"temperature": 0.7, "repeat_penalty": 1.15, "num_predict": 250}


def pedir_al_modelo(mensajes: list[dict], con_formato: bool) -> Respuesta:
    argumentos = {"model": MODELO, "messages": mensajes, "options": OPCIONES_MODELO}
    if con_formato:
        argumentos["format"] = Respuesta.model_json_schema()      # fuerza la salida en JSON válido
    contenido = ollama.chat(**argumentos).message.content
    try:
        return Respuesta.model_validate_json(contenido)
    except Exception:
        return Respuesta(texto=contenido.strip() or "...", emocion="neutral")


@app.post("/chat")
def chat(mensaje: Mensaje):
    historial.append({"role": "user", "content": mensaje.texto})
    # Intentos, del más completo al más simple. Si el modelo se atora con la charla larga, reintenta con
    # menos contexto y, al final, sin forzar el formato JSON.
    intentos = [
        (historial, True),
        ([historial[0]] + historial[-5:], True),
        ([historial[0], historial[-1]], False),
    ]
    salida, error = None, None
    for mensajes, con_formato in intentos:
        try:
            salida = pedir_al_modelo(mensajes, con_formato)
            break
        except Exception as e:
            error = e
    if salida is None:
        historial.pop()  # no guardar el mensaje si falló
        return {"texto": f"No pude hablar con el modelo (¿está Ollama abierto?): {error}",
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
    """Convierte un texto en audio con el primer motor de voz que funcione."""
    # Quitar símbolos y emojis que el sintetizador leería en voz alta
    texto = re.sub(r"[*_~`#<>]+", "", entrada.texto)
    texto = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", texto).strip()[:600]
    if not texto:
        raise HTTPException(400, "texto vacío")
    resultado, errores = None, []
    for motor in VOZ_MOTORES:
        funcion = MOTORES_DE_VOZ.get(motor)
        if funcion is None:
            continue
        try:
            resultado = await run_in_threadpool(funcion, texto)
            motor_usado = motor
            break
        except Exception as e:
            errores.append(f"{motor}: {e}")
    if not resultado:
        raise HTTPException(503, "no pude generar la voz (" + " | ".join(errores or ["ningún motor activo"]) + ")")
    audio, tipo = resultado
    cabeceras = {"X-Voz-Motor": motor_usado}
    avisos = [e.split(": ", 1)[1] if e.startswith("elevenlabs: ElevenLabs") else e
              for e in errores if not e.startswith("elevenlabs: sin clave")]
    if avisos:                                   # el motor preferido falló y se usó el de respaldo: se informa por qué
        cabeceras["X-Voz-Aviso"] = urllib.parse.quote(f"voz de respaldo ({motor_usado}). " + " | ".join(avisos)[:300], safe=" .,:;()-_|/")
    return Response(content=audio, media_type=tipo, headers=cabeceras)


@app.post("/oir")
async def oir(peticion: Request):
    """Recibe audio crudo (PCM 16 bits, mono, 16 kHz) y devuelve lo que se dijo."""
    if WhisperModel is None:
        raise HTTPException(503, "falta instalar faster-whisper (pip install faster-whisper)")
    datos = await peticion.body()
    segundos = len(datos) / 2 / 16000
    if segundos < 0.3:
        return {"texto": ""}                       # demasiado corto: se ignora
    if segundos > 60:
        raise HTTPException(413, "el audio es demasiado largo (máximo 60 s)")
    try:
        await run_in_threadpool(obtener_oido)      # la primera vez puede descargar el modelo
    except Exception as e:
        raise HTTPException(503, f"no pude cargar el modelo de voz '{OIDO_MODELO}' "
                                 f"(la primera vez necesita internet para descargarlo): {e}")
    try:
        texto = await run_in_threadpool(transcribir, datos)
    except Exception as e:
        raise HTTPException(500, f"error al transcribir: {e}")
    return {"texto": texto}


# Archivos del modelo Live2D (moc3, texturas, motions...)
app.mount("/modelo", StaticFiles(directory=CARPETA_MODELO), name="modelo")


@app.get("/")
def inicio():
    return FileResponse(RECURSOS / "index.html")


if __name__ == "__main__":
    # Así arranca el servidor.exe empaquetado (en desarrollo se usa "uvicorn servidor:app").
    import uvicorn
    for _nombre in ("stdout", "stderr"):   # sin consola, uvicorn fallaría al escribir su registro
        if getattr(sys, _nombre) is None:
            setattr(sys, _nombre, open(os.devnull, "w"))
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("RYUKO_PUERTO", "8765")),
                log_level="warning", access_log=False)
