"""Calculadora y conversiones exactas: realiza operaciones matemáticas y conversiones
sin usar el modelo de lenguaje, para evitar errores de cálculo.
Se integra en el pipeline de utilidades del servidor."""
import re
import math

# ---------- Patrones de detección ----------
# "cuanto es 25 por 4", "calculate 15% of 200", "what is 123 divided by 5"
_CALC = re.compile(r"^\s*(?:cuanto\s+es|calcula|calculadora|what\s+is|calculate)\s+(?P<expr>.+)$", re.I | re.S)
# "convierte 10 kilos a libras", "convert 50 celsius to fahrenheit"
_CONV = re.compile(r"^\s*(?:convierte|convert)\s+(?P<val>\d+(?:\.\d+)?)\s+(?P<de>\w+)\s+(?:a|to)\s+(?P<a_unidad>\w+)$", re.I)

def _limpiar_expr(expr: str) -> str:
    # Reemplazos comunes de lenguaje natural a operadores matemáticos
    replacements = {
        " por ": "*", " multiplied by ": "*",
        " dividido ": "/", " divided by ": "/",
        " mas ": "+", " plus ": "+",
        " menos ": "-", " minus ": "-",
        "al cuadrado": "**2", "squared": "**2",
        "raiz de": "math.sqrt", "square root of": "math.sqrt",
    }
    res = expr.lower()
    for k, v in replacements.items():
        res = res.replace(k, v)
    # Permitir solo caracteres seguros para eval()
    return re.sub(r"[^0-9.+\-*/%() \s]", "", res)

def interpretar(texto: str):
    """Devuelve None si no es una operación matemática o conversión.
    Si no, un diccionario con 'tipo': 'calc' o 'conv'."""
    t = texto.strip()
    if not t:
        return None

    if (m := _CONV.search(t)):
        return {"tipo": "conv", "valor": float(m["val"]), "de": m["de"].lower(), "a": m["a_unidad"].lower()}

    if (m := _CALC.search(t)):
        return {"tipo": "calc", "expr": m["expr"]}

    return None

def resolver_calc(expr: str) -> str:
    """Evalúa la expresión matemática de forma segura."""
    expr_limpia = _limpiar_expr(expr)
    try:
        # Usamos un entorno limitado para eval por seguridad
        resultado = eval(expr_limpia, {"__builtins__": None}, {"math": math})
        return str(round(resultado, 4))
    except Exception:
        return None

def resolver_conv(valor: float, de_u: str, a_u: str) -> str:
    """Realiza conversiones comunes."""
    # Mapa de conversiones (unidad_origen: { unidad_destino: factor })
    convs = {
        "kilo": {"libras": 2.20462, "gramos": 1000},
        "kilogramos": {"libras": 2.20462, "gramos": 1000},
        "kg": {"libras": 2.20462, "gramos": 1000},
        "libra": {"kilos": 0.453592, "gramos": 453.59},
        "lbs": {"kilos": 0.453592, "gramos": 453.59},
        "metro": {"pies": 3.28084, "cm": 100},
        "m": {"pies": 3.28084, "cm": 100},
        "pie": {"metros": 0.3048, "cm": 30.48},
        "ft": {"metros": 0.3048, "cm": 30.48},
        "mile": {"km": 1.60934},
        "milla": {"km": 1.60934},
        "km": {"millas": 0.621371},
    }

    # Manejo especial para temperatura
    if "celsius" in de_u and "fahrenheit" in a_u:
        return str(round((valor * 9/5) + 32, 2))
    if "fahrenheit" in de_u and "celsius" in a_u:
        return str(round((valor - 32) * 5/9, 2))

    # Conversiones lineales
    for origen, destinos in convs.items():
        if origen in de_u:
            for destino, factor in destinos.items():
                if destino in a_u:
                    return str(round(valor * factor, 4))

    return None

def texto_resultado(tipo: str, res: str, original: str, idioma: str) -> str:
    if idioma == "en":
        if tipo == "calc": return f"The result of {original} is {res}."
        return f"{res} is the converted value."
    else:
        if tipo == "calc": return f"El resultado de {original} es {res}."
        return f"El valor convertido es {res}."
