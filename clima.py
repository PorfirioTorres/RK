"""Gestión del clima: obtiene el clima actual y pronóstico corto usando Open-Meteo (gratuito, sin API key)."""
import urllib.request
import json
import re

def obtener_clima(lat: float, lon: float, idioma: str) -> str | None:
    """
    Consulta el clima para unas coordenadas dadas.
    Devuelve un texto formateado o None si falla.
    """
    try:
        # Open-Meteo API: clima actual y temperatura
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&temperature_unit=celsius"
        with urllib.request.urlopen(url, timeout=10) as r:
            datos = json.loads(r.read().decode("utf-8"))

        current = datos.get("current_weather")
        if not current:
            return None

        temp = current.get("temperature")
        wind = current.get("windspeed")
        # Código de clima (WMO) -> Descripción simple
        # 0: Clear, 1-3: Partly cloudy, 45-48: Fog, 51-67: Rain, 71-77: Snow, 80+: Storms
        code = current.get("weathercode", 0)

        desc_en = {
            0: "clear sky",
            1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "depositing rime fog",
            51: "light drizzle", 61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            80: "rainy showers", 95: "thunderstorm"
        }
        desc_es = {
            0: "despejado",
            1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
            45: "con niebla", 48: "niebla helada",
            51: "llovizna ligera", 61: "lluvia ligera", 63: "lluvia moderada", 65: "lluvia fuerte",
            71: "nieve ligera", 73: "nieve moderada", 75: "nieve fuerte",
            80: "chubascos", 95: "tormenta eléctrica"
        }

        d = desc_en.get(code, "unknown") if idioma == "en" else desc_es.get(code, "desconocido")

        if idioma == "en":
            return f"The current weather is {d} with a temperature of {temp}°C and wind speed of {wind} km/h."
        else:
            return f"El clima actual está {d}, con una temperatura de {temp}°C y viento de {wind} km/h."

    except Exception:
        return None

def interpretar(texto: str):
    """
    Detecta si el usuario pregunta por el clima.
    Ejemplos: 'what's the weather?', '¿cómo está el clima?', 'tell me the forecast'
    """
    import re
    t = texto.lower().strip()

    patrones = [
        r"\b(weather|clima|tiempo|forecast|pronóstico)\b",
        r"\b(how is it outside|cómo está afuera)\b",
    ]

    for p in patrones:
        if re.search(p, t, re.I):
            return {"tipo": "clima"}

    return None
