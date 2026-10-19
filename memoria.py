"""Memoria de largo plazo: datos sobre el usuario que Ryuko recuerda entre sesiones (nombre, proyectos, gustos...).
Se guardan en memoria.json (legible y editable a mano) y se agregan a su personalidad en cada arranque.
Funciona con órdenes claras («remember that...», «recuerda que...», «forget...», «what do you remember?») que se
entienden con reglas, y, si se activa, también con un resumen automático hecho por el modelo (ver servidor.py)."""
import json
import re
import threading
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

MAX_HECHOS = 50
MAX_CARACTERES = 200

_RECORDAR = re.compile(
    r"^\s*(?:please\s+|por\s+favor\s+)?(?:remember|don'?t\s+forget|keep\s+in\s+mind|note|recuerda|acu[eé]rdate\s+de|"
    r"ten\s+en\s+cuenta|no\s+olvides|anota)\s+(?:that\s+|about\s+|que\s+)?(?P<h>.{3,})$", re.I | re.S)
_NOMBRE = re.compile(
    r"^\s*(?:my\s+name\s+is|my\s+name's|call\s+me|you\s+can\s+call\s+me|me\s+llamo|mi\s+nombre\s+es|ll[aá]mame)\s+(?P<n>[^\W\d_][\w'’-]*(?:\s+[^\W\d_][\w'’-]*)?)\s*[.!]?\s*$", re.I)
_OLVIDAR = re.compile(r"^\s*(?:please\s+|por\s+favor\s+)?(?:forget|olvida|borra\s+de\s+tu\s+memoria)\s+"
                      r"(?:that\s+|about\s+|what\s+i\s+said\s+about\s+|que\s+|lo\s+de\s+|sobre\s+)?(?P<h>.{3,})$", re.I | re.S)
_OLVIDAR_TODO = re.compile(r"^\s*(?:please\s+|por\s+favor\s+)?(?:forget\s+everything(?:\s+about\s+me)?|"
                           r"wipe\s+(?:your\s+)?memory|clear\s+(?:your\s+)?memory|olvida\s+todo(?:\s+(?:lo\s+que\s+sabes\s+)?de\s+m[ií])?|"
                           r"borra\s+(?:tu\s+)?memoria)\s*[.!]?\s*$", re.I)
_LISTAR = re.compile(r"(what\s+do\s+you\s+(?:remember|know)\s+about\s+me|what\s+(?:have\s+)?i\s+told\s+you|"
                     r"qu[eé]\s+(?:recuerdas|sabes)\s+(?:de|sobre)\s+m[ií]|qu[eé]\s+te\s+(?:he\s+)?dicho|"
                     r"show\s+(?:me\s+)?your\s+memory|muestra\s+tu\s+memoria)", re.I)

_NO_ES_NOMBRE = {"later", "back", "now", "tomorrow", "tonight", "please", "maybe", "when", "if", "soon", "again", "once",
                 "luego", "despues", "mañana", "ahora", "pronto", "cuando", "si", "otra", "manana", "mas", "tarde"}


def _limpiar(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" \t\r\n.,;:!¡¿?")
    return t[:MAX_CARACTERES]


def _normalizar(t: str) -> set[str]:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return {p for p in re.findall(r"[a-z0-9ñ]+", t) if len(p) > 2}


def interpretar(texto: str):
    """None si no es una orden de memoria. Si no, un diccionario con "tipo":
    recordar (con "hecho" y quizá "clave"), olvidar (con "consulta"), olvidar_todo, listar."""
    t = texto.strip()
    if not t or len(t) > 400:
        return None
    if _OLVIDAR_TODO.match(t):
        return {"tipo": "olvidar_todo"}
    if (m := _NOMBRE.match(t)) and m["n"].split()[0].lower() not in _NO_ES_NOMBRE:
        return {"tipo": "recordar", "clave": "nombre", "hecho": f"The user's name is {_limpiar(m['n'])}"}
    if (m := _OLVIDAR.match(t)):
        return {"tipo": "olvidar", "consulta": _limpiar(m["h"])}
    if (m := _RECORDAR.match(t)):
        hecho = _limpiar(m["h"])
        if len(hecho) >= 3 and not re.match(r"^(?:to|de|a)\s", hecho, re.I):       # «remember to X» es más bien un recordatorio
            return {"tipo": "recordar", "clave": None, "hecho": hecho}
    if _LISTAR.search(t):
        return {"tipo": "listar"}
    return None


