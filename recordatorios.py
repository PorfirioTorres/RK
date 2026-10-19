"""Recordatorios por voz: entiende frases como «remind me in 20 minutes to call mom» o
«recuérdame en 20 minutos llamar a mi mamá», los guarda en un archivo (sobreviven al cerrar la app)
y avisa cuando llega la hora. Funciona sin el modelo de lenguaje, solo con reglas."""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ---------- Números escritos con letras (Whisper a veces los escribe así) ----------
_NUMEROS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
}
_UNIDADES = {"second": 1, "sec": 1, "segundo": 1, "minute": 60, "min": 60, "minuto": 60,
             "hour": 3600, "hr": 3600, "hora": 3600}


def _sin_acentos(t: str) -> str:
    return t.translate(str.maketrans("áéíóúü", "aeiouu"))


def a_numero(t: str):
    """'20' -> 20, 'twenty five' -> 25, 'treinta y cinco' -> 35; None si no se entiende."""
    t = _sin_acentos(t.strip().lower())
    if t.isdigit():
        return int(t)
    palabras = [p for p in re.split(r"[\s-]+", t) if p and p != "y"]
    if not palabras or any(p not in _NUMEROS for p in palabras):
        return None
    return sum(_NUMEROS[p] for p in palabras)


# ---------- Patrones ----------
_VERBO = re.compile(r"\b(remind\s+me|set\s+(?:a|an|the)?\s*reminder|recu[eé]rdame|rec[uú]erdame|av[ií]same|"
                    r"ponme\s+un\s+recordatorio|pon\s+un\s+recordatorio)\b", re.I)
_RELATIVO = re.compile(
    r"\b(?:in|within|dentro\s+de|en)\s+(?P<n>\d+|(?:[a-záéíóúñ]+)(?:[\s-]+(?:y\s+)?[a-záéíóúñ]+)?)\s*"
    r"(?P<u>seconds?|secs?|segundos?|minutes?|mins?|minutos?|hours?|hrs?|horas?|days?|d[ií]as?|weeks?|semanas?)\b", re.I)
_MEDIA_HORA = re.compile(r"\b(?:in|en|dentro\s+de)\s+(?:half\s+an?\s+hour|media\s+hora)\b", re.I)
_UNA_Y_MEDIA = re.compile(r"\b(?:in|en|dentro\s+de)\s+(?:an?\s+hour\s+and\s+a\s+half|una\s+hora\s+y\s+media)\b", re.I)
_ABSOLUTO = re.compile(
    r"\b(?:at|a\s+las?|para\s+las?)\s+(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*"
    r"(?P<ap>a\.?\s?m\.?|p\.?\s?m\.?|de\s+la\s+(?:ma[ñn]ana|tarde|noche))?(?=[\s,.!?]|$)", re.I)
# Días: mañana / tomorrow, pasado mañana, y los días de la semana (opcionalmente con «el», «on», «next»...)
_DIAS_SEMANA = {"monday": 0, "lunes": 0, "tuesday": 1, "martes": 1, "wednesday": 2, "miercoles": 2, "thursday": 3,
                "jueves": 3, "friday": 4, "viernes": 4, "saturday": 5, "sabado": 5, "sunday": 6, "domingo": 6}
_DIA = re.compile(
    r"(?P<pas>pasado\s+)?(?<!de la )(?<!la )(?<!esta )\b(?P<man>tomorrow|ma[ñn]ana)\b|"
    r"(?:\b(?:on|next|this|el|este|pr[oó]ximo|el\s+pr[oó]ximo)\s+)?\b(?P<sem>monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b", re.I)
_PARTE = re.compile(r"\b(?:(?:in\s+the|this)\s+(?P<en>morning|afternoon|evening)|(?P<solo>tonight)|(?:por|en|de)\s+la\s+(?P<es>ma[ñn]ana|tarde|noche)|"
                    r"esta\s+(?P<esta>noche|tarde))\b|\b(?<=tomorrow )(?P<t>morning|afternoon|evening|night)\b", re.I)
