"""
Google Maps, gratis y sin API key.

Cuando abres Google Maps y buscas "barberías en Getafe", la página no trae los
resultados dentro: los pide después a un endpoint interno que devuelve un JSON
enorme. Ese endpoint es público y responde a httpx sin navegador, sin cuenta y
sin pagar nada. Es lo que hace este módulo.

Rinde mucho más que las demás fuentes: Maps publica el teléfono y la web de
casi todos los negocios, mientras que OpenStreetMap solo los tiene en un puñado.

    Medido en Madrid: 99 negocios únicos en 5 páginas, 6 segundos, 0 euros.

AVISO SOBRE LA FRAGILIDAD
Los datos vienen como listas anidadas sin nombres: el nombre del negocio está
en la posición 11, la dirección en la 39... Google no documenta esto y lo puede
cambiar cuando quiera. Por eso TODO lo que sale del árbol pasa por g(), que
devuelve None en vez de reventar. Si mañana la 39 deja de ser la dirección,
perdemos la dirección; no perdemos la ejecución.
"""

import json
import re
import time

import httpx

from .. import lead
from ..filtros import dominio_util
from ..geo import centro
from ..paises import Pais

# El endpoint quiere estos parámetros empaquetados en un solo string. Los que
# nos importan son los tres interpolados; el resto le dice qué campos incluir.
#
#   OJO: va !2d{LONGITUD} y luego !3d{LATITUD}. Longitud primero. Si los
#   inviertes, Google te devuelve resultados del hemisferio contrario sin
#   dar ningún error. Es la trampa más cara de este fichero.
PB = ("!4m12!1m3!1d{zoom}!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1"
      "!7i{por_pagina}!8i{offset}!10b1!12m3!1e3!2b1!3e3!2b1!5m1!1e2!10b1!16b1")

ZOOM = 20000          # radio aproximado en metros que abarca la búsqueda
POR_PAGINA = 20       # lo máximo que devuelve el endpoint de una tacada

CABECERAS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Referer": "https://www.google.com/maps/",
}

# Sin la cookie de consentimiento el endpoint contesta 200 con 5 KB vacíos.
# No identifica a nadie: es la misma que se pone al pulsar "Aceptar" en el
# aviso de cookies de Google.
COOKIES = {
    "SOCS": "CAISHAgCEhJnd3NfMjAyNDA5MDMtMF9SQzEaAmVzIAEaBgiA_LyyBg",
    "CONSENT": "YES+",
}

# Un teléfono internacional, sea del país que sea. Deliberadamente genérico:
# la primera versión de esto usaba el prefijo del país y funcionaba en España
# pero devolvía CERO fichas en México. Los formatos nacionales varían
# demasiado como para fiarse de ellos aquí.
TELEFONO = re.compile(r'"(\+\d[\d ().\-]{7,17})"')
URL = re.compile(r'https?://[^"\\ ]{6,90}')


def g(nodo, *indices):
    """
    Baja por índices sin romperse.  g(ficha, 4, 7) es ficha[4][7], o None.

    Es la red de seguridad de todo el módulo: los índices de Google no están
    documentados y cambian sin avisar. Perder un campo es aceptable; que se
    caiga la caza del alumno, no.
    """
    for i in indices:
        try:
            nodo = nodo[i]
        except (IndexError, KeyError, TypeError):
            return None
    return nodo


def _fichas(datos) -> list:
    """
    Saca las fichas de negocio del árbol que devuelve Google.

    La estructura es datos[0][1] = lista de resultados, y dentro de cada
    resultado la ficha es la primera sublista larga cuyo elemento 11 es el
    nombre. Buscarlas así (por forma) y no por contenido es lo que hace que
    esto funcione igual en España, Chile, México o Estados Unidos.
    """
    salida = []
    for resultado in (g(datos, 0, 1) or []):
        if not isinstance(resultado, list):
            continue
        for candidato in resultado:
            if not isinstance(candidato, list) or len(candidato) <= 30:
                continue
            nombre = g(candidato, 11)
            if isinstance(nombre, str) and nombre.strip():
                salida.append(candidato)
                break
    return salida


def _numero(valor):
    """El rating y las coordenadas vienen como float; los queremos como texto."""
    return str(valor) if isinstance(valor, (int, float)) else ""


def _a_negocio(ficha, ciudad: str, nicho: str) -> dict | None:
    """
    Convierte una ficha cruda en un lead. Solo el nombre es obligatorio: sin
    nombre no hay nada que ofrecerle al usuario, pero un negocio sin rating o
    sin dirección sigue siendo un buen prospecto.
    """
    nombre = g(ficha, 11)
    if not isinstance(nombre, str) or not nombre.strip():
        return None

    crudo = json.dumps(ficha, ensure_ascii=False)

    telefono = ""
    m = TELEFONO.search(crudo)
    if m:
        telefono = m.group(1).strip()

    web = ""
    for url in URL.findall(crudo):
        url = url.rstrip('",\\')
        if dominio_util(url):
            web = url
            break

    categorias = [c for c in (g(ficha, 13) or []) if isinstance(c, str)]

    return lead.nuevo(
        nombre=nombre.strip(),
        web=web,
        telefono=telefono,
        direccion=g(ficha, 39) if isinstance(g(ficha, 39), str) else "",
        categoria=", ".join(categorias[:3]),
        rating=_numero(g(ficha, 4, 7)),
        resenas=_numero(g(ficha, 4, 8)),
        lat=_numero(g(ficha, 9, 2)),
        lng=_numero(g(ficha, 9, 3)),
        ciudad=ciudad,
        nicho=nicho,
        fuente="google_maps",
    )


