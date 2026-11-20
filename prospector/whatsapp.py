"""
WhatsApp: el canal de prospección propio (ver wa_prospeccion.py y plantillas/whatsapp.md).

El mensaje 1 de cada prospecto lo apruebas tú en el panel, uno por uno. Después sale
solo, en las mejores horas (WA_VENTANAS), con una pausa al azar entre mensaje y
mensaje, rotando entre tus números y sin pasar del tope diario de cada uno. Un mensaje
que no aprobaste no sale nunca.

Va por una API NO oficial (wa_puente.py). Meta banea rápido los números que escriben
en frío, así que:

    - un solo mensaje de conexión por negocio: si no responde, no se insiste
    - solo a números que el negocio publica como WhatsApp, nunca a un teléfono suelto
    - números nuevos parten con pocos mensajes al día y suben por semanas
      (WA_CALENTAMIENTO=8,15,20)
    - nada de respuestas automáticas ni reintentos solos

Cuando responde, la conversación sigue en el CRM: los mensajes de las fases 2 a 6 se
mandan con un clic tuyo cada uno (enviar_conversacion), o desde el celular.
"""

import hashlib
import json
import random
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta

from . import base as bd
from . import config, correos, nicho, wa_filtro, wa_puente
from . import wa_prospeccion as wp
from .base import bloqueado
from .cazador import telefono as tel
from .cazador.rastrear import ENLACE_WA, Robots
from .puente import RAIZ

ESTADO = RAIZ / "datos" / "whatsapp.json"
REVISAR_CADA = timedelta(minutes=10)
MIRAR_DURANTE = timedelta(days=14)
# Un saludo automático de WhatsApp Business llega en segundos: eso no es una respuesta.
SEGUNDOS_AUTOMATICA = 90
SEGUNDOS_INSTANTANEA = 8
LARGO_PLANTILLA = 60
# Lo que escribe un bot o un saludo automático de WhatsApp Business. Solo se descarta ESE
# mensaje: si después escribe una persona, se le contesta. "bot" suelto no basta: una persona
# puede preguntar "¿eres un bot?" (el paso "bot" del método).
AUTOMATICA = re.compile(r"mensaje autom[aá]tico|respuesta autom[aá]tica|"
                        r"(te|le|les) (responderemos|contestaremos|atenderemos|contactaremos) (a la brevedad|en breve|lo antes posible|pronto)|"
                        r"fuera de(l)? horario|horario de atenci[oó]n|"
                        r"asistente (virtual|digital|autom[aá]tic[oa]|inteligente|de ia)|chat ?bot|"
                        r"soy (un |una |el |la |tu |su )?(bot|robot)\b|"
                        r"gracias por (comunicarte|comunicarse|contactar|contactarte|contactarse|contactarnos|escribirnos|escribir a|tu mensaje|su mensaje)|"
                        r"(tu|su) nombre y (rut|correo|comuna)|"
                        r"(te|se) (has|ha) comunicado con|bienvenid[oa]s? a |"
                        r"(elige|selecciona|escoge|escribe|responde con|marca|digita) (una |el |la )?(opci[oó]n|n[uú]mero)|"
                        r"un(a)? (ejecutiv[oa]|asesor[a]?|agente) (te|le|les) (atender[aá]|contactar[aá]|responder[aá])", re.I)
DIAS = {"lu": 0, "ma": 1, "mi": 2, "ju": 3, "vi": 4, "sa": 5, "do": 6}
NOMBRE_DIA = {v: k for k, v in DIAS.items()}
# Martes 10, miércoles 17, jueves 10 o 17 y sábado en la mañana.
VENTANAS = "ma10-12,mi17-19,ju10-12,ju17-19,sa10-12"


def numeros_en(html: str, pais) -> list[str]:
    """Los números de sus botones de WhatsApp, el más usado primero."""
    hallados = Counter(tel.desde_enlace_wa(m.group(1), pais) for m in ENLACE_WA.finditer(html or ""))
    hallados.pop("", None)
    return [n for n, _ in hallados.most_common(3)]


def limpiar(numero: str) -> str:
    """El número como +569..., o "" si no parece uno."""
    bruto = (numero or "").strip()
    if not bruto:
        return ""
    return tel.desde_enlace_wa(bruto, nicho.pais())


# --- estado del canal (datos/whatsapp.json) ---------------------------------------

