"""
Investigar en tu PC, enviar desde el servidor.

    python prospector.py subir            sube los borradores nuevos al servidor
    python prospector.py subir --forzar   también reemplaza los que allá siguen "por revisar"

La investigación (lo caro) la hace Claude Code en tu PC, con tu suscripción, cuando
tú se lo pides. El servidor solo recibe los borradores, y ahí los apruebas y salen.

El servidor manda: nunca se pisa un borrador que ya aprobaste o que ya salió, se
respeta su lista negra y todo llega "por revisar".

Credenciales, en este orden: SERVIDOR_URL / SERVIDOR_USUARIO / SERVIDOR_CLAVE en el
entorno o el .env; si no, PANEL_USUARIO_SERVIDOR / PANEL_CLAVE_SERVIDOR / SERVIDOR_URL
del .env.local. Nunca se imprimen.
"""

import json
import os
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import base as bd
from . import correos
from .analizar import FICHAS
from .base import bloqueado
from .puente import RAIZ, exclusiones

LOTE = 10
LOTE_NEGOCIOS = 300
MAX_FICHA = 500_000
MAX_NEGOCIO = 100_000
# Lo que solo tiene sentido en el servidor: nunca viaja desde el PC.
SOLO_SERVIDOR = ("envios", "whatsapp_envios", "crm", "historial", "respuesta_detectada",
                 "respuesta_canal", "aprobado_en", "subido", "rebotes", "retomar_en", "etiquetas")
LIMPIO = re.compile(r"[^a-z0-9.\-]")


# --- en el servidor ----------------------------------------------------------------

def _limpiar(b: dict) -> dict:
    nuevo = {k: v for k, v in b.items() if k not in SOLO_SERVIDOR}
    nuevo["envios"] = []
    # Lo que se aprobó en el PC se vuelve a aprobar aquí: aquí es donde sale.
    if nuevo.get("estado") != "descartada":
        nuevo["estado"] = "por revisar"
    w = dict(nuevo.get("whatsapp") or {})
    for k in ("estado", "desde", "enviado", "error", "intentos", "respuesta", "recibido"):
        w.pop(k, None)
    nuevo["whatsapp"] = w
    return nuevo


