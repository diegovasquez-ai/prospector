"""
La base: un JSON con una ficha por negocio, indexada por dominio.

Un archivo y no una base de datos porque cabe de sobra (unos cientos de
negocios por ciudad) y porque así Claude Code lo puede leer y corregir
directamente cuando hace de agente.

Estados, en el orden en que avanza cada negocio:

    nueva        la trajo Maps, aún sin analizar
    descartada   no es ICP (con motivo): desarrolladora, franquicia, portal...
    floja        es del rubro, pero las señales no cuadran
    sin correo   cuadra, pero no publica ningún correo usable
    candidata    cuadra y tiene correo: le toca borrador
"""

import json
import os
from pathlib import Path

from .puente import RAIZ, dominio, exclusiones, sin_acentos

ARCHIVO = RAIZ / "datos" / "negocios.json"
# Se llamaba así cuando el proyecto era solo para inmobiliarias.
_ANTIGUO = RAIZ / "datos" / "inmobiliarias.json"
if _ANTIGUO.exists() and not ARCHIVO.exists():
    os.replace(_ANTIGUO, ARCHIVO)


def bloqueado(lead: dict, fuera: dict | None = None) -> bool:
    """
    La lista negra mira el campo 'email', que es el que trae Maps.
    El correo al que escribimos nosotros va en 'correo': sin mirarlo también,
    quien pidió la baja desde ese correo volvería a recibir el siguiente.
    """
    fuera = exclusiones.cargar() if fuera is None else fuera
    return (exclusiones.esta_bloqueado(lead, fuera)
            or exclusiones.esta_bloqueado({"email": lead.get("correo", "")}, fuera))


def clave(lead: dict) -> str:
    """Por dominio, y si no tiene web, por nombre."""
    d = dominio(lead.get("web") or "")
    return d if d else "n:" + sin_acentos(lead.get("nombre") or "").strip()


def cargar() -> dict[str, dict]:
    if not ARCHIVO.exists():
        return {}
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def guardar(base: dict[str, dict]) -> Path:
    """
    Escribe en un temporal y lo renombra. Si se corta a mitad (Ctrl+C, se
    apaga el PC) no te quedas con un JSON partido y sin tu base.
    """
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ARCHIVO)
    return ARCHIVO
