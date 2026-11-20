"""
El puente a WhatsApp: un proceso de Node por número, solo en esta máquina.

Usa el WhatsApp Assistant (Baileys, MIT), instalado en whatsapp/ con
`npm install`. Es una API NO oficial: Meta puede banear el número sin aviso,
sobre todo si escribe en frío. Por eso este módulo solo sabe arrancar, mirar,
mandar UN mensaje cuando se lo piden y leer si alguien contestó. Quién recibe
qué y cuándo lo decide whatsapp.py, y solo con mensajes que aprobaste.

Cada número vive en .whatsapp/numero-N/ (sesión, token y copia de los chats
de la última semana). Esa carpeta da acceso a tu WhatsApp: no la compartas.
"""

import json
from pathlib import Path
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from . import config
from .puente import RAIZ

CARPETA_NODE = RAIZ / "whatsapp"
ENTRADA = CARPETA_NODE / "node_modules" / "@diegomarvid" / "whatsapp-assistant" / "src" / "server.js"
SESIONES = RAIZ / ".whatsapp"
# Lejos del 3850, el puerto por defecto del asistente, por si ya hay otro corriendo.
PUERTO_BASE = 3870


def numeros() -> list[int]:
    """Los números configurados: WA_NUMEROS=2 -> [1, 2]. Entre 1 y 3."""
    return list(range(1, max(1, min(3, config.numero("WA_NUMEROS", 2))) + 1))


def es_numero(valor) -> bool:
    try:
        return int(valor) in numeros()
    except (TypeError, ValueError):
        return False


def carpeta(n: int):
    return SESIONES / f"numero-{int(n)}"


def _puerto(n: int) -> int:
    return config.numero("WA_PUERTO_BASE", PUERTO_BASE) + int(n)


def _url(n: int, ruta: str) -> str:
    return f"http://127.0.0.1:{_puerto(n)}{ruta}"


def node() -> str:
    return shutil.which("node") or ""


def instalado() -> bool:
    return ENTRADA.exists()


def vinculado(n: int) -> bool:
    return (carpeta(n) / "auth" / "creds.json").exists()


def _token(n: int) -> str:
    try:
        return (carpeta(n) / "data" / "bridge-token").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _pedir(n: int, ruta: str, cuerpo: dict | None = None, espera: float = 2.0,
           token: bool = True) -> tuple[int, dict]:
    """(código HTTP, JSON). Código 0 si el puente no contesta."""
    cab = {"Content-Type": "application/json"}
    if token:
        t = _token(n)
        if not t:
            return 0, {}
        cab["Authorization"] = f"Bearer {t}"
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    peticion = Request(_url(n, ruta), data=datos, headers=cab, method="POST" if datos else "GET")
    try:
        with urlopen(peticion, timeout=espera) as r:
            return r.status, json.loads(r.read() or b"{}")
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (URLError, OSError, ValueError):
        return 0, {}


# --- estado de cada número -----------------------------------------------------

def _salud(n: int) -> dict | None:
    # Si nunca se lanzó, no se pregunta: en Windows, tocar un puerto cerrado tarda segundos.
    if not _archivo_pid(n).exists():
        return None
    codigo, datos = _pedir(n, "/health", espera=1.5, token=False)
    return datos if codigo == 200 else None


def _archivo_pid(n: int):
    return carpeta(n) / "asistente.pid"


def _recien_lanzado(n: int) -> bool:
    try:
        return time.time() - _archivo_pid(n).stat().st_mtime < 25
    except OSError:
        return False


def conexion(n: int, salud: dict | None = None) -> str:
    """apagado · iniciando · esperando_qr · conectado · sesion_cerrada · desconectado"""
    s = salud if salud is not None else _salud(n)
    if not s:
        return "iniciando" if _recien_lanzado(n) else "apagado"
    c = s.get("connection")
    if c == "open":
        return "conectado"
    if c == "logged_out":
        return "sesion_cerrada"
    if c == "connecting" and s.get("qrPending"):
        return "esperando_qr"
    if c in ("connecting", "starting"):
        return "iniciando"
    return "desconectado"


