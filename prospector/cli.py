"""
Los comandos, en el orden en que se usan:

    python prospector.py buscar "Las Condes" "Providencia"     Fase 2
    python prospector.py analizar                               Fases 3, 4 y 5
    python prospector.py lista                                  a quién escribir
    python prospector.py baja ana@negocio.cl                    Fase 9: lista negra

La redacción (Fase 6) y la aprobación (Fase 7) las hace Claude Code leyendo
las fichas: ver CLAUDE.md.
"""

import argparse
import csv
import time
from datetime import date

from . import base as bd
from .analizar import FICHAS, analizar
from . import nicho
from .puente import RAIZ, descubrir, dominio, exclusiones, pantalla

RANKING = RAIZ / "datos" / "ranking.csv"


def buscar(comunas: list[str], limite: int, fuente: str) -> int:
    if not nicho.existe():
        pantalla.aviso("Falta nicho.json. Corre primero:  python prospector.py iniciar")
        return 1
    n, pais = nicho.actual(), nicho.pais()
    base = bd.cargar()
    nuevas = repetidas = 0
    for comuna in comunas:
        for consulta in n["busquedas"]:
            print(pantalla.c(f"\n  {consulta} · {comuna}", "negrita"))
            for l in descubrir(consulta, comuna, pais, fuente, limite):
                k = bd.clave(l)
                if k in base:
                    repetidas += 1
                    continue
                base[k] = {**l, "comuna": comuna, "consulta": consulta,
                           "estado": "nueva", "descubierta": date.today().isoformat()}
                nuevas += 1
    ruta = bd.guardar(base)
    print(f"\n> {nuevas} negocios nuevos · {repetidas} repetidos · {len(base)} en total")
    print(f"  {pantalla.ruta(str(ruta))}")
    print("\n  Siguiente:  python prospector.py analizar")
    return 0


def cmd_analizar(todas: bool, concurrencia: int) -> int:
    base = bd.cargar()
    if not base:
        pantalla.aviso("La base está vacía. Empieza por:  python prospector.py buscar \"Las Condes\"")
        return 1
    inicio = time.time()
    conteo = analizar(base, todas=todas, concurrencia=concurrencia)
    bd.guardar(base)
    print()
    for estado in ("candidata", "sin correo", "floja", "descartada", "baja", "nueva"):
        if conteo.get(estado):
            print(f"  {conteo[estado]:>4}  {estado}")
    print(f"\n  Tiempo {time.time() - inicio:.0f}s · fichas en {pantalla.ruta(str(FICHAS))}")
    print("\n  Siguiente:  python prospector.py lista")
    return 0


def lista(todas: bool) -> int:
    base = bd.cargar()
    estados = ("candidata", "sin correo", "floja") if todas else ("candidata", "sin correo")
    filas = sorted((l for l in base.values() if l.get("estado") in estados),
                   key=lambda l: (l["estado"] != "candidata", -l.get("puntaje", 0)))

    RANKING.parent.mkdir(exist_ok=True)
    with RANKING.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["estado", "puntaje", "nombre", "comuna", "web", "correo",
                    "correo_estado", "puede_pagar", "le_falta", "motivo", "ficha"])
        for l in filas:
            w.writerow([l["estado"], l["puntaje"], l["nombre"], l.get("comuna", ""),
                        l.get("web", ""), l.get("correo", ""), l.get("correo_estado", ""),
                        " · ".join(l["puede_pagar"]), " · ".join(l["le_falta"]),
                        l.get("motivo", ""), f"fichas/{dominio(l.get('web', ''))}.md"])

    print()
    for l in filas:
        marca = pantalla.c("●", "verde") if l["estado"] == "candidata" else "○"
        print(f"  {marca} {l['puntaje']:>3}  {l['nombre'][:30]:<30} {l.get('comuna', '')[:12]:<12} "
              f"{(l.get('correo') or '—')[:32]:<32} {l.get('correo_estado', '')}")
        print(pantalla.c(f"          puede pagar: {' · '.join(l['puede_pagar']) or '—'}", "gris"))
        print(pantalla.c(f"          le falta:    {' · '.join(l['le_falta']) or '—'}", "gris"))
        if l.get("motivo"):
            print(pantalla.c(f"          ojo:         {l['motivo']}", "amarillo"))

    descartes: dict[str, int] = {}
    for l in base.values():
        if l.get("estado") == "descartada":
            descartes[l.get("tipo", "?")] = descartes.get(l.get("tipo", "?"), 0) + 1
    if descartes:
        print("\n  Descartadas: " + " · ".join(f"{n} {t}" for t, n in
                                               sorted(descartes.items(), key=lambda x: -x[1])))
    print(f"\n  {pantalla.ruta(str(RANKING))}")
    return 0


