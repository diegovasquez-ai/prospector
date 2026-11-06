"""
WhatsApp, a mano.

El panel abre el chat con el mensaje escrito y tú lo envías: nada sale solo. WhatsApp
suele banear los números que mandan mensajes en frío automatizados, y aprobar cada
mensaje es la regla de este proyecto. Sale después del correo 1, nunca antes.

Solo se usa un número que el negocio publica como WhatsApp (un botón o un enlace).
Un teléfono cualquiera puede ser un fijo, o el celular personal de alguien.
"""

from collections import Counter
from datetime import datetime

from . import config, correos, gmail, nicho
from .base import bloqueado
from .cazador import telefono as tel
from .cazador.rastrear import ENLACE_WA, Robots

# Solo cuando ya salió el correo 1 y sigue sin responder.
PERMITIDOS = ("enviando", "terminado")
# A estos no vale la pena buscarles número: no se les va a escribir.
ACTIVOS = ("por revisar", "aprobado", *PERMITIDOS)


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


def _yo() -> str:
    nombre = config.texto("GMAIL_NOMBRE") or gmail.firma().split("\n")[0]
    return nombre.split(" ")[0] if nombre else ""


def mensaje_por_defecto(b: dict) -> str:
    """
    Corto, sin vender y honesto: recuerda el correo y no da por hecho quién contesta,
    porque el número general suele responderlo otra persona.
    """
    w = b.get("whatsapp") or {}
    yo = _yo()
    soy = f" soy {yo}." if yo else ""
    nombre = ((b.get("decisor") or {}).get("nombre") or "").split(" ")[0]
    if nombre and w.get("de") == "persona":
        return f"Hola {nombre},{soy} Te escribí por correo hace unos días. ¿Lo alcanzaste a ver?".replace(",  ", ", ")
    if nombre:
        return f"Hola,{soy} Le escribí por correo a {nombre} hace unos días. ¿Sabes si lo alcanzó a ver?"
    return f"Hola,{soy} Les escribí por correo hace unos días. ¿Lo alcanzaron a ver?"


def puede(b: dict) -> str:
    """Por qué no se puede escribirle ahora, o "" si se puede."""
    w = b.get("whatsapp") or {}
    if bloqueado({"whatsapp": w.get("numero", ""), "email": b.get("para", ""), "web": b.get("web", "")}):
        return "Está en la lista negra"
    if b.get("estado") not in PERMITIDOS or not b.get("envios"):
        return "Primero tiene que salir el correo 1"
    if not w.get("numero"):
        return "Falta el número"
    return ""


def vista(b: dict) -> dict:
    """Lo que necesita el panel."""
    w = b.get("whatsapp") or {}
    numero = w.get("numero", "")
    return {"numero": numero, "de": w.get("de", ""), "fuente": w.get("fuente", ""),
            "mensaje": w.get("mensaje") or mensaje_por_defecto(b),
            "enlace": tel.enlace(numero) if numero else "",
            "bloqueo": puede(b), "enviados": b.get("whatsapp_envios", []),
            "mostrar": b.get("estado") in ACTIVOS}


def accion(b: dict, d: dict) -> str:
    """Guardar el número o el mensaje, marcar que lo enviaste o que te respondió."""
    w = dict(b.get("whatsapp") or {})
    if "numero" in d:
        escrito = (d.get("numero") or "").strip()
        numero = limpiar(escrito)
        if escrito and not numero:
            return "Ese número no parece válido: escríbelo con su código de país"
        if numero != w.get("numero", ""):
            w.update(numero=numero, de="", fuente="escrito a mano" if numero else "")
    if "mensaje" in d:
        w["mensaje"] = (d.get("mensaje") or "").strip()
    b["whatsapp"] = w

    ahora = datetime.now().isoformat(timespec="seconds")
    que = d.get("accion", "guardar")
    if que == "enviado":
        error = puede(b)
        if error:
            return error
        b.setdefault("whatsapp_envios", []).append(ahora)
    elif que == "respondio":
        if b.get("estado") not in PERMITIDOS:
            return "Solo se marca si ya salió el correo y no ha respondido"
        # Así se cortan los recordatorios por correo: el panel solo ve el correo.
        b.update(estado="respondió", respuesta_detectada=ahora, respuesta_canal="whatsapp")
    elif que != "guardar":
        return "Acción desconocida"
    return ""


def completar(log=print) -> int:
    """
    Busca el número de los borradores activos que no lo tienen, en los botones de su
    web. No toca nada más ni contacta a nadie. Sirve para borradores anteriores.
    """
    from .analizar import _visitar  # aquí: analizar es pesado y no siempre hace falta

    pais, robots = nicho.pais(), Robots(True)
    hallados = 0
    for b in correos.listar():
        if b.get("estado") not in ACTIVOS or (b.get("whatsapp") or {}).get("numero") or not b.get("web"):
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
    log(f"\n> {hallados} números nuevos. Revísalos en el panel antes de escribir.")
    return 0
