"""
Fase 7: el panel donde apruebas, afinas y mandas.

    python prospector.py panel        ->  http://127.0.0.1:8765

Un servidor de la biblioteca estándar y una sola página HTML: nada que
instalar. Escucha solo en tu máquina y cada POST exige la cabecera
X-Panel, que una web ajena no puede poner sin permiso del navegador. Sin
eso, cualquier página que visitaras podría aprobar y mandar correos por ti.
"""

import json
import socket
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from urllib.request import urlopen

from . import config, correos, envio, gmail, radar, whatsapp
from .analizar import FICHAS
from .puente import RAIZ, exclusiones

PAGINA = RAIZ / "panel" / "index.html"
ACCIONES = ("guardar", "aprobar", "devolver", "rechazar", "deshacer", "prueba", "respuesta", "whatsapp")
RESPUESTAS = {
    "si": ("interesado", "Quiere el diagnóstico: prepáralo y propón 20 minutos para revisarlo."),
    "info": ("interesado", "Pidió información: mándale el diagnóstico, no un PDF de servicios."),
    "ahora_no": ("retomar", "Ahora no. Volver a escribirle en 60 días."),
    "baja": ("baja", "No le interesa o pidió la baja. En la lista negra."),
}


def resumen(b: dict) -> dict:
    claves = ("dominio", "nombre", "comuna", "estado", "para", "correo_estado", "creado")
    return {k: b.get(k, "") for k in claves} | {"envios": len(b.get("envios", []))}


def estado_general() -> dict:
    e = envio.leer_estado()
    bs = correos.listar()
    conteos: dict[str, int] = {}
    for b in bs:
        conteos[b.get("estado", "")] = conteos.get(b.get("estado", ""), 0) + 1
    ini, fin = config.rango("ENVIO_HORARIO", (9, 18))
    return {
        "gmail": gmail.configurado(), "usuario": gmail.usuario(),
        "activo": e.get("activo", False), "proximo": e.get("proximo", ""), "error": e.get("error", ""),
        "enviados_hoy": envio.enviados_hoy(bs), "max_dia": config.numero("ENVIO_MAX_DIA", 20),
        "horario": f"{ini}-{fin}", "en_horario": envio.en_horario(datetime.now()),
        "conteos": conteos, "firma": gmail.firma(), "claude": bool(correos.claude_disponible()),
    }


