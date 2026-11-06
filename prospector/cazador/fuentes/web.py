"""
Búsqueda web abierta: los negocios que no salen en ningún mapa.

Rinde menos que Maps y el buscador se defiende (bloquea si insistes), pero
pesca al negocio que tiene web y no ha reclamado su ficha de Google. Como
fuente suelta es floja; como complemento de Maps suma.
"""

import re
from urllib.parse import quote_plus, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from .. import lead
from ..filtros import dominio, dominio_util, limpiar_nombre, titulo_util
from ..paises import Pais

CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

def _limpiar_enlace(href: str) -> str:
    """DuckDuckGo envuelve los resultados en /l/?uddg=<url>. Lo desenvolvemos."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href or href.startswith("/l/"):
        q = parse_qs(urlparse(href).query)
        if "uddg" in q:
            return unquote(q["uddg"][0])
        return ""
    return href if href.startswith("http") else ""


def _parsear_ddg(html: str) -> list[tuple]:
    sopa = BeautifulSoup(html, "lxml")
    salida = []
    for a in sopa.find_all("a", href=True):
        clases = " ".join(a.get("class") or [])
        if "result" not in clases and "/l/?uddg=" not in a["href"]:
            continue
        enlace = _limpiar_enlace(a["href"])
        if enlace:
            salida.append((enlace, a.get_text(" ", strip=True)))
    return salida


def _ddg(consulta: str, cliente: httpx.Client, pagina: int = 0) -> tuple[list, bool]:
    """
    Devuelve ([(url, titulo)], bloqueado). DuckDuckGo no tiene API pública: si
    le pides demasiado seguido responde 202 con una página de verificación.
    Cuando eso pasa avisamos y seguimos con las otras fuentes en vez de morir.
    """
    for url in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
        datos = {"q": consulta}
        if pagina:
            datos.update({"s": str(pagina * 25), "dc": str(pagina * 25 + 1)})
        try:
            r = cliente.post(url, data=datos)
        except Exception:
            continue
        if r.status_code == 202 or "verificand" in r.text[:400].lower() or "anomaly" in r.text[:400].lower():
            return [], True
        if r.status_code != 200:
            continue
        encontrados = _parsear_ddg(r.text)
        if encontrados:
            return encontrados, False
    return [], False


def _firecrawl(consulta: str, clave: str) -> list[tuple]:
    try:
        r = httpx.post(
            "https://api.firecrawl.dev/v1/search",
            headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
            json={"query": consulta, "limit": 20}, timeout=60,
        )
        if r.status_code != 200:
            return []
        j = r.json()
        return [(it.get("url", ""), it.get("title", "")) for it in (j.get("data") or j.get("web") or [])]
    except Exception:
        return []


def buscar(nicho: str, ciudad: str, pais: Pais, limite: int = 200, log=print) -> list[dict]:
    consultas = [
        (f"{nicho} {ciudad}", 0),
        (f"{nicho} {ciudad}", 1),
        (f"{nicho} en {ciudad} {pais.nombre} contacto", 0),
        (f"{nicho} {ciudad} whatsapp", 0),
        (f"{nicho} {ciudad} teléfono", 0),
    ]
    clave_fc = os.environ.get("FIRECRAWL_KEY", "").strip()
    encontrados: dict[str, dict] = {}
    bloqueos = 0

    with httpx.Client(headers=CABECERAS, follow_redirects=True, timeout=30) as cliente:
        for i, (c, pagina) in enumerate(consultas, 1):
            resultados, bloqueado = _ddg(c, cliente, pagina)
            if bloqueado:
                bloqueos += 1
                log(f"  [{i}/{len(consultas)}] el buscador está limitando las consultas, espero...")
                time.sleep(8)
                if bloqueos >= 3:
                    log("  ! DuckDuckGo nos cortó. Sigo con lo que traiga OpenStreetMap.")
                    log("    (vuelve a intentarlo en unos minutos, o usa --fuente osm)")
                    break
                continue
            if clave_fc:
                resultados += _firecrawl(c, clave_fc)
            nuevos = 0
            for url, titulo in resultados:
                if not dominio_util(url) or not titulo_util(titulo):
                    continue
                dom = dominio(url)
                if dom in encontrados:
                    continue
                encontrados[dom] = {
                    "nombre": limpiar_nombre(titulo, dom),
                    "web": f"https://{dom}",
                    "telefono": "", "whatsapp_osm": "", "email": "", "direccion": "",
                    "fuente": "busqueda_web",
                }
                nuevos += 1
            log(f"  [{i}/{len(consultas)}] {c!r} -> +{nuevos} webs (total {len(encontrados)})")
            if len(encontrados) >= limite:
                break
            time.sleep(3)  # buena vecindad con el buscador (y menos bloqueos)

    return list(encontrados.values())[:limite]

