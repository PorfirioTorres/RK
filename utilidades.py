"""Utilidades rápidas que Ryuko resuelve con reglas (sin el modelo, para que sean exactas):
hora y fecha, temporizadores (con Pomodoro) y cronómetro."""
import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from recordatorios import _UNIDADES, _sin_acentos, a_numero

POMODORO_MIN = 25
DESCANSO_MIN = 5

_UNIDAD = r"(?:seconds?|secs?|segundos?|minutes?|mins?|minutos?|hours?|hrs?|horas?)"
_NUM = r"(?:\d+|[a-záéíóúñ]+(?:[\s-]+(?:y\s+)?[a-záéíóúñ]+)?)"
_DUR = rf"(?:(?:(?:for|of|de|por|to)\s+)?(?P<mh>half\s+an?\s+hour|media\s+hora)|(?P<n>{_NUM})[\s-]*(?P<u>{_UNIDAD}))"
_TIMER_VERBO = re.compile(rf"\b(?:timer|temporizador|cuenta\s+regresiva)\b(?:.*?)\b(?:for|of|de|por|to)?\s*{_DUR}\b", re.I)
_TIMER_ANTES = re.compile(rf"\b{_DUR}\s+(?:timer|temporizador)\b", re.I)
_POMODORO = re.compile(r"\bpomodoro\b", re.I)
_CANCELAR_TIMER = re.compile(r"\b(?:cancel|stop|clear|delete|cancela\w*|det[eé]n\w*|para|quita\w*|borra\w*)\b.*"
                             r"\b(?:timers?|temporizadors?|temporizadores|pomodoro|cuenta\s+regresiva)\b", re.I)
_CONSULTAR_TIMER = re.compile(r"(\bhow\s+much\s+(?:time\s+)?(?:is\s+)?left\b|\btime\s+left\b|\bcu[aá]nto\s+(?:tiempo\s+)?(?:falta|queda)\b)", re.I)
_HORA = re.compile(r"(\bwhat(?:'s|\s+is)?\s+the\s+time\b|\bwhat\s+time\s+is\s+it\b|\btell\s+me\s+the\s+time\b|"
                   r"\bqu[eé]\s+hora\s+es\b|\bdime\s+la\s+hora\b|\bme\s+das\s+la\s+hora\b|\bqu[eé]\s+horas\s+son\b)", re.I)
_FECHA = re.compile(r"(\bwhat(?:'s|\s+is)?\s+(?:today's\s+date|the\s+date|the\s+date\s+today|today's\s+date)\b|\bwhat\s+day\s+is\s+(?:it|today)\b|"
                    r"\bwhat\s+is\s+today\b|\bqu[eé]\s+d[ií]a\s+es\s+(?:hoy|ma[ñn]ana)?\b|\bqu[eé]\s+fecha\s+es\b|\ba\s+cu[aá]ntos\s+estamos\b|"
                    r"\bqu[eé]\s+fecha\s+(?:es\s+)?hoy\b)", re.I)
_CRON_INICIAR = re.compile(r"\b(?:start|begin|set|inicia\w*|empieza\w*|activa\w*|arranca\w*|pon\w*)\b.*\b(?:stopwatch|cron[oó]metro)\b", re.I)
_CRON_PARAR = re.compile(r"\b(?:stop|end|pause|para|det[eé]n\w*|termina\w*|cierra\w*)\b.*\b(?:stopwatch|cron[oó]metro)\b", re.I)
_CRON_VER = re.compile(r"(\bhow\s+long\b.*\b(?:stopwatch|running)\b|\b(?:stopwatch)\b.*\b(?:status|now|time)\b|\bcheck\s+the\s+stopwatch\b|"
                       r"\bcu[aá]nto\s+(?:lleva|marca)\b.*\bcron[oó]metro\b|\bcron[oó]metro\b.*\b(?:cu[aá]nto|marca|lleva)\b)", re.I)


def _segundos(m) -> float | None:
    if m.groupdict().get("mh"):
        return 1800.0
    palabras = m["n"].split()
    n = None
    for i in range(len(palabras)):                 # «for ninety» -> «ninety»: se ignoran las palabras de enlace del principio
        n = a_numero(" ".join(palabras[i:]))
        if n is not None:
            break
    if n is None:
        return None
    return n * _UNIDADES[_sin_acentos(m["u"].lower()).rstrip("s")]


def interpretar(texto: str, ahora: datetime):
    """None si no es una utilidad. Si no, un diccionario con "tipo":
    hora | fecha | timer (con "segundos", "clase") | cancelar_timer | consultar_timer |
    cron_iniciar | cron_parar | cron_ver"""
    t = texto.strip()
    if not t or len(t) > 140:
        return None
    if _CANCELAR_TIMER.search(t) and not re.search(r"\breminders?\b|\brecordatorios?\b", t, re.I):
        return {"tipo": "cancelar_timer"}
    if _CRON_PARAR.search(t):
        return {"tipo": "cron_parar"}
    if _CRON_INICIAR.search(t):
        return {"tipo": "cron_iniciar"}
    if _CRON_VER.search(t):
        return {"tipo": "cron_ver"}
    if _POMODORO.search(t) and re.search(r"\b(?:start|begin|set|inicia\w*|empieza\w*|activa\w*|arranca\w*|pon\w*|let'?s|vamos|hagamos)\b", t, re.I):
        return {"tipo": "timer", "segundos": POMODORO_MIN * 60.0, "clase": "pomodoro"}
    for patron in (_TIMER_ANTES, _TIMER_VERBO):
        if (m := patron.search(t)):
            seg = _segundos(m)
            if seg and 1 <= seg <= 24 * 3600:
                return {"tipo": "timer", "segundos": float(seg), "clase": "timer"}
    if _CONSULTAR_TIMER.search(t):
        return {"tipo": "consultar_timer"}
    if _HORA.search(t):
        return {"tipo": "hora"}
    if _FECHA.search(t):
        return {"tipo": "fecha"}
    return None


