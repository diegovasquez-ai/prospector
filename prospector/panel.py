"""
Fase 7: el panel donde apruebas, afinas y mandas.

    python prospector.py panel        ->  http://127.0.0.1:8765

Un servidor de la biblioteca estándar y una sola página HTML: nada que
instalar. Escucha solo en tu máquina y cada POST exige la cabecera
X-Panel, que una web ajena no puede poner sin permiso del navegador. Sin
eso, cualquier página que visitaras podría aprobar y mandar correos por ti.

En un servidor (python prospector.py panel --host 0.0.0.0) exige PANEL_CLAVE:
pide la contraseña y deja una sesión firmada (acceso.py).
"""

import json
import signal
import socket
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from urllib.request import urlopen

from . import acceso, config, correos, crm, envio, gmail, radar, wa_filtro, wa_puente, whatsapp
from . import wa_prospeccion as wp
from .analizar import FICHAS
from .puente import RAIZ, exclusiones

PAGINA = RAIZ / "panel" / "index.html"
ENTRAR = RAIZ / "panel" / "entrar.html"
ACCIONES = ("guardar", "aprobar", "devolver", "rechazar", "deshacer", "prueba", "respuesta")
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
        "prueba_demo": envio.resultados_demo(bs), "auto_correos": envio.auto_aprobar_activo(),
        "wa": whatsapp.resumen(wp.listar()) | {"auto_responder": config.texto("WA_AUTO_RESPONDER").lower() in ("1", "si", "sí", "true")}, "crm_hoy": crm.para_hoy(wp.todos()), "servidor": acceso.activo(),
    }


