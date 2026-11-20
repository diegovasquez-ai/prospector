"""
Prospección por WhatsApp: un canal propio, separado del correo.

Cada negocio va por UN canal. Por correo, las investigadas a fondo (las
candidatas, con su borrador en borradores/). Por WhatsApp, las que publican un
WhatsApp y no un correo, o quedaron flojas: no hace falta investigarlas, porque el
primer mensaje no vende nada.

El método está en plantillas/whatsapp.md (lo puedes editar):

    Fase 1  mensaje de conexión, 3 líneas (rotan las variaciones A, B y C)
    Fase 2  responde → el pitch corto, igual para todos (audio o texto, se alternan
            para medir), que pide permiso para mandar un video
    Fase 3  acepta → confirmación: el video llega en 24 h
    Fase 4  el Loom de 60-90 s con su caso
    Fase 5  hasta 3 seguimientos, SOLO a quien aceptó el Loom
    Fase 6  audio de llamada de diagnóstico: ¿te acomoda esta semana?
    Fase 7  agenda

Aquí vive la fase 1: elegir a quién, preparar el mensaje y que lo apruebes uno por
uno. Lo envía whatsapp.py, en las mejores horas. Desde que responde, sigue en el CRM.

Cada prospecto es un archivo en datos/whatsapp/, con la misma forma que un borrador
de correo (dominio, nombre, estado, crm...) y "canal": "whatsapp".
"""

import hashlib
import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta

from . import base as bd
from . import config, correos, gmail, nicho
from .base import bloqueado
from .cazador import telefono as tel
from .puente import RAIZ

CARPETA = RAIZ / "datos" / "whatsapp"
METODO = RAIZ / "plantillas" / "whatsapp.md"
RESPUESTAS = RAIZ / "plantillas" / "respuestas.md"
# De la base salen por WhatsApp las que no van por correo.
ORIGENES = ("sin correo", "floja")
# por revisar → aprobado (en cola) → enviado → respondió (CRM) | sin respuesta
EDITABLES = ("por revisar",)
LLAVE = re.compile(r"\{(\w+)\}")
# El mensaje 1 tiene que entrar en la vista previa de WhatsApp.
LARGO_IDEAL = 90
LARGO_MAX = 300


# --- archivos ----------------------------------------------------------------------

def _archivo(clave: str):
    limpio = re.sub(r"[^a-z0-9.\-]", "", clave.lower())
    if not limpio or limpio != clave.lower():
        # "n:Nombre sin web" no es un nombre de archivo válido en Windows.
        limpio = "n-" + hashlib.sha1(clave.encode("utf-8")).hexdigest()[:16]
    return CARPETA / f"{limpio}.json"


def existe(clave: str) -> bool:
    return _archivo(clave).exists()


def leer(clave: str) -> dict:
    return json.loads(_archivo(clave).read_text(encoding="utf-8"))


def guardar(b: dict) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = _archivo(b["dominio"])
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, destino)


def listar() -> list[dict]:
    if not CARPETA.exists():
        return []
    salida = []
    for p in sorted(CARPETA.glob("*.json")):
        try:
            salida.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return salida


def leer_cualquiera(clave: str) -> dict:
    """Un negocio del CRM: prospecto de WhatsApp o borrador de correo."""
    if existe(clave):
        return leer(clave)
    return correos.leer(clave)


def guardar_cualquiera(b: dict) -> None:
    (guardar if b.get("canal") == "whatsapp" else correos.guardar)(b)


def todos() -> list[dict]:
    """Los borradores de correo y los prospectos de WhatsApp: lo que ve el CRM."""
    return correos.listar() + listar()


# --- los textos del método ----------------------------------------------------------

_cache: dict = {}


def metodo() -> dict[str, str]:
    """{clave: texto} de plantillas/whatsapp.md: el primer bloque ``` de cada sección."""
    try:
        firma = METODO.stat().st_mtime_ns
    except OSError:
        return {}
    if _cache.get("firma") != firma:
        textos = {}
        for seccion in re.split(r"^## ", METODO.read_text(encoding="utf-8"), flags=re.M)[1:]:
            clave = seccion.split(None, 1)[0]
            bloque = re.search(r"```[^\n]*\n(.*?)```", seccion, re.S)
            if bloque and re.fullmatch(r"\w+", clave):
                textos[clave] = bloque.group(1).strip()
        _cache.update(firma=firma, textos=textos)
    return _cache["textos"]