class Memoria:
    def __init__(self, archivo: Path):
        self.archivo = Path(archivo)
        self._candado = threading.Lock()

    def _leer(self) -> list[dict]:
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8-sig"))
            lista = []
            for d in datos:
                if isinstance(d, str):                       # permite editar el archivo a mano con frases sueltas
                    d = {"hecho": d}
                if isinstance(d, dict) and str(d.get("hecho", "")).strip():
                    d.setdefault("id", uuid.uuid4().hex[:8])
                    lista.append(d)
            return lista
        except Exception:
            return []

    def _escribir(self, lista: list[dict]) -> None:
        temporal = self.archivo.with_name(self.archivo.name + ".tmp")
        temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
        temporal.replace(self.archivo)

    def listar(self) -> list[dict]:
        with self._candado:
            return self._leer()

    def agregar(self, hecho: str, clave: str | None = None, auto: bool = False) -> bool:
        """True si se guardó algo nuevo (False si ya estaba)."""
        hecho = _limpiar(hecho)
        with self._candado:
            lista = self._leer()
            if clave:
                lista = [d for d in lista if d.get("clave") != clave]       # p. ej. un nombre nuevo reemplaza al anterior
            nuevo = _normalizar(hecho)
            for d in lista:
                viejo = _normalizar(d["hecho"])
                if viejo and nuevo and len(viejo & nuevo) / max(len(viejo | nuevo), 1) >= 0.8:
                    return False
            item = {"id": uuid.uuid4().hex[:8], "hecho": hecho, "fecha": datetime.now().strftime("%Y-%m-%d")}
            if clave:
                item["clave"] = clave
            if auto:
                item["auto"] = True
            lista.append(item)
            self._escribir(lista[-MAX_HECHOS:])
            return True

    def olvidar(self, consulta: str) -> int:
        """Borra los hechos que mencionan lo que se pidió olvidar. Devuelve cuántos."""
        palabras = _normalizar(consulta)
        if not palabras:
            return 0
        with self._candado:
            lista = self._leer()
            quedan = [d for d in lista if not (palabras & _normalizar(d["hecho"]) and
                      len(palabras & _normalizar(d["hecho"])) >= min(len(palabras), 2))]
            borrados = len(lista) - len(quedan)
            if borrados:
                self._escribir(quedan)
            return borrados

    def vaciar(self) -> int:
        with self._candado:
            n = len(self._leer())
            self._escribir([])
            return n

    def bloque_para_personalidad(self, idioma: str) -> str:
        lista = self.listar()
        if not lista:
            return ""
        pref = "User said: " if idioma == "en" else "El usuario dijo: "
        lineas = "\n".join("- " + (re.sub(r"\s+", " ", d["hecho"]) if re.match(r"^(the user|el usuario)\b", d["hecho"], re.I)
                                   else pref + re.sub(r"\s+", " ", d["hecho"])) for d in lista)
        if idioma == "en":
            return ("\n\nThings you know about the user (they told you these; use them naturally when relevant, "
                    "never recite the list, never invent more):\n" + lineas)
        return ("\n\nCosas que sabes del usuario (te las dijo él/ella; úsalas con naturalidad cuando vengan al caso, "
                "sin recitar la lista ni inventar más):\n" + lineas)


# ---------- Textos que dice Ryuko ----------
_A_TU = [(r"\bmyself\b", "yourself"), (r"\bI'm\b", "you're"), (r"\bI've\b", "you've"), (r"\bI'll\b", "you'll"),
         (r"\bI\b", "you"), (r"\bmy\b", "your"), (r"\bmine\b", "yours"), (r"\bme\b", "you"),
         (r"\bmis\b", "tus"), (r"\bmi\b", "tu"), (r"\bme\b", "te")]


