"""
A quién le vendes: nicho.json.

El motor (buscar en Maps, visitar webs, medir señales, enviar) sirve para
cualquier rubro. Lo que cambia entre dentistas y corredoras vive en este archivo:
qué buscar, cómo reconocer un negocio que sirve y a quién descartar.

    nichos/inmobiliarias.json    un ejemplo completo y probado
    nicho.json                   el tuyo. Lo crea `python prospector.py iniciar`

Claude puede proponer uno para tu rubro (proponer). Es un punto de partida: se
afina mirando qué descarta y qué deja pasar `python prospector.py lista`.
"""

import json
import re
import shutil
import subprocess
import tempfile

from .puente import RAIZ, paises

ARCHIVO = RAIZ / "nicho.json"
EJEMPLOS = RAIZ / "nichos"
NUNCA = re.compile(r"(?!x)x")  # un patrón que no encuentra nada


def existe() -> bool:
    return ARCHIVO.exists()


def _vacio() -> dict:
    return {"rubro": "negocios", "singular": "negocio", "pais": "CL", "busquedas": [],
            "confirman_en_nombre": [], "confirman_en_web": [], "descartar": [], "cadenas": [],
            "portales": {}, "directorios": [], "sistemas": {}, "catalogo": {}, "paginas_equipo": [],
            "textos": {}}


def _leido() -> tuple[int, dict]:
    if not ARCHIVO.exists():
        return 0, {}
    return ARCHIVO.stat().st_mtime_ns, json.loads(ARCHIVO.read_text(encoding="utf-8"))


_cache: tuple[tuple, dict] = ((), {})


def actual() -> dict:
    """El nicho activo, con todo lo opcional relleno. Se relee si cambió el archivo."""
    global _cache
    firma = (str(ARCHIVO),) + (ARCHIVO.stat().st_mtime_ns,) if ARCHIVO.exists() else (str(ARCHIVO), 0)
    if _cache[0] != firma:
        _cache = (firma, {**_vacio(), **_leido()[1]})
    return _cache[1]


def pais():
    return paises.obtener(actual().get("pais") or "CL")


def validar(d) -> list[str]:
    """Qué le falta o qué está mal. Una lista vacía es que sirve."""
    if not isinstance(d, dict):
        return ["no es un objeto JSON"]
    malos = []
    if not (isinstance(d.get("rubro"), str) and d["rubro"].strip()):
        malos.append("falta «rubro»")
    if not (isinstance(d.get("busquedas"), list) and d["busquedas"]
            and all(isinstance(x, str) and x.strip() for x in d["busquedas"])):
        malos.append("«busquedas» necesita al menos una búsqueda para Google Maps")
    try:
        paises.obtener(d.get("pais") or "")
    except KeyError:
        malos.append(f"país desconocido: {d.get('pais')!r}. Usa uno de: {paises.listado()}")
    for clave in ("confirman_en_nombre", "confirman_en_web", "cadenas", "directorios", "paginas_equipo"):
        if not isinstance(d.get(clave, []), list):
            malos.append(f"«{clave}» debe ser una lista")
    for clave in ("portales", "sistemas", "catalogo", "textos"):
        if not isinstance(d.get(clave, {}), dict):
            malos.append(f"«{clave}» debe ser un objeto")
    reglas = d.get("descartar", [])
    if not isinstance(reglas, list) or not all(isinstance(r, dict) and r.get("tipo") for r in reglas):
        malos.append("cada regla de «descartar» necesita un «tipo»")
    return malos


def guardar(d: dict) -> None:
    malos = validar(d)
    if malos:
        raise ValueError("; ".join(malos))
    ARCHIVO.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ejemplo(nombre: str = "inmobiliarias") -> dict:
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


# --- Lo que usa el analizador -----------------------------------------------------

def _alternativas(palabras) -> str:
    return "|".join(re.escape(p).replace(r"\ ", r"[\s-]*") for p in palabras if p)


def rx_equipo():
    base = r"equipo|nosotros|qui[eé]nes[\s-]*somos|team|about|staff"
    extra = _alternativas(actual().get("paginas_equipo") or [])
    return re.compile(base + ("|" + extra if extra else ""), re.I)


def rx_catalogo():
    palabras = _alternativas((actual().get("catalogo") or {}).get("paginas") or [])
    return re.compile(palabras, re.I) if palabras else NUNCA


def rx_detalle():
    palabras = _alternativas((actual().get("catalogo") or {}).get("enlace_detalle") or [])
    return re.compile(rf"(?:{palabras})[^?#]*\d", re.I) if palabras else NUNCA


