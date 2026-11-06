"""
La primera vez: quién eres y a quién le vendes.

    python prospector.py iniciar

Hace unas preguntas y crea nicho.json, negocio.md, firma.txt y comunas.txt, que
son tuyos y no se suben al repo. Sin ellos el agente no tiene de quién hablar, así
que no investiga: un correo con la experiencia de otro sería mentirle a quien lo recibe.

No pisa nada: lo que ya existe, no lo toca.
"""

import re

from . import config, gmail, nicho
from .puente import RAIZ, paises

EJEMPLO = RAIZ / "negocio.ejemplo.md"
NEGOCIO = RAIZ / "negocio.md"
COMUNAS = RAIZ / "comunas.txt"
HUECO = re.compile(r"\{[A-ZÁÉÍÓÚÑ_ ]+\}")
LINEA_BAJA = "Si prefieres que no te escriba más, respóndeme «baja» y no te escribo más."
INMOBILIARIAS = re.compile(r"inmobiliari|corredor[ae]s? de propiedades|bienes ra[ií]ces", re.I)
SIN_CASO = "Todavía no hay un caso para contar. Cuando lo tengas, escríbelo aquí, con su resultado solo si lo mediste."


def pendiente() -> str:
    """Qué falta para poder redactar, o "" si está todo."""
    if not nicho.existe():
        return "Falta nicho.json. Corre primero:  python prospector.py iniciar"
    for ruta, nombre in ((NEGOCIO, "negocio.md"), (gmail.FIRMA, "firma.txt")):
        if not ruta.exists():
            return f"Falta {nombre}. Corre primero:  python prospector.py iniciar"
        if HUECO.search(ruta.read_text(encoding="utf-8")):
            return f"{nombre} tiene huecos {{...}} sin rellenar. Complétalos antes de seguir."
    return ""


def redactar(r: dict, n: dict) -> tuple[str, str]:
    """(negocio.md, firma.txt) a partir de las respuestas y el nicho."""
    t = n.get("textos") or {}
    rubro = n.get("rubro", "negocios")
    marca, web = r.get("marca", "").strip(), r.get("web", "").strip()
    resultado = (r.get("resultado") or t.get("resultado") or "").strip().rstrip(".")
    que_hago = f" a {resultado}" if resultado else ""
    if r.get("tiempo") and r.get("cuantas"):
        logro = (r.get("logro") or t.get("logro") or "").strip()
        frase = f"Trabajo justo en esto: llevo {r['tiempo'].strip()} ayudando a {r['cuantas'].strip()} {rubro}{que_hago}."
        frase += f" {logro}" if logro else ""
        cierre = "Si quieres, te cuento cómo lo hemos resuelto en otros negocios como el tuyo: basta con que respondas este correo."
    else:
        # Sin clientes todavía se dice lo que haces, no lo que ya hiciste.
        frase = f"Trabajo justo en esto: ayudo a {rubro}{que_hago}."
        cierre = "Si quieres, te cuento cómo lo resolvería en su caso: basta con que respondas este correo."
    texto = EJEMPLO.read_text(encoding="utf-8")
    for clave, valor in {
        "{NOMBRE}": r["nombre"].strip(), "{DE_MARCA}": f", de {marca}" if marca else "",
        "{RUBRO}": rubro,
        "{OFERTA}": r.get("oferta", "").strip() or f"Ayudo a {rubro}{que_hago}.",
        "{PROBLEMA}": (r.get("problema") or t.get("problema") or "(escribe aquí el problema que resuelves)").strip(),
        "{ICP_SI}": t.get("icp_si") or f"{rubro} con equipo. Se le escribe al dueño o gerente.",
        "{ICP_NO}": t.get("icp_no") or "Negocios de una sola persona, cadenas con sistema corporativo y webs abandonadas.",
        "{FRASE_EXPERIENCIA}": frase, "{CIERRE}": cierre, "{CIUDAD}": r["ciudad"].strip(),
        "{CASO}": r.get("caso", "").strip() or SIN_CASO,
    }.items():
        texto = texto.replace(clave, valor)
    linea = " · ".join(x for x in (marca, web) if x)
    firma = "\n".join(x for x in (r["nombre"].strip(), linea) if x) + f"\n\n{LINEA_BAJA}\n"
    return texto, firma


def crear(r: dict, n: dict) -> list[str]:
    """Escribe lo que falte y devuelve qué creó. Lo que ya existe no se toca."""
    creados = []
    if not nicho.existe():
        nicho.guardar(n)
        creados.append(nicho.ARCHIVO.name)
    negocio, firma = redactar(r, n)
    comunas = ("# Comunas o ciudades por barrer, en orden. Una por línea.\n"
               "# Cuando `preparar` se queda sin candidatos, sigue con la primera que falte.\n"
               + r["ciudad"].strip() + "\n")
    for ruta, contenido in ((NEGOCIO, negocio), (gmail.FIRMA, firma), (COMUNAS, comunas)):
        if not ruta.exists():
            ruta.write_text(contenido, encoding="utf-8")
            creados.append(ruta.name)
    return creados