def baja(valor: str, motivo: str) -> int:
    tipo, normal = exclusiones.anadir(valor, motivo or "pidió la baja")
    base = bd.cargar()
    fuera = exclusiones.cargar()
    marcadas = 0
    for l in base.values():
        if bd.bloqueado(l, fuera) and l.get("estado") != "baja":
            l["estado"] = "baja"
            marcadas += 1
    bd.guardar(base)
    print(f"> {normal} ({tipo}) en la lista negra. No vuelve a salir.")
    if marcadas:
        print(f"  {marcadas} negocio(s) marcados como baja en la base.")
    return 0


def metricas() -> int:
    """
    Fase 10, contada por la fecha del correo 1. Un "baja" que llegó como
    respuesta también es una respuesta: cuenta en la tasa.
    """
    from datetime import datetime, timedelta

    from . import correos
    con_envio = [b for b in correos.listar() if b.get("envios")]
    hoy = datetime.now()
    lunes = (hoy - timedelta(days=hoy.weekday())).date()
    for titulo, desde in ((f"Esta semana (desde el lunes {lunes:%d-%m})", lunes),
                          ("Desde el principio", date.min)):
        g = [b for b in con_envio if datetime.fromisoformat(b["envios"][0]["fecha"]).date() >= desde]
        cuenta = lambda *estados: sum(1 for b in g if b.get("estado") in estados)  # noqa: E731
        respondieron = cuenta("respondió", "interesado", "retomar", "baja")
        tasa = f"{respondieron / len(g):.0%}" if g else "—"
        print(f"\n  {titulo}")
        print(f"    {len(g):>4}  correos 1 enviados")
        print(f"    {respondieron:>4}  respondieron            {tasa}")
        print(f"    {cuenta('interesado'):>4}  interesados (sí / info)")
        print(f"    {cuenta('retomar'):>4}  ahora no (60 días)")
        print(f"    {cuenta('baja'):>4}  bajas")
        print(f"    {cuenta('rebotó'):>4}  rebotaron")
        print(f"    {cuenta('respondió'):>4}  respondieron y falta clasificarlas en el panel")
    print(pantalla.c("\n  Cambia una sola cosa por semana (asunto, observación o CTA) para saber qué movió el número.", "gris"))
    return 0


def conectar_gmail() -> int:
    """Pide el correo y la contraseña de aplicación, los prueba y los guarda en el .env."""
    from getpass import getpass

    from . import config, gmail
    config.cargar()
    print("\n  Conectar tu Gmail (2 minutos)")
    print("    1. Ten activada la verificación en dos pasos: https://myaccount.google.com/security")
    print("    2. Crea una contraseña de aplicación:          https://myaccount.google.com/apppasswords")
    print("       Nombre: Prospector -> Crear -> copia las 16 letras.\n")
    actual = gmail.usuario()
    usuario = input(f"  Tu Gmail{f' [{actual}]' if actual else ''}: ").strip() or actual
    clave = getpass("  Contraseña de aplicación (no se ve al escribir): ").strip()
    if not usuario or not clave:
        pantalla.aviso("Faltan el correo o la contraseña. No guardé nada.")
        return 1
    print("  Probando con Gmail...")
    error = gmail.probar(usuario, clave)
    if error:
        pantalla.aviso(error + "\nNo guardé nada.")
        return 1
    config.guardar({"GMAIL_USUARIO": usuario, "GMAIL_CLAVE_APP": clave.replace(" ", "")})
    print(pantalla.c(f"  ✓ Conectado: envío y lectura de respuestas funcionan con {usuario}.", "verde"))
    print("    Guardado en .env (no se sube a ningún sitio).")
    print("\n  Siguiente: python prospector.py panel  ->  «Enviarme prueba» en un borrador.")
    return 0