def detalle(b: dict) -> dict:
    ficha = FICHAS / f"{b['dominio']}.md"
    return correos.con_revision(b) | {
        "ficha": ficha.read_text(encoding="utf-8") if ficha.exists() else "",
        "firma": gmail.firma(),
    }


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):  # sin una línea por petición en la terminal
        pass

    def _responder(self, codigo: int, datos, tipo: str = "application/json", cookie: str | None = None) -> None:
        cuerpo = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie is not None:
            self.send_header("Set-Cookie", acceso.cabecera_cookie(
                cookie, segura=self.headers.get("X-Forwarded-Proto", "") == "https"))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta, tipo: str) -> None:
        cuerpo = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "max-age=3600")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, codigo: int, mensaje: str) -> None:
        self._responder(codigo, {"error": mensaje})

    def _host_local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("localhost", "127.0.0.1")

    def _host_ok(self) -> bool:
        # En un servidor el Host es tu dominio; lo que protege ahí es el login.
        return acceso.activo() or self._host_local()

    def _autorizado(self) -> bool:
        return not acceso.activo() or acceso.valida(acceso.de_cookie(self.headers.get("Cookie", "")))

    def _ip(self) -> str:
        # Detrás del proxy de Coolify, la IP real viene en X-Forwarded-For.
        reenviada = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return reenviada if acceso.activo() and reenviada else self.client_address[0]

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(largo) or b"{}") if largo else {}

    # --- GET -----------------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._error(403, "Solo desde tu máquina")
        partes = [unquote(p) for p in self.path.split("?")[0].strip("/").split("/") if p]
        if partes == ["salud"]:  # para el chequeo de Coolify: no dice nada de tus datos
            return self._responder(200, {"ok": True})
        if partes == ["logo.svg"]:
            return self._archivo(PAGINA.parent / "logo.svg", "image/svg+xml")
        if partes == ["audio", "pitch.ogg"] and self._autorizado():
            if not whatsapp.AUDIO_PITCH.exists():
                return self._error(404, "Todavía no subes el audio")
            return self._archivo(whatsapp.AUDIO_PITCH, "audio/ogg")
        if not self._autorizado():
            if not partes:
                return self._responder(200, ENTRAR.read_bytes(), "text/html")
            return self._error(401, "Inicia sesión")
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
        if partes == ["api", "whatsapp"]:
            return self._responder(200, whatsapp.estado_panel())
        if partes == ["api", "conversaciones"]:
            return self._responder(200, whatsapp.conversaciones())
        if len(partes) == 3 and partes[:2] == ["api", "conversaciones"]:
            try:
                return self._responder(200, whatsapp.conversacion(partes[2]))
            except (FileNotFoundError, KeyError):
                return self._error(404, "No hay chat con ese prospecto")
        if partes == ["api", "crm"]:
            return self._responder(200, {"filas": crm.lista(wp.todos()), "prueba": crm.audio_contra_texto(wp.todos()),
                                         "etapas": [{"clave": e[0], "nombre": e[1], "sugerencia": e[2]} for e in crm.ETAPAS],
                                         "tipos": crm.TIPOS})
        if len(partes) == 3 and partes[:2] == ["api", "crm"]:
            try:
                with correos.CANDADO:
                    b = wp.leer_cualquiera(partes[2])
                    # Quien respondió antes de la prueba audio/texto recibe su formato al abrirlo.
                    if (crm.entra(b) and not crm.por_correo(b) and crm.etapa(b) == "respondio"
                            and crm.asignar_formato(b)):
                        wp.guardar_cualquiera(b)
                return self._responder(200, crm.vista(b, completa=True))
            except FileNotFoundError:
                return self._error(404, "No existe ese negocio")
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
        except (json.JSONDecodeError, UnicodeDecodeError):
            datos = None
        if not self._host_ok() or self.headers.get("X-Panel") != "1":
            return self._error(403, "Solo desde el panel")
        if datos is None:
            return self._error(400, "JSON inválido")
        partes = [unquote(p) for p in self.path.strip("/").split("/") if p]

        if partes == ["api", "login"]:
            if not acceso.activo():
                return self._error(400, "Este panel no usa contraseña")
            error = acceso.entrar(str(datos.get("clave", "")), self._ip(), str(datos.get("correo", "")))
            if error:
                return self._error(429 if "intentos" in error else 401, error)
            return self._responder(200, {"ok": True}, cookie=acceso.nueva_sesion())
        if partes == ["api", "salir"]:
            return self._responder(200, {"ok": True}, cookie="")
        if not self._autorizado():
            return self._error(401, "Inicia sesión")

        if partes == ["api", "envio"]:
            with correos.CANDADO:
                e = envio.leer_estado()
                e["activo"] = bool(datos.get("activo"))
                if e["activo"]:
                    e["error"] = ""
                envio.guardar_estado(e)
            return self._responder(200, estado_general())

        if len(partes) == 3 and partes[:2] == ["api", "conversaciones"]:
            # Tu respuesta escrita en el panel: sale con tu clic, desde el mismo número.
            error, b = whatsapp.enviar_conversacion(partes[2], str(datos.get("paso") or "libre"), str(datos.get("texto", "")))
            if b is None:
                return self._error(400, error)
            return self._responder(200, whatsapp.conversacion(partes[2]) | {"aviso": error})

        if partes == ["api", "audio"]:
            import base64
            try:
                bruto = base64.b64decode(str(datos.get("base64", "")), validate=True)
            except ValueError:
                return self._error(400, "El archivo llegó mal: vuelve a subirlo")
            error = whatsapp.guardar_audio(bruto)
            return self._error(400, error) if error else self._responder(200, whatsapp.audio_info())
        if partes == ["api", "audio", "prueba"]:
            error = whatsapp.enviar_audio_prueba()
            return self._error(400, error) if error else self._responder(200, {"ok": True})
        if len(partes) == 4 and partes[:2] == ["api", "conversaciones"] and partes[3] == "bot":
            error = whatsapp.bot_chat(partes[2], bool(datos.get("apagado")))
            if error:
                return self._error(404, error)
            try:
                return self._responder(200, whatsapp.conversacion(partes[2]))
            except (FileNotFoundError, KeyError):
                return self._responder(200, {"ok": True})
        if len(partes) == 4 and partes[:2] == ["api", "conversaciones"] and partes[3] == "etiquetas":
            error = whatsapp.etiquetar(partes[2], datos.get("etiquetas"))
            if error:
                return self._error(404, error)
            with correos.CANDADO:
                return self._responder(200, {"etiquetas": whatsapp.limpiar_etiquetas(wp.leer(partes[2]).get("etiquetas"))})
        if len(partes) == 4 and partes[:2] == ["api", "conversaciones"] and partes[3] == "sugerir":
            # Claude redacta la respuesta; no se envía: queda en la caja para que la revises.
            try:
                conv = whatsapp.conversacion(partes[2])
                with correos.CANDADO:
                    b = wp.leer(partes[2])
                return self._responder(200, {"texto": crm.sugerir_respuesta(b, conv.get("mensajes") or [])})
            except (FileNotFoundError, KeyError):
                return self._error(404, "No hay chat con ese prospecto")
            except Exception as e:
                return self._error(500, str(e))
        if len(partes) == 4 and partes[:2] == ["api", "conversaciones"] and partes[3] == "audio":
            error, b = whatsapp.enviar_audio_conversacion(partes[2])
            if b is None:
                return self._error(400, error)
            return self._responder(200, whatsapp.conversacion(partes[2]) | {"aviso": error})

        if partes == ["api", "importar"]:
            from . import sincronizar
            return self._responder(200, sincronizar.importar(datos))

        if partes == ["api", "whatsapp"]:
            with correos.CANDADO:
                error = whatsapp.accion_canal(datos)
            if error:
                return self._error(400, error)
            return self._responder(200, whatsapp.estado_panel())

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
            if accion == "guion":
                return self._guion(dominio, datos.get("tipo", ""), datos.get("nota", ""))
            if accion == "crm":
                with correos.CANDADO:
                    b = wp.leer_cualquiera(dominio)
                    error = crm.accion(b, datos)
                    if error:
                        return self._error(400, error)
                    wp.guardar_cualquiera(b)
                    return self._responder(200, crm.vista(b, completa=True))
            if accion == "loom":
                # Pegaste el enlace: sale el Loom y quedan los seguimientos que aprobaste.
                error, b = whatsapp.enviar_loom(dominio, str(datos.get("texto", "")), datos.get("seguimientos") or [])
                if b is None:
                    return self._error(400, error)
                return self._responder(200, crm.vista(b, completa=True) | {"aviso": error})
            if accion == "wa_enviar":
                # Un mensaje de la conversación: sale al tiro, con tu clic.
                error, b = whatsapp.enviar_conversacion(dominio, str(datos.get("paso", "")), str(datos.get("texto", "")))
                if b is None:
                    return self._error(400, error)
                return self._responder(200, crm.vista(b, completa=True) | {"aviso": error})
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
        envio.asignar_demo(b, correos.listar())
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
        crm.al_clasificar(b, tipo)
        b["estado"] = RESPUESTAS[tipo][0]  # el CRM no le cambia lo que elegiste aquí
        return ""

    def _guion(self, dominio: str, tipo: str, nota: str):
        """Claude escribe el guion del próximo paso. Tarda: no bloquea el resto del panel."""
        if tipo not in crm.TIPOS:
            return self._error(400, "Elige qué quieres preparar")
        with correos.CANDADO:
            b = wp.leer_cualquiera(dominio)
        try:
            texto = crm.guion(b, tipo, nota)
        except Exception as e:
            return self._error(500, str(e))
        with correos.CANDADO:
            b = wp.leer_cualquiera(dominio)
            crm.guardar_guion(b, tipo, texto)
            wp.guardar_cualquiera(b)
        return self._responder(200, crm.vista(b, completa=True))

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