_HORA_PARTE = {"morning": 9, "afternoon": 15, "evening": 19, "night": 21, "tonight": 21, "mañana": 9, "manana": 9, "tarde": 16, "noche": 21}
_CANCELAR_TODOS = re.compile(r"\b(cancel|delete|clear|remove|forget|cancela\w*|borra\w*|elimina\w*|olvida\w*|quita\w*)\b.*"
                             r"\b(reminders|recordatorios)\b", re.I)
_CANCELAR_UNO = re.compile(r"\b(?:cancel|delete|remove|forget|cancela\w*|borra\w*|elimina\w*|olvida\w*|quita\w*)\b\s+"
                           r"(?:(?:the|my|that|el|ese|mi|este)\s+)?(?:(?P<ult>last|latest|[uú]ltimo|reciente)\s+)?"
                           r"(?:reminder|recordatorio)\b\s*(?:(?:about|for|to|of|de|sobre|para|que)\s+)?(?P<q>.*)$", re.I)
_LISTAR = re.compile(r"(\b(what|which|list|show|any|tell)\b.*\breminders?\b|\bmy\s+reminders\b|"
                     r"\b(qu[eé]|cu[aá]les|lista\w*|muestra\w*|dime|tengo)\b.*\brecordatorios?\b|\bmis\s+recordatorios\b)", re.I)
_CONECTORES = re.compile(r"^(?:to|that|about|of|for|de|que|para|a|sobre)\s+", re.I)
_UNIDADES["day"] = 86400
_UNIDADES["dia"] = 86400
_UNIDADES["week"] = 604800
_UNIDADES["semana"] = 604800

_PRONOMBRES_EN = [(r"\bmyself\b", "yourself"), (r"\bI'm\b", "you're"), (r"\bI've\b", "you've"), (r"\bI'll\b", "you'll"),
                  (r"\bI\b", "you"), (r"\bmy\b", "your"), (r"\bmine\b", "yours"), (r"\bme\b", "you")]
_PRONOMBRES_ES = [(r"\bmis\b", "tus"), (r"\bmi\b", "tu")]
HORA_POR_DEFECTO = 9      # con «mañana» o un día de la semana sin hora, avisa a las 9:00


def _cambiar_persona(asunto: str) -> str:
    """Lo que dijo el usuario se lo repite ella: 'call my mom' -> 'call your mom'."""
    for patron, nuevo in _PRONOMBRES_EN + _PRONOMBRES_ES:
        asunto = re.sub(patron, nuevo, asunto, flags=re.I)
    return asunto


def _fecha_del_dia(m, hoy):
    """La fecha a la que se refiere «mañana» / «pasado mañana» / un día de la semana (siempre en el futuro)."""
    if m["man"]:
        return hoy + timedelta(days=2 if m["pas"] else 1)
    dia = _DIAS_SEMANA[_sin_acentos(m["sem"].lower())]
    falta = (dia - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=falta)


