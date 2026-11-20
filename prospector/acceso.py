"""
El login del panel, para cuando corre en un servidor.

En tu computador el panel no pide nada: solo escucha en 127.0.0.1. En un servidor
(Coolify, un VPS) cualquiera en internet podría abrirlo, y ahí están tus prospectos,
tu Gmail y tus números de WhatsApp. Por eso, si defines PANEL_CLAVE, el panel pide esa
contraseña y deja una sesión firmada por 30 días. Sin PANEL_CLAVE no se deja abrir
fuera de 127.0.0.1 (ver panel.abrir).

Cambiar PANEL_CLAVE cierra todas las sesiones abiertas.
"""

import hashlib
import hmac
import threading
import time
from http.cookies import CookieError, SimpleCookie

from . import config

COOKIE = "prospector_sesion"
DURACION = 30 * 24 * 3600
# Contra quien prueba contraseñas: por IP y en total, en una ventana de 15 minutos.
VENTANA = 15 * 60
MAX_POR_IP = 5
MAX_TOTAL = 30

_fallos: dict[str, list[float]] = {}
_candado = threading.Lock()


def activo() -> bool:
    return bool(config.texto("PANEL_CLAVE"))


def usuario() -> str:
    """El correo de acceso (PANEL_USUARIO). Si no está, basta la contraseña."""
    return config.texto("PANEL_USUARIO").strip().lower()


def _secreto() -> bytes:
    base = f"prospector-sesion|{usuario()}|{config.texto('PANEL_CLAVE')}"
    return hashlib.sha256(base.encode("utf-8")).digest()


def _firma(expira: str) -> str:
    return hmac.new(_secreto(), expira.encode("utf-8"), hashlib.sha256).hexdigest()


def nueva_sesion(ahora: float | None = None) -> str:
    expira = str(int((ahora or time.time()) + DURACION))
    return f"{expira}.{_firma(expira)}"


def valida(valor: str, ahora: float | None = None) -> bool:
    if not activo() or not valor or "." not in valor:
        return False
    expira, firma = valor.split(".", 1)
    if not expira.isdigit() or int(expira) < (ahora or time.time()):
        return False
    return hmac.compare_digest(firma, _firma(expira))


def de_cookie(cabecera: str) -> str:
    try:
        galleta = SimpleCookie(cabecera or "")
    except CookieError:
        return ""
    return galleta[COOKIE].value if COOKIE in galleta else ""


def cabecera_cookie(valor: str, segura: bool) -> str:
    edad = DURACION if valor else 0
    return (f"{COOKIE}={valor}; Path=/; HttpOnly; SameSite=Strict; Max-Age={edad}"
            + ("; Secure" if segura else ""))


def _recientes(ip: str, ahora: float) -> tuple[int, int]:
    for clave in list(_fallos):
        _fallos[clave] = [t for t in _fallos[clave] if ahora - t < VENTANA]
        if not _fallos[clave]:
            del _fallos[clave]
    return len(_fallos.get(ip, [])), sum(len(v) for v in _fallos.values())


def _igual(a: str, b: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(a.encode("utf-8")).digest(),
                               hashlib.sha256(b.encode("utf-8")).digest())


def entrar(clave: str, ip: str, correo: str = "", ahora: float | None = None) -> str:
    """"" si el correo (si se exige) y la contraseña son correctos; si no, el motivo."""
    ahora = ahora or time.time()
    with _candado:
        de_ip, total = _recientes(ip, ahora)
        if de_ip >= MAX_POR_IP or total >= MAX_TOTAL:
            return "Demasiados intentos. Espera 15 minutos."
        # Se comparan los dos siempre: así no se sabe cuál de los dos falló.
        correo_ok = _igual((correo or "").strip().lower(), usuario()) if usuario() else True
        clave_ok = _igual(clave or "", config.texto("PANEL_CLAVE"))
        if activo() and correo_ok and clave_ok:
            _fallos.pop(ip, None)
            return ""
        _fallos.setdefault(ip, []).append(ahora)
        return "Correo o contraseña incorrectos" if usuario() else "Contraseña incorrecta"