def _qr_imagen(n: int) -> str:
    """El QR para vincular, como imagen lista para el navegador. "" si no hay."""
    codigo, datos = _pedir(n, "/qr", espera=1.5)
    if codigo != 200 or not datos.get("code") or not node():
        return ""
    try:
        r = subprocess.run([node(), str(CARPETA_NODE / "qr.mjs")], input=datos["code"].encode("utf-8"),
                           capture_output=True, timeout=15, cwd=CARPETA_NODE)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    salida = r.stdout.decode("ascii", errors="ignore").strip()
    return salida if salida.startswith("data:image/") else ""


def estado(n: int) -> dict:
    s = _salud(n)
    c = conexion(n, s)
    return {"numero": n, "vinculado": vinculado(n), "conexion": c,
            "qr": _qr_imagen(n) if c == "esperando_qr" else "",
            "error": (s or {}).get("lastError") or ""}


# --- arrancar y parar ------------------------------------------------------------

def iniciar(n: int) -> str:
    """Levanta el puente de un número. Devuelve un error legible, o ""."""
    if not instalado():
        return "Falta instalar el puente: en la carpeta whatsapp, corre  npm install"
    if not node():
        return "No encuentro Node.js. Instálalo desde nodejs.org (versión 22.13 o más)"
    actual = conexion(n)
    if actual not in ("apagado", "desconectado", "sesion_cerrada"):
        return ""  # ya está andando o arrancando: no lanzar otro encima
    if actual != "apagado":
        detener(n)  # con el QR vencido o la sesión cerrada, el puente no se recupera solo

    carpeta(n).mkdir(parents=True, exist_ok=True)
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("NODE_OPTIONS", "NODE_ENV", "PORT") and not k.startswith(("GMAIL_", "TREG_"))}
    entorno.update(WA_STATE_DIR=str(carpeta(n)), WA_BRIDGE_PORT=str(_puerto(n)),
                   LOG_LEVEL=entorno.get("LOG_LEVEL", "warn"))
    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        opciones["start_new_session"] = True
    with (carpeta(n) / "asistente.log").open("ab") as registro:
        proceso = subprocess.Popen([node(), str(ENTRADA)], cwd=carpeta(n), env=entorno,
                                   stdin=subprocess.DEVNULL, stdout=registro, stderr=registro, **opciones)
    _archivo_pid(n).write_text(str(proceso.pid), encoding="utf-8")
    return ""


