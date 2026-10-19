"""Prepara un modelo Live2D para Ryuko: lo copia a la carpeta modelo\\ con nombres ASCII (sin caracteres chinos,
que dan problemas en Windows y en las direcciones web) y rellena los grupos de parpadeo y boca si vienen vacíos.

Uso:   python preparar_modelo.py "C:\\ruta\\a\\la\\carpeta\\del\\modelo" [nombre]
Ejemplo para el modelo Jian:   python preparar_modelo.py "C:\\Users\\juan\\Downloads\\简" jian
Después ejecuta construir_exe.bat (o usa la opción A para probar).
"""
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(__doc__)
origen = Path(sys.argv[1])
nombre = sys.argv[2] if len(sys.argv) > 2 else "modelo"
destino = Path(__file__).parent / "modelo"

modelos = sorted(origen.glob("*.model3.json"))
if not modelos:
    sys.exit(f"No encuentro ningún archivo .model3.json dentro de {origen}")
ajustes = json.loads(modelos[0].read_text(encoding="utf-8-sig"))
refs = ajustes["FileReferences"]
raiz = Path(refs["Moc"]).stem          # prefijo que usa el modelo en sus archivos (p. ej. "简")


def nuevo(ruta: str) -> str:
    return ruta.replace(raiz, nombre, 1)


if destino.exists() and any(destino.iterdir()):
    respaldo = destino.with_name("modelo_anterior")
    if respaldo.exists():
        shutil.rmtree(respaldo)
    destino.rename(respaldo)
    print(f"La carpeta modelo anterior se guardó como {respaldo.name}")
destino.mkdir(exist_ok=True)

archivos = [refs["Moc"], *refs.get("Textures", [])]
for clave in ("Physics", "Pose", "DisplayInfo", "UserData"):
    if refs.get(clave):
        archivos.append(refs[clave])
for ruta in archivos:
    fuente = origen / ruta
    salida = destino / nuevo(ruta)
    salida.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fuente, salida)
    print("copiado:", nuevo(ruta))

# Referencias con los nombres nuevos
for clave, valor in list(refs.items()):
    if isinstance(valor, str):
        refs[clave] = nuevo(valor)
    elif isinstance(valor, list) and all(isinstance(v, str) for v in valor):
        refs[clave] = [nuevo(v) for v in valor]
for clave in ("Expressions", "Motions"):
    refs.pop(clave, None)              # no se usan; evita referencias a archivos que no se copiaron

# Parpadeo y boca: si los grupos están vacíos, se rellenan con los parámetros estándar que existan
existentes = set()
if refs.get("DisplayInfo"):
    cdi = json.loads((destino / refs["DisplayInfo"]).read_text(encoding="utf-8-sig"))
    existentes = {p["Id"] for p in cdi.get("Parameters", [])}
estandar = {"EyeBlink": ["ParamEyeLOpen", "ParamEyeROpen"], "LipSync": ["ParamMouthOpenY"]}
grupos = ajustes.setdefault("Groups", [])
for nombre_grupo, ids in estandar.items():
    grupo = next((g for g in grupos if g.get("Name") == nombre_grupo), None)
    if grupo is None:
        grupo = {"Target": "Parameter", "Name": nombre_grupo, "Ids": []}
        grupos.append(grupo)
    if not grupo.get("Ids"):
        grupo["Ids"] = [i for i in ids if not existentes or i in existentes]

(destino / f"{nombre}.model3.json").write_text(json.dumps(ajustes, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nListo: modelo\\{nombre}.model3.json")