def importar(d: dict) -> dict:
    """Recibe un lote del PC. Devuelve cuántos entraron y por qué no entraron los demás."""
    r = {"nuevos": 0, "reemplazados": 0, "ya_estaban": 0, "lista_negra": 0, "fichas": 0,
         "negocios": 0, "negocio": False, "exclusiones": 0, "errores": []}
    # La lista negra del PC se suma a la del servidor (nunca le quita nada): un cliente
    # tuyo o alguien que pidió la baja no puede recibir nada desde aquí.
    for linea in (d.get("exclusiones") or [])[:5000]:
        if not isinstance(linea, str) or len(linea) > 400:
            continue
        entrada, _, comentario = linea.partition("#")
        entrada = entrada.strip()
        if not entrada or exclusiones.normalizar(entrada)[1] in exclusiones.cargar()[exclusiones.normalizar(entrada)[0]]:
            continue
        motivo = comentario.split("·", 1)[1].strip() if "·" in comentario else ""
        exclusiones.anadir(entrada, motivo or "desde tu PC")
        r["exclusiones"] += 1
    # negocio.md manda el del PC, que es donde se edita: el servidor lo usa para afinar
    # correos y escribir guiones.
    negocio = d.get("negocio")
    if isinstance(negocio, str) and negocio.strip() and len(negocio) <= MAX_NEGOCIO:
        from . import iniciar  # aquí: iniciar importa medio paquete
        actual = iniciar.NEGOCIO.read_text(encoding="utf-8") if iniciar.NEGOCIO.exists() else ""
        if actual != negocio:
            iniciar.NEGOCIO.write_text(negocio, encoding="utf-8")
            r["negocio"] = True
    forzar = bool(d.get("forzar"))
    with correos.CANDADO:
        for b in d.get("borradores") or []:
            dominio = str((b or {}).get("dominio", "")).lower() if isinstance(b, dict) else ""
            if not dominio or LIMPIO.sub("", dominio) != dominio or ".." in dominio:
                r["errores"].append(f"Dominio inválido: {dominio[:60]!r}")
                continue
            if not isinstance(b.get("correos"), list) and b.get("estado") != "descartada":
                r["errores"].append(f"{dominio}: sin correos")
                continue
            w = b.get("whatsapp") or {}
            if bloqueado({"email": b.get("para", ""), "web": b.get("web", ""), "whatsapp": w.get("numero", "")}):
                r["lista_negra"] += 1
                continue
            if correos.ruta(dominio).exists():
                actual = correos.leer(dominio)
                if not (forzar and actual.get("estado") == "por revisar"):
                    r["ya_estaban"] += 1
                    continue
                r["reemplazados"] += 1
            else:
                r["nuevos"] += 1
            correos.guardar(_limpiar({**b, "dominio": dominio}))

        FICHAS.mkdir(parents=True, exist_ok=True)
        for dominio, texto in (d.get("fichas") or {}).items():
            dominio = str(dominio).lower()
            if LIMPIO.sub("", dominio) != dominio or ".." in dominio or not isinstance(texto, str):
                continue
            if len(texto) <= MAX_FICHA:
                (FICHAS / f"{dominio}.md").write_text(texto, encoding="utf-8")
                r["fichas"] += 1

    negocios = d.get("negocios") or {}
    if isinstance(negocios, dict) and negocios:
        from . import radar  # aquí: radar importa medio paquete
        with radar.CANDADO:
            base = bd.cargar()
            for clave, lead in negocios.items():
                # Solo los que el servidor no tiene: lo que ya hay allá es más nuevo.
                if isinstance(lead, dict) and isinstance(clave, str) and clave not in base and len(clave) < 200:
                    base[clave] = lead
                    r["negocios"] += 1
            if r["negocios"]:
                bd.guardar(base)
    return r


# --- en tu PC ------------------------------------------------------------------------

def _env_local() -> dict:
    ruta = RAIZ / ".env.local"
    v = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, _, x = linea.partition("=")
                v[k.strip().upper()] = x.strip().strip("'\"")
    return v


def credenciales() -> tuple[str, str, str]:
    local = _env_local()
    url = os.environ.get("SERVIDOR_URL") or local.get("SERVIDOR_URL", "")
    usuario = os.environ.get("SERVIDOR_USUARIO") or local.get("SERVIDOR_USUARIO") or local.get("PANEL_USUARIO_SERVIDOR", "")
    clave = os.environ.get("SERVIDOR_CLAVE") or local.get("SERVIDOR_CLAVE") or local.get("PANEL_CLAVE_SERVIDOR", "")
    return url.rstrip("/"), usuario, clave


def _pedir(url: str, ruta: str, cuerpo: dict, galleta: str = "") -> tuple[int, dict, str]:
    # Cloudflare rechaza (error 1010) el User-Agent por defecto de Python.
    cab = {"Content-Type": "application/json", "X-Panel": "1", "User-Agent": "prospector/1.0"}
    if galleta:
        cab["Cookie"] = galleta
    peticion = Request(url + ruta, data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
                       headers=cab, method="POST")
    try:
        with urlopen(peticion, timeout=120) as r:
            nueva = (r.headers.get("Set-Cookie") or "").split(";")[0]
            return r.status, json.loads(r.read() or b"{}"), nueva
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}"), ""
        except ValueError:
            return e.code, {}, ""


def reserva_whatsapp() -> int | None:
    """Cuántos negocios le quedan al WhatsApp del servidor (verificadas + por verificar)."""
    url, usuario, clave = credenciales()
    if not url or not clave:
        return None
    try:
        codigo, _, galleta = _pedir(url, "/api/login", {"correo": usuario, "clave": clave})
        if codigo != 200:
            return None
        peticion = Request(url + "/api/whatsapp", headers={"Cookie": galleta, "X-Panel": "1",
                                                            "User-Agent": "prospector/1.0"})
        with urlopen(peticion, timeout=120) as r:
            res = json.loads(r.read()).get("reserva") or {}
        return int(res.get("verificadas", 0)) + int(res.get("por_verificar", 0))
    except (URLError, OSError, ValueError):
        return None


