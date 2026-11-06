"""
Tus claves y ajustes: el .env de esta carpeta. Sin python-dotenv.
Una variable de entorno de verdad siempre gana sobre el archivo.
"""

import os

from .puente import RAIZ


def cargar() -> None:
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip("'\""))


def guardar(nuevas: dict[str, str]) -> None:
    """
    Escribe o actualiza claves en el .env sin perder los comentarios. Si aún
    no hay .env, parte de .env.example, que es también la chuleta de qué es cada cosa.
    """
    ruta, ejemplo = RAIZ / ".env", RAIZ / ".env.example"
    origen = ruta if ruta.exists() else ejemplo
    lineas = origen.read_text(encoding="utf-8").splitlines() if origen.exists() else []
    faltan = dict(nuevas)
    for i, linea in enumerate(lineas):
        clave = linea.split("=", 1)[0].strip()
        if "=" in linea and not linea.lstrip().startswith("#") and clave in faltan:
            lineas[i] = f"{clave}={faltan.pop(clave)}"
    lineas += [f"{k}={v}" for k, v in faltan.items()]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    os.environ.update(nuevas)


def texto(clave: str, defecto: str = "") -> str:
    return os.environ.get(clave, "").strip() or defecto


def numero(clave: str, defecto: int) -> int:
    try:
        return int(texto(clave))
    except ValueError:
        return defecto


def rango(clave: str, defecto: tuple[int, int]) -> tuple[int, int]:
    """'9-18' -> (9, 18)."""
    try:
        a, b = texto(clave).split("-")
        return int(a), int(b)
    except ValueError:
        return defecto
