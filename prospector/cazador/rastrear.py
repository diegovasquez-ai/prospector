"""
Rastreo del sitio del negocio para sacar su WhatsApp (y de paso, su email).

Esta es la mitad del canal WhatsApp, no un extra. Google Maps publica el
teléfono de la ficha, pero la mitad son fijos, que para WhatsApp no sirven:

    Medido sobre 95 barberías de Madrid
      46%  teléfono móvil        -> vale como WhatsApp tal cual
      51%  teléfono fijo         -> inservible, hay que entrar en su web
       -   de los fijos, 47 tenían web
      80%  de esos se rescatan entrando en la web

Sin este módulo Maps entrega un 46% de leads accionables. Con él, un 86%.

El WhatsApp casi nunca está en los directorios: está en el botón flotante de
la web, en el pie de página o en la página de contacto. Aquí visitamos esas
páginas públicas y extraemos el número, ordenado por confianza:

  alta   -> enlace wa.me / api.whatsapp.com. El dueño declaró "este es mi WhatsApp".
  media  -> móvil en un tel: o en el texto, con la palabra "whatsapp" al lado.
  baja   -> móvil publicado suelto. Suele ser WhatsApp, pero verifícalo.

La mayoría de los rescates son de confianza baja. Decir que están "confirmados"
sería mentir, y por eso la columna existe.
"""

import os
import re
import threading
import urllib.robotparser as robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from . import lead
from . import telefono as tel
from .filtros import dominio
from .paises import Pais

CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

# Rutas que probamos a ciegas. La portada va primero porque es donde suele
# estar el botón flotante de WhatsApp; el resto son las formas más comunes de
# escribir "contacto" en español, inglés y portugués.
RUTAS = ["", "/contacto", "/contacto/", "/contactar", "/contactenos",
         "/es/contacto", "/contact", "/contact-us", "/contato"]

# Cuántos enlaces de "contacto" encontrados en el menú seguimos. Adivinar
# rutas falla en cuanto la web usa /quienes-somes o /donde-estamos; leer su
# propio menú acierta siempre.
MAX_ENLACES_MENU = 2
TEXTO_CONTACTO = re.compile(r"contact|contáct|contac|escríbenos|escribenos|dónde|donde estamos", re.I)

