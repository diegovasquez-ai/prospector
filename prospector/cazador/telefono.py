"""
Normalización de teléfonos a formato WhatsApp (E.164).

Dos caminos distintos a propósito:

* `desde_enlace_wa()`  -> el número venía dentro de un enlace wa.me / api.whatsapp.
  Ahí el dueño del sitio ya declaró "este es mi WhatsApp" y el número trae su
  código de país incluido, así que somos permisivos.

* `normalizar()`       -> el número venía de un `tel:` o del texto de la página.
  Ahí hay que ser estrictos: la mayoría son fijos, y un fijo en un CSV de
  WhatsApp es ruido que te hace perder el tiempo.
"""

import re

from .paises import Pais

_NO_DIGITO = re.compile(r"\D")

# Números que aparecen en todas las webs y nunca son un negocio.
BASURA = {
    "56999999999", "56900000000", "34600000000", "34123456789",
    "5491111111111", "1234567890", "0000000000", "1111111111",
    "123456789", "987654321", "5215555555555",
}


def digitos(bruto: str) -> str:
    return _NO_DIGITO.sub("", bruto or "")


def _es_basura(d: str) -> bool:
    if d in BASURA:
        return True
    # 000000000, 111111111, 123456789 y similares
    if len(set(d)) <= 2:
        return True
    if d in "01234567890123456789" or d in "98765432109876543210":
        return True
    return False


def _armar(pais: Pais, nacional: str) -> str:
    return "+" + pais.dial + pais.wa_prefijo + nacional


def _movil_valido(pais: Pais, nacional: str) -> bool:
    return (
        len(nacional) in pais.largo_movil
        and nacional.startswith(pais.prefijos_movil)
    )


def normalizar(bruto: str, pais: Pais) -> str:
    """
    Devuelve el número en E.164 ('+56912345678') si parece un móvil del país,
    o '' si es un fijo, un número incompleto o basura.
    """
    d = digitos(bruto)
    if not d or _es_basura(d):
        return ""

    # 1) ya viene internacional: +56 9 1234 5678
    if d.startswith(pais.dial):
        resto = d[len(pais.dial):]
        if pais.wa_prefijo and resto.startswith(pais.wa_prefijo):
            resto_sin = resto[len(pais.wa_prefijo):]
            if _movil_valido(pais, resto_sin):
                return _armar(pais, resto_sin)
        if _movil_valido(pais, resto):
            return _armar(pais, resto)

    # 2) formato nacional con 0 de salida: 011 2345 6789
    nacional = d.lstrip("0")
    # Argentina: el "15" de móvil va después del prefijo de área y sobra
    if pais.codigo == "AR" and len(nacional) > 10 and "15" in nacional[:5]:
        nacional = nacional.replace("15", "", 1)
    if _movil_valido(pais, nacional):
        return _armar(pais, nacional)

    return ""


def desde_enlace_wa(bruto: str, pais: Pais | None = None) -> str:
    """
    Número sacado de un enlace de WhatsApp explícito. Trae el código de país
    dentro, así que solo validamos que tenga largo de teléfono real.
    """
    d = digitos(bruto)
    if not d or _es_basura(d):
        return ""
    if not (8 <= len(d) <= 15):
        return ""
    # Si el sitio puso el número nacional sin código de país, se lo agregamos.
    if pais and not d.startswith(pais.dial):
        nac = normalizar(d, pais)
        if nac:
            return nac
    return "+" + d


def enlace(e164: str) -> str:
    """https://wa.me/56912345678 — listo para pegar en el navegador."""
    return "https://wa.me/" + digitos(e164) if e164 else ""


def _agrupar(nacional: str) -> str:
    """Agrupa el número nacional como lo escribiría alguien del país."""
    n = len(nacional)
    if n == 9 and nacional.startswith("9"):      # Chile, Perú, Ecuador: 9 1234 5678
        cortes = (1, 4, 4)
    elif n == 9:                                  # España: 600 11 22 33
        cortes = (3, 3, 3)
    elif n == 10:                                 # México, Colombia: 55 1234 5678
        cortes = (2, 4, 4)
    elif n == 8:                                  # Uruguay, Centroamérica: 1234 5678
        cortes = (4, 4)
    elif n == 11:                                 # Argentina/Brasil con 9 inicial
        cortes = (1, 2, 4, 4)
    else:
        return nacional
    partes, i = [], 0
    for c in cortes:
        partes.append(nacional[i:i + c])
        i += c
    if i < n:
        partes.append(nacional[i:])
    return " ".join(p for p in partes if p)


def bonito(e164: str, pais: Pais | None = None) -> str:
    """Formato legible: +56 9 1234 5678 / +34 600 11 22 33."""
    if not e164:
        return ""
    d = digitos(e164)
    if pais and d.startswith(pais.dial):
        return f"+{pais.dial} " + _agrupar(d[len(pais.dial):])
    return "+" + d
