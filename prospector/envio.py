"""
Fase 8: el envío, a ritmo de persona.

Mientras el panel esté abierto y los envíos activados, cada medio minuto se
mira si toca mandar algo:

    - solo de lunes a viernes, dentro de ENVIO_HORARIO (9-18)
    - entre correo y correo, una pausa al azar de ENVIO_PAUSA minutos (6-18)
    - como mucho ENVIO_MAX_DIA correos nuevos al día (20); los seguimientos aparte
    - primero los seguimientos que vencen (día 3 y día 7), después los nuevos

Antes de cada seguimiento se mira tu bandeja: si alguien de su dominio
contestó, la secuencia se para ahí. Mandarle "¿te armo el diagnóstico?" a
quien ya te respondió es la forma más rápida de quedar como un robot.

Si cierras el panel no se envía nada, y al abrirlo sigue donde lo dejó. Es a
propósito: nada sale mientras no estás mirando.
"""

import json
import random
import smtplib
import threading
import time
from datetime import datetime, timedelta

from . import config, correos, gmail
from .base import bloqueado
from .puente import RAIZ

ESTADO = RAIZ / "datos" / "envio.json"
REVISAR_CADA = timedelta(minutes=10)
# Una respuesta puede llegar después del correo 3: se sigue mirando un tiempo.
MIRAR_TERMINADOS = timedelta(days=14)
# Rebotes nuevos que aguantamos antes de parar: muchos dañan la reputación del Gmail.
MAX_REBOTES = 2


def leer_estado() -> dict:
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"activo": False, "proximo": "", "error": ""}


def guardar_estado(e: dict) -> None:
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")