def detener(n: int) -> None:
    try:
        pid = int(_archivo_pid(n).read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass  # no había proceso, o ya estaba cerrado
    try:
        _archivo_pid(n).unlink()
    except OSError:
        pass


def desvincular(n: int) -> None:
    """Apaga el puente y borra la sesión: para volver a usarlo hay que escanear el QR."""
    detener(n)
    time.sleep(0.5)
    shutil.rmtree(carpeta(n), ignore_errors=True)


def levantar_vinculados(saltar: set[int] | None = None) -> None:
    """Al abrir el panel: los números ya vinculados vuelven a conectarse solos."""
    if not instalado() or not node():
        return
    for n in numeros():
        if n in (saltar or set()):
            continue
        # Un pid que quedó de antes (se reinició el servidor) no es de este proceso:
        # se borra para no matar después a otro programa con ese número.
        if _archivo_pid(n).exists() and not _recien_lanzado(n) and _salud(n) is None:
            _archivo_pid(n).unlink(missing_ok=True)
        if vinculado(n) and conexion(n) == "apagado":
            iniciar(n)


def detener_todos() -> None:
    for n in numeros():
        detener(n)


# --- mandar y leer ---------------------------------------------------------------

def jid(telefono: str) -> str:
    """+56912345678 -> 56912345678@s.whatsapp.net"""
    digitos = "".join(c for c in telefono or "" if c.isdigit())
    return f"{digitos}@s.whatsapp.net" if len(digitos) >= 10 else ""


def _resultado(n: int, codigo: int, datos: dict) -> tuple[str, str]:
    if codigo == 200:
        return "ok", ""
    if codigo in (0, 202):
        return "incierto", "Se cortó la conexión con el puente: mira en el celular si el mensaje salió"
    if codigo == 503:
        return "error", f"El número {n} se desconectó"
    return "error", datos.get("message") or datos.get("error") or f"WhatsApp rechazó el mensaje ({codigo})"


def enviar_audio(n: int, telefono: str, ruta, id_pedido: str) -> tuple[str, str]:
    """
    Manda un .ogg (Opus) como nota de voz: le llega como un audio grabado, no como un
    archivo adjunto. Mismo (resultado, error) que enviar().
    """
    destino = jid(telefono)
    if not destino:
        return "error", "El número no tiene código de país"
    if not _token(n):
        return "error", f"El número {n} todavía no está vinculado"
    codigo, datos = _pedir(n, "/media/send", {"jid": destino, "filePath": str(Path(ruta).resolve()), "kind": "audio",
                                              "voice": True, "requestId": id_pedido}, espera=60)
    return _resultado(n, codigo, datos)


def enviar(n: int, telefono: str, texto: str, id_pedido: str) -> tuple[str, str]:
    """
    Manda UN mensaje de texto. (resultado, error):

        ok          salió
        incierto    no sabemos si salió: no se reintenta solo, hay que mirar el celular
        error       no salió (el error dice por qué)

    `id_pedido` evita duplicados: si el mismo pedido llega dos veces, el puente no
    lo manda de nuevo.
    """
    destino = jid(telefono)
    if not destino:
        return "error", "El número no tiene código de país"
    if not _token(n):
        return "error", f"El número {n} todavía no está vinculado"
    codigo, datos = _pedir(n, "/messages/send", {"jid": destino, "text": texto, "requestId": id_pedido},
                           espera=30)
    return _resultado(n, codigo, datos)


def recibidos(n: int, telefono: str, desde: datetime) -> list[dict]:
    """
    Lo que esa persona te escribió después de `desde`, del más viejo al más nuevo.
    WhatsApp a veces guarda el chat con otro identificador (LID): se miran los dos.
    """
    destino = jid(telefono)
    if not destino:
        return []
    jids = _jids(n, destino)
    if jids is None:
        return []
    limite = desde.timestamp()
    mensajes = []
    for j in jids:
        codigo, datos = _pedir(n, f"/messages?jid={quote(j)}&limit=50", espera=5)
        if codigo != 200:
            continue
        mensajes += [m for m in datos.get("messages", [])
                     if not m.get("fromMe") and float(m.get("timestamp") or 0) >= limite and not interno(m.get("type"))]
    return sorted(mensajes, key=lambda m: float(m.get("timestamp") or 0))


# El LID de cada chat: WhatsApp guarda los mensajes del cliente con ese otro identificador.
# El puente solo lo entrega mientras el último mensaje del chat es del cliente; si el último
# es tuyo, devuelve el número y los mensajes del cliente quedan sin ver. Por eso, cuando
# se conoce, se recuerda en un archivo: sobrevive a los reinicios y a los despliegues.
LIDS = RAIZ / "datos" / "whatsapp-lids.json"
_lid: dict[tuple[int, str], str] = {}
_lid_cargado = False
_sin_lid: dict[tuple[int, str], float] = {}  # cuándo se preguntó sin suerte (para no preguntar a cada rato)
SIN_LID_CADA = 60


def _cargar_lids() -> None:
    global _lid_cargado
    if _lid_cargado:
        return
    _lid_cargado = True
    try:
        for clave, valor in json.loads(LIDS.read_text(encoding="utf-8")).items():
            n, _, destino = clave.partition("|")
            if n.isdigit() and str(valor).endswith("@lid"):
                _lid.setdefault((int(n), destino), valor)
    except (OSError, ValueError):
        pass


def recordar_lid(n: int, telefono_o_jid: str, lid: str) -> bool:
    """Guarda el LID de un chat. True si es nuevo."""
    _cargar_lids()
    destino = telefono_o_jid if "@" in telefono_o_jid else jid(telefono_o_jid)
    if not destino or not str(lid).endswith("@lid") or _lid.get((n, destino)) == lid:
        return False
    _lid[(n, destino)] = lid
    try:
        LIDS.parent.mkdir(parents=True, exist_ok=True)
        tmp = LIDS.with_suffix(".tmp")
        tmp.write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in _lid.items()}, indent=1), encoding="utf-8")
        tmp.replace(LIDS)
    except OSError:
        pass
    return True