def yo() -> str:
    nombre = config.texto("GMAIL_NOMBRE") or gmail.firma().split("\n")[0]
    return nombre.split(" ")[0] if nombre else ""


def nombre_corto(nombre: str) -> str:
    """'Sol Propiedades | Corredores de Propiedades' → 'Sol Propiedades'."""
    n = re.split(r"\s+[|\-–·:]\s+|\s*\|\s*", nombre or "")[0]
    n = re.sub(r"\s+(spa|ltda\.?|limitada|s\.a\.?|eirl)$", "", n.strip(), flags=re.I).strip(" .,")
    if n.isupper() and len(n) > 4:
        n = n.title()
    return n


DIAS_HABILES = ("lunes", "martes", "miércoles", "jueves", "viernes")


def dias_reunion(hoy: date | None = None) -> tuple[str, str]:
    """El próximo día hábil y el que le sigue: para ofrecer la llamada, y otro si no puede."""
    d = hoy or date.today()
    dias = []
    while len(dias) < 2:
        d += timedelta(days=1)
        if d.weekday() < 5:
            dias.append(DIAS_HABILES[d.weekday()])
    return dias[0], dias[1]


def horarios() -> str:
    """Los dos horarios que se ofrecen para la llamada (REUNION_HORARIOS)."""
    return config.texto("REUNION_HORARIOS").strip() or "a las 11 de la mañana o a las 4 de la tarde"


def _plano(texto: str) -> str:
    return unicodedata.normalize("NFD", (texto or "").lower()).encode("ascii", "ignore").decode()


def presencial(direccion: str) -> bool:
    """
    ¿Se le ofrece ir a su oficina? Solo si su dirección de Maps tiene alguna de las palabras
    de REUNION_PRESENCIAL (tu ciudad o región, separadas por comas). Sin eso, solo videollamada.
    """
    zonas = [_plano(z).strip() for z in config.texto("REUNION_PRESENCIAL").split(",") if z.strip()]
    return bool(zonas) and any(z in _plano(direccion) for z in zonas)


def _frase(texto: str) -> str:
    """Un texto de nicho.json para ir dentro de una oración: sin mayúscula inicial ni punto final."""
    t = (texto or "").strip().rstrip(".")
    return t[:1].lower() + t[1:] if t[:2] != t[:2].upper() else t


def rellenar(texto: str, b: dict, extra: dict | None = None) -> str:
    """Pone lo que se sabe; lo que falta queda entre llaves para que se note."""
    persona = ((b.get("contacto") or "").strip().split(" ") or [""])[0]
    dia, dia_siguiente = dias_reunion()
    reunion = "por videollamada o, si prefieres, voy a verlos a la oficina" if b.get("presencial") else "por videollamada"
    n = nicho.actual()
    textos = n.get("textos") or {}
    negocio = b.get("inmobiliaria") or nombre_corto(b.get("nombre", ""))
    valores = {"yo": yo(), "nombre": persona, "negocio": negocio, "inmobiliaria": negocio,
               "rubro": n.get("rubro", ""), "singular": n.get("singular", ""),
               "problema": _frase(textos.get("problema", "")), "resultado": _frase(textos.get("resultado", "")),
               "demo": config.texto("DEMO_URL").strip(), "horarios": horarios(),
               "dia": dia, "dia_siguiente": dia_siguiente, "reunion": reunion} | (extra or {})
    if not persona:
        texto = re.sub(r"\s*\{nombre\}", "", texto)
    return LLAVE.sub(lambda m: valores.get(m.group(1)) or m.group(0), texto)


def pendientes(texto: str) -> list[str]:
    return LLAVE.findall(texto or "")


def variante(b: dict, n: int) -> str:
    """C si sabes con quién hablas; si no, A y B se turnan."""
    if (b.get("contacto") or "").strip() and "conexion_c" in metodo():
        return "c"
    return "ab"[n % 2]


def mensaje_conexion(b: dict, var: str) -> str:
    return rellenar(metodo().get(f"conexion_{var}", ""), b)


