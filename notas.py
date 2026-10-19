"""Notas y lista de pendientes: permite anotar cosas sencillas y gestionarlas por voz.
Se guardan en notas.json y sobreviven al cerrar la app.
Funciona con reglas exactas para evitar que el modelo de lenguaje invente notas."""
import json
import re
import threading
from pathlib import Path

# ---------- Patrones de detección ----------
# "anota comprar leche", "agrega a mi lista leer el libro", "note that I need to call the bank"
_AGREGAR = re.compile(r"^\s*(?:please\s+|por\s+favor\s+)?(?:anota|agrega\s+(?:a\s+)?(?:mi\s+)?lista|nota|note)\s+(?:que\s+)?(?P<h>.{3,})$", re.I | re.S)
# "¿qué tengo en mi lista?", "show my notes", "dime mis pendientes"
_LISTAR = re.compile(r"(\b(what|which|list|show|any|tell)\b.*\b(notes?|list|todo)\b|\bmy\s+(notes?|list|todo)\b|"
                     r"\b(qu[eé]|cu[aá]les|lista\w*|muestra\w*|dime|tengo)\b.*\b(notas?|lista|pendientes)\b|\bmis\s+(notas?|lista|pendientes)\b)", re.I)
# "tacha lo de la leche", "borra la nota de la tinta", "remove the note about the bank"
_BORRAR = re.compile(r"\b(?:tacha|borra|elimina|quita|remove|delete|forget)\b\s+"
                    r"(?:(?:the|my|that|el|ese|mi|este)\s+)?(?:nota|pendiente|item)?\s*(?:(?:about|for|to|of|de|sobre|para|que)\s+)?(?P<q>.*)$", re.I)

def _limpiar(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip(" \t\r\n.,;:!¡¿?")

def interpretar(texto: str):
    """Devuelve None si no es una orden de notas. Si no, un diccionario con "tipo":
    agregar (con "hecho"), listar, borrar (con "consulta")."""
    t = texto.strip()
    if not t:
        return None

    if (m := _AGREGAR.match(t)):
        return {"tipo": "agregar", "hecho": _limpiar(m["h"])}

    if _LISTAR.search(t):
        return {"tipo": "listar"}

    if (m := _BORRAR.search(t)):
        return {"tipo": "borrar", "consulta": _limpiar(m["q"])}

    return None

class Almacen:
    def __init__(self, archivo: Path):
        self.archivo = Path(archivo)
        self._candado = threading.Lock()

    def _leer(self) -> list[str]:
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            return [d for d in datos if isinstance(d, str)]
        except Exception:
            return []

    def _escribir(self, lista: list[str]) -> None:
        temporal = self.archivo.with_name(self.archivo.name + ".tmp")
        temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
        temporal.replace(self.archivo)

    def agregar(self, texto: str) -> bool:
        with self._candado:
            lista = self._leer()
            if texto in lista:
                return False
            lista.append(texto)
            self._escribir(lista)
            return True

    def listar(self) -> list[str]:
        with self._candado:
            return self._leer()

    def borrar(self, consulta: str) -> int:
        """Borra las notas que contengan la palabra de consulta."""
        if not consulta:
            return 0
        with self._candado:
            todos = self._leer()
            consulta_norm = consulta.lower()
            quedan = [d for d in todos if consulta_norm not in d.lower()]
            n = len(todos) - len(quedan)
            if n:
                self._escribir(quedan)
            return n

# ---------- Textos que dice Ryuko ----------
def texto_agregado(hecho: str, idioma: str, nuevo: bool) -> str:
    if idioma == "en":
        return (f"Noted. I've added '{hecho}' to your list." if nuevo else "That's already on the list. Stop repeating yourself.")
    return (f"Anotado. Agregué '{hecho}' a tu lista." if nuevo else "Eso ya estaba en la lista. No me lo repitas.")

def texto_lista(lista: list[str], idioma: str) -> str:
    if not lista:
        return "Your list is empty. Finally, something you can't forget." if idioma == "en" else "Tu lista está vacía. Por fin algo que no puedes olvidar."

    cab = f"You have {len(lista)} items: " if idioma == "en" else f"Tienes {len(lista)} cosas: "
    # Numeramos las notas para que sea más fácil borrarlas ("borra la número 2")
    items = [f"{i+1}. {txt}" for i, txt in enumerate(lista[:6])]
    extra = len(lista) - len(items)
    cola = (f" and {extra} more" if idioma == "en" else f" y {extra} más") if extra > 0 else ""
    return cab + "; ".join(items) + cola + "."

def texto_borrado(n: int, idioma: str) -> str:
    if idioma == "en":
        return f"Done. {n} item{'s' if n != 1 else ''} removed." if n else "I couldn't find any note like that."
    return f"Listo. Borré {n} cosa{'s' if n != 1 else ''} de la lista." if n else "No encontré ninguna nota así."
