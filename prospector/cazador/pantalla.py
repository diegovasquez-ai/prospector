"""
Lo que se ve en la terminal.

Sin librerías: ANSI a pelo. Con `rich` quedaría más bonito, pero serían cuatro
dependencias en vez de tres, las barras de progreso ensucian cualquier log
redirigido y el output dejaría de poder pegarse tal cual en Discord cuando un
alumno pide ayuda. No compensa.

El color se apaga solo cuando no hay una terminal de verdad delante, así que
`python cazador.py ... > salida.txt` produce un archivo limpio.
"""

import os
import sys

BANNER = r"""
   ___ _   ___  _   ___  ___  ___
  | __| | / __|/_\ |_  )/ _ \| _ \   EL CAZADOR 2.0
  | _|| |_\__ / _ \ / // (_) |   /   de un nicho y una ciudad  ->  WhatsApp  ->  Airtable
  |___|____|___/_/ \_/___\___/|_|_\  """

_CODIGOS = {
    "verde": "\033[32m", "amarillo": "\033[33m", "cian": "\033[36m",
    "gris": "\033[90m", "negrita": "\033[1m", "fin": "\033[0m",
}


def hay_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def c(texto: str, color: str) -> str:
    if not hay_color() or color not in _CODIGOS:
        return texto
    return f"{_CODIGOS[color]}{texto}{_CODIGOS['fin']}"


def preparar_consola() -> None:
    """
    En Windows la consola a veces no viene en UTF-8 y rompe los acentos.

    stdin va en la lista y no es un detalle: casi todos los nichos en español
    llevan tilde o eñe. Si no se reconfigura, el alumno escribe "barberías" y
    al programa le llega "barberÃ­as", que acaba en el nombre del archivo y en
    su Airtable. errors="replace" para que un carácter raro nunca aborte la
    caza entera.
    """
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def titulo(texto: str) -> None:
    print(c(texto, "negrita"))


def aviso(texto: str) -> None:
    """Un ! con lo que ha pasado. Amarillo, nunca rojo: casi nada es terminal."""
    for i, linea in enumerate(texto.splitlines()):
        print(c("!  " + linea if i == 0 else "   " + linea, "amarillo"))


def lead_encontrado(nombre: str, contacto: str, etiqueta: str, hechos: int, total: int) -> None:
    """
    La línea que engancha al alumno. Se imprime en cuanto aparece el lead, no
    al final: ver el primero a los 20 segundos es lo que hace que no abandone.
    """
    print("  " + c("+", "verde") + f" {nombre[:30]:<30} {contacto:<17} "
          f"{etiqueta:<6} {c(f'[{hechos:>3}/{total}]', 'gris')}")


def latido(texto: str) -> None:
    print(c("  · " + texto, "gris"))


def ruta(texto: str) -> str:
    return c(texto, "cian")


def regla(ancho: int = 64) -> None:
    print("═" * ancho)


def tabla_estado(filas: list[tuple]) -> None:
    """
    Qué tiene activo el usuario. Es una tabla de lo que YA funciona, no una
    lista de errores: quien acaba de clonar el repo no ha hecho nada mal.
    """
    print()
    print("  Lo que tienes activo ahora mismo")
    for nombre, activo, coste, beneficio, _var in filas:
        marca = c("[·]", "verde") if activo else "[ ]"
        estado = coste if activo else f"falta la clave · {coste}"
        print(f"    {marca} {nombre:<15} {estado:<26} {c(beneficio, 'gris')}")
    faltan = [f for f in filas if not f[1]]
    if faltan:
        print()
        print(c("  Con lo de arriba ya sacas negocios con WhatsApp en CSV.", "gris"))
        print(c("  Todo lo demás es opcional:  python cazador.py configurar", "gris"))
    print()