# --- a quién se le escribe ------------------------------------------------------------

def numero_de(lead: dict) -> str:
    a = lead.get("analisis") or {}
    for bruto in [*(a.get("whatsapp_numeros") or []), lead.get("whatsapp", "")]:
        n = tel.desde_enlace_wa(bruto or "", nicho.pais())
        if n:
            return n
    return ""


def _tiene_correo(clave: str) -> bool:
    try:
        return correos.ruta(clave).exists() and not clave.startswith("n:")
    except Exception:
        return False


def candidatos(base: dict | None = None) -> list[dict]:
    """Las que van por WhatsApp y todavía no tienen mensaje: primero las que más prometen."""
    base = bd.cargar() if base is None else base
    filas = []
    for clave, l in base.items():
        if l.get("estado") not in ORIGENES or existe(clave) or _tiene_correo(clave):
            continue
        numero = numero_de(l)
        if not numero or bloqueado({**l, "whatsapp": numero}):
            continue
        filas.append({"clave": clave, "nombre": l.get("nombre", ""), "comuna": l.get("comuna", ""),
                      "numero": numero, "origen": l.get("estado", ""), "motivo": l.get("motivo", ""),
                      "puntaje": l.get("puntaje", 0), "resenas": l.get("resenas", ""), "web": l.get("web", "")})

    def resenas(f):
        try:
            return int(f["resenas"] or 0)
        except ValueError:
            return 0
    return sorted(filas, key=lambda f: (-f["puntaje"], -resenas(f), f["nombre"].lower()))


def automaticos(base: dict | None = None) -> list[dict]:
    """
    Las que se pueden preparar solas: las que tienen todo para ser cliente salvo el
    correo, y después las que simplemente dieron pocas señales. Lo que el filtro apartó
    por otra cosa (no es de tu rubro, una red, una web abandonada) solo lo eliges tú.
    """
    buenas = [f for f in candidatos(base) if f["origen"] == "sin correo" or f["motivo"].startswith("pocas señales")]
    return sorted(buenas, key=lambda f: f["origen"] != "sin correo")  # estable: dentro, por puntaje


def preparar(claves: list[str]) -> tuple[int, list[str]]:
    """Deja el mensaje 1 de cada una listo para que lo revises. No envía nada."""
    validos = {f["clave"]: f for f in candidatos()}
    base = bd.cargar()
    hechos, errores = 0, []
    n = sum(1 for b in listar() if (b.get("whatsapp") or {}).get("variante") in ("a", "b"))
    for clave in claves:
        f = validos.get(clave)
        if not f:
            errores.append(f"{clave}: ya tiene mensaje, va por correo o está en la lista negra")
            continue
        l = base.get(clave, {})
        b = {"dominio": clave, "canal": "whatsapp", "nombre": l.get("nombre", ""),
             "inmobiliaria": nombre_corto(l.get("nombre", "")), "contacto": "",
             "comuna": l.get("comuna", ""), "web": l.get("web", ""), "origen": l.get("estado", ""),
             "presencial": presencial(l.get("direccion") or ""),
             "motivo": l.get("motivo", ""), "estado": "por revisar",
             "creado": datetime.now().isoformat(timespec="seconds")}
        var = variante(b, n)
        n += var in ("a", "b")
        b["whatsapp"] = {"numero": f["numero"], "fuente": l.get("web", ""), "variante": var,
                         "mensaje": mensaje_conexion(b, var)}
        guardar(b)
        hechos += 1
    return hechos, errores


# --- lo que haces con cada uno ---------------------------------------------------------

def sin_tocar(b: dict) -> bool:
    """El saludo sigue tal como lo dejó el sistema: nadie lo editó ni le puso un nombre."""
    w = b.get("whatsapp") or {}
    return not (b.get("contacto") or "").strip() and w.get("mensaje") == mensaje_conexion(b, w.get("variante") or "a")