def leer_estado() -> dict:
    e = {"activo": False, "acepto_riesgo": False, "numeros": {}, "error": ""}
    if ESTADO.exists():
        try:
            e.update(json.loads(ESTADO.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return e


def guardar_estado(e: dict) -> None:
    ESTADO.parent.mkdir(exist_ok=True)
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ESTADO)


def _num(e: dict, n: int) -> dict:
    return e.setdefault("numeros", {}).setdefault(str(n), {})


def escalones() -> list[int]:
    """WA_CALENTAMIENTO=8,15,20: tope diario de la semana 1, la 2 y de la 3 en adelante."""
    try:
        valores = [int(x) for x in config.texto("WA_CALENTAMIENTO", "8,15,20").split(",") if x.strip()]
    except ValueError:
        valores = []
    return [v for v in valores if v > 0] or [8, 15, 20]


def semana(e: dict, n: int, hoy) -> int:
    """En qué semana de uso va el número (1 = la primera)."""
    primero = _num(e, n).get("primer_envio")
    if not primero:
        return 1
    return (hoy - datetime.fromisoformat(primero).date()).days // 7 + 1


def _rampa(n: int) -> tuple[int, int, int] | None:
    """WA_RAMPA_2=5:3:25 → parte en 5 al día, sube 3 por cada día en que envió, hasta 25."""
    m = re.fullmatch(r"(\d+):(\d+):(\d+)", config.texto(f"WA_RAMPA_{n}").replace(" ", ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m and int(m.group(1)) > 0 else None


def tope(e: dict, n: int, hoy) -> int:
    """
    Cuántos saludos puede mandar hoy ese número. Por número: WA_TOPE_n (fijo, para uno ya
    caliente) o WA_RAMPA_n (sube de a poco). Si no, el calentamiento por semanas.
    """
    fijo = config.texto(f"WA_TOPE_{n}")
    if fijo.isdigit():
        return int(fijo)
    rampa = _rampa(n)
    if rampa:
        inicio, paso, maximo = rampa
        dias = sum(1 for d in _num(e, n).get("dias_envio", []) if d < hoy.isoformat())
        return min(maximo, inicio + paso * dias)
    esc = escalones()
    return esc[min(semana(e, n, hoy), len(esc)) - 1]


def regla_tope(e: dict, n: int, hoy) -> str:
    if config.texto(f"WA_TOPE_{n}").isdigit():
        return "tope fijo"
    rampa = _rampa(n)
    if rampa:
        return f"parte en {rampa[0]} y sube {rampa[1]} por día de envío, hasta {rampa[2]}"
    return f"semana {semana(e, n, hoy)} de calentamiento"


def auto_preparar_activo() -> bool:
    return config.texto("WA_AUTO_PREPARAR").lower() in ("1", "si", "sí", "true")


def auto_aprobar_activo() -> bool:
    return config.texto("WA_AUTO_APROBAR").lower() in ("1", "si", "sí", "true")


def por_verificar() -> list[str]:
    """Los negocios cuya web conviene leer: los que están por aprobar y los que siguen en la lista."""
    claves = [b["dominio"] for b in wp.listar() if b.get("estado") == "por revisar"]
    return claves + [f["clave"] for f in wp.automaticos() if f["clave"] not in claves]


def _aprobar_solo(b: dict) -> bool:
    if wp.accion(b, {"accion": "aprobar"}):
        return False
    b["aprobado_por"] = "automático"
    b.pop("verificacion", None)
    wp.guardar(b)
    return True


def auto_aprobar(ahora: datetime, e: dict) -> int:
    """
    WA_AUTO_APROBAR=si: los saludos salen sin tu clic, pero SOLO a negocios
    verificadas (wa_filtro: reglas fijas + Claude leyó su web y lo confirmó), y solo los
    que caben en el tope de hoy. Lo que no pasa el filtro queda en "Por aprobar" con el
    motivo: no sale solo. Devuelve cuántos aprobó.
    """
    with correos.CANDADO:
        base, prospectos = bd.cargar(), wp.listar()
        cupo = (sum(tope(e, n, ahora.date()) for n in wa_puente.numeros() if prospecta(e, n))
                - enviados_hoy(prospectos, hoy=ahora.date())
                - sum(1 for b in prospectos if b.get("estado") == "aprobado"))
        hechos = 0
        # Primero, los que ya estaban por aprobar y nadie tocó.
        for b in prospectos:
            if b.get("estado") != "por revisar" or not wp.sin_tocar(b):
                continue
            apto, motivo = wa_filtro.veredicto(base.get(b["dominio"]) or {})
            if apto and cupo > 0 and _aprobar_solo(b):
                cupo, hechos = cupo - 1, hechos + 1
            elif not apto and motivo and b.get("verificacion") != motivo:
                b["verificacion"] = motivo  # se ve en su tarjeta: por qué no salió solo
                wp.guardar(b)
        # Después, de la lista: solo los ya verificados, del mejor al peor.
        for f in wp.automaticos(base):
            if cupo <= 0:
                break
            if not wa_filtro.veredicto(base.get(f["clave"]) or {})[0] or not wp.preparar([f["clave"]])[0]:
                continue
            if _aprobar_solo(wp.leer(f["clave"])):
                cupo, hechos = cupo - 1, hechos + 1
        return hechos


def reserva(e: dict, prospectos: list[dict], ahora: datetime) -> dict:
    """
    Cuánto queda para el envío automático: negocios ya verificados, las que falta
    revisar y para cuántos días de envío alcanzan las verificadas (con los topes de
    cada número, que van subiendo).
    """
    base = bd.cargar()
    verificadas = pendientes = 0
    for f in wp.automaticos(base):
        lead = base.get(f["clave"]) or {}
        if wa_filtro.veredicto(lead)[0]:
            verificadas += 1
        elif wa_filtro.pendiente(lead):
            pendientes += 1
    en_cola = sum(1 for b in prospectos if b.get("estado") == "aprobado")
    quedan, dias, copia = verificadas + en_cola, 0, json.loads(json.dumps(e))
    numeros = [n for n in wa_puente.numeros() if prospecta(e, n)]
    dia = ahora.date()
    while quedan > 0 and dias < 60 and numeros:
        cupo = sum(tope(copia, n, dia) for n in numeros)
        if cupo <= 0:
            break
        quedan -= cupo
        dias += 1
        for n in numeros:  # ese día cuenta como día de envío para la rampa
            _num(copia, n).setdefault("dias_envio", []).append(dia.isoformat())
        dia += timedelta(days=1)
    return {"verificadas": verificadas, "por_verificar": pendientes, "en_cola": en_cola, "dias": dias}


def auto_preparar(ahora: datetime, e: dict) -> int:
    """
    Deja listos para aprobar los saludos que caben hoy (WA_AUTO_PREPARAR=si): los toma de
    wp.automaticos(), del mejor al peor. No aprueba ni envía nada. Con WA_AUTO_APROBAR
    manda auto_aprobar(), que además los aprueba si son negocios verificados de tu rubro.
    """
    if auto_aprobar_activo():
        return auto_aprobar(ahora, e)
    if not auto_preparar_activo():
        return 0
    with correos.CANDADO:
        prospectos = wp.listar()
        capacidad = (sum(tope(e, n, ahora.date()) for n in wa_puente.numeros() if prospecta(e, n))
                     - enviados_hoy(prospectos, hoy=ahora.date()))
        esperando = sum(1 for b in prospectos if b.get("estado") in ("por revisar", "aprobado"))
        faltan = capacidad - esperando
        if faltan <= 0:
            return 0
        claves = [f["clave"] for f in wp.automaticos()[:faltan]]
        return wp.preparar(claves)[0] if claves else 0


def enviados_hoy(prospectos: list[dict], n: int | None = None, hoy=None) -> int:
    """Los mensajes 1 que salieron hoy por el puente (desde el número n, o desde todos)."""
    hoy = hoy or datetime.now().date()
    total = 0
    for b in prospectos:
        w = b.get("whatsapp") or {}
        if w.get("estado") not in ("enviado", "incierto") or not isinstance(w.get("desde"), int):
            continue
        if n is not None and w["desde"] != n:
            continue
        if w.get("enviado") and datetime.fromisoformat(w["enviado"]).date() == hoy:
            total += 1
    return total


def ventanas() -> list[tuple[int, int, int]]:
    """WA_VENTANAS=ma10-12,ju17-19 → [(día, desde, hasta)]: cuándo sale el mensaje 1."""
    salida = []
    for trozo in (config.texto("WA_VENTANAS", VENTANAS) or VENTANAS).lower().replace(" ", "").split(","):
        m = re.fullmatch(r"([a-z]{2})(\d{1,2})-(\d{1,2})", trozo)
        if m and m.group(1) in DIAS and 0 <= int(m.group(2)) < int(m.group(3)) <= 24:
            salida.append((DIAS[m.group(1)], int(m.group(2)), int(m.group(3))))
    return salida or ventanas_por_defecto()


def ventanas_por_defecto() -> list[tuple[int, int, int]]:
    return [(DIAS[t[:2]], int(t[2:].split("-")[0]), int(t.split("-")[1])) for t in VENTANAS.split(",")]


def en_ventana(ahora: datetime) -> bool:
    return any(ahora.weekday() == d and a <= ahora.hour < b for d, a, b in ventanas())


def texto_ventanas() -> str:
    return " · ".join(f"{NOMBRE_DIA[d]} {a}-{b} h" for d, a, b in ventanas())


def pausa_total() -> tuple[int, int]:
    """WA_PAUSA_TOTAL=14-16: minutos entre un saludo y el siguiente, contando todos los
    números juntos (unos 4 por hora en total). WA_PAUSA es aparte, por número."""
    return config.rango("WA_PAUSA_TOTAL", (14, 16))


def sin_respuesta_dias() -> int:
    return max(1, config.numero("WA_SIN_RESPUESTA", 5))


# --- el envío del mensaje 1 -------------------------------------------------------------

def toca(b: dict) -> bool:
    w = b.get("whatsapp") or {}
    return b.get("estado") == "aprobado" and w.get("estado") == "en cola" and not b.get("bot_apagado")


def id_pedido(b: dict) -> str:
    """El mismo en cada intento: si el puente ya lo mandó, no lo repite."""
    w = b.get("whatsapp") or {}
    base = f"{b.get('dominio', '')}|conexion|{w.get('intentos', 0)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


# El método: a CUALQUIER respuesta al saludo
# se le manda el pitch, sea una persona, un saludo automático, un menú o un "fuera de
# horario". La única excepción es que el mensaje diga que es un bot o un asistente virtual:
# ese prospecto se descarta. "¿Eres un bot?" de una persona no cuenta (es el paso "bot").
BOT_DECLARADO = re.compile(r"(?<!eres un )(?<!eres una )(?<!es un )(?<!es una )"
                           r"asist[ae]nte (virtual|digital|autom[aá]tic[oa]|inteligente|de ia)|"
                           r"\bno soy (un |una )?(humano|humana|persona)\b|"
                           r"(?<!eres un )(?<!es un )chat ?bot|"
                           r"\b(soy|hablas con|est[aá]s hablando con|te atiende|te habla|te responde) "
                           r"(un |una |el |la |tu |su |nuestr[oa] )?(bot|robot|ia|inteligencia artificial)\b", re.I)


def bot_declarado(texto: str) -> bool:
    return bool(BOT_DECLARADO.search(texto or ""))


def contesto(m: dict) -> bool:
    """¿Cuenta como respuesta al saludo? Todo, menos un bot que dice que es un bot."""
    return not bot_declarado(m.get("text") or "")


def respuesta_real(m: dict, enviado: datetime) -> bool:
    """
    ¿Parece una persona? (para el saludo ya no importa: ver contesto). Se usa para no seguir
    contestándole a un bot a mitad de conversación y en la respuesta al Loom. Lo que llega
    en los primeros SEGUNDOS_AUTOMATICA solo es automático si parece plantilla (largo o en
    varias líneas): una persona que contesta al tiro escribe corto ("Si, dime.").
    """
    texto = (m.get("text") or "").strip()
    if AUTOMATICA.search(texto):
        return False
    pasados = float(m.get("timestamp") or 0) - enviado.timestamp()
    if pasados < SEGUNDOS_INSTANTANEA:
        return False  # nadie lee y contesta tan rápido
    if pasados < SEGUNDOS_AUTOMATICA and (len(texto) > LARGO_PLANTILLA or "\n" in texto):
        return False
    return True


def prospecta(e: dict, n: int) -> bool:
    """¿Salen mensajes en frío desde este número? (el de tu negocio, mejor que no)"""
    return _num(e, n).get("prospectar", True) is not False


def elegir_numero(prospectos: list[dict], e: dict, conectados: set[int], ahora: datetime) -> int | None:
    """El número conectado con menos envíos hoy, que no esté en pausa ni en su tope."""
    libres = []
    for n in sorted(conectados):
        if not prospecta(e, n):
            continue
        proximo = _num(e, n).get("proximo")
        if proximo and ahora < datetime.fromisoformat(proximo):
            continue
        hoy = enviados_hoy(prospectos, n, ahora.date())
        if hoy < tope(e, n, ahora.date()):
            libres.append((hoy, random.random(), n))
    return min(libres)[2] if libres else None


def conectados() -> set[int]:
    return {n for n in wa_puente.numeros() if wa_puente.conexion(n) == "conectado"}


def mirar_respuestas(prospectos: list[dict], ahora: datetime, activos: set[int]) -> None:
    """Quién contestó pasa al CRM; a quien no contesta en unos días no se le insiste."""
    for b in prospectos:
        w = b.get("whatsapp") or {}
        if w.get("estado") != "enviado" or b.get("estado") not in ("enviado", "sin respuesta"):
            continue
        enviado = datetime.fromisoformat(w["enviado"])
        if ahora - enviado > MIRAR_DURANTE:
            continue
        n = w.get("desde")
        recibidos = wa_puente.recibidos(n, w["numero"], enviado) if n in activos else []
        # Cualquier respuesta cuenta, salvo que en ese chat un bot diga que es un bot: se descarta.
        reales = recibidos if all(contesto(m) for m in recibidos) else []
        if reales:
            ultimo = reales[-1]
            w["respuesta"] = (ultimo.get("text") or "(un audio, foto o archivo)").strip()[:500]
            b.update(estado="respondió", respuesta_detectada=ahora.isoformat(timespec="seconds"),
                     respuesta_canal="whatsapp")
            from . import crm  # aquí: crm importa este módulo de forma indirecta
            crm.asignar_formato(b)  # le toca el pitch en audio o en texto
            wp.guardar(b)
            continue
        if recibidos:
            texto = (recibidos[-1].get("text") or "(un audio, foto o archivo)").strip()[:500]
            if w.get("recibido") != texto:
                # Parece automático: se enseña en el panel por si acaso, sin moverlo.
                w["recibido"] = texto
                wp.guardar(b)
        if b["estado"] == "enviado" and ahora - enviado > timedelta(days=sin_respuesta_dias()):
            b["estado"] = "sin respuesta"
            wp.guardar(b)


REANIMAR_CADA = timedelta(minutes=2)


def apagados_a_mano(e: dict | None = None) -> set[int]:
    e = e or leer_estado()
    return {n for n in wa_puente.numeros() if _num(e, n).get("apagado_a_mano")}


def reanimar() -> list[int]:
    """
    Un número vinculado que se apagó solo (un reinicio del servidor, un despliegue que
    se cruzó con el anterior) se vuelve a encender. Si lo apagaste tú, se respeta.
    """
    e = leer_estado()
    if not e.get("acepto_riesgo") or not wa_puente.instalado():
        return []
    encendidos = []
    for n in wa_puente.numeros():
        if n in apagados_a_mano(e) or not wa_puente.vinculado(n):
            continue
        # "desconectado" también: tras un despliegue WhatsApp corta con el error 440 (otra
        # sesión ocupó su lugar) y el puente no se recupera solo. La sesión cerrada pide el QR.
        if wa_puente.conexion(n) in ("apagado", "desconectado") and not wa_puente.iniciar(n):
            encendidos.append(n)
    return encendidos


class EnvioWhatsApp(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.ultima_revision = datetime.min
        self.ultima_reanimacion = datetime.now()

    def run(self) -> None:
        self.recuperar()
        try:
            recuperar_lids()  # los chats que quedaron sin ver antes de recordar los LID
        except Exception:  # noqa: BLE001
            pass
        while True:
            try:
                if datetime.now() - self.ultima_reanimacion >= REANIMAR_CADA:
                    self.ultima_reanimacion = datetime.now()
                    reanimar()
                self.ciclo()
            except Exception as ex:  # el hilo no puede morir por un error raro
                e = leer_estado()
                e["error"] = f"{type(ex).__name__}: {ex}"
                guardar_estado(e)
            time.sleep(30)

    @staticmethod
    def recuperar() -> None:
        """Si el panel se cerró a mitad de un envío, ese mensaje queda en duda: no se repite solo."""
        with correos.CANDADO:
            for b in wp.listar():
                w = b.get("whatsapp") or {}
                if w.get("estado") == "enviando":
                    w.update(estado="incierto", error="El panel se cerró mientras salía: mira en el celular si llegó")
                    wp.guardar(b)

    def ciclo(self, ahora: datetime | None = None) -> None:
        ahora = ahora or datetime.now()
        e = leer_estado()
        if not e.get("acepto_riesgo"):
            return
        activos = conectados()
        revisar = ahora - self.ultima_revision >= REVISAR_CADA
        seguimientos_programados(ahora, e, activos, revisar)
        if revisar:
            auto_preparar(ahora, e)
        with correos.CANDADO:
            prospectos = wp.listar()
            if revisar:
                self.ultima_revision = ahora
                mirar_respuestas(prospectos, ahora, activos)
                prospectos = wp.listar()
            if not e.get("activo") or not en_ventana(ahora):
                return
            if e.get("proximo") and ahora < datetime.fromisoformat(e["proximo"]):
                return  # la pausa entre saludos, contando todos los números juntos
            elegido = None
            for b in sorted((b for b in prospectos if toca(b)), key=lambda b: b.get("aprobado_en", "")):
                if bloqueado({"whatsapp": b["whatsapp"].get("numero", ""), "web": b.get("web", "")}):
                    b["estado"] = "por revisar"
                    b["whatsapp"].update(estado="", error="Está en la lista negra")
                    wp.guardar(b)
                    continue
                elegido = b
                break
            if not elegido:
                return
            n = elegir_numero(prospectos, e, activos, ahora)
            if n is None:
                return
            b, w = elegido, elegido["whatsapp"]
            # Si ese número ya tiene un chat contigo (un cliente, un proveedor, alguien de tu
            # negocio), un saludo en frío no corresponde: se queda para que decidas tú.
            previos = wa_puente.conversacion(n, w["numero"], limite=3)
            if previos is None:
                return  # el puente no contestó: se intenta en la próxima vuelta
            if previos:
                b["estado"] = "por revisar"
                w.update(estado="", error="")
                b["verificacion"] = f"Ya tienes una conversación con este número en tu número {n}: no se le escribió en frío"
                wp.guardar(b)
                return
            w["intentos"] = w.get("intentos", 0) + 1
            w.update(estado="enviando", desde=n, enviado=ahora.isoformat(timespec="seconds"), error="")
            wp.guardar(b)
            clave, numero, texto, pedido = b["dominio"], w["numero"], w["mensaje"], id_pedido(b)

        # Fuera del candado: el envío puede tardar y el panel no se tiene que congelar.
        resultado, error = wa_puente.enviar(n, numero, texto, pedido)

        with correos.CANDADO:
            b = wp.leer(clave)
            w = b["whatsapp"]
            if resultado == "ok":
                w.update(estado="enviado", error="")
                b["estado"] = "enviado"
            elif resultado == "incierto":
                w.update(estado="incierto", error=error)
            elif "desconect" in error:
                # El número se cayó: el mensaje vuelve a la cola y sale por otro o más tarde.
                w.update(estado="en cola", error=error, desde="", enviado="")
            else:
                w.update(estado="error", error=error)
            wp.guardar(b)

        e = leer_estado()  # otra vez: mientras salía, pudiste pausar desde el panel
        num = _num(e, n)
        if resultado != "error":
            num.setdefault("primer_envio", ahora.date().isoformat())
            dias = num.setdefault("dias_envio", [])  # para la rampa: en cuántos días ha enviado
            if ahora.date().isoformat() not in dias:
                dias.append(ahora.date().isoformat())
        pmin, pmax = config.rango("WA_PAUSA", (4, 12))
        num["proximo"] = (ahora + timedelta(minutes=random.uniform(pmin, pmax))).isoformat(timespec="seconds")
        tmin, tmax = pausa_total()
        e["proximo"] = (ahora + timedelta(minutes=random.uniform(tmin, tmax))).isoformat(timespec="seconds")
        e["error"] = "" if resultado == "ok" else f"Número {n}: {error}"
        guardar_estado(e)


# --- la conversación, después de que responde -------------------------------------------

dormir = time.sleep  # aparte, para que las pruebas no esperen de verdad


def espera_respuesta() -> int:
    """Segundos que se deja pasar desde que el cliente escribe hasta contestarle."""
    return max(0, min(120, config.numero("WA_ESPERA_RESPUESTA", 30)))


def _entrantes(n: int, numero: str) -> list[dict]:
    return [m for m in (wa_puente.conversacion(n, numero, limite=8) or []) if not m["yo"]]


def _esperar_turno(n: int, numero: str) -> str:
    """
    Contestar al segundo no es de persona, y la gente escribe en varios mensajes ("hola",
    y después "sí, dime"). Se espera hasta que pasen WA_ESPERA_RESPUESTA segundos desde
    su último mensaje. Si mientras tanto escribe algo más, no se envía: devuelve el aviso
    para que lo leas antes de contestar. "" = se puede enviar.
    """
    espera = espera_respuesta()
    antes = _entrantes(n, numero) if espera else []
    if not antes:
        return ""
    falta = espera - (time.time() - max(m["hora"] for m in antes))
    if falta <= 0:
        return ""
    dormir(min(espera, falta))
    vistos = {m["id"] for m in antes}
    nuevos = [m for m in _entrantes(n, numero) if m["id"] not in vistos]
    if nuevos:
        dijo = (nuevos[-1].get("texto") or "un audio o un archivo").strip()[:120]
        return f"No lo envié: mientras esperaba, escribió algo más («{dijo}»). Léelo y vuelve a enviar."
    return ""


def enviar_conversacion(clave: str, paso: str, texto: str) -> tuple[str, dict | None]:
    """
    Un mensaje de las fases 2 a 6, cuando tú aprietas Enviar. Sale al tiro, desde el
    mismo número con que le escribiste. Devuelve (error, prospecto).
    """
    from . import crm  # aquí: crm importa este módulo de forma indirecta

    texto = (texto or "").strip()
    if not texto:
        return "Escribe el mensaje", None
    if wp.pendientes(texto):
        return "Rellena antes: " + ", ".join("{" + x + "}" for x in wp.pendientes(texto)), None
    if not leer_estado().get("acepto_riesgo"):
        return "Primero acepta el aviso de riesgo en la pestaña WhatsApp", None
    with correos.CANDADO:
        b = wp.leer(clave)
        error = wp.puede_conversar(b)
        if error:
            return error, None
        w = b["whatsapp"]
        n, numero = w["desde"], w["numero"]
        enviados = (b.get("crm") or {}).get("mensajes", 0)
        pedido = hashlib.sha1(f"{clave}|conversacion|{enviados}|{texto}".encode("utf-8")).hexdigest()
    if wa_puente.conexion(n) != "conectado":
        return f"El número {n} no está conectado: conéctalo en la pestaña WhatsApp o mándalo desde el celular", None

    aviso = _esperar_turno(n, numero)  # fuera del candado: el panel no se congela mientras espera
    if aviso:
        return aviso, None
    resultado, error = wa_puente.enviar(n, numero, texto, pedido)

    with correos.CANDADO:
        b = wp.leer(clave)
        if resultado == "error":
            return f"No salió: {error}", None
        crm.registrar_envio(b, paso, texto, dudoso=resultado == "incierto")
        wp.guardar(b)
    if resultado == "incierto":
        return f"No sé si salió ({error}). Míralo en el celular antes de reenviarlo.", b
    return "", b


# --- el Loom y sus seguimientos ----------------------------------------------------------

ENTRE_SEGUIMIENTOS = timedelta(hours=20)


def estado_bot(b: dict) -> dict:
    """Qué hay andando solo en ese chat."""
    from . import crm

    pend = crm.pendientes_programados(b)
    return {"apagado": bool(b.get("bot_apagado")), "pendientes": len(pend),
            "proximo": pend[0]["cuando"] if pend else "", "en_cola": toca({**b, "bot_apagado": False})}


def bot_chat(clave: str, apagado: bool) -> str:
    """El interruptor de un chat: apagado, a ese prospecto no le sale nada solo."""
    with correos.CANDADO:
        if not wp.existe(clave):
            return "No existe ese prospecto"
        b = wp.leer(clave)
        if apagado:
            b["bot_apagado"] = True
        else:
            b.pop("bot_apagado", None)
        wp.guardar(b)
    return ""


MAX_ETIQUETAS = 8
LARGO_ETIQUETA = 24


def limpiar_etiquetas(etiquetas) -> list[str]:
    """Tus etiquetas de un chat: sin vacías ni repetidas (da igual la mayúscula), cortas y pocas."""
    if not isinstance(etiquetas, list):
        return []
    limpias, vistas = [], set()
    for e in etiquetas:
        if not isinstance(e, str):
            continue
        e = " ".join(e.split())[:LARGO_ETIQUETA].strip()
        if e and e.lower() not in vistas:
            vistas.add(e.lower())
            limpias.append(e)
    return limpias[:MAX_ETIQUETAS]


def etiquetar(clave: str, etiquetas) -> str:
    """Pone las etiquetas de un chat (reemplaza las que tenía). Solo ordenan: no envían nada."""
    with correos.CANDADO:
        if not wp.existe(clave):
            return "No existe ese prospecto"
        b = wp.leer(clave)
        limpias = limpiar_etiquetas(etiquetas)
        if limpias:
            b["etiquetas"] = limpias
        else:
            b.pop("etiquetas", None)
        wp.guardar(b)
    return ""


def hora_humana(ahora: datetime) -> bool:
    """Cuándo puede salir un seguimiento: de lunes a sábado, en horario de oficina."""
    ini, fin = config.rango("WA_HORARIO_SEGUIMIENTOS", (9, 19))
    return ahora.weekday() < 6 and ini <= ahora.hour < fin


def enviar_loom(clave: str, texto: str, seguimientos: list) -> tuple[str, dict | None]:
    """
    Pegaste el enlace: sale el mensaje del Loom y quedan programados los seguimientos
    que aprobaste ahí mismo. Devuelve (error, prospecto).
    """
    from . import crm

    if not re.search(r"https?://\S+", texto or ""):
        return "Pega el enlace del Loom", None
    error, b = enviar_conversacion(clave, "envio_loom", texto)
    if b is None or error:  # si quedó en duda, no se programa nada a ciegas
        return error, b
    with correos.CANDADO:
        b = wp.leer(clave)
        if crm.etapa(b) == "video":
            crm.programar_seguimientos(b, seguimientos)
            wp.guardar(b)
    return "", b


def seguimientos_programados(ahora: datetime, e: dict, activos: set[int], revisar: bool = False) -> int:
    """
    Manda, uno por vuelta, el seguimiento del Loom al que ya le llegó su hora. Solo los
    que aprobaste al mandar el Loom, solo si no ha respondido, con WhatsApp activo y en
    horario. Si respondió, cancela los que faltan y te avisa en el CRM.
    """
    from . import crm

    enviados = 0
    for b in wp.listar():
        pend = crm.pendientes_programados(b)
        if not pend or b.get("bot_apagado"):  # apagado en ese chat: no sale nada solo
            continue
        le_toca = ahora >= datetime.fromisoformat(pend[0]["cuando"])
        if not (le_toca or revisar):
            continue
        clave, w = b["dominio"], b.get("whatsapp") or {}
        n, numero = w.get("desde"), w.get("numero", "")
        if crm.etapa(b) != "video" or bloqueado({"whatsapp": numero, "web": b.get("web", "")}):
            with correos.CANDADO:
                b = wp.leer(clave)
                crm.cancelar_programados(b)
                wp.guardar(b)
            continue
        if n not in activos:
            continue
        desde = datetime.fromisoformat((b.get("crm") or {}).get("loom_enviado") or w.get("enviado") or pend[0]["cuando"])
        reales = [m for m in wa_puente.recibidos(n, numero, desde) if respuesta_real(m, desde)]
        if reales:
            with correos.CANDADO:
                b = wp.leer(clave)
                crm.respondio_al_video(b, (reales[-1].get("text") or "(un audio, foto o archivo)").strip())
                wp.guardar(b)
            continue
        if not le_toca or enviados or not e.get("activo") or not hora_humana(ahora):
            continue
        # Nunca dos seguidos: si se atrasaron (una pausa, el servidor apagado), salen de a
        # uno por día y no todos juntos.
        ultimos = [x.get("enviado") for x in (b.get("crm") or {}).get("programados") or [] if x.get("enviado")]
        if ultimos and ahora - datetime.fromisoformat(max(ultimos)) < ENTRE_SEGUIMIENTOS:
            continue
        p = pend[0]
        pedido = hashlib.sha1(f"{clave}|{p['paso']}|{p['cuando']}".encode("utf-8")).hexdigest()
        resultado, error = wa_puente.enviar(n, numero, p["texto"], pedido)
        with correos.CANDADO:
            b = wp.leer(clave)
            actual = next((x for x in crm.pendientes_programados(b) if x["paso"] == p["paso"]), None)
            if actual is None:
                continue
            if resultado == "ok":
                actual.update(estado="enviado", enviado=ahora.isoformat(timespec="seconds"))
                crm.registrar_envio(b, p["paso"], p["texto"])
            elif resultado == "incierto":
                # No se sabe si salió: no se sigue mandando a ciegas.
                actual.update(estado="incierto", error=error)
                crm.registrar_envio(b, p["paso"], p["texto"], dudoso=True)
                crm.cancelar_programados(b)
            elif "desconect" not in error:
                actual.update(estado="error", error=error)
            wp.guardar(b)
        enviados += 1
    return enviados


# --- el audio del pitch ------------------------------------------------------------------

AUDIOS = RAIZ / "datos" / "audios"
AUDIO_PITCH = AUDIOS / "pitch.ogg"
MAX_AUDIO = 3_000_000  # un audio de 1 minuto en Opus pesa unos 200 KB


def guardar_audio(datos: bytes) -> str:
    """El audio del pitch, grabado una vez (una nota de voz de WhatsApp, .ogg)."""
    if not datos.startswith(b"OggS"):
        return "Tiene que ser una nota de voz de WhatsApp (.ogg). Grábate un audio, descárgalo y súbelo."
    if len(datos) > MAX_AUDIO:
        return "Es muy pesado para una nota de voz: que dure menos de un minuto y medio"
    AUDIOS.mkdir(parents=True, exist_ok=True)
    tmp = AUDIO_PITCH.with_suffix(".tmp")
    tmp.write_bytes(datos)
    tmp.replace(AUDIO_PITCH)
    return ""


def audio_info() -> dict:
    if not AUDIO_PITCH.exists():
        return {"existe": False, "prueba": bool(config.texto("WA_PRUEBA"))}
    st = AUDIO_PITCH.stat()
    return {"existe": True, "bytes": st.st_size, "fecha": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "prueba": bool(config.texto("WA_PRUEBA"))}


def _primero_conectado() -> int | None:
    e = leer_estado()
    libres = [n for n in wa_puente.numeros() if wa_puente.conexion(n) == "conectado"]
    # Para la prueba conviene el número que no prospecta (el tuyo), si está conectado.
    libres.sort(key=lambda n: prospecta(e, n))
    return libres[0] if libres else None


def enviar_audio_prueba() -> str:
    """El audio del pitch a TU número (WA_PRUEBA), para escuchar cómo llega. Nunca a otro."""
    numero = limpiar(config.texto("WA_PRUEBA"))
    if not numero:
        return "Configura tu número de prueba: WA_PRUEBA=+569... en las variables de entorno"
    if not AUDIO_PITCH.exists():
        return "Primero sube el audio del pitch"
    if not leer_estado().get("acepto_riesgo"):
        return "Primero acepta el aviso de riesgo"
    n = _primero_conectado()
    if n is None:
        return "No hay ningún número conectado"
    pedido = hashlib.sha1(f"prueba|{numero}|{AUDIO_PITCH.stat().st_mtime_ns}|{time.time()}".encode()).hexdigest()
    resultado, error = wa_puente.enviar_audio(n, numero, AUDIO_PITCH, pedido)
    if resultado == "error":
        return f"No salió: {error}"
    return "" if resultado == "ok" else f"No sé si salió ({error}). Míralo en el celular."


def enviar_audio_conversacion(clave: str) -> tuple[str, dict | None]:
    """El audio del pitch a un prospecto que respondió, con tu clic, por el mismo número."""
    from . import crm  # aquí: crm importa este módulo de forma indirecta

    if not AUDIO_PITCH.exists():
        return "Primero sube el audio del pitch en la pestaña WhatsApp", None
    if not leer_estado().get("acepto_riesgo"):
        return "Primero acepta el aviso de riesgo en la pestaña WhatsApp", None
    with correos.CANDADO:
        b = wp.leer(clave)
        error = wp.puede_conversar(b)
        if error:
            return error, None
        w = b["whatsapp"]
        n, numero = w["desde"], w["numero"]
        pedido = hashlib.sha1(f"{clave}|audio_pitch|{AUDIO_PITCH.stat().st_mtime_ns}".encode()).hexdigest()
    if wa_puente.conexion(n) != "conectado":
        return f"El número {n} no está conectado: conéctalo en la pestaña WhatsApp", None

    aviso = _esperar_turno(n, numero)
    if aviso:
        return aviso, None
    resultado, error = wa_puente.enviar_audio(n, numero, AUDIO_PITCH, pedido)

    with correos.CANDADO:
        b = wp.leer(clave)
        if resultado == "error":
            return f"No salió: {error}", None
        crm.registrar_envio(b, "pitch", "🎤 Audio del pitch", dudoso=resultado == "incierto", formato="audio")
        wp.guardar(b)
    if resultado == "incierto":
        return f"No sé si salió ({error}). Míralo en el celular antes de reenviarlo.", b
    return "", b


# --- lo que ve el panel -----------------------------------------------------------------

def resumen(prospectos: list[dict], ahora: datetime | None = None) -> dict:
    """Para la barra de arriba: sin preguntarle nada al puente, que es rápido."""
    ahora = ahora or datetime.now()
    e = leer_estado()
    estados = Counter(b.get("estado", "") for b in prospectos)
    wa = Counter((b.get("whatsapp") or {}).get("estado", "") for b in prospectos)
    return {"activo": bool(e.get("activo")), "acepto_riesgo": bool(e.get("acepto_riesgo")),
            "enviados_hoy": enviados_hoy(prospectos, hoy=ahora.date()),
            "tope_hoy": sum(tope(e, n, ahora.date()) for n in wa_puente.numeros() if prospecta(e, n)),
            "por_revisar": estados.get("por revisar", 0), "en_cola": wa.get("en cola", 0),
            "en_duda": wa.get("incierto", 0), "error": e.get("error", ""), "en_ventana": en_ventana(ahora),
            "espera": espera_respuesta()}


def estado_panel(prospectos: list[dict] | None = None, ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now()
    prospectos = wp.listar() if prospectos is None else prospectos
    e = leer_estado()
    filas = []
    for n in wa_puente.numeros():
        datos = wa_puente.estado(n)
        num = _num(e, n)
        datos.update(hoy=enviados_hoy(prospectos, n, ahora.date()), tope=tope(e, n, ahora.date()),
                     semana=semana(e, n, ahora.date()), proximo=num.get("proximo", ""), prospectar=prospecta(e, n),
                     regla=regla_tope(e, n, ahora.date()))
        filas.append(datos)
    grupos: dict[str, list] = {"revisar": [], "cola": [], "dudas": [], "enviados": [], "sin_respuesta": []}
    respondieron = 0
    for b in prospectos:
        estado, w = b.get("estado", ""), b.get("whatsapp") or {}
        if estado == "por revisar":
            grupos["revisar"].append(wp.vista(b))
        elif w.get("estado") in ("incierto", "error"):
            grupos["dudas"].append(wp.vista(b))
        elif toca(b) or w.get("estado") == "enviando":
            grupos["cola"].append(wp.vista(b))
        elif estado == "enviado":
            grupos["enviados"].append(wp.vista(b))
        elif estado == "sin respuesta":
            grupos["sin_respuesta"].append(wp.vista(b))
        elif estado in ("respondió", "interesado", "retomar", "baja"):
            respondieron += 1
    grupos["revisar"].sort(key=lambda v: v["nombre"].lower())
    grupos["cola"].sort(key=lambda v: v["nombre"].lower())
    for g in ("enviados", "sin_respuesta"):
        grupos[g].sort(key=lambda v: v["enviado"], reverse=True)
        grupos[g] = grupos[g][:60]
    candidatos = wp.candidatos()
    return resumen(prospectos, ahora) | grupos | {
        "instalado": wa_puente.instalado(), "node": bool(wa_puente.node()), "numeros": filas,
        "respondieron": respondieron, "candidatos": candidatos[:200], "total_candidatos": len(candidatos),
        "ventanas": texto_ventanas(), "escalones": escalones(), "largo_ideal": wp.LARGO_IDEAL,
        "sin_respuesta_dias": sin_respuesta_dias(), "audio": audio_info(), "auto_preparar": auto_preparar_activo(), "auto_aprobar": auto_aprobar_activo(),
        "auto_responder": config.texto("WA_AUTO_RESPONDER").lower() in ("1", "si", "sí", "true"),
        "reserva": reserva(e, prospectos, ahora) if auto_aprobar_activo() else None,
        "pausa": "-".join(map(str, config.rango("WA_PAUSA", (4, 12)))),
        "pausa_total": "-".join(map(str, pausa_total())), "proximo": e.get("proximo", ""),
    }


def accion_canal(d: dict) -> str:
    """Las acciones de la pestaña WhatsApp."""
    e = leer_estado()
    que = d.get("accion", "")
    if que == "riesgo":
        e["acepto_riesgo"] = bool(d.get("valor"))
        if not e["acepto_riesgo"]:
            e["activo"] = False
        guardar_estado(e)
        return ""
    # Preparar y revisar mensajes no manda nada: se puede antes de conectar.
    if que == "preparar":
        claves = [str(c) for c in (d.get("claves") or []) if isinstance(c, str)][:100]
        if not claves:
            return "Elige al menos un negocio"
        hechos, errores = wp.preparar(claves)
        return "" if hechos else ("; ".join(errores[:3]) or "No se preparó ninguno")
    if que in ("editar", "aprobar", "quitar", "descartar", "salio", "reintentar", "respondio"):
        clave = str(d.get("dominio") or "")
        if not wp.existe(clave):
            return "No existe ese prospecto"
        b = wp.leer(clave)
        error = wp.accion(b, d)
        if not error:
            wp.guardar(b)
        return error
    if not e.get("acepto_riesgo"):
        return "Primero lee y acepta el aviso de riesgo"
    if que in ("activar", "pausar"):
        e["activo"] = que == "activar"
        if e["activo"]:
            e["error"] = ""
        guardar_estado(e)
        return ""
    if not wa_puente.es_numero(d.get("numero")):
        return "Ese número no existe: revisa WA_NUMEROS en el .env"
    n = int(d["numero"])
    if que == "prospectar":
        _num(e, n)["prospectar"] = bool(d.get("valor"))
        guardar_estado(e)
        return ""
    if que == "conectar":
        _num(e, n).pop("apagado_a_mano", None)
        guardar_estado(e)
        return wa_puente.iniciar(n)
    if que == "detener":
        _num(e, n)["apagado_a_mano"] = True  # que el vigilante no lo vuelva a encender
        guardar_estado(e)
        wa_puente.detener(n)
        return ""
    if que == "desvincular":
        _num(e, n).pop("apagado_a_mano", None)
        guardar_estado(e)
        wa_puente.desvincular(n)
        return ""
    return "Acción desconocida"


# --- conversaciones: solo los chats con prospectos ---------------------------------------

CON_CHAT = ("enviado", "incierto")


def _con_chat(b: dict) -> bool:
    w = b.get("whatsapp") or {}
    return w.get("estado") in CON_CHAT and isinstance(w.get("desde"), int) and bool(w.get("numero"))


def _resumen_chat(m: dict) -> str:
    if m.get("texto"):
        return m["texto"]
    return {"audioMessage": "🎤 Audio", "imageMessage": "📷 Foto", "videoMessage": "🎬 Video",
            "documentMessage": "📄 Documento", "stickerMessage": "Sticker"}.get(m.get("tipo"), "(mensaje sin texto)")


def _agente_estado(b: dict) -> dict:
    from . import agente  # aquí: agente importa este módulo
    return agente.estado(b)


COMILLAS = re.compile(r"«([^»]{6,400})»")


def recuperar_lids(prospectos: list[dict] | None = None) -> int:
    """
    Los chats de quienes ya respondieron pero cuyo LID no se conoce (se olvidó en un
    reinicio): se recupera buscando lo que esa persona te escribió. Devuelve cuántos encontró.
    """
    hallados = 0
    for b in prospectos if prospectos is not None else wp.listar():
        w = b.get("whatsapp") or {}
        n, numero = w.get("desde"), w.get("numero", "")
        if not isinstance(n, int) or not numero or wa_puente.lid_de(n, numero):
            continue
        textos = [w.get("respuesta", ""), w.get("recibido", "")]
        for h in (b.get("crm") or {}).get("historial", []):
            if h.get("tipo") in ("respuesta", "nota") and not str(h.get("nota", "")).startswith("Agente"):
                textos += COMILLAS.findall(h.get("nota", ""))
        textos = [x for x in dict.fromkeys(textos) if x and not x.startswith("(")]
        if not textos or not w.get("enviado"):
            continue
        lid = wa_puente.buscar_lid(n, numero, textos, datetime.fromisoformat(w["enviado"]).timestamp())
        if lid and wa_puente.recordar_lid(n, numero, lid):
            hallados += 1
    return hallados


def conversaciones() -> list[dict]:
    """
    Los chats de prospección: solo los prospectos a los que ya les escribiste, y de cada
    uno solo su chat. Las demás conversaciones de tus números no se leen.
    """
    from . import crm

    filas = []
    for b in wp.listar():
        if not _con_chat(b):
            continue
        w = b["whatsapp"]
        mensajes = wa_puente.conversacion(w["desde"], w["numero"], limite=20) or []
        ultimo = mensajes[-1] if mensajes else None
        entrantes = [m for m in mensajes if not m["yo"]]
        visto = float(w.get("visto") or 0)
        filas.append({"dominio": b["dominio"], "nombre": b.get("inmobiliaria") or b.get("nombre", ""),
                      "contacto": b.get("contacto", ""), "numero": w["numero"], "desde": w["desde"],
                      "estado": b.get("estado", ""), "etapa": crm.NOMBRE[crm.etapa(b)] if crm.entra(b) else "",
                      "ultimo": _resumen_chat(ultimo) if ultimo else "", "ultimo_yo": bool(ultimo and ultimo["yo"]),
                      "hora": ultimo["hora"] if ultimo else datetime.fromisoformat(w["enviado"]).timestamp(),
                      "nuevos": sum(1 for m in entrantes if m["hora"] > visto), "bot_apagado": bool(b.get("bot_apagado")),
                      # Aceptó el video o más allá: los que de verdad importan, primero en la lista.
                      "interesado": crm.entra(b) and crm.etapa(b) in crm.ACEPTARON,
                      "escalado": bool((b.get("agente") or {}).get("escalado")),
                      "etiquetas": limpiar_etiquetas(b.get("etiquetas"))})
    return sorted(filas, key=lambda f: (not f["interesado"], -f["hora"]))  # los interesados, arriba


def conversacion(clave: str) -> dict:
    """El chat completo con un prospecto. Abrirlo lo marca como leído (en el panel)."""
    from . import crm

    b = wp.leer(clave)  # se guarda con un reemplazo atómico: leerlo no necesita el candado
    if not _con_chat(b):
        raise KeyError(clave)
    w = b["whatsapp"]
    mensajes = wa_puente.conversacion(w["desde"], w["numero"], limite=300)
    if mensajes and not any(not m["yo"] for m in mensajes) and crm.entra(b):
        # Respondió, pero no se ven sus mensajes: su LID se olvidó. Se recupera y se lee de nuevo.
        if recuperar_lids([b]):
            mensajes = wa_puente.conversacion(w["desde"], w["numero"], limite=300)
    for m in mensajes or []:
        m["resumen"] = _resumen_chat(m)
    if mensajes and max(m["hora"] for m in mensajes) > float(w.get("visto") or 0):
        visto = max(m["hora"] for m in mensajes)

        def marcar():  # aparte: la respuesta no espera a que se libere el candado
            with correos.CANDADO:
                x = wp.leer(clave)
                x["whatsapp"]["visto"] = max(visto, float(x["whatsapp"].get("visto") or 0))
                wp.guardar(x)
        threading.Thread(target=marcar, daemon=True).start()
    v = crm.vista(b, completa=True) if crm.entra(b) else {}
    return {"dominio": b["dominio"], "nombre": b.get("inmobiliaria") or b.get("nombre", ""), "web": b.get("web", ""),
            "contacto": b.get("contacto", ""), "numero": w["numero"], "desde": w["desde"],
            "conectado": wa_puente.conexion(w["desde"]) == "conectado",
            "mensajes": mensajes, "sin_puente": mensajes is None, "en_crm": bool(v),
            "etapa": v.get("etapa", ""), "metodo": v.get("metodo", []), "no_enviar": wp.puede_conversar(b), "bot": estado_bot(b),
            "agente": _agente_estado(b), "etiquetas": limpiar_etiquetas(b.get("etiquetas"))}


# --- para borradores de correo ----------------------------------------------------------

def completar(log=print) -> int:
    """
    Busca el WhatsApp de los borradores de correo que no lo tienen, en los botones de
    su web: sirve para seguir la conversación cuando responden. No contacta a nadie.
    """
    from .analizar import _visitar  # aquí: analizar es pesado y no siempre hace falta

    pais, robots = nicho.pais(), Robots(True)
    hallados = 0
    for b in correos.listar():
        if b.get("estado") in ("descartada", "rechazado", "baja") or (b.get("whatsapp") or {}).get("numero") or not b.get("web"):
            continue
        try:
            paginas, _ = _visitar(b["web"], robots)
        except Exception as e:
            log(f"  ! {b['dominio']:<28} {type(e).__name__}")
            continue
        numeros = numeros_en(" ".join(h for _, h in paginas.values()).lower(), pais)
        if not numeros:
            log(f"  · {b['dominio']:<28} no publica un botón de WhatsApp")
            continue
        with correos.CANDADO:
            actual = correos.leer(b["dominio"])
            actual["whatsapp"] = {**(actual.get("whatsapp") or {}), "numero": numeros[0], "de": "",
                                  "fuente": b["web"]}
            correos.guardar(actual)
        hallados += 1
        log(f"  ✓ {b['dominio']:<28} {tel.bonito(numeros[0], pais)}")
    log(f"\n> {hallados} números nuevos.")
    return 0
