"""
Reglas de teléfono móvil por país.

WhatsApp siempre trabaja en formato internacional (E.164 sin '+'), así que
para cada país necesitamos: el código de marcación, cuántos dígitos tiene un
móvil nacional y con qué dígitos empieza. Con eso descartamos fijos, faxes y
números basura antes de escribirlos al CSV.

Para agregar un país nuevo, copia una línea y ajusta los valores.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pais:
    codigo: str          # ISO-2, ej. "ES"
    nombre: str
    dial: str            # código de marcación sin '+', ej. "34"
    largo_movil: tuple   # largos válidos del número nacional
    prefijos_movil: tuple  # con qué empieza un móvil nacional
    wa_prefijo: str = ""  # dígito extra que WhatsApp exige (Argentina: "9")
    ejemplo_ciudad: str = ""
    idioma: str = "es"


PAISES: dict[str, Pais] = {
    p.codigo: p
    for p in [
        Pais("CL", "Chile", "56", (9,), ("9",), ejemplo_ciudad="Santiago"),
        Pais("ES", "España", "34", (9,), ("6", "7"), ejemplo_ciudad="Madrid"),
        Pais("MX", "México", "52", (10,), ("1", "2", "3", "4", "5", "6", "7", "8", "9"), ejemplo_ciudad="Guadalajara"),
        Pais("AR", "Argentina", "54", (10,), ("1", "2", "3"), wa_prefijo="9", ejemplo_ciudad="Buenos Aires"),
        Pais("CO", "Colombia", "57", (10,), ("3",), ejemplo_ciudad="Bogotá"),
        Pais("PE", "Perú", "51", (9,), ("9",), ejemplo_ciudad="Lima"),
        Pais("EC", "Ecuador", "593", (9,), ("9",), ejemplo_ciudad="Quito"),
        Pais("UY", "Uruguay", "598", (8,), ("9",), ejemplo_ciudad="Montevideo"),
        Pais("PY", "Paraguay", "595", (9,), ("9",), ejemplo_ciudad="Asunción"),
        Pais("BO", "Bolivia", "591", (8,), ("6", "7"), ejemplo_ciudad="Santa Cruz"),
        Pais("VE", "Venezuela", "58", (10,), ("4",), ejemplo_ciudad="Caracas"),
        Pais("BR", "Brasil", "55", (10, 11), ("1", "2", "3", "4", "5", "6", "7", "8", "9"), ejemplo_ciudad="São Paulo", idioma="pt"),
        Pais("PT", "Portugal", "351", (9,), ("9",), ejemplo_ciudad="Lisboa", idioma="pt"),
        Pais("CR", "Costa Rica", "506", (8,), ("6", "7", "8"), ejemplo_ciudad="San José"),
        Pais("PA", "Panamá", "507", (8,), ("6",), ejemplo_ciudad="Ciudad de Panamá"),
        Pais("GT", "Guatemala", "502", (8,), ("3", "4", "5"), ejemplo_ciudad="Guatemala"),
        Pais("SV", "El Salvador", "503", (8,), ("6", "7"), ejemplo_ciudad="San Salvador"),
        Pais("HN", "Honduras", "504", (8,), ("3", "8", "9"), ejemplo_ciudad="Tegucigalpa"),
        Pais("NI", "Nicaragua", "505", (8,), ("5", "7", "8"), ejemplo_ciudad="Managua"),
        Pais("DO", "República Dominicana", "1", (10,), ("8",), ejemplo_ciudad="Santo Domingo"),
        Pais("US", "Estados Unidos", "1", (10,), tuple("23456789"), ejemplo_ciudad="Miami", idioma="en"),
        Pais("CA", "Canadá", "1", (10,), tuple("23456789"), ejemplo_ciudad="Toronto", idioma="en"),
        Pais("IT", "Italia", "39", (10,), ("3",), ejemplo_ciudad="Milán", idioma="it"),
        Pais("FR", "Francia", "33", (9,), ("6", "7"), ejemplo_ciudad="París", idioma="fr"),
        Pais("DE", "Alemania", "49", (10, 11), ("1",), ejemplo_ciudad="Berlín", idioma="de"),
        Pais("GB", "Reino Unido", "44", (10,), ("7",), ejemplo_ciudad="Londres", idioma="en"),
    ]
}


def obtener(codigo: str) -> Pais:
    """Devuelve el país por ISO-2 (case-insensitive). Lanza KeyError si no existe."""
    return PAISES[(codigo or "").strip().upper()]


def listado() -> str:
    """Línea legible con todos los países soportados, para mensajes de ayuda."""
    return ", ".join(f"{c} (+{p.dial})" for c, p in sorted(PAISES.items()))
