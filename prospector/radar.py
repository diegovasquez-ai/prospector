"""
El radar: todos los negocios que trajo `buscar`, de más a menos oportunidad,
con su ficha. Desde aquí también se rastrea una comuna nueva y se manda a
investigar uno sin esperar a la tanda de la mañana.

Rastrear tarda minutos e investigar unos 10, así que los dos corren en un
hilo y el panel pregunta cómo van. Una búsqueda a la vez (dos escribiendo la
base a la vez se pisarían) y como mucho MAX_INVESTIGANDO investigaciones.
"""

import threading
from datetime import datetime

from . import base as bd
from . import config, correos, iniciar, nicho, preparar
from .analizar import FICHAS, analizar
from .puente import exclusiones

ORDEN = {"candidata": 0, "sin correo": 1, "floja": 2, "nueva": 3, "descartada": 4, "baja": 5}
INVESTIGABLES = ("candidata", "sin correo", "floja")
MAX_INVESTIGANDO = 3

CANDADO = threading.Lock()
_busqueda: dict = {"comuna": "", "fase": "", "mensaje": "", "inicio": "", "fin": ""}
_investigando: dict[str, dict] = {}
_terminadas: list[dict] = []


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- Lectura -------------------------------------------------------------------

def _fila(l: dict, b: dict | None, fuera: dict) -> dict:
    """
    Si ya hay borrador, manda lo que decidió la investigación: a quién se le
    escribe de verdad (puede no ser el correo que eligió el código) y, si la
    descartó, por qué.
    """
    a = l.get("analisis") or {}
    b = b or {}
    clave = bd.clave(l)
    return {
        "clave": clave,
        "nombre": b.get("nombre") or l.get("nombre", ""),
        "comuna": l.get("comuna", ""), "tipo": l.get("tipo", ""),
        "estado": l.get("estado", ""), "motivo": b.get("motivo") or l.get("motivo", ""),
        "puntaje": l.get("puntaje", 0),
        "correo": b.get("para") or l.get("correo", ""),
        "correo_estado": b.get("correo_estado", "") if b.get("para") else l.get("correo_estado", ""),
        "telefono": l.get("telefono", ""), "web": l.get("web", ""),
        "rating": l.get("rating", ""), "resenas": l.get("resenas", ""), "categoria": l.get("categoria", ""),
        "direccion": l.get("direccion", ""), "lat": l.get("lat", ""), "lng": l.get("lng", ""),
        "whatsapp": bool(a.get("whatsapp") or l.get("whatsapp")),
        "puede_pagar": l.get("puede_pagar") or [], "le_falta": l.get("le_falta") or [],
        "descubierta": l.get("descubierta", ""),
        "borrador": b.get("estado", ""),
        "bloqueado": bd.bloqueado(l, fuera),
        "investigando": clave in _investigando,
    }


def listar() -> list[dict]:
    """Todas, las que más prometen primero."""
    borradores = {b["dominio"]: b for b in correos.listar()}
    fuera = exclusiones.cargar()
    filas = [_fila(l, borradores.get(bd.clave(l)), fuera) for l in bd.cargar().values()]
    return sorted(filas, key=lambda f: (ORDEN.get(f["estado"], 9), -f["puntaje"], f["nombre"].lower()))


def detalle(clave: str) -> dict:
    l = bd.cargar().get(clave)
    if l is None:
        raise KeyError(clave)
    b = None
    if not clave.startswith("n:"):
        try:
            b = correos.leer(clave)
        except (FileNotFoundError, ValueError):
            b = None
    ficha = FICHAS / f"{clave}.md"
    a = l.get("analisis") or {}
    return _fila(l, b, exclusiones.cargar()) | {
        "ficha": ficha.read_text(encoding="utf-8") if ficha.exists() and not clave.startswith("n:") else "",
        "analisis": {k: a.get(k) for k in ("fecha", "paginas", "whatsapp", "chat", "formulario", "telefono",
                                           "correos", "cargos", "biblioteca_meta", "catalogo_fichas",
                                           "catalogo_texto", "sucursales", "portales", "sistemas")},
        "observacion": (b or {}).get("observacion", ""),
    }


