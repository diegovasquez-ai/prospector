"""
Filtros de calidad.

La búsqueda web abierta trae de todo: portales, agregadores, redes sociales,
prensa, ayuntamientos, blogs de "los 10 mejores X de tu ciudad". Nada de eso
es un negocio al que puedas escribirle. Este módulo es el que separa el
prospecto real del ruido, y es la parte que más conviene ir engordando a
medida que corres el cazador en tu nicho.
"""

import re
import unicodedata
from urllib.parse import urlparse

# Dominios que nunca son el negocio en sí (agregadores, redes, prensa, mapas).
DOMINIOS_BLOQUEADOS = (
    # redes y plataformas
    "facebook.", "instagram.", "linkedin.", "twitter.", "x.com", "tiktok.",
    "youtube.", "pinterest.", "whatsapp.com", "t.me", "telegram.",
    "wa.me", "threads.net", "reddit.", "quora.",
    # buscadores y mapas
    "google.", "bing.", "duckduckgo.", "yahoo.", "yandex.", "waze.com",
    "openstreetmap.", "mapquest.",
    # ruido del JSON de Google Maps: fotos, iconos y metadatos.
    # Ojo: "google." NO cubre "googleusercontent" (tras google viene una u,
    # no un punto), asi que hay que listarlos aparte.
    "gstatic", "ggpht", "schema.org", "googleusercontent", "googleapis",
    # agregadores / directorios / marketplaces
    "paginasamarillas", "amarillas", "yelp.", "tripadvisor.", "trustpilot.",
    "booking.", "airbnb.", "doctoralia.", "milanuncios.", "wallapop.",
    "mercadolibre.", "mercadolibre", "amazon.", "aliexpress.", "ebay.",
    "yapo.cl", "olx.", "vulpe.", "cylex", "infoisinfo", "einforma",
    "empresite", "axesor", "hotfrog", "tuugo", "opendi", "yellowpages",
    "brownbook", "solucionesyservicios", "guiatelefonica", "clasificados",
    "indeed.", "glassdoor.", "infojobs.", "computrabajo.",
    # enciclopedias, prensa, gobierno
    "wikipedia.", "wikimedia.", "blogspot.", "wordpress.com", "medium.com",
    "elpais.", "elmundo.", "abc.es", "lavanguardia.", "emol.", "latercera.",
    "biobiochile.", "clarin.", "infobae.", "eltiempo.", "elcomercio.",
    ".gob.", ".gov", ".gouv.", "ayuntamiento", "municipalidad", "municipal",
    "juntadeandalucia", "comunidad.madrid",
    # constructores de webs y plantillas (webs demo, no negocios)
    "wix.com", "squarespace.com", "shopify.com", "godaddy.com", "webnode",
    "jimdo", "weebly", "blogger.com", "sites.google",
)

# Palabras que delatan un artículo/listado en vez de un negocio.
TITULOS_BASURA = re.compile(
    r"\b(los|las)\s+\d+\s+mejores|\bmejores\s+\w+\s+(de|en)\b|\btop\s*\d+|"
    r"\bcomparativa\b|\branking\b|\bguía\s+de\b|\bopiniones\b|\bprecios\s+de\b|"
    r"\bqué\s+es\b|\bcómo\s+\w+\b|\blistado\s+de\b|\bdirectorio\b|\bofertas\s+de\b",
    re.I,
)

# Extensiones de archivo que no son una web de negocio.
EXT_MALAS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".png", ".zip")


def sin_acentos(texto: str) -> str:
    """'Peluquerías' -> 'peluquerias'. Comparar nichos sin que la tilde estorbe."""
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


def dominio(url: str) -> str:
    """Dominio limpio, sin www ni puerto."""
    try:
        red = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    except Exception:
        return ""
    red = red.split(":")[0]
    return red[4:] if red.startswith("www.") else red


def dominio_util(url: str) -> bool:
    """False si el dominio es un agregador, una red social o un archivo."""
    d = dominio(url)
    if not d or "." not in d:
        return False
    if any(b in d for b in DOMINIOS_BLOQUEADOS):
        return False
    if url.lower().endswith(EXT_MALAS):
        return False
    return True


def titulo_util(titulo: str) -> bool:
    """False si el título huele a artículo de blog / listado."""
    return not TITULOS_BASURA.search(titulo or "")


def limpiar_nombre(titulo: str, dom: str) -> str:
    """
    Saca un nombre de negocio presentable desde el <title> de la página.
    'Gimnasio Atlas | Entrena en Valencia - Home' -> 'Gimnasio Atlas'
    """
    t = (titulo or "").strip()
    if t:
        t = re.split(r"\s*[|·—–-]\s*", t)[0].strip()
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"^(inicio|home|bienvenidos?a?|portada)\s*[:\-]?\s*", "", t, flags=re.I)
        if 3 <= len(t) <= 70:
            return t
    base = (dom or "").split(".")[0]
    return base.replace("-", " ").title()


def deduplicar(registros: list[dict], clave: str) -> list[dict]:
    """Deduplica manteniendo el primero visto (el de mejor confianza si vienen ordenados)."""
    vistos, salida = set(), []
    for r in registros:
        k = (r.get(clave) or "").strip().lower()
        if not k or k in vistos:
            continue
        vistos.add(k)
        salida.append(r)
    return salida