def detalle(b: dict) -> dict:
    ficha = FICHAS / f"{b['dominio']}.md"
    return correos.con_revision(b) | {
        "ficha": ficha.read_text(encoding="utf-8") if ficha.exists() else "",
        "firma": gmail.firma(),
        "whatsapp_vista": whatsapp.vista(b),
    }


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):  # sin una línea por petición en la terminal
        pass

    def _responder(self, codigo: int, datos, tipo: str = "application/json") -> None:
        cuerpo = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, codigo: int, mensaje: str) -> None:
        self._responder(codigo, {"error": mensaje})

    def _host_local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("localhost", "127.0.0.1")

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(largo) or b"{}") if largo else {}

    # --- GET -----------------------------------------------------------------
    def do_GET(self):
        if not self._host_local():
            return self._error(403, "Solo desde tu máquina")
        partes = [unquote(p) for p in self.path.split("?")[0].strip("/").split("/") if p]
        if not partes:
            return self._responder(200, PAGINA.read_bytes(), "text/html")
        if partes == ["api", "estado"]:
            return self._responder(200, estado_general())
        if partes == ["api", "borradores"]:
            return self._responder(200, [resumen(b) for b in correos.listar()])
        if len(partes) == 3 and partes[:2] == ["api", "borradores"]:
            try:
                return self._responder(200, detalle(correos.leer(partes[2])))
            except FileNotFoundError:
                return self._error(404, "No existe ese borrador")
        if partes == ["api", "radar"]:
            return self._responder(200, {"filas": radar.listar(), "trabajos": radar.trabajos(),
                                         "comunas": radar.comunas_sugeridas()})
        if partes == ["api", "radar", "trabajos"]:
            return self._responder(200, radar.trabajos())
        if len(partes) == 3 and partes[:2] == ["api", "radar"]:
            try:
                return self._responder(200, radar.detalle(partes[2]))
            except KeyError:
                return self._error(404, "No está en la base")
        self._error(404, "No existe")

    # --- POST ----------------------------------------------------------------
    def do_POST(self):
        # El cuerpo se lee siempre, también para rechazar: si se responde con
        # él sin leer, Windows corta la conexión y el navegador ve un error de red.
        try:
            datos = self._cuerpo()
        except json.JSONDecodeError:
            datos = None
        if not self._host_local() or self.headers.get("X-Panel") != "1":
            return self._error(403, "Solo desde el panel")
        if datos is None:
            return self._error(400, "JSON inválido")
        partes = [unquote(p) for p in self.path.strip("/").split("/") if p]

        if partes == ["api", "envio"]:
            with correos.CANDADO:
                e = envio.leer_estado()
                e["activo"] = bool(datos.get("activo"))
                if e["activo"]:
                    e["error"] = ""
                envio.guardar_estado(e)
            return self._responder(200, estado_general())

        # Radar: los dos arrancan un hilo y vuelven al instante.
        if partes == ["api", "radar", "rastrear"]:
            error = radar.rastrear(datos.get("comuna", ""))
            return self._error(400, error) if error else self._responder(200, radar.trabajos())
        if len(partes) == 4 and partes[:2] == ["api", "radar"] and partes[3] == "investigar":
            error = radar.investigar(partes[2])
            return self._error(400, error) if error else self._responder(200, radar.trabajos())

        if len(partes) < 3 or partes[:2] != ["api", "borradores"]:
            return self._error(404, "No existe")
        dominio, accion = partes[2], (partes[3] if len(partes) > 3 else "guardar")
        try:
            # Afinar tarda un minuto: no bloquea el resto mientras Claude piensa.
            if accion == "afinar":
                return self._afinar(dominio, datos.get("nota", ""))
            if accion not in ACCIONES:
                return self._error(404, f"Acción desconocida: {accion}")
            with correos.CANDADO:
                b = correos.leer(dominio)
                b.setdefault("envios", [])
                error = getattr(self, "_" + accion)(b, datos)
                if error:
                    return self._error(400, error)
                correos.guardar(b)
                return self._responder(200, detalle(b))
        except FileNotFoundError:
            return self._error(404, "No existe ese borrador")
        except Exception as e:
            return self._error(500, f"{type(e).__name__}: {e}")

    # Cada acción recibe el borrador y el JSON del POST. Devuelve un texto si
    # no se puede hacer; si no, el borrador se guarda tal cual quedó.

    def _guardar(self, b: dict, d: dict) -> str:
        if b.get("estado") not in correos.EDITABLES:
            return "Ya salió: no se puede editar"
        for clave in ("para", "correo_estado", "correos", "nota", "comprobado"):
            if clave in d:
                b[clave] = d[clave]
        return ""

    def _aprobar(self, b: dict, d: dict) -> str:
        error = self._guardar(b, d)
        if error:
            return error
        problemas, _ = correos.revisar(b)
        if problemas:
            return "No se puede aprobar: " + "; ".join(problemas)
        b.update(estado="aprobado", aprobado_en=datetime.now().isoformat(timespec="seconds"),
                 motivo="")
        return ""

    def _devolver(self, b: dict, d: dict) -> str:
        if b.get("estado") not in ("aprobado", "rechazado"):
            return "Solo se devuelve a revisión lo aprobado o rechazado"
        b["estado"] = "por revisar"
        return ""

    def _rechazar(self, b: dict, d: dict) -> str:
        if b.get("estado") not in correos.EDITABLES:
            return "Ya salió: no se puede rechazar"
        b.update(estado="rechazado", motivo=d.get("motivo", "").strip() or "Rechazado en el panel")
        return ""

    def _deshacer(self, b: dict, d: dict) -> str:
        if not b.get("historial"):
            return "No hay una versión anterior"
        b["correos"] = b["historial"].pop()["correos"]
        return ""

    def _prueba(self, b: dict, d: dict) -> str:
        """Los tres correos a ti mismo, en el mismo hilo, tal como saldrían."""
        if not gmail.configurado():
            return "Configura GMAIL_USUARIO y GMAIL_CLAVE_APP en el .env"
        self._guardar(b, d)
        yo = gmail.usuario()
        primero = ""
        for paso in range(len(b["correos"])):
            asunto = "[Prueba] " + envio.asunto_de(b, paso)
            mid = gmail.enviar(yo, asunto, envio.cuerpo_de(b, paso), responde_a=primero)
            primero = primero or mid
        b["ultima_prueba"] = datetime.now().isoformat(timespec="seconds")
        return ""

    def _respuesta(self, b: dict, d: dict) -> str:
        tipo = d.get("tipo", "")
        if tipo not in RESPUESTAS:
            return "Tipo de respuesta desconocido"
        b["estado"], b["motivo"] = RESPUESTAS[tipo]
        if tipo == "ahora_no":
            b["retomar_en"] = (date.today() + timedelta(days=60)).isoformat()
        if tipo == "baja":
            exclusiones.anadir(b["dominio"], f"respondió: no le interesa ({date.today()})")
        return ""

    def _whatsapp(self, b: dict, d: dict) -> str:
        return whatsapp.accion(b, d)

    def _afinar(self, dominio: str, nota: str):
        if not nota.strip():
            return self._error(400, "Escribe qué quieres cambiar")
        with correos.CANDADO:
            b = correos.leer(dominio)
            if b.get("estado") not in correos.EDITABLES:
                return self._error(400, "Ya salió: no se puede afinar")
        try:
            nuevos = correos.afinar(b, nota)
        except Exception as e:
            return self._error(500, str(e))
        with correos.CANDADO:
            b = correos.leer(dominio)  # por si lo editaste mientras Claude pensaba
            correos.respaldar(b)
            b["correos"] = nuevos
            b.setdefault("notas", []).append({"fecha": datetime.now().isoformat(timespec="seconds"),
                                              "nota": nota.strip()})
            b["nota"] = ""
            correos.guardar(b)
        return self._responder(200, detalle(b))


