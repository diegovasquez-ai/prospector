"""
Geocodificación: de "Madrid" a unas coordenadas.

Lo usan dos fuentes (Google Maps necesita un centro, OpenStreetMap una caja),
así que vive aquí y no dentro de una de ellas. El resultado se cachea porque
Nominatim pide como mucho una consulta por segundo y en una caza con
`-f todas` le preguntaríamos lo mismo dos veces seguidas.
"""

from functools import lru_cache

import httpx

from .paises import Pais

UA = {"User-Agent": "cazador/2.0 (https://github.com/topics/lead-generation)"}


@lru_cache(maxsize=64)
def caja(ciudad: str, pais: Pais) -> tuple | None:
    """
    Devuelve (sur, oeste, norte, este) de la ciudad, o None si no la encuentra.

    Pais es un dataclass frozen, así que se puede usar como clave de caché.
    """
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{ciudad}, {pais.nombre}", "format": "json", "limit": 1},
            headers=UA, timeout=30, follow_redirects=True,
        )
        datos = r.json()
        if not datos:
            return None
        s, n, o, e = (float(x) for x in datos[0]["boundingbox"])
        # Ciudades con área administrativa gigante (comunas rurales): recortamos
        # a ~0.6 grados para que Overpass no se ahogue.
        cl = 0.3
        clat, clon = (s + n) / 2, (o + e) / 2
        s, n = max(s, clat - cl), min(n, clat + cl)
        o, e = max(o, clon - cl), min(e, clon + cl)
        return (s, o, n, e)
    except Exception:
        return None


def centro(ciudad: str, pais: Pais) -> tuple | None:
    """Devuelve (lat, lng) del centro de la ciudad, o None."""
    c = caja(ciudad, pais)
    if not c:
        return None
    sur, oeste, norte, este = c
    return ((sur + norte) / 2, (oeste + este) / 2)


def candidatas(ciudad: str, pais: Pais, limite: int = 3) -> list[str]:
    """
    Ciudades parecidas, para cuando la que escribió el usuario no existe.
    Un 'no la encuentro' a secas deja al alumno sin saber qué hacer; tres
    alternativas reales le resuelven la errata en un segundo.
    """
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{ciudad}, {pais.nombre}", "format": "json",
                    "limit": limite, "addressdetails": 0},
            headers=UA, timeout=20, follow_redirects=True,
        )
        return [d.get("display_name", "") for d in r.json() if d.get("display_name")]
    except Exception:
        return []
