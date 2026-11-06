"""
Que funcione sin acordarte: dos piezas de Windows, sin permisos de administrador.

    python prospector.py automatizar           las instala
    python prospector.py automatizar --quitar  las quita

1. Tarea programada "Prospector - preparar": de lunes a viernes a las 07:00
   investiga y redacta los correos del día (preparar -n 20). A las ~8:30
   tienes los borradores esperando en el panel. Log en datos/preparar.log.
2. Acceso directo en Inicio de Windows: al encender el PC abre el panel en
   segundo plano, así la cola envía y los seguimientos salen aunque no te
   acuerdes de abrirlo.

Lo que sigue siendo tuyo, a propósito: aprobar. Nada sale sin tu clic.

El PC tiene que estar encendido: a las 7 para preparar, y de 9 a 18 para enviar.
"""

import os
import subprocess
import sys
from pathlib import Path

from .puente import RAIZ

TAREA = "Prospector - preparar"
INICIO = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
ARRANQUE = INICIO / "Prospector panel.cmd"
PREPARAR = RAIZ / "datos" / "preparar.cmd"


def instalar(n: int = 20, hora: str = "07:00") -> int:
    if os.name != "nt":
        print("  Esto programa tareas de Windows. En Mac o Linux, usa cron con:")
        print(f"    {sys.executable} {RAIZ / 'prospector.py'} preparar -n {n}")
        return 1
    # pythonw: sin ventana negra. Si no existe (algún Python raro), python normal.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    python_panel = pythonw if pythonw.exists() else Path(sys.executable)

    PREPARAR.parent.mkdir(exist_ok=True)
    PREPARAR.write_text(
        "@echo off\r\n"
        f'cd /d "{RAIZ}"\r\n'
        f'echo ===== %date% %time% >> "datos\\preparar.log"\r\n'
        f'"{sys.executable}" prospector.py preparar -n {n} >> "datos\\preparar.log" 2>&1\r\n',
        encoding="utf-8")
    r = subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", TAREA, "/TR", f'"{PREPARAR}"',
         "/SC", "WEEKLY", "/D", "MON,TUE,WED,THU,FRI", "/ST", hora],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ! Windows no dejó crear la tarea: {(r.stderr or r.stdout).strip()}")
        return 1

    ARRANQUE.write_text(
        "@echo off\r\n"
        f'cd /d "{RAIZ}"\r\n'
        f'start "" "{python_panel}" prospector.py panel --sin-navegador\r\n',
        encoding="utf-8")

    print(f"  ✓ De lunes a viernes a las {hora}: se preparan {n} correos (log en datos\\preparar.log)")
    print("  ✓ Al encender el PC: el panel arranca solo en http://127.0.0.1:8765 (o el siguiente puerto libre)")
    print("\n  Para quitarlo:  python prospector.py automatizar --quitar")
    return 0


def quitar() -> int:
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", TAREA], capture_output=True)
    for archivo in (ARRANQUE, PREPARAR):
        if archivo.exists():
            archivo.unlink()
    print("  ✓ Quitado. Ya nada corre solo; el panel actual sigue hasta que lo cierres.")
    return 0