# ---------- Cronómetro (se guarda en disco para que sobreviva si se cierra la app) ----------
class Cronometro:
    def __init__(self, archivo: Path):
        self.archivo = Path(archivo)
        self._candado = threading.Lock()

    def _inicio(self):
        try:
            return float(json.loads(self.archivo.read_text(encoding="utf-8"))["inicio"])
        except Exception:
            return None

    def iniciar(self) -> bool:
        """False si ya estaba corriendo."""
        with self._candado:
            if self._inicio() is not None:
                return False
            self.archivo.write_text(json.dumps({"inicio": time.time()}), encoding="utf-8")
            return True

    def transcurrido(self):
        with self._candado:
            i = self._inicio()
            return None if i is None else time.time() - i

    def parar(self):
        with self._candado:
            i = self._inicio()
            if i is None:
                return None
            self.archivo.unlink(missing_ok=True)
            return time.time() - i


# ---------- Textos ----------
_MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def duracion_texto(seg: float, idioma: str) -> str:
    seg = max(0, round(seg))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    en = idioma == "en"
    partes = []
    if h:
        partes.append(f"{h} {'hour' if en else 'hora'}{'' if h == 1 else 's'}")
    if m:
        partes.append(f"{m} {'minute' if en else 'minuto'}{'' if m == 1 else 's'}")
    if s and not h:
        partes.append(f"{s} {'second' if en else 'segundo'}{'' if s == 1 else 's'}")
    return (" and " if en else " y ").join(partes) if partes else ("0 seconds" if en else "0 segundos")


def texto_hora(ahora: datetime, idioma: str) -> str:
    if idioma == "en":
        return f"It's {ahora.strftime('%I:%M %p').lstrip('0')}."
    h = ahora.hour
    return f"Es la {h}:{ahora.minute:02d}." if h in (1, 13) else f"Son las {h}:{ahora.minute:02d}."


def texto_fecha(ahora: datetime, idioma: str) -> str:
    if idioma == "en":
        return f"Today is {_DIAS_EN[ahora.weekday()]}, {_MESES_EN[ahora.month - 1]} {ahora.day}, {ahora.year}."
    return f"Hoy es {_DIAS_ES[ahora.weekday()]} {ahora.day} de {_MESES_ES[ahora.month - 1]} de {ahora.year}."


def texto_timer_creado(r: dict, idioma: str) -> str:
    dur = duracion_texto(r["segundos"], idioma)
    if r["clase"] == "pomodoro":
        return (f"Pomodoro started: {dur} of focus. Don't slack off." if idioma == "en"
                else f"Pomodoro iniciado: {dur} de concentración. Nada de distraerse.")
    return f"Timer set for {dur}. Starting now." if idioma == "en" else f"Temporizador de {dur}. Empieza ya."


def texto_timer_cancelado(n: int, idioma: str) -> str:
    if idioma == "en":
        return "Timer cancelled." if n else "There's no timer running."
    return "Temporizador cancelado." if n else "No hay ningún temporizador en marcha."


def texto_timer_restante(lista: list[dict], ahora: float, idioma: str) -> str:
    timers = [d for d in lista if d.get("tipo")]
    if not timers:
        return "There's no timer running." if idioma == "en" else "No hay ningún temporizador en marcha."
    d = min(timers, key=lambda x: x["cuando"])
    resto = max(0, d["cuando"] - ahora)
    return (f"{duracion_texto(resto, idioma)} left." if idioma == "en" else f"Faltan {duracion_texto(resto, idioma)}.")


def texto_aviso_temporizador(d: dict, idioma: str) -> str:
    tipo, dur = d.get("tipo"), duracion_texto(d.get("duracion") or 0, idioma)
    if tipo == "pomodoro":
        return (f"Pomodoro done! Take a {DESCANSO_MIN} minute break. I'll tell you when it's over." if idioma == "en"
                else f"¡Pomodoro terminado! Descansa {DESCANSO_MIN} minutos. Yo te aviso cuando acabe.")
    if tipo == "descanso":
        return "Break's over. Back to work." if idioma == "en" else "Se acabó el descanso. A trabajar."
    return (f"Time's up! Your {dur} timer is done." if idioma == "en" else f"¡Se acabó el tiempo! Tu temporizador de {dur} terminó.")


def texto_cron(accion: str, seg, idioma: str) -> str:
    en = idioma == "en"
    if accion == "iniciar":
        return ("Stopwatch started." if seg else "The stopwatch was already running.") if en else \
               ("Cronómetro en marcha." if seg else "El cronómetro ya estaba corriendo.")
    if seg is None:
        return "No stopwatch is running." if en else "No hay ningún cronómetro en marcha."
    dur = duracion_texto(seg, idioma)
    if accion == "parar":
        return f"Stopped at {dur}." if en else f"Detenido en {dur}."
    return f"{dur} so far." if en else f"Lleva {dur}."