def interpretar(texto: str, ahora: datetime):
    """Devuelve None si el texto no trata de recordatorios, o un diccionario:
    {"tipo": "crear", "cuando": datetime, "asunto": str, "relativo": bool, "dia": date|None}
    {"tipo": "sin_hora"} | {"tipo": "listar"} | {"tipo": "cancelar"} (todos) |
    {"tipo": "cancelar_uno", "consulta": str, "ultimo": bool}"""
    t = texto.strip()
    if not t:
        return None
    if _CANCELAR_TODOS.search(t):
        return {"tipo": "cancelar"}
    if (m := _CANCELAR_UNO.search(t)):
        q = re.sub(r"\s+", " ", m["q"]).strip(" ,.;:!?¿¡")
        return {"tipo": "cancelar_uno", "consulta": _cambiar_persona(q) if False else q, "ultimo": bool(m["ult"]) or not q}
    if not _VERBO.search(t):
        if _LISTAR.search(t):
            return {"tipo": "listar"}
        return None
    cuando, relativo, tramos, dia = None, True, [], None
    if (m := _MEDIA_HORA.search(t)):
        cuando, tramos = ahora + timedelta(minutes=30), [m.span()]
    elif (m := _UNA_Y_MEDIA.search(t)):
        cuando, tramos = ahora + timedelta(minutes=90), [m.span()]
    else:
        for m in _RELATIVO.finditer(t):
            n = a_numero(m["n"])
            if n is None:
                continue
            unidad = _UNIDADES[_sin_acentos(m["u"].lower()).rstrip("s")]
            cuando, tramos = ahora + timedelta(seconds=n * unidad), [m.span()]
            break
    if cuando is None:
        md = _DIA.search(t)
        ma = _ABSOLUTO.search(t)
        mp_inicio = 0
        mp = None if ma else _PARTE.search(t)          # «mañana por la tarde», «tomorrow morning», «esta noche»
        if md and not ma and not mp and (m2 := re.match(r"\s+(?P<t>morning|afternoon|evening|night)\b", t[md.end():], re.I)):
            mp = m2                                   # «on monday morning»
            mp_inicio = md.end()
        if md or ma or mp:
            h, minuto, marca = HORA_POR_DEFECTO, 0, ""
            if mp:
                palabra = next(v for k, v in mp.groupdict().items() if v)
                h = _HORA_PARTE[_sin_acentos(palabra.lower())]
                tramos.append((mp_inicio + mp.start(), mp_inicio + mp.end()))
            if ma:
                h, minuto = int(ma["h"]), int(ma["m"] or 0)
                marca = (ma["ap"] or "").lower().replace(".", "").replace(" ", "")
                if marca.startswith("p") or marca.endswith(("tarde", "noche")):
                    if h < 12:
                        h += 12
                elif marca.startswith("a") or marca.endswith(("mañana", "manana")):
                    if h == 12:
                        h = 0
            if h <= 23 and minuto <= 59:
                if md:
                    dia = _fecha_del_dia(md, ahora.date())
                    cuando = datetime.combine(dia, ahora.time().replace(hour=h, minute=minuto, second=0, microsecond=0))
                    tramos.append(md.span())
                else:
                    cuando = ahora.replace(hour=h, minute=minuto, second=0, microsecond=0)
                    if not marca and not mp and h < 12 and cuando < ahora:      # «at 5» sin am/pm: la próxima vez que sea las 5 o las 17
                        alterna = cuando + timedelta(hours=12)
                        if alterna > ahora:
                            cuando = alterna
                    if cuando <= ahora:
                        cuando += timedelta(days=1)
                if ma:
                    tramos.append(ma.span())
                relativo = False
    if cuando is None:
        return {"tipo": "sin_hora"}
    resto = t
    for ini, fin in sorted(tramos, reverse=True):
        resto = resto[:ini] + " " + resto[fin:]
    resto = _VERBO.sub(" ", resto, count=1)
    resto = re.sub(r"\s+", " ", resto).strip(" ,.;:!?¿¡")
    resto = _CONECTORES.sub("", resto).strip(" ,.;:!?¿¡")
    resto = re.sub(r"^(?:please|por favor)\b[ ,]*", "", resto, flags=re.I).strip(" ,.;:!?¿¡")
    resto = _CONECTORES.sub("", resto).strip()
    return {"tipo": "crear", "cuando": cuando, "asunto": _cambiar_persona(resto) or "", "relativo": relativo, "dia": dia}