def pendientes(forzar: bool = False) -> list[dict]:
    """Los borradores del PC que faltan por subir."""
    return [b for b in correos.listar()
            if b.get("estado") in ("por revisar", "descartada") and (forzar or not b.get("subido"))]


def subir(forzar: bool = False, log=print) -> int:
    url, usuario, clave = credenciales()
    if not url or not clave:
        log("! Falta a qué servidor subir. En .env.local pon SERVIDOR_URL=https://tu-dominio "
            "(y PANEL_USUARIO_SERVIDOR / PANEL_CLAVE_SERVIDOR con tu login).")
        return 1
    try:
        codigo, datos, galleta = _pedir(url, "/api/login", {"correo": usuario, "clave": clave})
    except (URLError, OSError) as e:
        log(f"! No pude conectar con {url}: {e}")
        return 1
    if codigo != 200 or not galleta:
        log(f"! El servidor no aceptó el login: {datos.get('error') or codigo}")
        return 1

    lista = pendientes(forzar)
    total = {"nuevos": 0, "reemplazados": 0, "ya_estaban": 0, "lista_negra": 0, "negocios": 0}
    errores = []
    for i in range(0, len(lista), LOTE):
        lote = lista[i:i + LOTE]
        fichas = {}
        for b in lote:
            ficha = FICHAS / f"{b['dominio']}.md"
            if ficha.exists():
                fichas[b["dominio"]] = ficha.read_text(encoding="utf-8")
        codigo, r, _ = _pedir(url, "/api/importar", {"borradores": lote, "fichas": fichas, "forzar": forzar}, galleta)
        if codigo != 200:
            log(f"! El servidor rechazó un lote: {r.get('error') or codigo}")
            return 1
        for k in total:
            total[k] += r.get(k, 0)
        errores += r.get("errores", [])
        ahora = datetime.now().isoformat(timespec="seconds")
        with correos.CANDADO:
            for b in lote:
                actual = correos.leer(b["dominio"])
                actual["subido"] = ahora
                correos.guardar(actual)
        log(f"  ↑ {min(i + LOTE, len(lista))}/{len(lista)} borradores")

    # La base de negocios, para que el Radar del servidor sepa qué ya se miró.
    base = bd.cargar()
    claves = list(base)
    for i in range(0, len(claves), LOTE_NEGOCIOS):
        trozo = {k: base[k] for k in claves[i:i + LOTE_NEGOCIOS]}
        codigo, r, _ = _pedir(url, "/api/importar", {"negocios": trozo}, galleta)
        if codigo == 200:
            total["negocios"] += r.get("negocios", 0)

    negras = 0
    lista_negra = exclusiones.listar()
    if lista_negra:
        codigo, r, _ = _pedir(url, "/api/importar", {"exclusiones": lista_negra}, galleta)
        negras = r.get("exclusiones", 0) if codigo == 200 else 0

    negocio = RAIZ / "negocio.md"
    cambio = False
    if negocio.exists():
        codigo, r, _ = _pedir(url, "/api/importar", {"negocio": negocio.read_text(encoding="utf-8")}, galleta)
        cambio = codigo == 200 and bool(r.get("negocio"))

    log(f"\n> {total['nuevos']} borradores nuevos en el servidor"
        + (f" · {total['reemplazados']} reemplazados" if total["reemplazados"] else "")
        + (f" · {total['ya_estaban']} ya estaban" if total["ya_estaban"] else "")
        + (f" · {total['lista_negra']} en su lista negra (no se subieron)" if total["lista_negra"] else "")
        + f" · {total['negocios']} negocios nuevos en su Radar"
        + (" · negocio.md actualizado allá" if cambio else "")
        + (f" · {negras} nuevas en su lista negra" if negras else ""))
    for e in errores[:5]:
        log(f"  ! {e}")
    log(f"  Revísalos y apruébalos en {url}")
    return 0