def _fecha(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def enviados_hoy(borradores: list[dict], ahora: datetime | None = None) -> int:
    hoy = (ahora or datetime.now()).date()
    return sum(1 for b in borradores for e in b.get("envios", [])
               if e["paso"] == 0 and _fecha(e["fecha"]).date() == hoy)


def en_horario(ahora: datetime) -> bool:
    ini, fin = config.rango("ENVIO_HORARIO", (9, 18))
    return ahora.weekday() < 5 and ini <= ahora.hour < fin


def seguimiento_pendiente(b: dict, ahora: datetime) -> int | None:
    """El índice del correo que toca, si ya venció su día. None si no toca."""
    if b.get("estado") != "enviando":
        return None
    hechos = len(b["envios"])
    if hechos >= len(b["correos"]):
        return None
    vence = _fecha(b["envios"][0]["fecha"]) + timedelta(days=b["correos"][hechos]["dia"])
    return hechos if ahora >= vence else None


def asunto_de(b: dict, paso: int) -> str:
    asunto = b["correos"][0]["asunto"].strip()
    return asunto if paso == 0 else "Re: " + asunto


def cuerpo_de(b: dict, paso: int) -> str:
    return b["correos"][paso]["cuerpo"].strip() + "\n\n" + gmail.firma()


def mandar(b: dict, paso: int, ahora: datetime) -> None:
    responde = b["envios"][0]["message_id"] if paso else ""
    mid = gmail.enviar(b["para"], asunto_de(b, paso), cuerpo_de(b, paso), responde_a=responde)
    b["envios"].append({"paso": paso, "fecha": ahora.isoformat(timespec="seconds"),
                        "message_id": mid, "para": b["para"]})
    b["estado"] = "enviando" if paso < len(b["correos"]) - 1 else "terminado"


def mirar_respuestas(borradores: list[dict], ahora: datetime) -> None:
    """Para las secuencias en curso (y las recién terminadas) en cuanto contestan."""
    for b in borradores:
        if b.get("estado") not in ("enviando", "terminado") or not b["envios"]:
            continue
        primero = _fecha(b["envios"][0]["fecha"])
        if b["estado"] == "terminado" and ahora - _fecha(b["envios"][-1]["fecha"]) > MIRAR_TERMINADOS:
            continue
        resultado = gmail.revisar(b["para"], primero)
        if resultado:
            b["estado"] = resultado
            b["respuesta_detectada"] = ahora.isoformat(timespec="seconds")
            correos.guardar(b)


def rebotes_de(borradores: list[dict]) -> int:
    return sum(len(b.get("rebotes", [])) + (b.get("estado") == "rebotó") for b in borradores)


def frenar_por_rebotes(estado: dict, borradores: list[dict]) -> bool:
    """
    Pausa los envíos si hay MAX_REBOTES nuevos. Cuenta desde la última pausa,
    para que al reactivar no se vuelva a frenar por los mismos.
    """
    total = rebotes_de(borradores)
    if "rebotes_base" not in estado:
        estado["rebotes_base"] = total
        guardar_estado(estado)
    nuevos = total - estado["rebotes_base"]
    if nuevos < MAX_REBOTES:
        return False
    estado.update(activo=False, rebotes_base=total,
                  error=f"Pausé los envíos: rebotaron {nuevos} correos. "
                        "Revísalos en Cerrados y reactiva cuando quieras.")
    guardar_estado(estado)
    return True


def siguiente(borradores: list[dict], ahora: datetime) -> tuple[dict, int] | None:
    for b in borradores:
        paso = seguimiento_pendiente(b, ahora)
        if paso is not None:
            return b, paso
    if enviados_hoy(borradores, ahora) >= config.numero("ENVIO_MAX_DIA", 20):
        return None
    cola = sorted((b for b in borradores if b.get("estado") == "aprobado"),
                  key=lambda b: b.get("aprobado_en", ""))
    for b in cola:
        problemas, _ = correos.revisar(b)
        if bloqueado({"email": b["para"], "web": b.get("web", "")}):
            b["estado"] = "baja"
            correos.guardar(b)
        elif problemas:
            # Algo cambió desde que se aprobó (p. ej. la firma): vuelve a revisión.
            b["estado"] = "por revisar"
            b["motivo"] = "Volvió a revisión: " + problemas[0]
            correos.guardar(b)
        else:
            return b, 0
    return None


class Envio(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.ultima_revision = datetime.min

    def run(self) -> None:
        while True:
            try:
                self.ciclo()
            except Exception as e:  # el hilo no puede morir por un error raro
                e_ = leer_estado()
                e_["error"] = f"{type(e).__name__}: {e}"
                guardar_estado(e_)
            time.sleep(30)

    def ciclo(self, ahora: datetime | None = None) -> None:
        estado = leer_estado()
        if not estado.get("activo") or not gmail.configurado():
            return
        ahora = ahora or datetime.now()
        with correos.CANDADO:
            borradores = correos.listar()
            if ahora - self.ultima_revision >= REVISAR_CADA:
                # Antes de mirar: si el IMAP falla, no reintentar cada 30 s.
                self.ultima_revision = ahora
                mirar_respuestas(borradores, ahora)
            if frenar_por_rebotes(estado, borradores):
                return
            if not en_horario(ahora):
                return
            if estado.get("proximo") and ahora < _fecha(estado["proximo"]):
                return
            elegido = siguiente(borradores, ahora)
            if not elegido:
                return
            b, paso = elegido
            if paso:
                # Justo antes del seguimiento, otra mirada a la bandeja.
                resultado = gmail.revisar(b["para"], _fecha(b["envios"][0]["fecha"]))
                if resultado:
                    b["estado"] = resultado
                    correos.guardar(b)
                    return
            try:
                mandar(b, paso, ahora)
            except smtplib.SMTPAuthenticationError:
                estado.update(activo=False, error="Gmail rechazó la contraseña de aplicación. "
                                                  "Envíos pausados.")
                guardar_estado(estado)
                return
            except smtplib.SMTPRecipientsRefused:
                b["estado"] = "rebotó"
                correos.guardar(b)
                return
            except (smtplib.SMTPException, OSError) as e:
                estado["error"] = f"No pude enviar a {b['para']} ({e}). Reintento en 10 min."
                estado["proximo"] = (ahora + timedelta(minutes=10)).isoformat(timespec="seconds")
                guardar_estado(estado)
                return
            correos.guardar(b)

        pmin, pmax = config.rango("ENVIO_PAUSA", (6, 18))
        estado["proximo"] = (ahora + timedelta(minutes=random.uniform(pmin, pmax))
                             ).isoformat(timespec="seconds")
        estado["error"] = ""
        guardar_estado(estado)