def comunas_sugeridas() -> list[str]:
    """Las de comunas.txt que aún no se han rastreado, en su orden."""
    return preparar.comunas_por_barrer(bd.cargar())


def trabajos() -> dict:
    with CANDADO:
        return {
            "busqueda": dict(_busqueda),
            "investigando": [{"clave": k, **v} for k, v in _investigando.items()],
            "terminadas": list(_terminadas[-10:]),
            "claude": bool(correos.claude_disponible()),
        }


# --- Rastrear una comuna ---------------------------------------------------------

def rastrear(comuna: str) -> str:
    """Arranca buscar + analizar en un hilo. Devuelve un error o ""."""
    comuna = " ".join((comuna or "").split())
    if not comuna or len(comuna) > 60:
        return "Escribe una comuna o ciudad"
    if not nicho.existe():
        return "Falta nicho.json. Corre primero:  python prospector.py iniciar"
    with CANDADO:
        if _busqueda["fase"] in ("buscando", "analizando"):
            return f"Ya estoy rastreando {_busqueda['comuna']}: espera a que termine"
        _busqueda.update(comuna=comuna, fase="buscando", mensaje="Buscando en Google Maps…",
                         inicio=_ahora(), fin="")
    threading.Thread(target=_rastrear, args=(comuna,), daemon=True).start()
    return ""


def _fase(**cambios) -> None:
    with CANDADO:
        _busqueda.update(cambios)


def _rastrear(comuna: str) -> None:
    from .cli import buscar  # aquí y no arriba: cli importa medio paquete
    try:
        antes = set(bd.cargar())
        buscar([comuna], 60, "maps")
        base = bd.cargar()
        nuevas = set(base) - antes
        _fase(fase="analizando", mensaje=f"{len(nuevas)} nuevas: visitando sus webs…")
        analizar(base, log=lambda m: _fase(mensaje=str(m).strip(" >·")))
        bd.guardar(base)
        cand = sum(1 for k in nuevas if base[k].get("estado") == "candidata")
        _fase(fase="listo", fin=_ahora(),
              mensaje=f"{len(nuevas)} nuevas en {comuna} · {cand} candidatas")
    except (Exception, SystemExit) as e:
        _fase(fase="error", fin=_ahora(), mensaje=f"{type(e).__name__}: {e}")


# --- Investigar una -----------------------------------------------------------------

def investigar(clave: str) -> str:
    """Manda a Claude a investigar y redactar este negocio. Devuelve un error o ""."""
    l = bd.cargar().get(clave)
    if l is None:
        return "No está en la base"
    if clave.startswith("n:") or not l.get("web"):
        return "Sin web no hay nada que investigar"
    if bd.bloqueado(l):
        return "Está en la lista negra"
    if l.get("estado") not in INVESTIGABLES:
        return f"Está {l.get('estado')}: {l.get('motivo') or 'no es para escribirle'}"
    if correos.ruta(clave).exists():
        return "Ya tiene borrador: míralo en Correos"
    falta = iniciar.pendiente()
    if falta:
        return falta
    exe = correos.claude_disponible()
    if not exe:
        return "No encuentro el comando claude"
    with CANDADO:
        if clave in _investigando:
            return "Ya la estoy investigando"
        if len(_investigando) >= MAX_INVESTIGANDO:
            return f"Ya hay {MAX_INVESTIGANDO} investigándose: espera a que termine una"
        _investigando[clave] = {"nombre": l.get("nombre", clave), "inicio": _ahora()}
    threading.Thread(target=_investigar, args=(clave, l, exe), daemon=True).start()
    return ""


def _investigar(clave: str, lead: dict, exe: str) -> None:
    try:
        estado, mensaje = preparar.investigar(lead, exe, config.texto("PREPARAR_MODELO"))
    except Exception as e:
        estado, mensaje = "error", f"{type(e).__name__}: {e}"
    with CANDADO:
        info = _investigando.pop(clave, {})
        _terminadas.append({"clave": clave, "nombre": info.get("nombre", clave),
                            "estado": estado, "mensaje": mensaje, "fin": _ahora()})