# ---------- Almacén en disco ----------
class Almacen:
    def __init__(self, archivo: Path):
        self.archivo = Path(archivo)
        self._candado = threading.Lock()

    def _leer(self) -> list[dict]:
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            return [d for d in datos if isinstance(d, dict) and "cuando" in d]
        except Exception:
            return []

    def _escribir(self, lista: list[dict]) -> None:
        temporal = self.archivo.with_name(self.archivo.name + ".tmp")
        temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
        temporal.replace(self.archivo)

    def agregar(self, cuando: datetime, asunto: str, tipo: str | None = None, duracion: float | None = None) -> dict:
        """tipo: None = recordatorio normal; "timer", "pomodoro" o "descanso" = temporizadores (ver utilidades.py)."""
        with self._candado:
            lista = self._leer()
            item = {"id": uuid.uuid4().hex[:8], "cuando": cuando.timestamp(), "asunto": asunto, "creado": time.time()}
            if tipo:
                item["tipo"] = tipo
                item["duracion"] = duracion
            lista.append(item)
            lista.sort(key=lambda d: d["cuando"])
            self._escribir(lista)
            return item

    def listar(self) -> list[dict]:
        with self._candado:
            return self._leer()

    def cancelar_uno(self, consulta: str, ultimo: bool) -> int:
        """Borra el recordatorio que menciona `consulta` (o el último que se creó). Devuelve cuántos borró."""
        with self._candado:
            todos = self._leer()
            lista = [d for d in todos if not d.get("tipo")]          # los temporizadores no se tocan desde aquí
            if not lista:
                return 0
            if ultimo:
                objetivo = max(lista, key=lambda d: d.get("creado", 0))
                quedan = [d for d in lista if d is not objetivo]
            else:
                palabras = {w for w in re.findall(r"[a-z0-9ñ]+", _sin_acentos(consulta.lower())) if len(w) > 2}
                if not palabras:
                    return 0
                quedan = [d for d in lista if not (palabras & {w for w in re.findall(r"[a-z0-9ñ]+", _sin_acentos(d["asunto"].lower()))
                                                                  if len(w) > 2})]
            n = len(lista) - len(quedan)
            if n:
                self._escribir(quedan + [d for d in todos if d.get("tipo")])
            return n

    def cancelar_temporizadores(self) -> int:
        with self._candado:
            todos = self._leer()
            quedan = [d for d in todos if not d.get("tipo")]
            if len(quedan) != len(todos):
                self._escribir(quedan)
            return len(todos) - len(quedan)

    def cancelar_todos(self) -> int:
        with self._candado:
            todos = self._leer()
            quedan = [d for d in todos if d.get("tipo")]             # los temporizadores se cancelan aparte
            self._escribir(quedan)
            return len(todos) - len(quedan)

    def sacar_vencido(self, ahora: float | None = None):
        """Quita y devuelve el primer recordatorio cuya hora ya llegó (o None)."""
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            lista = self._leer()
            for i, d in enumerate(lista):
                if d["cuando"] <= ahora:
                    del lista[i]
                    self._escribir(lista)
                    return d
            return None


# ---------- Textos que dice Ryuko ----------
_DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _hora(ts: float, idioma: str) -> str:
    d = datetime.fromtimestamp(ts)
    return d.strftime("%I:%M %p").lstrip("0") if idioma == "en" else d.strftime("%H:%M")


def _etiqueta_dia(ts: float, ahora: datetime, idioma: str) -> str:
    """'tomorrow', 'on Monday'... (vacío si es hoy)."""
    d = datetime.fromtimestamp(ts).date()
    delta = (d - ahora.date()).days
    if delta <= 0:
        return ""
    if idioma == "en":
        return "tomorrow" if delta == 1 else (f"on {_DIAS_EN[d.weekday()]}" if delta < 7 else f"on {d.strftime('%b')} {d.day}")
    return "mañana" if delta == 1 else (f"el {_DIAS_ES[d.weekday()]}" if delta < 7 else f"el {d.day}/{d.month}")