def _parar(*_):
    """Docker y Coolify detienen con SIGTERM: se cierra igual que con Ctrl+C."""
    raise KeyboardInterrupt


def abrir(puerto: int = 8765, navegador: bool = True, host: str = "127.0.0.1") -> int:
    config.cargar()
    publico = host not in ("127.0.0.1", "localhost")
    if publico:
        # Fuera de tu computador, sin contraseña cualquiera vería tus prospectos y enviaría por ti.
        if not acceso.activo():
            raise SystemExit("Para abrir el panel fuera de 127.0.0.1 define PANEL_CLAVE "
                             "(una contraseña larga) en el entorno o en el .env.")
        servidor, elegido = Servidor((host, puerto), Manejador), puerto
        url = f"http://{host}:{elegido} (detrás de tu dominio)"
        navegador = False
        signal.signal(signal.SIGTERM, _parar)
    else:
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
    if whatsapp.leer_estado().get("acepto_riesgo"):
        wa_puente.levantar_vinculados(saltar=whatsapp.apagados_a_mano())
    whatsapp.EnvioWhatsApp().start()
    wa_filtro.Verificador(whatsapp.por_verificar).start()  # solo trabaja con WA_AUTO_APROBAR
    from . import agente
    agente.Agente().start()  # solo contesta con WA_AUTO_RESPONDER
    print(f"\n  Panel abierto en {url}")
    print("  Los envíos solo corren mientras esta ventana siga abierta. Ctrl+C para cerrar.\n")
    if navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        wa_puente.detener_todos()
        print("\n  Panel cerrado. Nada más sale hasta que lo vuelvas a abrir.")
    return 0