def main(argv: list[str] | None = None) -> int:
    pantalla.preparar_consola()
    p = argparse.ArgumentParser(prog="prospector",
                                description="Correo frío B2B, escrito uno a uno.")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("buscar", help="Fase 2: negocios de tu rubro en una o varias comunas o ciudades")
    b.add_argument("comunas", nargs="+", help='Ej: "Las Condes" Providencia Ñuñoa')
    b.add_argument("-l", "--limite", type=int, default=60, help="Máximo por consulta (60)")
    b.add_argument("-f", "--fuente", default="maps", choices=["maps", "osm", "todas"])

    a = sub.add_parser("analizar", help="Fases 3-5: señales, filtro y correo de cada una")
    a.add_argument("--todas", action="store_true", help="Vuelve a analizar también las ya vistas")
    a.add_argument("--concurrencia", type=int, default=8)

    li = sub.add_parser("lista", help="Las candidatas, de más a menos puntaje")
    li.add_argument("--todas", action="store_true", help="Incluye las flojas")

    ba = sub.add_parser("baja", help="Fase 9: a la lista negra, para siempre")
    ba.add_argument("valor", help="Correo o dominio")
    ba.add_argument("--motivo", default="")

    pa = sub.add_parser("panel", help="Fases 7-9: aprobar, afinar y enviar desde el navegador")
    pa.add_argument("--puerto", type=int, default=8765)
    pa.add_argument("--sin-navegador", action="store_true")

    pr = sub.add_parser("preparar", help="Investiga y redacta N correos sin abrir Claude Code")
    pr.add_argument("-n", type=int, default=20, help="Cuántos negocios (20)")
    pr.add_argument("--paralelo", type=int, default=3, help="Cuántas a la vez (3)")

    sub.add_parser("iniciar", help="La primera vez: define tu nicho y crea negocio.md y firma.txt")
    sub.add_parser("gmail", help="Conecta tu Gmail y comprueba que funciona")

    au = sub.add_parser("automatizar", help="Preparar cada mañana y panel al encender el PC")
    au.add_argument("-n", type=int, default=20)
    au.add_argument("--hora", default="07:00")
    au.add_argument("--quitar", action="store_true")

    sub.add_parser("metricas", help="Fase 10: cómo va la semana")

    sub.add_parser("treg", help="Conecta Treg (buscar y verificar el correo del decisor)")
    co = sub.add_parser("contactos", help="Prueba de Treg: ¿encuentra el correo del decisor? No toca nada")
    co.add_argument("--tope", type=float, default=0.8, help="USD máximos para la prueba (0.80)")
    co.add_argument("--si", action="store_true", help="Sin pedir confirmación")

    ns = p.parse_args(argv)
    if ns.cmd in ("treg", "contactos"):
        from . import contactos
        return contactos.conectar() if ns.cmd == "treg" else contactos.prueba(ns.tope, ns.si)
    if ns.cmd == "automatizar":
        from . import automatizar
        return automatizar.quitar() if ns.quitar else automatizar.instalar(ns.n, ns.hora)
    if ns.cmd == "metricas":
        return metricas()
    if ns.cmd == "panel":
        from .panel import abrir
        return abrir(ns.puerto, navegador=not ns.sin_navegador)
    if ns.cmd == "preparar":
        from . import config
        from .preparar import preparar
        config.cargar()
        return preparar(ns.n, ns.paralelo)
    if ns.cmd == "iniciar":
        from . import iniciar
        return iniciar.asistente()
    if ns.cmd == "gmail":
        return conectar_gmail()
    if ns.cmd == "buscar":
        return buscar(ns.comunas, ns.limite, ns.fuente)
    if ns.cmd == "analizar":
        return cmd_analizar(ns.todas, ns.concurrencia)
    if ns.cmd == "lista":
        return lista(ns.todas)
    return baja(ns.valor, ns.motivo)