def _duracion(segundos: float, idioma: str) -> str:
    s = max(1, round(segundos))
    if s < 90:
        n, u = s, ("second" if idioma == "en" else "segundo")
    elif s < 5400:
        n, u = round(s / 60), ("minute" if idioma == "en" else "minuto")
    elif s < 172800:
        n, u = round(s / 3600, 1), ("hour" if idioma == "en" else "hora")
        n = int(n) if n == int(n) else n
    else:
        n, u = round(s / 86400), ("day" if idioma == "en" else "día")
    return f"{n} {u}{'' if n == 1 else 's'}"


def texto_confirmacion(r: dict, ahora: datetime, idioma: str) -> str:
    asunto = r["asunto"]
    if r["relativo"]:
        cuando = _duracion((r["cuando"] - ahora).total_seconds(), idioma)
        cuando = f"in {cuando}" if idioma == "en" else f"en {cuando}"
    else:
        ts = r["cuando"].timestamp()
        dia = _etiqueta_dia(ts, ahora, idioma)
        if idioma == "en":
            cuando = (dia + " " if dia else "") + f"at {_hora(ts, idioma)}"
        else:
            cuando = (dia + " " if dia else "") + f"a las {_hora(ts, idioma)}"
    if idioma == "en":
        return f"Fine. I'll remind you {cuando}" + (f": {asunto}." if asunto else ".")
    return f"Está bien. Te lo recuerdo {cuando}" + (f": {asunto}." if asunto else ".")


def texto_sin_hora(idioma: str) -> str:
    return ("When? Tell me something like \"in 20 minutes\" or \"at 5 PM\"." if idioma == "en"
            else "¿Cuándo? Dime algo como «en 20 minutos» o «a las 5 pm».")


def texto_lista(lista: list[dict], idioma: str) -> str:
    lista = [d for d in lista if not d.get("tipo")]
    if not lista:
        return "You have no reminders. Don't expect me to nag you for free." if idioma == "en" else "No tienes recordatorios. Y no creas que te voy a perseguir gratis."
    ahora = datetime.now()
    partes = [f"{(_etiqueta_dia(d['cuando'], ahora, idioma) + ' ').lstrip()}{_hora(d['cuando'], idioma)}: "
              f"{d['asunto'] or ('something' if idioma == 'en' else 'algo')}" for d in lista[:4]]
    extra = len(lista) - len(partes)
    cola = (f" and {extra} more" if idioma == "en" else f" y {extra} más") if extra > 0 else ""
    cab = f"You have {len(lista)}: " if idioma == "en" else f"Tienes {len(lista)}: "
    return cab + "; ".join(partes) + cola + "."


def texto_cancelado(n: int, idioma: str) -> str:
    if idioma == "en":
        return f"Done. {n} reminder{'s' if n != 1 else ''} gone." if n else "There was nothing to cancel."
    return f"Listo. Borré {n} recordatorio{'s' if n != 1 else ''}." if n else "No había nada que cancelar."


def texto_aviso(d: dict, ahora: float, idioma: str) -> str:
    tipo = d.get("tipo")
    if tipo:
        import utilidades
        return utilidades.texto_aviso_temporizador(d, idioma)
    asunto = d.get("asunto") or ("something" if idioma == "en" else "algo")
    tarde = ahora - d["cuando"] > 180
    if idioma == "en":
        return ("Sorry, I'm late. " if tarde else "Hey! ") + f"Reminder: {asunto}."
    return ("Perdón, se me hizo tarde. " if tarde else "¡Oye! ") + f"Recordatorio: {asunto}."


def texto_cancelado_uno(n: int, idioma: str) -> str:
    if idioma == "en":
        return "Done. That reminder is gone." if n == 1 else (f"Done. {n} reminders matched and are gone." if n else "I couldn't find a reminder like that.")
    return "Listo. Ese recordatorio ya no existe." if n == 1 else (f"Listo. Borré {n} recordatorios que coincidían." if n else "No encontré un recordatorio así.")