def lid_de(n: int, telefono: str) -> str:
    _cargar_lids()
    return _lid.get((n, jid(telefono)), "")


def _jids(n: int, destino: str) -> set[str] | None:
    """Los identificadores donde puede estar ese chat. None si el puente no contesta."""
    _cargar_lids()
    jids = {destino}
    if (n, destino) not in _lid and time.time() - _sin_lid.get((n, destino), 0) > SIN_LID_CADA:
        codigo, datos = _pedir(n, f"/resolve?jid={quote(destino)}", espera=5)
        if codigo == 0:
            return None
        otro = datos.get("jid", "") if codigo == 200 else ""
        if otro and otro != destino:
            recordar_lid(n, destino, otro)
        else:
            _sin_lid[(n, destino)] = time.time()
    if _lid.get((n, destino)):
        jids.add(_lid[(n, destino)])
    return jids


def buscar_lid(n: int, telefono: str, textos: list[str], desde: float) -> str:
    """
    Recupera el LID de un chat que quedó sin ver, buscando en el puente los mensajes que esa
    persona te escribió (los textos que el panel ya había guardado de ella). Solo se usa el
    identificador si todas las coincidencias, escritas por ellos después de tu saludo, caen en
    UN mismo chat; no se lee nada más de esos resultados.
    """
    vistos: set[str] = set()
    for texto in [t.strip() for t in textos if len((t or "").strip()) >= 6][:4]:
        codigo, datos = _pedir(n, f"/search?q={quote(texto[:120])}&scope=direct&limit=20", espera=5)
        if codigo != 200:
            continue
        for m in datos.get("messages", []):
            if (not m.get("fromMe") and str(m.get("jid", "")).endswith("@lid")
                    and float(m.get("timestamp") or 0) >= desde - 60
                    and (m.get("text") or "").strip().lower() == texto.lower()):
                vistos.add(m["jid"])
    return vistos.pop() if len(vistos) == 1 else ""


# Mensajes internos de WhatsApp (avisos del sistema, llaves de cifrado, reacciones): no son
# algo que alguien escribió. Sin filtrarlos, uno "tuyo" hacía creer que ya habías contestado.
INTERNOS = ("protocolMessage", "senderKeyDistributionMessage", "messageContextInfo", "reactionMessage",
            "keepInChatMessage", "pinInChatMessage", "editedMessage", "encReactionMessage", "pollUpdateMessage")


def interno(tipo: str | None) -> bool:
    return (tipo or "") in INTERNOS


def conversacion(n: int, telefono: str, limite: int = 200) -> list[dict] | None:
    """
    El chat con ESE número (los dos lados), del más viejo al más nuevo. Solo se pide el
    chat de ese teléfono: el resto de las conversaciones del número no se leen.
    None si el puente no contesta.
    """
    destino = jid(telefono)
    if not destino:
        return []
    jids = _jids(n, destino)
    if jids is None:
        return None
    vistos, mensajes, alguno = set(), [], False
    for j in jids:
        codigo, datos = _pedir(n, f"/messages?jid={quote(j)}&limit={int(limite)}", espera=5)
        if codigo != 200:
            continue
        alguno = True
        for m in datos.get("messages", []):
            if m.get("id") in vistos or interno(m.get("type")):
                continue
            vistos.add(m.get("id"))
            mensajes.append({"id": m.get("id"), "yo": bool(m.get("fromMe")), "hora": float(m.get("timestamp") or 0),
                             "tipo": m.get("type") or "", "texto": m.get("text") or ""})
    if not alguno:
        return None
    return sorted(mensajes, key=lambda m: m["hora"])