def problemas(b: dict) -> list[str]:
    """Por qué no se puede aprobar todavía."""
    w = b.get("whatsapp") or {}
    p = []
    texto = (w.get("mensaje") or "").strip()
    if not w.get("numero"):
        p.append("Falta el número")
    if not texto:
        p.append("Falta el mensaje")
    elif pendientes(texto):
        p.append("Quedan huecos sin rellenar: " + ", ".join("{" + x + "}" for x in pendientes(texto)))
    elif len(texto) > LARGO_MAX:
        p.append(f"Es muy largo para un primer mensaje ({len(texto)} caracteres)")
    if bloqueado({"whatsapp": w.get("numero", ""), "web": b.get("web", "")}):
        p.append("Está en la lista negra")
    return p


def accion(b: dict, d: dict) -> str:
    """Desde la pestaña WhatsApp: editar, aprobar, quitar de la cola, descartar..."""
    w = b.setdefault("whatsapp", {})
    que = d.get("accion", "")
    ahora = datetime.now().isoformat(timespec="seconds")
    if que in ("editar", "aprobar"):
        if b.get("estado") not in EDITABLES:
            return "Ya está aprobado o salió: no se puede editar"
        if "numero" in d:
            escrito = str(d.get("numero") or "").strip()
            numero = tel.desde_enlace_wa(escrito, nicho.pais()) if escrito else ""
            if escrito and not numero:
                return "Ese número no parece válido: escríbelo con su código de país"
            w["numero"] = numero
        if "contacto" in d:
            antes = (b.get("contacto") or "").strip()
            b["contacto"] = str(d.get("contacto") or "").strip()[:60]
            # Con nombre, el mensaje sin tocar pasa a la variación C (y al revés).
            if b["contacto"] != antes and w.get("mensaje") == mensaje_conexion({**b, "contacto": antes}, w.get("variante", "a")) \
                    and "mensaje" not in d:
                var = "c" if b["contacto"] else ("a" if w.get("variante") == "c" else w.get("variante", "a"))
                w.update(variante=var, mensaje=mensaje_conexion(b, var))
        if "inmobiliaria" in d:
            b["inmobiliaria"] = str(d.get("inmobiliaria") or "").strip()[:80]
        if "mensaje" in d:
            w["mensaje"] = str(d.get("mensaje") or "").strip()
        if que == "aprobar":
            p = problemas(b)
            if p:
                return "No se puede aprobar: " + "; ".join(p)
            b.update(estado="aprobado", aprobado_en=ahora)
            w.update(estado="en cola", error="")
        return ""
    if que == "quitar":
        if b.get("estado") != "aprobado" or w.get("estado") != "en cola":
            return "No está en la cola"
        b["estado"] = "por revisar"
        w["estado"] = ""
        return ""
    if que == "descartar":
        if b.get("estado") not in (*EDITABLES, "aprobado") or w.get("estado") not in ("", None, "en cola"):
            return "Ya salió: no se puede descartar"
        b.update(estado="descartada", motivo=str(d.get("motivo") or "").strip() or "Descartada en el panel")
        w["estado"] = ""
        return ""
    if que == "salio":  # quedó en duda y en el celular se ve que llegó
        if w.get("estado") != "incierto":
            return "Solo se confirma un envío que quedó en duda"
        w.update(estado="enviado", error="")
        b["estado"] = "enviado"
        return ""
    if que == "reintentar":  # no salió: vuelve a la cola (lo decides tú, nunca solo)
        if w.get("estado") not in ("incierto", "error"):
            return "Solo se reintenta un envío que falló o quedó en duda"
        w.update(estado="en cola", error="")
        b["estado"] = "aprobado"
        return ""
    if que == "respondio":  # contestó y el panel no lo vio (un audio, otro número...)
        if b.get("estado") not in ("enviado", "sin respuesta"):
            return "Solo se marca si ya le escribiste"
        b.update(estado="respondió", respuesta_detectada=ahora, respuesta_canal="whatsapp")
        from . import crm  # aquí: crm importa este módulo
        crm.asignar_formato(b)  # le toca el pitch en audio o en texto
        return ""
    return "Acción desconocida"


