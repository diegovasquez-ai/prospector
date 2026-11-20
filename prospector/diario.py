"""
Lo que corre solo cada mañana en tu PC (lo programa `python prospector.py automatizar`):

    python prospector.py diario -n 20

1. Investiga y redacta N correos en modo rápido (con tu suscripción de Claude Code).
   Si quedan pocas candidatas, barre antes la siguiente comuna de comunas.txt.
2. Los sube al servidor. Allá se aprueban solos (ENVIO_AUTO_APROBAR) si el panel no ve
   ningún problema, y salen de 9 a 18 con su ritmo y su tope.
3. Si al WhatsApp le quedan pocos negocios para los saludos automáticos, barre hasta
   COMUNAS_POR_DIA comunas más y las sube: el servidor las verifica antes de escribirles.

Log en datos/preparar.log.
"""

from . import base as bd
from . import config, preparar, sincronizar
from .analizar import analizar

COMUNAS_POR_DIA = 3


def _barrer(log) -> bool:
    from .cli import buscar  # aquí: cli importa este módulo
    quedan = preparar.comunas_por_barrer(bd.cargar())
    if not quedan:
        log("  ! No quedan comunas en comunas.txt: agrega más (o pasamos a otro país).")
        return False
    log(f"> Barro {quedan[0]} para tener más negocios")
    buscar([quedan[0]], 60, "maps")
    base = bd.cargar()
    analizar(base, log=log)
    bd.guardar(base)
    return True


def diario(n: int = 20, log=print) -> int:
    config.cargar()
    codigo = preparar.preparar(n, paralelo=4, log=log, rapido=True)
    sincronizar.subir(log=log)
    reserva = sincronizar.reserva_whatsapp()
    minimo = config.numero("WA_RESERVA_MIN", 200)
    if reserva is not None and reserva < minimo:
        log(f"> Al WhatsApp le quedan {reserva} negocios (mínimo {minimo}): busco más")
        barridas = sum(_barrer(log) for _ in range(COMUNAS_POR_DIA))
        if barridas:
            sincronizar.subir(log=log)
    return codigo
