"""
OpenStreetMap: el mapa libre.

Cobertura mucho menor que Google Maps (en Madrid, 15 inmobiliarias frente a
99), y pocas fichas traen teléfono o web. Pero es abierto, no tiene términos
de servicio que sortear y a veces publica la etiqueta contact:whatsapp, que es
un WhatsApp confirmado por el propio negocio. Vale la pena tenerlo.

El grueso de este módulo es CATEGORIAS: la traducción de "peluquerías" a las
etiquetas que OSM usa de verdad. Sin ella, buscar por texto devuelve basura.
"""

import re

import httpx

from .. import lead
from ..filtros import sin_acentos
from ..geo import caja as caja_de
from ..paises import Pais

UA_OSM = {"User-Agent": "cazador/2.0 (https://github.com/topics/lead-generation)"}

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


CATEGORIAS: dict[tuple, tuple] = {
    ("gimnasio", "gym", "fitness", "crossfit", "box"): ('["leisure"="fitness_centre"]', '["leisure"="sports_centre"]'),
    ("restaurante", "restaurant", "comida"): ('["amenity"="restaurant"]',),
    ("cafeteria", "cafetería", "cafe", "café"): ('["amenity"="cafe"]',),
    ("bar", "pub", "cerveceria", "cervecería"): ('["amenity"="bar"]', '["amenity"="pub"]'),
    ("pizzeria", "pizzería", "pizza"): ('["cuisine"="pizza"]',),
    ("hotel", "hostal", "alojamiento", "hospedaje"): ('["tourism"="hotel"]', '["tourism"="guest_house"]', '["tourism"="hostel"]'),
    ("peluqueria", "peluquería", "barberia", "barbería", "barber"): ('["shop"="hairdresser"]',),
    ("estetica", "estética", "belleza", "spa", "uñas", "manicura"): ('["shop"="beauty"]', '["leisure"="spa"]'),
    ("tatuaje", "tatuajes", "tattoo"): ('["shop"="tattoo"]',),
    ("dentista", "dental", "odontologia", "odontología"): ('["amenity"="dentist"]', '["healthcare"="dentist"]'),
    ("clinica", "clínica", "medico", "médico", "consulta"): ('["amenity"="clinic"]', '["amenity"="doctors"]'),
    ("fisioterapia", "fisioterapeuta", "kinesiologia", "kinesiología"): ('["healthcare"="physiotherapist"]',),
    ("psicologo", "psicólogo", "psicologia", "psicología"): ('["healthcare"="psychotherapist"]',),
    ("nutricion", "nutrición", "nutricionista"): ('["healthcare"="nutrition_counselling"]',),
    ("veterinaria", "veterinario"): ('["amenity"="veterinary"]',),
    ("farmacia", "botica"): ('["amenity"="pharmacy"]',),
    ("optica", "óptica"): ('["shop"="optician"]',),
    ("abogado", "abogados", "juridico", "jurídico", "legal", "bufete"): ('["office"="lawyer"]',),
    ("notaria", "notaría", "notario"): ('["office"="notary"]',),
    ("contador", "contable", "asesoria", "asesoría", "gestoria", "gestoría"): ('["office"="accountant"]', '["office"="tax_advisor"]'),
    ("inmobiliaria", "corredora", "bienes raices", "bienes raíces"): ('["office"="estate_agent"]',),
    ("seguros", "corredor de seguros"): ('["office"="insurance"]',),
    ("arquitecto", "arquitectura", "estudio de arquitectura"): ('["office"="architect"]',),
    ("constructora", "construccion", "construcción"): ('["office"="construction_company"]', '["craft"="builder"]',),
    ("marketing", "publicidad", "agencia"): ('["office"="advertising_agency"]', '["office"="marketing"]',),
    ("coworking", "oficinas compartidas"): ('["amenity"="coworking_space"]', '["office"="coworking"]'),
    ("taller", "mecanico", "mecánico", "automotriz", "desabolladura"): ('["shop"="car_repair"]',),
    ("automotora", "concesionario", "venta de autos"): ('["shop"="car"]',),
    ("ferreteria", "ferretería"): ('["shop"="doityourself"]', '["shop"="hardware"]'),
    ("panaderia", "panadería"): ('["shop"="bakery"]',),
    ("pasteleria", "pastelería", "reposteria", "repostería"): ('["shop"="pastry"]',),
    ("carniceria", "carnicería"): ('["shop"="butcher"]',),
    ("supermercado", "minimarket", "almacen", "almacén"): ('["shop"="supermarket"]', '["shop"="convenience"]'),
    ("floristeria", "floristería", "floreria", "florería"): ('["shop"="florist"]',),
    ("ropa", "boutique", "moda"): ('["shop"="clothes"]',),
    ("zapateria", "zapatería", "calzado"): ('["shop"="shoes"]',),
    ("joyeria", "joyería"): ('["shop"="jewelry"]',),
    ("muebles", "mueblería", "mublería"): ('["shop"="furniture"]',),
    ("libreria", "librería"): ('["shop"="books"]',),
    ("jugueteria", "juguetería"): ('["shop"="toys"]',),
    ("escuela", "colegio", "instituto", "academia"): ('["amenity"="school"]', '["office"="educational_institution"]'),
    ("autoescuela", "escuela de conducir"): ('["amenity"="driving_school"]',),
    ("guarderia", "guardería", "jardin infantil", "jardín infantil"): ('["amenity"="kindergarten"]',),
    ("viajes", "agencia de viajes", "turismo"): ('["shop"="travel_agency"]',),
    ("imprenta", "impresion", "impresión", "rotulacion", "rotulación"): ('["shop"="copyshop"]', '["craft"="printer"]'),
    ("fotografo", "fotógrafo", "fotografia", "fotografía"): ('["craft"="photographer"]', '["shop"="photo"]'),
    ("lavanderia", "lavandería", "tintoreria", "tintorería"): ('["shop"="laundry"]', '["shop"="dry_cleaning"]'),
    ("electricista", "electricidad"): ('["craft"="electrician"]',),
    ("gasfiter", "fontanero", "plomero", "fontaneria", "fontanería"): ('["craft"="plumber"]',),
    ("carpinteria", "carpintería", "carpintero"): ('["craft"="carpenter"]',),
    ("cerrajeria", "cerrajería", "cerrajero"): ('["craft"="locksmith"]',),
    ("pintor", "pintura"): ('["craft"="painter"]',),
    ("panel solar", "solar", "fotovoltaica"): ('["craft"="solar"]', '["shop"="energy"]'),
    ("mudanzas", "fletes"): ('["shop"="moving_company"]', '["office"="moving_company"]'),
    ("guarderia canina", "peluqueria canina", "mascotas"): ('["shop"="pet"]', '["shop"="pet_grooming"]'),
}