def _a_segunda_persona(hecho: str) -> str:
    """'I study X' -> 'you study X'; 'The user's name is Juan' -> 'your name is Juan'."""
    hecho = re.sub(r"^(?:the user's|el usuario)\b", "your", hecho, flags=re.I) if hecho.lower().startswith("the user's") else hecho
    def _verbo(m):
        v = m["v"].lower()
        v = {"is": "are", "has": "have", "goes": "go", "does": "do"}.get(v) or (v[:-3] + "y" if v.endswith("ies") else
                 v[:-1] if v.endswith("s") and not v.endswith("ss") else v)
        return "you " + v
    hecho = re.sub(r"^the user (?P<v>[a-z]+)\b", _verbo, hecho, flags=re.I)
    for patron, nuevo in _A_TU:
        hecho = re.sub(patron, nuevo, hecho, flags=re.I)
    return hecho


def texto_recordado(hecho: str, idioma: str, nuevo: bool) -> str:
    if idioma == "en":
        return (f"Noted. I'll remember that: {_a_segunda_persona(hecho)}." if nuevo else "I already knew that. Pay attention.")
    return (f"Anotado. Lo voy a recordar: {_a_segunda_persona(hecho)}." if nuevo else "Eso ya lo sabía. Presta atención.")


def texto_olvidado(n: int, idioma: str) -> str:
    if idioma == "en":
        return f"Fine, forgotten. ({n})" if n else "I don't have anything like that."
    return f"Listo, olvidado. ({n})" if n else "No tengo nada parecido a eso."


def texto_vaciado(n: int, idioma: str) -> str:
    if idioma == "en":
        return f"Done. I wiped {n} thing{'s' if n != 1 else ''} about you." if n else "There was nothing to wipe."
    return f"Listo. Borré {n} cosa{'s' if n != 1 else ''} sobre ti." if n else "No había nada que borrar."


def texto_lista(lista: list[dict], idioma: str) -> str:
    if not lista:
        return ("I don't know anything about you yet. Tell me with \"remember that...\"." if idioma == "en"
                else "Todavía no sé nada de ti. Dímelo con «recuerda que...».")
    partes = [_a_segunda_persona(d["hecho"]) for d in lista[:6]]
    extra = len(lista) - len(partes)
    cola = (f" ...and {extra} more." if idioma == "en" else f" ...y {extra} más.") if extra > 0 else ""
    return ("I remember: " if idioma == "en" else "Recuerdo: ") + "; ".join(partes) + ("." if not cola else cola)


# ---------- Resumen automático (opcional) ----------
PROMPT_EXTRACCION = {
    "en": ("You extract durable facts about the USER from their messages, to remember in the long term "
           "(name, job or studies, projects, preferences, pets, routines). Rules: only facts the user clearly stated about "
           "themselves; no guesses; no temporary things (moods, what they are doing right now, questions); each fact one short "
           "sentence in English starting with \"The user\"; at most 3. If there is nothing worth remembering, return an empty list. "
           "Answer with JSON: {\"hechos\": [\"...\"]}"),
    "es": ("Extraes datos duraderos sobre el USUARIO a partir de sus mensajes, para recordarlos a largo plazo "
           "(nombre, trabajo o estudios, proyectos, gustos, mascotas, rutinas). Reglas: solo lo que el usuario dijo claramente de sí "
           "mismo; nada adivinado; nada temporal (estados de ánimo, lo que hace ahora, preguntas); cada dato en una frase corta "
           "que empiece con «El usuario»; máximo 3. Si no hay nada que valga la pena recordar, devuelve la lista vacía. "
           "Responde en JSON: {\"hechos\": [\"...\"]}"),
}


def filtrar_automaticos(hechos, existentes: list[dict]) -> list[str]:
    """Descarta lo dudoso de lo que propuso el modelo pequeño: preguntas, frases muy cortas o largas, repetidos."""
    salida = []
    for h in hechos or []:
        if not isinstance(h, str):
            continue
        h = _limpiar(h)
        if not (12 <= len(h) <= 140) or "?" in h or "\n" in h:
            continue
        if not re.match(r"^(the user|el usuario)\b", h, re.I):
            continue
        n = _normalizar(h)
        if any(len(n & _normalizar(d["hecho"])) / max(len(n | _normalizar(d["hecho"])), 1) >= 0.6
               for d in existentes + [{"hecho": x} for x in salida]):
            continue
        salida.append(h)
    return salida[:3]