def _lista(texto: str) -> list[str]:
    return [x.strip() for x in texto.split(",") if x.strip()]


def _elegir_nicho(pedir, rubro: str, pais_codigo: str, oferta: str, proponer) -> dict:
    if INMOBILIARIAS.search(rubro):
        print("\n  Para inmobiliarias ya hay un nicho probado. Uso ese como base.")
        n = nicho.ejemplo("inmobiliarias")
        if n["pais"] != pais_codigo:
            # El filtro sirve, pero los portales son de Chile.
            n.update(pais=pais_codigo, portales={}, directorios=[])
        return n
    print("\n  Le pido a Claude una propuesta para tu rubro (menos de un minuto)...")
    try:
        n = proponer(rubro, pais_codigo, oferta)
        print(f"\n  Rubro: {n['rubro']}")
        print(f"  Buscaré en Maps: {', '.join(n['busquedas'])}")
        print(f"  Sirve si su web dice: {', '.join(n.get('confirman_en_web', [])[:6])}...")
        descartes = [f"{x['tipo']} ({x.get('motivo', '')})" for x in n.get("descartar", [])]
        print(f"  Descarta: {', '.join(descartes) or 'nada en especial'}")
        print(f"  Problema: {(n.get('textos') or {}).get('problema', '')}")
        if not pedir("¿Te parece bien? La puedes afinar después en nicho.json (s/n)").lower().startswith("n"):
            return n
    except Exception as e:
        print(f"  No se pudo ({e}). Lo hacemos a mano.")
    return nicho.manual(
        rubro, pais_codigo,
        _lista(pedir(f"¿Qué escribirías en Google Maps para encontrar {rubro}? (separa con comas)", True)),
        _lista(pedir("Palabras que tendría la web de uno de estos negocios (separa con comas, Enter para saltar)")))


def asistente(preguntar=input, proponer=nicho.proponer) -> int:
    if nicho.existe() and NEGOCIO.exists() and gmail.FIRMA.exists():
        print("Ya tienes nicho.json, negocio.md y firma.txt: no toco nada. Edítalos a mano si algo cambió.")
        return 0

    def pedir(texto: str, obligatorio: bool = False) -> str:
        while True:
            valor = preguntar(f"  {texto}: ").strip()
            if valor or not obligatorio:
                return valor
            print("    Este dato hace falta.")

    print("\nUnas preguntas para que los correos hablen de ti. Solo cosas verdaderas:")
    print("lo que digas aquí es lo que leerán tus prospectos.\n")
    r = {"nombre": pedir("Tu nombre y apellido", True),
         "marca": pedir("Tu marca o empresa (Enter si no tienes)"),
         "web": pedir("Tu web (Enter si no tienes)")}
    while True:
        codigo = (pedir("Código de tu país, por ejemplo CL, MX, AR, CO, ES (Enter para CL)") or "CL").upper()
        if codigo in paises.PAISES:
            break
        print(f"    No lo conozco. Estos sí: {paises.listado()}")
    r["ciudad"] = pedir("La ciudad o comuna donde quieres empezar a buscar", True)
    rubro = pedir("¿A qué rubro le vendes? (por ejemplo: clínicas dentales, gimnasios)", True)
    r["oferta"] = pedir("¿Qué le ofreces, en una frase?", True)
    n = nicho.actual() if nicho.existe() else _elegir_nicho(pedir, rubro, codigo, r["oferta"], proponer)
    if not (n.get("textos") or {}).get("problema"):
        r["problema"] = pedir("¿Qué problema concreto les resuelves?", True)
    if not (n.get("textos") or {}).get("resultado"):
        r["resultado"] = pedir('¿Qué logras para ellos? En infinitivo (ej: "responder consultas al instante")', True)
    if pedir("¿Ya hiciste esto para algún cliente de este rubro? (s/n)").lower().startswith("s"):
        r["tiempo"] = pedir('¿Hace cuánto? (ej: "un año")', True)
        r["cuantas"] = pedir('¿A cuántos? (ej: "tres", "más de 10")', True)
        r["logro"] = pedir("¿Qué logran? Sin números que no hayas medido (Enter para saltar)")
        r["caso"] = pedir("Un caso real en una línea (Enter si prefieres no contarlo)")
    creados = crear(r, n)
    config.guardar({"GMAIL_NOMBRE": r["nombre"]})
    print(f"\n  Listo: {', '.join(creados) or 'no hacía falta crear nada'}. Revísalos cuando quieras.")
    print("  Siguiente:  python prospector.py gmail")
    return 0