class Servidor(ThreadingHTTPServer):
    """
    El puerto, en exclusiva. El servidor de Python activa SO_REUSEADDR, y en
    Windows eso deja que dos programas escuchen en el mismo puerto: el panel
    "abría" sin error encima de otro y el navegador acababa en el otro. Peor:
    dos paneles a la vez, dos colas, correos dobles.
    """
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # solo existe en Windows
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _contesta(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def es_panel(puerto: int) -> bool:
    """¿Lo que escucha en ese puerto es un panel del Prospector, o algo ajeno?"""
    try:
        with urlopen(f"http://127.0.0.1:{puerto}/api/estado", timeout=2) as r:
            datos = json.loads(r.read())
        return isinstance(datos, dict) and {"gmail", "max_dia", "conteos"} <= datos.keys()
    except (OSError, ValueError):
        return False


def elegir_puerto(puerto: int, intentos: int = 10) -> tuple[ThreadingHTTPServer | None, int]:
    """
    (servidor, puerto). Servidor None = ya hay un panel abierto en ese puerto.

    Si el puerto lo tiene otro programa (otro proyecto sirviendo archivos, por
    ejemplo), se prueba el siguiente. Si lo tiene un panel, no se abre otro:
    dos colas enviando a la vez mandarían correos dobles.
    """
    for p in range(puerto, puerto + intentos):
        # Primero se pregunta si alguien contesta: en Windows, quien escucha en
        # 0.0.0.0 o en :: no impide abrir 127.0.0.1 encima, aunque sea en exclusiva.
        if _contesta(p):
            if es_panel(p):
                return None, p
            continue
        try:
            return Servidor(("127.0.0.1", p), Manejador), p
        except OSError:
            if es_panel(p):
                return None, p
    raise SystemExit(f"Del {puerto} al {puerto + intentos - 1} están todos ocupados. "
                     f"Prueba:  python prospector.py panel --puerto 9000")


def abrir(puerto: int = 8765, navegador: bool = True) -> int:
    config.cargar()
    servidor, elegido = elegir_puerto(puerto)
    # 127.0.0.1 y no "localhost": localhost puede llevar a otro programa por IPv6.
    url = f"http://127.0.0.1:{elegido}"
    if servidor is None:
        print(f"\n  El panel ya está abierto en {url}")
        if navegador:
            webbrowser.open(url)
        return 0
    if elegido != puerto:
        print(f"\n  El puerto {puerto} lo usa otro programa: abro el panel en el {elegido}.")
    envio.Envio().start()
    print(f"\n  Panel abierto en {url}")
    print("  Los envíos solo corren mientras esta ventana siga abierta. Ctrl+C para cerrar.\n")
    if navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Panel cerrado. Nada más sale hasta que lo vuelvas a abrir.")
    return 0