ENLACE_WA = re.compile(
    r"(?:wa\.me/|whatsapp\.com/send[^\"'\s]*?[?&]phone=|whatsapp://send\?phone=|"
    r"api\.whatsapp\.com/send/?\?phone=)(\+?\d[\d\s\-()]{6,})", re.I,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EMAIL_BASURA = (
    "example.com", "dominio.com", "tudominio", "sentry.io", "wixpress.com",
    "@2x.png", ".png", ".jpg", ".webp", ".gif", "@sentry", "godaddy",
    "email@", "correo@correo", "nombre@", "user@", "info@example",
)
NUMERO_TEXTO = re.compile(r"(?:\+?\d[\d\s.\-()]{7,17}\d)")

ORDEN = {"alta": 3, "media": 2, "baja": 1, "": 0}


class Contador:
    """
    Cuenta cuántas veces tiramos de Firecrawl. Importa porque el plan gratuito
    son 500 páginas al mes: si nos la gastáramos en webs que httpx ya resolvió,
    el alumno se quedaría sin cuota para las que de verdad la necesitan.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.firecrawl = 0
        self.rescatados_firecrawl = 0

    def uso_firecrawl(self, rescatado: bool) -> None:
        with self._lock:
            self.firecrawl += 1
            if rescatado:
                self.rescatados_firecrawl += 1


class Robots:
    """Cachea robots.txt por dominio. Ser buen ciudadano sale barato."""

    def __init__(self, activo: bool = True):
        self.activo = activo
        self._cache: dict[str, object] = {}
        self._lock = threading.Lock()

    def permitido(self, url: str) -> bool:
        if not self.activo:
            return True
        dom = dominio(url)
        with self._lock:
            faltaba = dom not in self._cache
        if faltaba:
            rp = robotparser.RobotFileParser()
            try:
                r = httpx.get(f"https://{dom}/robots.txt", headers=CABECERAS,
                              timeout=8, follow_redirects=True)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except Exception:
                rp.parse([])
            with self._lock:
                self._cache[dom] = rp
        try:
            return self._cache[dom].can_fetch(CABECERAS["User-Agent"], url)
        except Exception:
            return True


def _emails(sopa: BeautifulSoup) -> list[str]:
    salida = []
    for a in sopa.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            salida.append(a["href"][7:].split("?")[0].strip())
    salida += EMAIL.findall(sopa.get_text(" ", strip=True))
    limpios = []
    for e in salida:
        el = e.strip().lower().strip(".")
        if not el or any(b in el for b in EMAIL_BASURA):
            continue
        if el not in limpios:
            limpios.append(el)
    return limpios


def enlaces_contacto(html: str, base: str) -> list[str]:
    """
    Enlaces del menú que apuntan a la página de contacto.

    Leer el menú de la propia web acierta donde adivinar rutas falla: hay
    negocios cuyo contacto vive en /donde-estamos o /reservas.
    """
    salida = []
    try:
        sopa = BeautifulSoup(html or "", "lxml")
    except Exception:
        return salida
    for a in sopa.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        texto = a.get_text(" ", strip=True)
        if not (TEXTO_CONTACTO.search(texto) or TEXTO_CONTACTO.search(href)):
            continue
        url = urljoin(base + "/", href)
        if dominio(url) != dominio(base):
            continue          # no nos vamos a otro dominio
        if url not in salida:
            salida.append(url)
        if len(salida) >= MAX_ENLACES_MENU:
            break
    return salida


def extraer(html: str, pais: Pais) -> dict:
    """Saca {whatsapp, confianza, telefono, email} del HTML de una página."""
    sopa = BeautifulSoup(html or "", "lxml")
    texto = sopa.get_text(" ", strip=True)
    bajo = (html or "").lower()

    # 1) enlaces explícitos de WhatsApp -> confianza alta
    candidatos = [m.group(1) for m in ENLACE_WA.finditer(html or "")]
    for a in sopa.find_all("a", href=True):
        m = ENLACE_WA.search(a["href"])
        if m:
            candidatos.append(m.group(1))
    for c in candidatos:
        num = tel.desde_enlace_wa(c, pais)
        if num:
            return {"whatsapp": num, "confianza": "alta", "telefono": "",
                    "email": (_emails(sopa) or [""])[0]}

    # 2) tel: y texto con la palabra "whatsapp" cerca -> confianza media
    telefonos = []
    for a in sopa.find_all("a", href=True):
        if a["href"].lower().startswith("tel:"):
            telefonos.append(a["href"][4:])
    cerca_wa = []
    if "whatsapp" in bajo or "wa.me" in bajo:
        for m in NUMERO_TEXTO.finditer(texto):
            ctx = texto[max(0, m.start() - 90):m.end() + 90].lower()
            if "whatsapp" in ctx or "wasap" in ctx or "wsp" in ctx:
                cerca_wa.append(m.group(0))

    email = (_emails(sopa) or [""])[0]

    for bruto in cerca_wa:
        num = tel.normalizar(bruto, pais)
        if num:
            return {"whatsapp": num, "confianza": "media", "telefono": "", "email": email}

    for bruto in telefonos:
        num = tel.normalizar(bruto, pais)
        if num:
            conf = "media" if ("whatsapp" in bajo) else "baja"
            return {"whatsapp": num, "confianza": conf, "telefono": "", "email": email}

    # 3) cualquier móvil publicado en el texto -> confianza baja
    for m in NUMERO_TEXTO.finditer(texto):
        num = tel.normalizar(m.group(0), pais)
        if num:
            return {"whatsapp": num, "confianza": "baja", "telefono": "", "email": email}

    return {"whatsapp": "", "confianza": "", "telefono": "", "email": email}


def _firecrawl_html(url: str, clave: str) -> str:
    """Renderiza la página con Firecrawl (opcional): pilla botones flotantes JS."""
    try:
        r = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["html"], "onlyMainContent": False,
                  "waitFor": 3000, "timeout": 30000},
            timeout=90,
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("html", "") or ""
    except Exception:
        pass
    return ""


def rastrear_sitio(negocio: dict, pais: Pais, robots: Robots,
                   usar_firecrawl: bool = False, contador: Contador | None = None,
                   detalle=None) -> dict:
    """Visita la web del negocio y devuelve el negocio enriquecido."""
    web = (negocio.get("web") or "").strip()
    if not web:
        return negocio
    if not web.startswith("http"):
        web = "https://" + web
    base = web.rstrip("/")

    previo = negocio.get("_wa_previo", "")
    mejor = {
        "whatsapp": previo,
        "confianza": "media" if previo else "",
        "email": negocio.get("email", ""),
    }
    if detalle and previo:
        detalle(f"    {negocio.get('nombre','?')[:28]}: móvil ya en el mapa")

    rutas = list(RUTAS)
    menu_leido = False

    try:
        with httpx.Client(headers=CABECERAS, follow_redirects=True, timeout=12) as cliente:
            i = 0
            while i < len(rutas):
                ruta = rutas[i]
                i += 1
                url = ruta if ruta.startswith("http") else base + ruta
                if not robots.permitido(url):
                    continue
                try:
                    r = cliente.get(url)
                    if r.status_code >= 400:
                        continue
                    if "text/html" not in r.headers.get("content-type", "text/html"):
                        continue
                    hallazgo = extraer(r.text, pais)
                except Exception:
                    continue

                # De la portada aprendemos a dónde va su enlace de contacto.
                if not menu_leido and ruta == "":
                    menu_leido = True
                    for extra in enlaces_contacto(r.text, base):
                        if extra not in rutas:
                            rutas.append(extra)

                if ORDEN[hallazgo["confianza"]] > ORDEN[mejor["confianza"]]:
                    mejor["whatsapp"] = hallazgo["whatsapp"]
                    mejor["confianza"] = hallazgo["confianza"]
                    if detalle:
                        detalle(f"    {negocio.get('nombre','?')[:28]}: "
                                f"{hallazgo['confianza']} en {url[:52]}")
                if hallazgo["email"] and not mejor["email"]:
                    mejor["email"] = hallazgo["email"]
                if mejor["confianza"] == "alta":
                    break
    except Exception:
        pass

    # Último intento con render JS. SOLO si httpx no sacó nada bueno: gastar
    # cuota de Firecrawl en una web ya resuelta sería tirar el dinero.
    if usar_firecrawl and mejor["confianza"] in ("", "baja"):
        clave = os.environ.get("FIRECRAWL_KEY", "").strip()
        if clave:
            antes = ORDEN[mejor["confianza"]]
            html = _firecrawl_html(base, clave)
            if html:
                hallazgo = extraer(html, pais)
                if ORDEN[hallazgo["confianza"]] > ORDEN[mejor["confianza"]]:
                    mejor["whatsapp"] = hallazgo["whatsapp"]
                    mejor["confianza"] = hallazgo["confianza"]
                if hallazgo["email"] and not mejor["email"]:
                    mejor["email"] = hallazgo["email"]
            if contador:
                contador.uso_firecrawl(ORDEN[mejor["confianza"]] > antes)

    negocio = dict(negocio)
    negocio.pop("_wa_previo", None)
    negocio["whatsapp"] = mejor["whatsapp"]
    negocio["confianza"] = mejor["confianza"]
    negocio["email"] = mejor["email"] or negocio.get("email", "")
    return negocio


def enriquecer(negocios: list[dict], pais: Pais, concurrencia: int = 10,
               respetar_robots: bool = True, usar_firecrawl: bool = False,
               log=print, detalle=None) -> list[dict]:
    """
    Enriquece la lista completa. Primero resuelve lo que ya viene servido
    (etiqueta de WhatsApp en el mapa, o un móvil en el teléfono publicado) y
    solo visita la web de los que siguen sin número.
    """
    resueltos, pendientes, sin_datos = [], [], 0
    for n in negocios:
        n = dict(n)

        wa = tel.desde_enlace_wa(n.get("whatsapp_osm", ""), pais) if n.get("whatsapp_osm") else ""
        if not wa and n.get("telefono"):
            wa = tel.normalizar(n["telefono"], pais)
        if wa and not n.get("web"):
            # Sin web que visitar: nos quedamos con lo que publica el mapa.
            n["whatsapp"] = wa
            n["confianza"] = "alta" if n.get("whatsapp_osm") else "media"
            resueltos.append(n)
        elif n.get("web"):
            n["_wa_previo"] = wa
            pendientes.append(n)
        else:
            n["whatsapp"] = ""
            n["confianza"] = ""
            sin_datos += 1
            resueltos.append(n)

    directos = len(resueltos) - sin_datos
    log(f"> {directos} con móvil directo del mapa | {len(pendientes)} webs por visitar "
        f"| {sin_datos} sin web ni móvil")
    if not pendientes:
        return resueltos

    log(f"  (entro en la portada y el contacto de cada una, {concurrencia} a la vez)")
    robots = Robots(respetar_robots)
    contador = Contador()
    hechos = 0
    with ThreadPoolExecutor(max_workers=concurrencia) as ex:
        futuros = {
            ex.submit(rastrear_sitio, n, pais, robots, usar_firecrawl, contador, detalle): n
            for n in pendientes
        }
        for fut in as_completed(futuros):
            try:
                resueltos.append(fut.result())
            except Exception:
                resueltos.append(futuros[fut])
            hechos += 1
            if hechos % 20 == 0 or hechos == len(pendientes):
                con_wa = sum(1 for r in resueltos if r.get("whatsapp"))
                log(f"  · {hechos}/{len(pendientes)} webs visitadas · {con_wa} con móvil")

    if contador.firecrawl:
        log(f"  Firecrawl: {contador.firecrawl} reintentos de {len(pendientes)}, "
            f"{contador.rescatados_firecrawl} rescatados")
    return resueltos