def _coincide(palabra: str, clave: str) -> bool:
    """
    'barberias' coincide con 'barberia', pero NO con 'bar'. Sin esto, buscar
    barberías te devuelve todos los bares del barrio (pasó de verdad).
    """
    # Singulares posibles de la palabra: bares -> bare, bar
    formas = {palabra, palabra[:-1], palabra[:-2]}
    if clave in formas:
        return True
    # Prefijo largo: 'inmobiliariaS' contra 'inmobiliaria'
    if len(clave) >= 5 and palabra.startswith(clave):
        return True
    return False


def _etiquetas_para(nicho: str) -> tuple:
    """
    Traduce el nicho a etiquetas de OpenStreetMap.

    - Si el nicho entero coincide con una categoría compuesta ('peluquería
      canina'), esa manda: no queremos mezclarla con las peluquerías de gente.
    - Si no, cada palabra aporta su categoría y las sumamos: 'clínicas
      dentales' busca clínicas Y dentistas.
    """
    limpio = sin_acentos(nicho)
    for claves, etiquetas in CATEGORIAS.items():
        for clave in claves:
            c = sin_acentos(clave)
            if " " in c and c in limpio:
                return etiquetas

    etiquetas_totales: list[str] = []
    for palabra in limpio.split():
        mejor, largo = (), 0
        for claves, etiquetas in CATEGORIAS.items():
            for clave in claves:
                c = sin_acentos(clave)
                if " " not in c and _coincide(palabra, c) and len(c) > largo:
                    mejor, largo = etiquetas, len(c)
        for e in mejor:
            if e not in etiquetas_totales:
                etiquetas_totales.append(e)
    return tuple(etiquetas_totales[:6])


