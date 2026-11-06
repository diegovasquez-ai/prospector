"""
La lista de exclusión: a quién no se le vuelve a escribir. Nunca.

Cuando alguien te pide la baja, deja de ser un lead. Este módulo se encarga de
que eso se cumpla de verdad y no dependa de que te acuerdes:

    cazador excluir +34641556164 --motivo "pidió baja 25/08"
    cazador excluir ana@empresa.com
    cazador excluir barberia-ejemplo.es          (el dominio entero)

TODA exportación — CSV, JSON y Airtable — pasa por aquí. Y a propósito NO hay
ningún flag para desactivarlo. Un --ignorar-exclusiones sería la diferencia
entre un proyecto que habla de ética y uno que la implementa.

El archivo es texto plano, una entrada por línea, y está en .gitignore: son
datos personales de gente que te ha pedido explícitamente que la dejes en paz.
"""

import re
from datetime import date
from pathlib import Path

ARCHIVO = Path("exclusiones.txt")

CABECERA = """# Lista de exclusión de El Cazador
#
# Quien esté aquí no vuelve a salir en ningún CSV, JSON ni Airtable tuyo.
# Una entrada por línea: un teléfono, un email o un dominio.
# Se añaden con:  python prospector.py baja <correo o dominio> --motivo "..."
#
"""


def _solo_digitos(texto: str) -> str:
    return re.sub(r"[^\d]", "", texto or "")


def normalizar(entrada: str) -> tuple[str, str]:
    """
    Devuelve (tipo, valor) donde tipo es 'telefono', 'email' o 'dominio'.
    Los teléfonos se guardan solo con sus dígitos, para que dé igual cómo se
    escriban: +34 641 556 164 y 0034641556164 son el mismo número.
    """
    e = (entrada or "").strip().lower()
    if "@" in e:
        return "email", e
    digitos = _solo_digitos(e)
    if len(digitos) >= 8 and len(digitos) >= len(e) - 6:
        return "telefono", digitos
    e = re.sub(r"^https?://", "", e).split("/")[0]
    return "dominio", e[4:] if e.startswith("www.") else e


def cargar() -> dict:
    """{'telefono': set, 'email': set, 'dominio': set}"""
    fuera = {"telefono": set(), "email": set(), "dominio": set()}
    if not ARCHIVO.exists():
        return fuera
    for linea in ARCHIVO.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        tipo, valor = normalizar(linea)
        fuera[tipo].add(valor)
    return fuera


def anadir(entrada: str, motivo: str = "") -> tuple[str, str]:
    tipo, valor = normalizar(entrada)
    existentes = cargar()
    if valor in existentes[tipo]:
        return tipo, valor
    if not ARCHIVO.exists():
        ARCHIVO.write_text(CABECERA, encoding="utf-8")
    comentario = f"   # {date.today().isoformat()}"
    if motivo:
        comentario += f" · {motivo}"
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(f"{entrada.strip()}{comentario}\n")
    return tipo, valor


def listar() -> list[str]:
    if not ARCHIVO.exists():
        return []
    return [l.rstrip() for l in ARCHIVO.read_text(encoding="utf-8",
                                                   errors="ignore").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def esta_bloqueado(l: dict, fuera: dict | None = None) -> bool:
    """¿Este lead está en la lista? Se mira por teléfono, email y dominio."""
    fuera = cargar() if fuera is None else fuera
    if not any(fuera.values()):
        return False

    for campo in ("whatsapp", "telefono"):
        digitos = _solo_digitos(l.get(campo) or "")
        if digitos and digitos in fuera["telefono"]:
            return True
        # También por los últimos 9 dígitos: el mismo número escrito con o sin
        # prefijo de país no debería colarse.
        if len(digitos) >= 9 and any(x.endswith(digitos[-9:]) for x in fuera["telefono"]):
            return True

    correo = (l.get("email") or "").strip().lower()
    if correo:
        if correo in fuera["email"]:
            return True
        if correo.split("@")[-1] in fuera["dominio"]:
            return True

    if fuera["dominio"]:
        from .filtros import dominio
        dom = dominio(l.get("web") or "")
        if dom and dom in fuera["dominio"]:
            return True

    return False
