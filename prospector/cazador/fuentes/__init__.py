"""
El registro de fuentes.

Añadir una fuente nueva es: copia uno de estos ficheros, escribe tu buscar()
devolviendo una lista de dicts con al menos {nombre, web, telefono}, y añádela
a REGISTRO. Nada más. Es la forma más fácil de contribuir al proyecto.

Todas las fuentes tienen la misma firma:

    buscar(nicho, ciudad, pais, limite=200, log=print) -> list[dict]
"""

from .. import lead
from ..paises import Pais
from . import maps, osm, serper, web

# Orden importante: se consultan de mejor a peor rendimiento, y cuando dos
# traen el mismo negocio gana el dato de la primera.
REGISTRO = [
    ("maps",   maps,   "Google Maps",     True),   # True = funciona sin API key
    ("osm",    osm,    "OpenStreetMap",   True),
    ("web",    web,    "Búsqueda web",    True),
    ("serper", serper, "Serper (Google)", False),
]

GRATIS = [nombre for nombre, _, _, gratis in REGISTRO if gratis]


def _normalizar(bruto: dict, ciudad: str, nicho: str, fuente: str) -> dict:
    """
    Cualquier cosa que devuelva una fuente pasa por aquí y sale con todas las
    claves de lead.CAMPOS. Así las fuentes viejas no tienen que saber nada del
    contrato nuevo.
    """
    datos = {k: v for k, v in bruto.items() if k in lead.CAMPOS}
    datos.setdefault("ciudad", ciudad)
    datos.setdefault("nicho", nicho)
    datos.setdefault("fuente", fuente)
    return lead.nuevo(**datos)


def _clave(l: dict) -> str:
    """Con qué decidimos que dos resultados son el mismo negocio."""
    from ..filtros import dominio, sin_acentos
    web_ = dominio(l.get("web") or "")
    if web_:
        return "w:" + web_
    return "n:" + sin_acentos(l.get("nombre") or "").strip()


def descubrir(nicho: str, ciudad: str, pais: Pais, fuente: str = "todas",
              limite: int = 200, log=print, depurar_maps: bool = False) -> list[dict]:
    """
    Busca en las fuentes pedidas y devuelve los negocios ya fusionados.

    Cuando dos fuentes traen el mismo negocio no se descarta el segundo: se
    fusionan. Maps suele aportar el rating y el teléfono, OSM a veces el email
    o un WhatsApp declarado. Quedarse solo con uno tiraría la mitad del dato.
    """
    import os

    activas = [(n, mod, etiqueta) for n, mod, etiqueta, _ in REGISTRO
               if fuente in (n, "todas")]
    if fuente == "todas":
        # Serper solo si el usuario tiene la clave; si no, ni lo mencionamos.
        activas = [(n, m, e) for n, m, e in activas
                   if n != "serper" or os.environ.get("SERPER_KEY", "").strip()]
        if os.environ.get("CAZADOR_SIN_MAPS", "").strip():
            activas = [(n, m, e) for n, m, e in activas if n != "maps"]

    encontrados: dict[str, dict] = {}
    for i, (nombre, modulo, etiqueta) in enumerate(activas, 1):
        log(f"> {etiqueta}" + " " * max(1, 56 - len(etiqueta))
            + f"[fuente {i} de {len(activas)}]")
        try:
            if nombre == "maps":
                brutos = modulo.buscar(nicho, ciudad, pais, limite, log,
                                       depurar=depurar_maps)
            else:
                brutos = modulo.buscar(nicho, ciudad, pais, limite, log)
        except Exception as e:
            log(f"  ! {etiqueta} falló ({type(e).__name__}). Sigo con el resto.")
            continue

        nuevos = fusionados = 0
        for bruto in brutos or []:
            l = _normalizar(bruto, ciudad, nicho, nombre)
            if not l["nombre"]:
                continue
            k = _clave(l)
            if k in encontrados:
                encontrados[k] = lead.fusionar(encontrados[k], l)
                fusionados += 1
            else:
                encontrados[k] = l
                nuevos += 1
        if fusionados:
            log(f"  {nuevos} nuevos, {fusionados} que ya tenía (fusionados)")
        log("")

    return list(encontrados.values())
