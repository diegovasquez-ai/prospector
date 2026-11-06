"""
Serper: Google (y Google Maps) a través de una API de pago.

En la versión 1 esta era LA forma de llegar a Google Maps. En la 2.0 ya no hace
falta: fuentes/maps.py hace lo mismo gratis y sin registrarse. Se mantiene como
respaldo por si Google cambia el formato interno y maps.py deja de funcionar
algún día. Si tienes SERPER_KEY puesta, se usa; si no, ni se menciona.

La cuenta gratuita da 2.500 búsquedas.
"""

import os

import httpx

from .. import lead
from ..filtros import dominio_util
from ..paises import Pais

def buscar(nicho: str, ciudad: str, pais: Pais, limite: int = 200, log=print) -> list[dict]:
    """
    Fuente opcional: Serper (resultados de Google, incluido Google Maps).
    Necesita SERPER_KEY — la cuenta gratuita da 2.500 búsquedas, de sobra para
    varias cacerías. Es la fuente que más rinde: Maps publica el teléfono y la
    web de casi todos los negocios.
    """
    clave = os.environ.get("SERPER_KEY", "").strip()
    if not clave:
        return []
    cab = {"X-API-KEY": clave, "Content-Type": "application/json"}
    cuerpo = {"q": f"{nicho} en {ciudad}", "gl": pais.codigo.lower(), "hl": pais.idioma}
    salida: list[dict] = []

    # 1) Google Maps: trae teléfono y web directamente.
    for pagina in (1, 2, 3):
        try:
            r = httpx.post("https://google.serper.dev/places", headers=cab,
                           json={**cuerpo, "page": pagina}, timeout=45)
            if r.status_code != 200:
                log(f"  ! Serper Places respondió {r.status_code}")
                break
            lugares = r.json().get("places", []) or []
        except Exception as e:
            log(f"  ! Serper Places falló ({type(e).__name__})")
            break
        if not lugares:
            break
        for lug in lugares:
            web = (lug.get("website") or "").strip()
            salida.append({
                "nombre": (lug.get("title") or "").strip(),
                "web": web if dominio_util(web) else "",
                "telefono": (lug.get("phoneNumber") or "").strip(),
                "whatsapp_osm": "",
                "email": "",
                "direccion": (lug.get("address") or "").strip(),
                "fuente": "google_maps",
            })
        log(f"  Google Maps (Serper) página {pagina}: {len(lugares)} negocios (total {len(salida)})")
        if len(salida) >= limite:
            break
        time.sleep(1)

    # 2) Resultados web de Google, por si el negocio no está en Maps.
    try:
        r = httpx.post("https://google.serper.dev/search", headers=cab,
                       json={**cuerpo, "num": 30}, timeout=45)
        if r.status_code == 200:
            nuevos = 0
            for it in r.json().get("organic", []) or []:
                url, titulo = it.get("link", ""), it.get("title", "")
                if not dominio_util(url) or not titulo_util(titulo):
                    continue
                salida.append({
                    "nombre": limpiar_nombre(titulo, dominio(url)),
                    "web": f"https://{dominio(url)}",
                    "telefono": "", "whatsapp_osm": "", "email": "", "direccion": "",
                    "fuente": "google",
                })
                nuevos += 1
            log(f"  Google (Serper): +{nuevos} webs")
    except Exception:
        pass

    return salida[:limite]