def vista(b: dict) -> dict:
    w = b.get("whatsapp") or {}
    texto = w.get("mensaje", "")
    return {"dominio": b["dominio"], "nombre": b.get("nombre", ""), "inmobiliaria": b.get("inmobiliaria", ""),
            "contacto": b.get("contacto", ""), "comuna": b.get("comuna", ""), "web": b.get("web", ""),
            "origen": b.get("origen", ""), "motivo": b.get("motivo", ""), "estado": b.get("estado", ""),
            "numero": w.get("numero", ""), "enlace": tel.enlace(w["numero"]) if w.get("numero") else "",
            "variante": w.get("variante", ""), "mensaje": texto, "largo": len(texto),
            "wa_estado": w.get("estado", ""), "desde": w.get("desde", ""), "enviado": w.get("enviado", ""),
            "error": w.get("error", ""), "respuesta": w.get("respuesta", ""), "recibido": w.get("recibido", ""),
            "problemas": problemas(b) if b.get("estado") in EDITABLES else [],
            "verificacion": b.get("verificacion", ""), "aprobado_por": b.get("aprobado_por", "")}


# --- lo que toca después de que responde (lo usa el CRM) -------------------------------

# (clave de la plantilla, título, ¿se puede enviar como texto?)
DECISOR = ("decisor", "Si quien contesta no decide", True)
CIERRE = ("cierre", "Si dice que no le interesa", True)
PRECIO = ("precio", "Si pregunta cuánto vale", True)
AGENDA = ("agenda", "Si quiere reunirse: dos horarios", True)
NUMERO = ("numero", "Si pregunta de dónde sacaste su número", True)
YA_TIENEN = ("ya_tienen", "Si dice que ya tienen algo parecido", True)
BOT = ("bot", "Si pregunta si es un bot", True)
INFO = ("info", "Si pide que le mandes información: la demo", True)
PASOS = {
    "respondio": [("pitch", "Fase 2 · el pitch, igual para todos", True), NUMERO, BOT, DECISOR, CIERRE],
    "pitch": [("confirmacion", "Fase 3 · confirmación, cuando acepte el video", True), INFO, PRECIO, YA_TIENEN, NUMERO, BOT,
              DECISOR, CIERRE],
    "acepto": [("loom_guion", "Fase 4 · guion del Loom (2-3 min)", False),
               ("envio_loom", "Fase 4 · el mensaje con el Loom", True), PRECIO, YA_TIENEN],
    "video": [PRECIO, AGENDA, INFO, YA_TIENEN, BOT],  # el seguimiento que toca va primero, abajo
    "diagnostico": [("cta_audio", "Fase 6 · la llamada de diagnóstico (audio o texto)", True), AGENDA,
                    ("agenda_otro", "Si no puede a esa hora: el día siguiente", True),
                    ("agendado", "Cuando elige horario", True), PRECIO],
}
# Lo que el usuario ya dejó escrito para lo que más le preguntan: "Sugerir respuesta" lo usa.
SUYAS = (PRECIO, INFO, NUMERO, YA_TIENEN, BOT, DECISOR, CIERRE, AGENDA,
         ("agenda_otro", "Si no puede a esa hora", True), ("agendado", "Cuando elige horario", True))


def respuestas_suyas(b: dict) -> str:
    textos = metodo()
    return "\n\n".join(f"{titulo}:\n{rellenar(textos[clave], b)}" for clave, titulo, _ in SUYAS if clave in textos)
MAX_SEGUIMIENTOS = 3


FORMATO = {"audio": "te toca en AUDIO: grábalo desde el celular (40-45 s)", "texto": "te toca en TEXTO"}


def respuestas_correo() -> list[tuple[str, str, str]]:
    """(clave, título, texto) de cada respuesta de plantillas/respuestas.md que trae un texto."""
    try:
        firma = RESPUESTAS.stat().st_mtime_ns
    except OSError:
        return []
    if _cache.get("firma_r") != firma:
        lista = []
        for seccion in re.split(r"^## ", RESPUESTAS.read_text(encoding="utf-8"), flags=re.M)[1:]:
            titulo = seccion.split("\n", 1)[0].strip()
            bloque = re.search(r"```[^\n]*\n(.*?)```", seccion, re.S)
            if not bloque or not titulo:
                continue
            plano = unicodedata.normalize("NFD", titulo.lower()).encode("ascii", "ignore").decode()
            lista.append(("correo_" + re.sub(r"[^a-z0-9]+", "_", plano).strip("_")[:48], titulo, bloque.group(1).strip()))
        _cache.update(firma_r=firma, respuestas=lista)
    return _cache["respuestas"]