def rx_conteo():
    # Sin pegarse a otro número ("9 9309 9187 propiedades@..." es un teléfono
    # seguido de un correo, no 9187 propiedades) ni seguir en un correo o dominio.
    palabras = _alternativas((actual().get("catalogo") or {}).get("conteo") or [])
    if not palabras:
        return NUNCA
    return re.compile(r"(?<![\d+])(?<!\d[\s\-])(\d{1,2}[.,]\d{3}|\d{1,5})\s+"
                      rf"(?:{palabras})\b(?![@.\-]\w)", re.I)


# --- Que Claude proponga uno ------------------------------------------------------

PROMPT = """Vas a configurar una herramienta de correo frío B2B. Busca negocios en Google Maps,
visita sus webs y descarta los que no sirven. Devuelve la configuración para este caso:

Rubro al que le vende: {rubro}
País (código): {pais}
Qué ofrece: {oferta}

Responde SOLO con un JSON así, sin nada antes ni después:

{{
  "rubro": "el rubro en plural y minúscula, como se diría en una frase",
  "singular": "un solo negocio de ese rubro, en una palabra si se puede",
  "pais": "{pais}",
  "busquedas": ["2 a 4 búsquedas tal como se escribirían en Google Maps en ese país"],
  "confirman_en_nombre": ["raíces cortas que, en el nombre del negocio, confirman el rubro"],
  "confirman_en_web": ["8 a 12 palabras o frases que usaría la web de un negocio de este rubro, sin acentos y en minúscula"],
  "descartar": [
    {{"tipo": "una palabra para el negocio parecido que NO sirve",
      "motivo": "por qué no sirve",
      "en_categoria": ["raíces de categorías de Maps de ese negocio parecido"],
      "en_web": ["frases sin acentos, en minúscula, propias de ese negocio y no del rubro buscado"],
      "min_web": 2}}
  ],
  "cadenas": ["marcas de cadenas o franquicias grandes del rubro en ese país, en minúscula"],
  "portales": {{"Nombre del directorio o portal del rubro": "dominio.com"}},
  "directorios": ["directorios genéricos que Maps podría poner como su web"],
  "sistemas": {{"Software típico del rubro": ["huella en el HTML, en minúscula"]}},
  "catalogo": {{"etiqueta": "lo que el negocio publica en su web, en plural (servicios, productos...), o vacío si no aplica",
               "paginas": ["palabras en el menú de esa página"],
               "enlace_detalle": ["palabras en la URL de cada ficha"],
               "conteo": ["palabras que siguen a una cantidad"],
               "minimo": 30}},
  "paginas_equipo": ["cómo llama este rubro a su página de equipo"],
  "textos": {{
    "problema": "el problema concreto que resuelve la oferta para este rubro, en una frase",
    "resultado": "qué logra para ellos, en infinitivo y sin nombrar la herramienta",
    "logro": "",
    "icp_si": "qué negocio sirve y a quién se le escribe (dueño, gerente...)",
    "icp_no": "a quién no se le escribe"
  }}
}}

Sé conservador: una palabra demasiado común descarta negocios buenos. No inventes
portales ni software: si no estás seguro, deja la lista vacía. "logro" va vacío siempre.
"""


def proponer(rubro: str, pais_codigo: str, oferta: str, correr=subprocess.run) -> dict:
    """Pide a Claude un nicho para este rubro. Sin herramientas: solo responde texto."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("No encuentro el comando claude")
    prompt = PROMPT.format(rubro=rubro.strip(), pais=pais_codigo.strip().upper(), oferta=oferta.strip() or "(sin detallar)")
    # En una carpeta vacía: no necesita leer nada de este proyecto.
    with tempfile.TemporaryDirectory(prefix="prospector-nicho-") as vacia:
        r = correr([exe, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config"],
                   input=prompt.encode("utf-8"), capture_output=True, cwd=vacia, timeout=240)
    salida = r.stdout.decode("utf-8", errors="replace")
    try:
        texto = json.loads(salida).get("result", "")
    except json.JSONDecodeError:
        texto = salida
    m = re.search(r"\{.*\}", texto, re.S)
    if r.returncode != 0 or not m:
        raise RuntimeError("Claude no devolvió una propuesta")
    d = json.loads(m.group(0))
    malos = validar(d)
    if malos:
        raise RuntimeError("La propuesta no sirve: " + "; ".join(malos))
    return d


def manual(rubro: str, pais_codigo: str, busquedas: list[str], palabras: list[str]) -> dict:
    """Lo mínimo para partir sin Claude."""
    return {**_vacio(), "rubro": rubro.strip(), "singular": rubro.strip(),
            "pais": pais_codigo.strip().upper(), "busquedas": busquedas, "confirman_en_web": palabras}