def _pedir(consulta: str, lat: float, lng: float, offset: int,
           pais: Pais, cliente: httpx.Client):
    """Una página de resultados. Devuelve el árbol ya parseado, o None."""
    pb = PB.format(zoom=ZOOM, lat=lat, lng=lng,
                   por_pagina=POR_PAGINA, offset=offset)
    try:
        r = cliente.get(
            "https://www.google.com/search",
            params={"tbm": "map", "authuser": "0", "hl": pais.idioma,
                    "gl": pais.codigo.lower(), "q": consulta, "pb": pb},
            headers={**CABECERAS,
                     "Accept-Language": f"{pais.idioma}-{pais.codigo},{pais.idioma};q=0.9"},
            cookies=COOKIES, timeout=45, follow_redirects=True,
        )
    except Exception:
        return None

    if r.status_code == 429 or "/sorry/" in str(r.url):
        return "limitado"
    if r.status_code != 200 or len(r.text) < 5000:
        return None
    try:
        return json.loads(r.text.split("\n", 1)[1])
    except Exception:
        return None


def buscar(nicho: str, ciudad: str, pais: Pais, limite: int = 200,
           log=print, depurar: bool = False) -> list[dict]:
    """
    Busca negocios en Google Maps. Misma firma que el resto de fuentes.

    Con depurar=True guarda el árbol crudo de la primera página en
    resultados/_maps-crudo-<ciudad>.json, que es lo que hay que adjuntar en un
    issue si Google cambia el formato.
    """
    punto = centro(ciudad, pais)
    if not punto:
        log(f"  ! No pude ubicar '{ciudad}' en el mapa.")
        return []
    lat, lng = punto

    consulta = f"{nicho} en {ciudad}"
    negocios: dict[str, dict] = {}
    paginas = max(1, (limite + POR_PAGINA - 1) // POR_PAGINA)
    sin_contacto = 0
    crudo_guardado = None

    with httpx.Client() as cliente:
        for pagina in range(paginas):
            datos = _pedir(consulta, lat, lng, pagina * POR_PAGINA, pais, cliente)

            if datos == "limitado":
                log("  ! Google nos está limitando. Espera unos minutos o usa -f osm.")
                break
            if datos is None:
                if pagina == 0:
                    log("  ! Google no devolvió resultados.")
                    log("    Puede ser la cookie de consentimiento, o que no haya")
                    log("    negocios de ese tipo por ahí. Sigo con las demás fuentes.")
                break

            if depurar and crudo_guardado is None:
                crudo_guardado = datos

            fichas = _fichas(datos)
            if not fichas:
                if pagina == 0:
                    log("  ! Google respondió, pero no reconocí ninguna ficha.")
                    log("    Probablemente hayan cambiado el formato: ejecuta otra vez")
                    log("    con --depurar-maps y abre un issue con el JSON.")
                break

            nuevos = 0
            for ficha in fichas:
                negocio = _a_negocio(ficha, ciudad, nicho)
                if not negocio:
                    continue
                clave = negocio["nombre"].strip().lower()
                if clave in negocios:
                    continue
                negocios[clave] = negocio
                nuevos += 1
                if not negocio["telefono"] and not negocio["web"]:
                    sin_contacto += 1

            con_tel = sum(1 for n in list(negocios.values())[-nuevos:] if n["telefono"]) if nuevos else 0
            con_web = sum(1 for n in list(negocios.values())[-nuevos:] if n["web"]) if nuevos else 0
            if nuevos:
                log(f"  página {pagina + 1}    {nuevos:2} negocios     "
                    f"{con_tel:2} con teléfono   {con_web:2} con web")
            else:
                log(f"  página {pagina + 1}    y se acabaron los resultados")
                break

            if len(negocios) >= limite:
                break
            time.sleep(1.1)   # no atropellar a Google

    if crudo_guardado is not None:
        _guardar_crudo(crudo_guardado, ciudad, log)

    # Si a casi nadie le sacamos contacto, o Google cambió algo o el nicho es raro.
    if negocios and sin_contacto >= len(negocios) * 0.5:
        log("  ! La mitad de las fichas salieron sin teléfono ni web.")
        log("    Si se repite, Google puede haber cambiado el formato:")
        log("    ejecuta con --depurar-maps y abre un issue.")

    return list(negocios.values())[:limite]


def _guardar_crudo(datos, ciudad: str, log) -> None:
    from pathlib import Path
    destino = Path("resultados") / f"_maps-crudo-{ciudad.lower().replace(' ', '-')}.json"
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        log(f"  (árbol crudo guardado en {destino})")
    except Exception:
        pass