def _termino_busqueda(nicho: str) -> str:
    """Raíz para buscar por nombre en el mapa: 'barberías' -> 'barberia'."""
    palabras = [p for p in sin_acentos(nicho).split() if len(p) >= 4] or sin_acentos(nicho).split()
    if not palabras:
        return sin_acentos(nicho)
    p = max(palabras, key=len)
    for sufijo in ("es", "s"):
        if p.endswith(sufijo) and len(p) - len(sufijo) >= 4:
            return p[:-len(sufijo)]
    return p


def _consulta_overpass(nicho: str, caja: tuple, limite: int) -> str:
    bbox = "{:.5f},{:.5f},{:.5f},{:.5f}".format(*caja)
    etiquetas = _etiquetas_para(nicho)
    partes = []
    if etiquetas:
        partes += [f'nwr{e}({bbox});' for e in etiquetas]
    # Siempre buscamos también por nombre: pilla los negocios mal etiquetados.
    termino = re.escape(_termino_busqueda(nicho))
    for llave in ("shop", "amenity", "office", "craft", "healthcare"):
        partes.append(f'nwr["name"~"{termino}",i]["{llave}"]({bbox});')
    cuerpo = "\n  ".join(partes)
    return f"[out:json][timeout:90];\n(\n  {cuerpo}\n);\nout center tags {limite};"


def buscar(nicho: str, ciudad: str, pais: Pais, limite: int = 200, log=print) -> list[dict]:
    caja = caja_de(ciudad, pais)
    if not caja:
        log(f"  ! No pude ubicar '{ciudad}' en el mapa, salto OpenStreetMap")
        return []
    # Pedimos de más: muchos negocios del mapa no publican web ni teléfono,
    # así que hay que traer bastantes para llenar el cupo con los que sí sirven.
    consulta = _consulta_overpass(nicho, caja, max(limite * 5, 300))
    # Los servidores de Overpass son gratuitos y se saturan: un 504 casi
    # siempre se arregla esperando un poco. Dos rondas por todos los espejos.
    elementos = []
    for ronda, espera in enumerate((2, 8), start=1):
        for espejo in OVERPASS:
            try:
                r = httpx.post(espejo, data={"data": consulta}, headers=UA_OSM, timeout=120)
                if r.status_code == 200:
                    elementos = r.json().get("elements", [])
                    break
                log(f"  . {urlparse(espejo).netloc} respondió {r.status_code}"
                    f"{', reintento en un momento' if ronda == 2 else ', pruebo otro espejo'}")
            except Exception:
                log(f"  . {urlparse(espejo).netloc} no respondió")
            time.sleep(espera)
        if elementos:
            break
        if ronda == 1:
            log("  . los servidores del mapa están saturados, espero y reintento...")

    salida = []
    for el in elementos:
        t = el.get("tags", {})
        nombre = (t.get("name") or "").strip()
        if not nombre:
            continue
        web = (t.get("website") or t.get("contact:website") or t.get("url") or "").strip()
        if web and not dominio_util(web):
            web = ""
        salida.append({
            "nombre": nombre,
            "web": web,
            "telefono": (t.get("phone") or t.get("contact:phone") or t.get("contact:mobile") or "").strip(),
            "whatsapp_osm": (t.get("contact:whatsapp") or t.get("whatsapp") or "").strip(),
            "email": (t.get("email") or t.get("contact:email") or "").strip(),
            "direccion": " ".join(x for x in [
                t.get("addr:street", ""), t.get("addr:housenumber", ""),
                t.get("addr:city", "")
            ] if x).strip(),
            "fuente": "openstreetmap",
        })

    # Primero los que tienen por dónde contactarlos: son los únicos que
    # pueden acabar con un WhatsApp en el CSV.
    salida.sort(key=lambda s: (
        0 if s["whatsapp_osm"] else 1,
        0 if s["telefono"] else 1,
        0 if s["web"] else 1,
    ))
    log(f"  OpenStreetMap: {len(salida)} negocios ({sum(1 for s in salida if s['web'])} con web, "
        f"{sum(1 for s in salida if s['telefono'])} con teléfono, "
        f"{sum(1 for s in salida if s['whatsapp_osm'])} con WhatsApp declarado)")
    return salida


