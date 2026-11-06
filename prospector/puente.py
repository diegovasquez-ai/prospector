"""
El puente al motor de búsqueda.

El motor es una copia del Cazador 2.0 (licencia MIT) que vive en
prospector/cazador/: ya sabe sacar negocios de Google Maps gratis, respetar el
robots.txt y llevar una lista de exclusión. Este proyecto no necesita nada
fuera de su carpeta. Aquí solo se elige qué se usa y dónde se guarda.
"""

from pathlib import Path

from .cazador import exclusiones, pantalla, paises
from .cazador.filtros import dominio, sin_acentos
from .cazador.fuentes import descubrir
from .cazador.rastrear import CABECERAS, EMAIL_BASURA, Robots

RAIZ = Path(__file__).resolve().parent.parent

# La lista negra es tuya y es personal: va con tus datos, que no se suben.
(RAIZ / "datos").mkdir(exist_ok=True)
exclusiones.ARCHIVO = RAIZ / "datos" / "exclusiones.txt"

__all__ = ["RAIZ", "CABECERAS", "EMAIL_BASURA", "Robots",
           "descubrir", "dominio", "exclusiones", "pantalla", "paises", "sin_acentos"]
