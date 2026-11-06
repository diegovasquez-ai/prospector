"""
Fases 3, 4 y 5: analizar cada negocio, filtrar con señales y encontrar a quién
escribirle.

Entramos en hasta cinco páginas de su web (portada, contacto, equipo, quiénes somos
y catálogo) y sacamos lo que se puede medir sin opinar:

    cómo entra una consulta    WhatsApp, chat, formulario, teléfono
    si invierten en anuncios   píxel de Meta, etiqueta de Google Ads
    qué sistema usan           HubSpot, Pipedrive... si la web lo delata
    tamaño                     lo que publican, portales, correos del equipo
    si la web está viva        el año del copyright
    si está creciendo          si busca gente
    correos                    todos los que publican, clasificados

Qué negocio sirve y cuál no depende del rubro: sale de nicho.json. Lo que exige
criterio —quién decide, si tiene equipo o es una persona con buena web, qué dato
usar como observación— no se adivina aquí. Se deja en la ficha
(fichas/<dominio>.md) para que lo lea el agente. Un regex que encuentra "Gerente
General" no sabe si es el de este negocio o el de un cliente que dejó un testimonio.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import filtro, nicho
from .base import bloqueado
from .puente import CABECERAS, EMAIL_BASURA, RAIZ, Robots, dominio, exclusiones, sin_acentos

FICHAS = RAIZ / "fichas"

# --- Qué páginas visitar ---------------------------------------------------
# Se buscan en el menú de la portada, por el texto del enlace o por su ruta.
# Nunca por el dominio: "casaandespropiedades.cl" contiene "propiedades" y todos
# sus enlaces darían positivo. Lo propio del rubro sale de nicho.json.
CONTACTO = re.compile(r"contact|cont[aá]ct|escr[ií]benos", re.I)
# Dice quiénes son: ahí se ve si es una empresa, una persona sola o una red.
EMPRESA = re.compile(r"nosotros|qui[eé]nes[\s-]*somos|about|la[\s-]*empresa|historia|sobre[\s-]*(?:mi|m[ií])\b", re.I)
# "Trabaja con nosotros" también dice "nosotros", pero no es quiénes son.
EMPLEO = re.compile(r"trabaj|emple|postul|career|vacante", re.I)


def paginas_a_buscar() -> dict:
    return {"contacto": CONTACTO, "equipo": nicho.rx_equipo(), "empresa": EMPRESA,
            "catalogo": nicho.rx_catalogo()}


NO_ES_PAGINA = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".zip", ".doc", ".docx")

# --- Cómo entra una consulta -----------------------------------------------
WHATSAPP = ("wa.me/", "api.whatsapp.com/send", "web.whatsapp.com/send",
            "whatsapp://send", "joinchat", "ht-ctc", "getbutton.io")

CHATS = {
    "Tidio": ("tidio.co",),
    "Intercom": ("intercom.io", "intercomcdn.com"),
    "Crisp": ("crisp.chat",),
    "Tawk.to": ("tawk.to",),
    "Zendesk": ("zdassets.com", "zopim.com"),
    "Drift": ("driftt.com", "js.drift.com"),
    "LiveChat": ("livechatinc.com",),
    "JivoChat": ("jivosite.com",),
    "Smartsupp": ("smartsuppchat.com",),
    "Kommo": ("kommo.com", "amocrm"),
}

# --- Qué sistema usan --------------------------------------------------------
# Que salga uno no la descarta: con Tokko o HubSpot ya tienen dónde guardar la
# consulta, y lo que falta es quién la responda. Cambia el ángulo del correo.
# Los propios del rubro se suman desde nicho.json.
SISTEMAS = {
    # Kommo es chat y CRM a la vez: sale en las dos listas a propósito.
    "Kommo": ("kommo.com", "amocrm"),
    "HubSpot": ("js.hs-scripts.com", "hsforms.net"),
    "Salesforce": ("pardot.com", ".force.com"),
    "Pipedrive": ("pipedrive.com",),
    "Zoho": ("zohopublic", "salesiq.zoho"),
    "RD Station": ("rdstation",),
    "Clientify": ("clientify",),
}

# Un bot o agente ya instalado: ya compraron algo parecido a lo que ofreces.
BOTS = {
    "ManyChat": ("manychat.com",),
    "Landbot": ("landbot.io",),
    "Botmaker": ("botmaker.com",),
    "Chatbase": ("chatbase.co",),
    "Treble": ("treble.ai",),
    "Wati": ("wati.io",),
    "Yalo": ("yalo.com",),
    "Voiceflow": ("voiceflow.com",),
    "Botpress": ("botpress.cloud",),
}

GOOGLE_ADS = re.compile(r"\baw-\d{6,}|googleadservices\.com")
# Busca gente: está creciendo, o le falta tiempo. Sale en el texto o en el menú.
CONTRATANDO = re.compile(
    r"trabaja con nosotros|[uú]nete a (?:nuestro|el) equipo|estamos contratando|bolsa de trabajo|"
    r"ofertas? de empleo|vacantes|buscamos (?:personas|talento|ejecutiv|vendedor|asesor|recepcionista|asistente)",
    re.I)
COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:20\d\d\s*[-–]\s*)?(20\d\d)")
SUCURSALES = re.compile(r"\bsucursal(?:es)?\b|\boficinas en\b", re.I)
CARGOS = re.compile(
    r"gerente general|gerente comercial|socio fundador|socia fundadora|"
    r"(?:co-?)?fundador[a]?\b|\b(?:co-?)?founder\b|"
    r"director[a]? (?:general|comercial|ejecutiv[oa])|\bdue[ñn][oa]\b|\bceo\b|"
    r"socio director|socia directora|socio gerente|socia gerente|"
    r"corredora? principal|broker owner", re.I)

# --- Qué es cada una ---------------------------------------------------------
# Webs de una sola persona: un perfil en una plataforma, no una empresa.
PLATAFORMAS_PERSONALES = ("encuadrado.com", "linktr.ee", "wixsite.com",
                          "sites.google.com", "carrd.co", "beacons.ai")

# --- Correos -----------------------------------------------------------------
EMAIL = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}", re.I)
GENERICOS = {
    "contacto", "contact", "info", "informacion", "informaciones", "hola",
    "ventas", "venta", "arriendos", "arriendo", "propiedades", "consultas",
    "administracion", "admin", "clientes", "servicioalcliente", "atencion",
    "atencionclientes", "recepcion", "oficina", "comercial", "marketing", "rrhh",
    "postulaciones", "trabajo", "corretaje", "secretaria", "web", "webmaster",
    "noreply", "no-reply", "soporte", "pagos", "cobranza", "finanzas",
    "contabilidad", "tasaciones", "captacion", "captaciones", "corredora",
    "corredores", "legal", "atencionalcliente", "atencioncliente",
}
# No llevan nombre, pero los lee quien decide.
DIRECCION = {"gerencia", "gerente", "direccion", "director", "dueno", "socio", "socios"}
WEBMAIL = ("gmail.", "hotmail.", "outlook.", "yahoo.", "live.", "icloud.", "msn.")
ORDEN_CORREO = {"direccion": 0, "persona": 1, "generico": 2, "webmail": 3}


def clasificar_correo(correo: str, dominios: set[str]) -> tuple[str, str]:
    """
    (clase, estado). Los estados son los de la Fase 5:

      verificado   de una persona o de gerencia, en su propio dominio y
                   publicado por ellos en su web. Se envía.
      dudoso       genérico de su dominio (contacto@, ventas@) o un webmail.
                   Llega a la empresa, no sabemos si a quien decide. Decides tú.
      supuesto     deducido por patrón, nunca publicado. No se envía. Este
                   módulo no inventa correos, así que nunca lo asigna: es la
                   etiqueta para los que añadas a mano.

    "Publicado en su web" no es lo mismo que "comprobado que el buzón existe":
    para eso hace falta un verificador (Hunter o similar).
    """
    local, _, dom = correo.partition("@")
    propio = any(dom == d or dom.endswith("." + d) or d.endswith("." + dom)
                 for d in dominios if d)
    if not propio:
        if dom.startswith(WEBMAIL):
            return "webmail", "dudoso"
        # El correo de la agencia que les hizo la web, el del portal...
        return "ajeno", "no usar"
    trozos = {t for t in re.split(r"[.\-_+\d]", local) if t} | {local}
    if trozos & DIRECCION:
        return "direccion", "verificado"
    # area.legal@, ventas.web@... y el que repite la marca: marcauno@marcauno.cl
    if trozos & GENERICOS or local == dom.split(".")[0]:
        return "generico", "dudoso"
    return "persona", "verificado"


# --- Bajar páginas -------------------------------------------------------------

def _bajar(cli: httpx.Client, url: str, robots: Robots) -> tuple[tuple[str, str] | None, str]:
    """((url final, html), "") o (None, por qué falló)."""
    if not robots.permitido(url):
        return None, "su robots.txt no deja leerla"
    try:
        r = cli.get(url)
    except httpx.ConnectError as e:
        if "getaddrinfo" in str(e) or "Name or service not known" in str(e):
            return None, "dominio"
        if "CERTIFICATE" in str(e):
            return None, "certificado de seguridad roto"
        return None, "no responde"
    except Exception:
        return None, "no responde"
    if r.status_code in (401, 403, 429):
        return None, f"bloquea las visitas automáticas ({r.status_code})"
    if r.status_code >= 400:
        return None, f"da error {r.status_code}"
    if "html" not in r.headers.get("content-type", "text/html"):
        return None, "no es una página"
    return (str(r.url), r.text), ""


def _elegir_enlaces(html: str, base: str) -> dict[str, str]:
    """De cada tipo de página, el enlace del menú con la ruta más corta."""
    buscadas = paginas_a_buscar()
    candidatos: dict[str, list[str]] = {t: [] for t in buscadas}
    sopa = BeautifulSoup(html, "lxml")
    for a in sopa.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "#", "javascript:", "whatsapp:")):
            continue
        url = urljoin(base + "/", href).split("#")[0]
        if dominio(url) != dominio(base) or url.lower().endswith(NO_ES_PAGINA):
            continue
        ruta = urlparse(url).path
        if ruta.strip("/") == "":
            continue
        texto = a.get_text(" ", strip=True)
        for tipo, rx in buscadas.items():
            if tipo in ("equipo", "empresa") and (EMPLEO.search(texto) or EMPLEO.search(ruta)):
                continue
            if rx.search(texto) or rx.search(ruta):
                candidatos[tipo].append(url)

    elegidos, usados = {}, set()
    for tipo, urls in candidatos.items():
        for url in sorted(set(urls), key=lambda u: (urlparse(u).path.count("/"), len(u))):
            if url not in usados:
                elegidos[tipo] = url
                usados.add(url)
                break
    if "contacto" not in elegidos:
        elegidos["contacto"] = base.rstrip("/") + "/contacto"
    return elegidos


def _visitar(web: str, robots: Robots) -> tuple[dict[str, tuple[str, str]], str]:
    """({tipo: (url, html)} con las páginas que respondieron, por qué falló la portada)."""
    if not web.startswith("http"):
        web = "https://" + web
    paginas = {}
    with httpx.Client(headers=CABECERAS, follow_redirects=True, timeout=12) as cli:
        portada, fallo = _bajar(cli, web, robots)
        if not portada:
            return {}, fallo
        paginas["portada"] = portada
        for tipo, url in _elegir_enlaces(portada[1], portada[0]).items():
            pagina, _ = _bajar(cli, url, robots)
            if pagina:
                paginas[tipo] = pagina
    return paginas, ""


def _texto(sopa: BeautifulSoup) -> str:
    for t in sopa(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    return re.sub(r"\s+", " ", sopa.get_text(" ", strip=True))


def _tiene_formulario(sopa: BeautifulSoup) -> bool:
    """Un formulario de contacto, no el buscador de propiedades."""
    for f in sopa.find_all("form"):
        rasgos = " ".join([f.get("action") or "", f.get("role") or "", f.get("id") or "",
                           " ".join(f.get("class") or [])]).lower()
        if any(p in rasgos for p in ("search", "buscar", "busqueda", "filtro")):
            continue
        if f.find("textarea") or f.find("input", attrs={"type": "email"}):
            return True
    return False


def _correos(sopa: BeautifulSoup, texto: str) -> list[str]:
    # unquote: hay mailto escritos como "mailto:%20contacto@...".
    brutos = [unquote(a["href"][7:].split("?")[0]) for a in sopa.find_all("a", href=True)
              if a["href"].lower().startswith("mailto:")]
    brutos += EMAIL.findall(texto)
    salida = []
    for c in brutos:
        c = c.strip().lower().strip(".")
        # fullmatch: un mailto: puede traer cualquier cosa ("x@localhost:8080").
        if not EMAIL.fullmatch(c) or any(b in c for b in EMAIL_BASURA):
            continue
        if c not in salida:
            salida.append(c)
    return salida


# --- Medir ----------------------------------------------------------------------

def _numeros_wa(html: str) -> list[str]:
    from .whatsapp import numeros_en  # aquí: whatsapp importa este paquete
    return numeros_en(html, nicho.pais())


def medir(lead: dict, paginas: dict[str, tuple[str, str]]) -> tuple[dict, dict[str, str]]:
    """Devuelve (señales, textos por página). Los textos solo van a la ficha."""
    nc = nicho.actual()
    detalle, conteo = nicho.rx_detalle(), nicho.rx_conteo()
    html_todo = " ".join(h for _, h in paginas.values()).lower()
    textos, correos, enlaces, formulario, telefono = {}, [], set(), False, False
    detalles, conteos = set(), [0]

    for tipo, (url, html) in paginas.items():
        sopa = BeautifulSoup(html, "lxml")
        for a in sopa.find_all("a", href=True):
            href = a["href"].strip()
            enlaces.add(href.lower())
            if href.lower().startswith("tel:"):
                telefono = True
            if tipo in ("portada", "catalogo"):
                completa = urljoin(url, href)
                if dominio(completa) == dominio(url) and detalle.search(urlparse(completa).path):
                    detalles.add(urlparse(completa).path)
        formulario = formulario or _tiene_formulario(sopa)
        texto = _texto(sopa)
        textos[tipo] = texto
        for c in _correos(sopa, texto):
            if c not in correos:
                correos.append(c)
        for m in conteo.finditer(texto):
            n = int(re.sub(r"[.,]", "", m.group(1)))
            if n <= 20000:
                conteos.append(n)

    dominios = {dominio(lead.get("web") or "")} | {dominio(u) for u, _ in paginas.values()}
    clasificados = []
    for c in correos:
        clase, estado = clasificar_correo(c, dominios)
        clasificados.append({"correo": c, "clase": clase, "estado": estado})

    # Las frases con un cargo, empezando por la página de equipo.
    cargos = []
    for tipo in ("equipo", "empresa", "portada", "contacto", "catalogo"):
        texto = textos.get(tipo, "")
        for m in CARGOS.finditer(texto):
            trozo = texto[max(0, m.start() - 70):m.end() + 50].strip()
            if not any(trozo[:40] in c for c in cargos):
                cargos.append(trozo)
            if len(cargos) >= 5:
                break

    anos = [int(a) for a in COPYRIGHT.findall(html_todo)]
    contrata = CONTRATANDO.search(" ".join(textos.values()))
    senales = {
        "fecha": date.today().isoformat(),
        "paginas": {t: u for t, (u, _) in paginas.items()},
        "whatsapp": any(w in html_todo for w in WHATSAPP),
        "whatsapp_numeros": _numeros_wa(html_todo),
        "chat": [n for n, huellas in CHATS.items() if any(h in html_todo for h in huellas)],
        "bots": [n for n, huellas in BOTS.items() if any(h in html_todo for h in huellas)],
        "contratando": contrata.group(0) if contrata else "",
        "formulario": formulario,
        "telefono": telefono,
        "meta_pixel": "connect.facebook.net" in html_todo and (
            "fbevents.js" in html_todo or "fbq(" in html_todo),
        "google_ads": bool(GOOGLE_ADS.search(html_todo)),
        "gtm": "googletagmanager.com/gtm.js" in html_todo,
        "sistemas": [n for n, huellas in {**SISTEMAS, **nc["sistemas"]}.items() if any(h in html_todo for h in huellas)],
        "portales": [n for n, d in nc["portales"].items() if any(d in e for e in enlaces)],
        # Dos cifras distintas y no se mezclan en el correo: una es lo que
        # contamos nosotros, la otra lo que ellos dicen de sí mismos.
        "catalogo_fichas": len(detalles),
        "catalogo_texto": max(conteos),
        "sucursales": bool(SUCURSALES.search(" ".join(textos.values()))),
        "copyright": max(anos) if anos else None,
        "correos": clasificados,
        "cargos": cargos,
        "biblioteca_meta": ("https://www.facebook.com/ads/library/?active_status=active"
                            f"&ad_type=all&country={nicho.pais().codigo}&search_type=keyword_unordered&q="
                            + quote_plus(lead.get("nombre", ""))),
    }
    return senales, textos


def tipo_de(lead: dict, textos: dict[str, str], fallo: str = "") -> tuple[str, str]:
    """(tipo, motivo). Solo 'objetivo' sigue adelante, y 'dudosa' a revisión."""
    n = nicho.actual()
    nombre = sin_acentos(lead.get("nombre", "")).lower()
    web = (lead.get("web") or "").lower()
    categoria = sin_acentos((lead.get("categoria") or "").split(",")[0]).lower()
    # Si el nombre confirma el rubro, manda sobre la categoría de Maps, que la
    # rellena cualquiera (una corredora puede salir como Condominio).
    se_confirma = any(p.lower() in nombre for p in n["confirman_en_nombre"])

    if any(f.lower() in nombre or f.lower() in web for f in n["cadenas"]):
        return "franquicia", "cadena o red con sistema corporativo"
    if any(d in web for d in (*n["portales"].values(), *n["directorios"])):
        return "portal", "su web es un portal o directorio, no la del negocio"
    if not se_confirma:
        for regla in n["descartar"]:
            if (any(c in categoria for c in regla.get("en_categoria", []))
                    or any(nombre.startswith(p) for p in regla.get("nombre_empieza", []))):
                return regla["tipo"], f"Maps lo cataloga como «{categoria or nombre}»"
    if any(p in web for p in PLATAFORMAS_PERSONALES):
        return "independiente", "perfil personal, sin web de empresa"
    if not web:
        return "sin web", "sin web no hay correo ni nada que investigar"
    if fallo == "dominio":
        return "abandonada", "su dominio ya no existe"
    if not textos:
        return "web cerrada", f"su web {fallo}: ábrela a mano"

    texto = sin_acentos(" ".join(textos.values())).lower()
    confirma = sum(texto.count(w) for w in n["confirman_en_web"])
    # En orden y comparando cuál pesa más: una corredora también dice "inversión"
    # a veces, y lo que importa es de qué habla sobre todo.
    for regla in n["descartar"]:
        cuenta = sum(texto.count(w) for w in regla.get("en_web", []))
        if not cuenta:
            continue
        if any(p in nombre for p in regla.get("en_nombre", [])) and cuenta >= confirma:
            return regla["tipo"], regla.get("motivo", "")
        if cuenta >= regla.get("min_web", 2) and cuenta > confirma:
            return regla["tipo"], regla.get("motivo", "")
    if confirma or se_confirma or not n["confirman_en_web"]:
        return "objetivo", ""
    return "dudosa", f"su web no parece de {n['rubro']}: confírmalo antes de escribir"


def _entero(valor) -> int:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


def calificar(lead: dict, s: dict) -> dict:
    """
    Fase 4. Lo que hay que saber antes de ofrecerle IA o automatización:

        volumen     ¿le llegan clientes? Sin volumen no hay nada que automatizar.
        capacidad   ¿puede pagar? Ya paga software o anuncios, o tiene equipo.
        manual      ¿hay trabajo repetitivo a la vista? Lo cita el filtro de Claude.
        momento     ¿está creciendo? Busca gente.

    Cada señal lleva sus puntos y una frase que ya se lee en la ficha. "Sin chat" no
    suma: lo cumplen casi todos, así que no distingue a nadie.
    """
    nc = nicho.actual()
    cat, umbral = nc["catalogo"], nc.get("resenas") or {}
    etiqueta, minimo = cat.get("etiqueta") or "elementos", cat.get("minimo") or 30
    bloques: dict[str, list[tuple[str, int]]] = {"volumen": [], "capacidad": [], "manual": [], "momento": []}

    resenas = _entero(lead.get("resenas"))
    if resenas >= umbral.get("muy_bueno", 100):
        bloques["volumen"].append((f"{resenas} reseñas en Google", 4))
    elif resenas >= umbral.get("bueno", 20):
        bloques["volumen"].append((f"{resenas} reseñas en Google", 2))
    if s["catalogo_fichas"] >= minimo:
        bloques["volumen"].append((f"{s['catalogo_fichas']} fichas de {etiqueta} enlazadas en su web", 1))
    elif s["catalogo_texto"] >= minimo:
        bloques["volumen"].append((f"su web dice «{s['catalogo_texto']} {etiqueta}»", 1))
    if s["sucursales"]:
        bloques["volumen"].append(("menciona sucursales u oficinas", 1))

    if s["sistemas"]:
        bloques["capacidad"].append(("ya paga software: " + ", ".join(s["sistemas"]), 2))
    personas = sum(1 for c in s["correos"] if c["clase"] == "persona")
    if personas >= 5:
        bloques["capacidad"].append((f"{personas} correos de personas del equipo", 2))
    if s["meta_pixel"]:
        bloques["capacidad"].append(("píxel de Meta en su web", 1))
    if s["google_ads"]:
        bloques["capacidad"].append(("etiqueta de Google Ads", 1))
    if s["portales"]:
        bloques["capacidad"].append(("enlaza a " + ", ".join(s["portales"]), 1))

    numeros = len(s.get("whatsapp_numeros") or [])
    if numeros >= 2:
        bloques["manual"].append((f"atiende por {numeros} WhatsApp distintos", 1))
    if s["formulario"] and not s["whatsapp"] and not s["chat"]:
        bloques["manual"].append(("las consultas entran solo por formulario", 1))
    # Sirven para escribirle y ordenan poco: un punto, aunque Claude cite dos.
    for i, tarea in enumerate(((lead.get("filtro") or {}).get("trabajo_manual") or [])[:2]):
        bloques["manual"].append((f"{tarea['tarea']} («{tarea['cita']}»)", 0 if i else 1))

    if s.get("contratando"):
        bloques["momento"].append((f"busca gente: «{s['contratando']}»", 1))

    contras = []
    # Medio internet lleva el año del pie sin actualizar: solo cuenta si es muy viejo,
    # y con muchas reseñas el negocio sigue vivo aunque su web no.
    if (s["copyright"] and s["copyright"] <= date.today().year - 4
            and resenas < umbral.get("bueno", 20)):
        contras.append(f"copyright de {s['copyright']}: puede estar abandonada")
    if s.get("bots"):
        contras.append("ya usa un bot: " + ", ".join(s["bots"]))
    puntos = {b: sum(n for _, n in lista) for b, lista in bloques.items()}
    return {
        "bloques": {b: [f for f, _ in lista] for b, lista in bloques.items()},
        "puntos": puntos, "contras": contras,
        # Volumen o capacidad, con más de una señal débil: lo que separa a un negocio
        # con algo que automatizar y con qué pagarlo de uno con una web bonita.
        "suficiente": puntos["volumen"] + puntos["capacidad"] >= 2,
    }


def _aplicar_calificacion(lead: dict, cal: dict) -> None:
    b = cal["bloques"]
    verificado = 1 if lead["correo_estado"] == "verificado" else 0
    lead.update(puntaje=sum(cal["puntos"].values()) + verificado - 2 * len(cal["contras"]),
                calificacion=cal["puntos"],
                puede_pagar=b["volumen"] + b["capacidad"], le_falta=b["manual"] + b["momento"])


def analizar_uno(lead: dict, robots: Robots) -> dict:
    lead = dict(lead)
    paginas, fallo = _visitar(lead["web"], robots) if lead.get("web") else ({}, "")
    senales, textos = medir(lead, paginas) if paginas else (None, {})
    tipo, motivo = tipo_de(lead, textos, fallo)
    lead.update(tipo=tipo, motivo=motivo, analisis=senales,
                puede_pagar=[], le_falta=[], puntaje=0, calificacion={}, correo="", correo_estado="")

    if tipo == "web cerrada":
        # Bloqueo, certificado roto, error del servidor: el negocio existe,
        # solo que no nos deja leerla. No se descarta, se mira a mano.
        lead["estado"] = "floja"
        return lead
    if tipo not in ("objetivo", "dudosa"):
        lead["estado"] = "descartada"
        return lead

    usables = sorted((c for c in senales["correos"] if c["clase"] in ORDEN_CORREO),
                     key=lambda c: ORDEN_CORREO[c["clase"]])
    if usables:
        lead["correo"], lead["correo_estado"] = usables[0]["correo"], usables[0]["estado"]
    cal = calificar(lead, senales)
    _aplicar_calificacion(lead, cal)

    if tipo == "dudosa":
        lead["estado"] = "floja"
    elif cal["contras"]:
        lead["estado"], lead["motivo"] = "floja", cal["contras"][0]
    elif not cal["suficiente"]:
        lead["estado"] = "floja"
        lead["motivo"] = "pocas señales de que le lleguen clientes o pueda pagar"
    elif not usables:
        lead["estado"], lead["motivo"] = "sin correo", "no publica ningún correo usable"
    else:
        lead["estado"] = "candidata"
        _filtrar(lead, senales, textos)
    escribir_ficha(lead, textos)
    return lead


def _filtrar(lead: dict, senales: dict, textos: dict[str, str]) -> None:
    """
    El filtro de Claude, solo para las que ya pasaron lo medible. Si falla, siguen.
    Aparta, no descarta: una floja no se investiga sola, pero desde el Radar se puede
    mandar a investigar igual si el filtro se equivocó.
    """
    resultado = filtro.revisar(lead, textos)
    if not resultado:
        return
    lead["filtro"] = resultado
    _aplicar_calificacion(lead, calificar(lead, senales))
    veredicto, cita = resultado["veredicto"], resultado.get("cita")
    minimo, personas = nicho.actual().get("equipo_minimo", 3), resultado.get("personas")
    if veredicto == "no_sirve" or (veredicto == "dudoso" and resultado["tipo"] in filtro.DESCARTABLES):
        lead.update(estado="floja", motivo=f"Claude: {resultado['motivo']}" + (f" («{cita}»)" if cita else ""))
    elif personas is not None and personas < minimo:
        # Puede haber más gente de la que muestra su web: esto lo mira una persona.
        lead.update(estado="floja", motivo=f"Claude ve solo {personas} persona(s) en su web: {resultado['motivo']}")
    elif veredicto == "dudoso":
        lead["motivo"] = f"Claude duda: {resultado['motivo']}"


def analizar(base: dict[str, dict], todas: bool = False, concurrencia: int = 8,
             log=print) -> dict[str, int]:
    """Analiza las nuevas (o todas) y devuelve cuántas quedaron en cada estado."""
    fuera = exclusiones.cargar()
    pendientes = []
    for k, l in base.items():
        if bloqueado(l, fuera):
            base[k]["estado"] = "baja"
        elif todas or l.get("estado") == "nueva":
            pendientes.append(k)

    log(f"> {len(pendientes)} negocios por analizar ({concurrencia} a la vez)")
    robots = Robots(True)
    hechas = 0
    with ThreadPoolExecutor(max_workers=concurrencia) as ex:
        futuros = {ex.submit(analizar_uno, base[k], robots): k for k in pendientes}
        for fut in as_completed(futuros):
            k = futuros[fut]
            try:
                base[k] = fut.result()
            except Exception as e:
                log(f"  ! {base[k].get('nombre', k)[:30]}: {type(e).__name__}, la salto")
            hechas += 1
            if hechas % 10 == 0 or hechas == len(pendientes):
                log(f"  · {hechas}/{len(pendientes)} analizadas")

    conteo: dict[str, int] = {}
    for l in base.values():
        conteo[l.get("estado", "nueva")] = conteo.get(l.get("estado", "nueva"), 0) + 1
    return conteo


# --- La ficha -------------------------------------------------------------------

def _si(v) -> str:
    return "sí" if v else "no"


def _ficha_filtro(lead: dict) -> list[str]:
    f = lead.get("filtro")
    if not f:
        return []
    personas = f"{f['personas']} personas a la vista · " if f.get("personas") else ""
    L = ["## Filtro de Claude (revísalo: es una primera lectura)",
         f"{f['veredicto']} · {f['tipo']} · {personas}{f['motivo']}"]
    if f.get("cita"):
        L.append(f"> {f['cita']}")
    return [*L, ""]


def escribir_ficha(lead: dict, textos: dict[str, str]) -> None:
    """
    Lo que lee el agente antes de redactar. Separa lo medido (arriba) del
    texto en bruto de su web (abajo), para que la observación del correo
    salga de un dato y no de una impresión.
    """
    s = lead["analisis"]
    propios = [c for c in s["correos"] if c["clase"] != "ajeno"]
    ajenos = [c["correo"] for c in s["correos"] if c["clase"] == "ajeno"]
    FICHAS.mkdir(exist_ok=True)
    nombre_archivo = re.sub(r"[^a-z0-9.\-]", "-", dominio(lead["web"]) or "sin-web")
    L = [
        f"# {lead['nombre']}",
        "",
        f"{lead['web']} · {lead.get('comuna', '')} · Maps {lead.get('rating') or '?'}★"
        f" ({lead.get('resenas') or '?'} reseñas) · {lead.get('categoria') or 'sin categoría'}",
        f"Estado: **{lead['estado']}** · puntaje {lead['puntaje']} · tipo {lead['tipo']}"
        + (f" · {lead['motivo']}" if lead.get("motivo") else ""),
        f"Analizada el {s['fecha']}",
        "",
        "## Le llegan clientes y puede pagar",
        *([f"- {x}" for x in lead["puede_pagar"]] or ["- (nada medible)"]),
        "",
        "## Trabajo manual y momento",
        *([f"- {x}" for x in lead["le_falta"]] or ["- (nada visible)"]),
        "",
        *_ficha_filtro(lead),
        "## Cómo entra una consulta",
        f"WhatsApp {_si(s['whatsapp'])} · chat {', '.join(s['chat']) or 'no'}"
        f" · bot {', '.join(s.get('bots') or []) or 'no'}"
        f" · formulario {_si(s['formulario'])} · teléfono {_si(s['telefono'])}",
        f"WhatsApp publicado: {', '.join(s['whatsapp_numeros']) or 'ninguno en un botón'}",
        "",
        "## Anuncios",
        f"Píxel de Meta {_si(s['meta_pixel'])} · Google Ads {_si(s['google_ads'])}"
        f" · Tag Manager {_si(s['gtm'])}" + (" (puede esconder píxeles)" if s["gtm"] else ""),
        f"Anuncios activos, comprobar a mano: {s['biblioteca_meta']}",
        "",
        "## Sistema y tamaño",
        f"Sistema detectado: {', '.join(s['sistemas']) or 'ninguno'}",
        f"Lo que publican: {s['catalogo_fichas']} fichas enlazadas (contadas por nosotros)"
        f" · {s['catalogo_texto'] or 'nada'} según su propio texto",
        f"Portales enlazados: {', '.join(s['portales']) or 'ninguno'}"
        f" · sucursales: {_si(s['sucursales'])} · copyright: {s['copyright'] or '?'}",
        "",
        "## Correos",
        *([f"- {c['correo']} · {c['clase']} · **{c['estado']}**" for c in propios]
          or ["- ninguno propio publicado"]),
        *([f"- de otros dominios, no usar ({len(ajenos)}): {', '.join(ajenos[:3])}"
           + ("..." if len(ajenos) > 3 else "")] if ajenos else []),
        "",
        "## Posible decisor (léelo: un regex no distingue)",
        *([f"> {c}" for c in s["cargos"]] or ["- ningún cargo en el texto: búscalo en LinkedIn"]),
        "",
        "## Páginas visitadas",
        *[f"- {t}: {u}" for t, u in s["paginas"].items()],
        "",
        "## Texto de su web",
    ]
    for tipo, limite in (("portada", 1500), ("empresa", 1500), ("equipo", 1500), ("contacto", 600), ("catalogo", 500)):
        if textos.get(tipo):
            L += ["", f"### {tipo}", textos[tipo][:limite]]
    (FICHAS / f"{nombre_archivo}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