def es_llamada(clave: str) -> bool:
    """La respuesta de correo que propone verse («Quiere saber más»)."""
    return clave.startswith("correo_") and "saber_mas" in clave


def _rellenar_correo(texto: str, b: dict) -> str:
    """Pone el nombre y la empresa; lo demás ({la señal}...) lo adaptas tú al contestar."""
    persona = ((b.get("decisor") or {}).get("nombre") or b.get("contacto") or "").strip().split(" ")[0]
    valores = {"empresa": nombre_corto(b.get("nombre", "")), "yo": yo(), "nombre": persona}
    return LLAVE.sub(lambda m: valores.get(m.group(1)) or m.group(0), texto)


# Por correo, después del Loom van como mucho 2 seguimientos (sin el 👋, que es de chat).
SEGUIMIENTOS_CORREO = ("seguimiento_1", "seguimiento_3")


def pasos_correo(b: dict, etapa: str, seguimientos: int = 0) -> list[dict]:
    """
    Quien responde un correo ya leyó el pitch en el correo 1: no se le manda otro. Se le
    contesta según lo que dijo (plantillas/respuestas.md): si quiere saber más, la
    llamada; si duda, el Loom. Se copia y se responde en el mismo hilo de Gmail.
    """
    textos = metodo()

    def tarjeta(clave, titulo, texto, marcable=True):
        return {"clave": clave, "titulo": titulo, "texto": texto, "enviable": False, "marcable": marcable}

    if etapa == "respondio":
        return [tarjeta(c, "Si " + t[0].lower() + t[1:], _rellenar_correo(x, b)) for c, t, x in respuestas_correo()]
    if etapa == "acepto":
        return [tarjeta(c, t, rellenar(textos[c], b), c == "envio_loom")
                for c, t in (("loom_guion", "El guion del Loom (60-90 s)"), ("envio_loom", "El correo con el Loom"))
                if c in textos]
    if etapa == "video" and seguimientos < len(SEGUIMIENTOS_CORREO):
        c = SEGUIMIENTOS_CORREO[seguimientos]
        total = len(SEGUIMIENTOS_CORREO)
        return [tarjeta(c, f"Seguimiento {seguimientos + 1} de {total}, en el mismo hilo", rellenar(textos[c], b))] if c in textos else []
    if etapa == "diagnostico":
        return [tarjeta(c, "Propón la llamada con dos horarios", _rellenar_correo(x, b))
                for c, _, x in respuestas_correo() if es_llamada(c)]
    return []


def pasos(b: dict, etapa: str, seguimientos: int = 0) -> list[dict]:
    if b.get("canal") != "whatsapp":
        return pasos_correo(b, etapa, seguimientos)
    lista = list(PASOS.get(etapa, []))
    formato = (b.get("crm") or {}).get("formato")
    if formato in FORMATO:  # la prueba audio contra texto
        lista = [(c, f"{t} · {FORMATO[formato]}" if c == "pitch" else t, e) for c, t, e in lista]
    if etapa == "video" and seguimientos < MAX_SEGUIMIENTOS:
        horas = 24 * (seguimientos + 1)
        lista.insert(0, (f"seguimiento_{seguimientos + 1}",
                         f"Fase 5 · seguimiento {seguimientos + 1} de {MAX_SEGUIMIENTOS} ({horas} h después del Loom)", True))
    textos = metodo()
    return [{"clave": c, "titulo": t, "texto": rellenar(textos[c], b), "enviable": e, "marcable": e}
            for c, t, e in lista if c in textos]


def puede_conversar(b: dict) -> str:
    """Por qué no se puede mandar desde el panel (y hay que hacerlo desde el celular)."""
    w = b.get("whatsapp") or {}
    if b.get("canal") != "whatsapp" or not w.get("numero"):
        return "Llegó por correo: cópialo y respóndele en el mismo hilo de Gmail"
    if not isinstance(w.get("desde"), int):
        return "No sé desde qué número le escribiste: contéstale desde tu celular"
    if bloqueado({"whatsapp": w["numero"], "web": b.get("web", "")}):
        return "Está en la lista negra"
    return ""
