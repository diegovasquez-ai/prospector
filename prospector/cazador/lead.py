"""
El contrato: qué lleva un lead desde que se descubre hasta que se guarda.

Un lead es un dict normal y corriente. Este módulo solo garantiza que SIEMPRE
tenga todas las claves (aunque estén vacías), para que nadie tenga que escribir
.get() defensivo en cada línea.

Por dónde pasa y qué le añade cada etapa:

    fuentes/   ->  nombre, web, telefono, direccion...   (lo que publique la fuente)
    rastrear   ->  + whatsapp, confianza, email          (entrando en su web)
    exportar   ->  + whatsapp_bonito, enlace_whatsapp, mensaje

¿Por qué un dict y no una dataclass? Porque rastrear hace dict(negocio) y
exportar hace json.dumps(filas): con dicts eso sale gratis.
"""

# Todas las claves que puede tener un lead, con su valor por defecto.
CAMPOS = {
    "nombre": "",
    "fuente": "",       # google_maps, osm, web, serper
    "web": "",
    "email": "",
    "telefono": "",     # tal cual lo publica la fuente, sin normalizar
    "direccion": "",
    "ciudad": "",
    "nicho": "",
    # --- los rellena rastrear.py ------------------------------------------
    "whatsapp": "",       # móvil en E.164, ya validado
    "whatsapp_osm": "",   # el que OSM declara en la etiqueta contact:whatsapp
    "confianza": "",      # alta | media | baja
    # --- solo Google Maps --------------------------------------------------
    "rating": "",
    "resenas": "",
    "categoria": "",
    "lat": "",
    "lng": "",
}


def nuevo(**datos) -> dict:
    """
    Un lead con todas las claves. Lo que no pases queda como "".

        >>> l = nuevo(nombre="Barbería Grasso", telefono="+34641556164")
        >>> l["confianza"]    # existe aunque aún no se haya rastreado
        ''
    """
    lead = dict(CAMPOS)
    for clave, valor in datos.items():
        if valor is None or valor == []:
            continue
        lead[clave] = valor
    return lead


def fusionar(a: dict, b: dict) -> dict:
    """
    Une dos leads del mismo negocio. Gana el valor no vacío; si los dos tienen,
    gana el primero (que viene de la fuente más fiable, porque descubrir()
    consulta Maps antes que OSM).

    Sin esto perderíamos datos: cuando Maps y OSM traen la misma inmobiliaria,
    Maps aporta el rating y OSM a veces el email. Quedarse solo con uno de los
    dos tira la mitad de la información.
    """
    salida = dict(a)
    for clave, valor in b.items():
        if valor and not salida.get(clave):
            salida[clave] = valor
    return salida


def clave_dedup(lead: dict) -> str:
    """
    Con qué decidimos que dos leads son el mismo. En este orden porque va de
    más identificativo a menos: dos negocios distintos no comparten WhatsApp,
    pero sí pueden llamarse parecido.
    """
    for campo in ("whatsapp", "email", "web"):
        valor = (lead.get(campo) or "").strip().lower()
        if valor:
            return valor
    return (lead.get("nombre") or "").strip().lower()
