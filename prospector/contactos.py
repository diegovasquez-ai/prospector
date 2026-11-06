"""
Prueba de Treg (treg.to): ¿encuentra y verifica el correo del decisor de
nuestros negocios? Solo mira y cuenta: no toca borradores ni la base.

    python prospector.py treg                conectar: pide el token, lo prueba, lo guarda en .env
    python prospector.py contactos           la prueba, con tope de gasto (US$0,80)

Tres preguntas, en orden de valor:

  1. Precisión. Donde el decisor ya publica su correo ,
     ¿Treg devuelve ese mismo? Si acierta ahí, se le puede creer en el resto.
  2. Lo que falta. Donde escribimos a un genérico (contacto@, info@),
     ¿encuentra el del decisor y la verificación dice que el buzón existe?
  3. Cobertura. En las candidatas aún sin investigar, ¿sus bases conocen a
     alguien de la empresa con cargo de decisión?

De paso verifica los correos a los que ya pensamos escribir: un rebote desde
tu Gmail principal sale caro.

Cada respuesta buena se guarda en datos/treg.json y no se vuelve a pedir:
Treg cobra cada acierto, también los repetidos.
"""

import json
import re
import unicodedata
from datetime import datetime

import httpx

from . import base as bd
from . import config, correos
from .analizar import clasificar_correo
from .puente import RAIZ, exclusiones

URL = "https://treg.to"
CACHE = RAIZ / "datos" / "treg.json"
INFORME = RAIZ / "datos" / "treg-prueba.md"
TOPE_LLAMADA = "0.10"  # USD: Treg rechaza (sin cobrar) la llamada que lo pasaría
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Palabras completas: "corredor asociado" contiene "socia" y es justo un agente, no quien decide.
DECIDE = re.compile(r"\b(ceo|gerente|fundador|fundadora|cofundador|cofundadora|socio|socia|socios|"
                    r"director|directora|dueno|duena|owner|founder|co-founder|partner|presidente|"
                    r"managing|broker|propietari[oa])\b")


class SinSaldo(Exception):
    pass


class TopeAlcanzado(Exception):
    pass


def _plano(s: str) -> str:
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def decide(cargo: str) -> bool:
    return bool(DECIDE.search(_plano(cargo)))


# --- Cliente ---------------------------------------------------------------------

class Treg:
    def __init__(self, token: str, org: str = "", tope_usd: float = 0.8, http: httpx.Client | None = None):
        self.cab = {"X-Treg-Token": token}
        if org:
            self.cab["X-Treg-Org"] = org
        self.tope = int(tope_usd * 1_000_000)
        self.gastado = 0
        self.llamadas = 0
        self.http = http or httpx.Client(timeout=90)
        self.cache: dict = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    def probar(self) -> str:
        """Una lectura sin costo para saber si el token sirve."""
        try:
            r = self.http.get(f"{URL}/tools", headers=self.cab)
        except httpx.HTTPError as e:
            return f"No pude llegar a treg.to: {type(e).__name__}"
        if r.status_code in (401, 403):
            return "Treg no acepta ese token"
        if r.status_code >= 400:
            return f"Treg respondió {r.status_code}: {r.text[:200]}"
        return ""

    def llamar(self, herramienta: str, cuerpo: dict, verificar: bool = False) -> dict:
        clave = f"{herramienta} {json.dumps(cuerpo, sort_keys=True, ensure_ascii=False)}{' +v' if verificar else ''}"
        if clave in self.cache:
            return self.cache[clave] | {"cache": True}
        if self.gastado >= self.tope:
            raise TopeAlcanzado
        cab = self.cab | {"X-Treg-Route-Max-Cost": TOPE_LLAMADA}
        if verificar:
            cab["X-Treg-Route-Verify"] = "true"
        r = self.http.post(f"{URL}/call/{herramienta}", headers=cab, json=cuerpo)
        self.llamadas += 1
        try:
            datos = r.json()
        except ValueError:
            datos = {"texto": r.text[:500]}
        meta = datos.get("_treg") if isinstance(datos, dict) and isinstance(datos.get("_treg"), dict) else {}
        if r.status_code == 402 and isinstance(datos, dict) and datos.get("error") == "insufficient_balance":
            raise SinSaldo(datos.get("topup_url", "https://treg.to"))
        costo = int(r.headers.get("X-Treg-Cost-Micro") or meta.get("charged_micro") or 0)
        self.gastado += costo
        res = {"status": r.status_code, "costo_micro": costo,
               "servido_por": r.headers.get("X-Treg-Served-By") or meta.get("served_by", ""),
               "coincide": r.headers.get("X-Treg-Domain-Match") or meta.get("domain_match", ""),
               "datos": datos, "fecha": datetime.now().isoformat(timespec="seconds")}
        # Solo lo bueno se guarda: un 5xx pasajero no debe quedar como respuesta para siempre.
        if r.status_code < 400:
            self.cache[clave] = res
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        return res


# --- Leer respuestas -----------------------------------------------------------------
# El formato de cada proveedor varía y Treg lo devuelve tal cual en "output":
# se busca con tolerancia y, ante la duda, se deja vacío antes que inventar.

def _salida(res: dict):
    d = res.get("datos")
    return d.get("output") if isinstance(d, dict) else None


def _meta(res: dict) -> dict:
    d = res.get("datos")
    return d.get("_treg") if isinstance(d, dict) and isinstance(d.get("_treg"), dict) else {}


def correo_de(res: dict, dominio: str) -> str:
    if res.get("status", 500) >= 400:
        return ""
    out = _salida(res)
    if isinstance(out, dict):
        for k in ("email", "email_address", "work_email", "address", "value"):
            v = out.get(k)
            if isinstance(v, str) and EMAIL.fullmatch(v.strip()):
                return v.strip().lower()
    if isinstance(out, str) and EMAIL.fullmatch(out.strip()):
        return out.strip().lower()
    # Último recurso: un correo de SU dominio en cualquier parte de la salida.
    for c in EMAIL.findall(json.dumps(out, ensure_ascii=False)):
        if c.lower().split("@")[1].endswith(dominio):
            return c.lower()
    return ""


def veredicto(res: dict) -> str:
    """valid · accept_all (riesgo: el dominio acepta todo) · invalid · '' si no se verificó."""
    v = _meta(res).get("verification")
    if isinstance(v, dict) and v.get("verdict"):
        return str(v["verdict"])
    out = _salida(res)
    if isinstance(out, dict):
        for k in ("status", "result", "verdict"):
            if isinstance(out.get(k), str) and out[k]:
                return out[k]
        if isinstance(out.get("valid"), bool):
            return "valid" if out["valid"] else "invalid"
    return ""


def personas_de(res: dict) -> list[dict]:
    if res.get("status", 500) >= 400:
        return []
    out = _salida(res)
    filas = out if isinstance(out, list) else []
    if isinstance(out, dict):
        for k in ("people", "results", "rows", "data", "persons", "items", "contacts"):
            if isinstance(out.get(k), list):
                filas = out[k]
                break
    personas = []
    for f in filas:
        if not isinstance(f, dict):
            continue
        nombre = (f.get("full_name") or f.get("name")
                  or " ".join(str(x) for x in (f.get("first_name"), f.get("last_name")) if x))
        cargo = (f.get("title") or f.get("job_title") or f.get("position")
                 or f.get("headline") or f.get("role") or "")
        if nombre:
            personas.append({"nombre": str(nombre).strip(), "cargo": str(cargo).strip()})
    return personas


# --- La prueba ------------------------------------------------------------------------

def _es_persona(correo: str, dominio: str) -> bool:
    return clasificar_correo(correo, {dominio})[0] == "persona"


def plan() -> list[dict]:
    """Qué se va a preguntar, en orden de valor. Aquí no se gasta nada."""
    fuera = exclusiones.cargar()
    tareas = []
    borradores = correos.listar()
    vistos = {b["dominio"] for b in borradores}  # ya investigadas, también las descartadas
    for b in borradores:
        if b.get("estado") not in ("por revisar", "aprobado"):
            continue
        dom, d = b["dominio"], b.get("decisor") or {}
        if d.get("nombre"):
            publicado = b.get("para", "") if _es_persona(b.get("para", ""), dom) else ""
            tareas.append({"tipo": "decisor", "dominio": dom, "empresa": b.get("nombre", dom),
                           "persona": d["nombre"], "para": b.get("para", ""), "publicado": publicado})
        if b.get("para"):
            tareas.append({"tipo": "verificar", "dominio": dom, "empresa": b.get("nombre", dom), "correo": b["para"]})
    base = bd.cargar()
    libres = sorted((l for k, l in base.items()
                     if l.get("estado") in ("candidata", "sin correo") and k not in vistos
                     and not k.startswith("n:") and not bd.bloqueado(l, fuera)),
                    key=lambda l: -l.get("puntaje", 0))
    for l in libres:
        k = bd.clave(l)
        tareas.append({"tipo": "equipo", "dominio": k, "empresa": l.get("nombre", k)})
        if l.get("correo"):
            tareas.append({"tipo": "verificar", "dominio": k, "empresa": l.get("nombre", k), "correo": l["correo"]})
    return tareas


def _buscar(t: Treg, persona: str, dominio: str) -> dict:
    res = t.llamar("treg.people.email.find", {"full_name": persona, "domain": dominio}, verificar=True)
    return {"correo": correo_de(res, dominio), "veredicto": veredicto(res), "proveedor": res.get("servido_por", ""),
            "coincide": res.get("coincide", ""), "costo": res.get("costo_micro", 0), "status": res.get("status")}


def ejecutar(tareas: list[dict], t: Treg, log=print) -> tuple[list[dict], str]:
    """Hace las llamadas en orden hasta acabar, quedarse sin saldo o tocar el tope."""
    hechas = []
    for tarea in tareas:
        r = dict(tarea)
        try:
            if tarea["tipo"] == "decisor":
                r |= _buscar(t, tarea["persona"], tarea["dominio"])
            elif tarea["tipo"] == "verificar":
                res = t.llamar("treg.people.email.verify", {"email": tarea["correo"]})
                r |= {"veredicto": veredicto(res), "costo": res.get("costo_micro", 0), "status": res.get("status")}
            else:
                res = t.llamar("treg.people.search", {"domain": tarea["dominio"]})
                gente = personas_de(res)
                jefes = [p for p in gente if decide(p["cargo"])]
                r |= {"personas": len(gente), "decisores": jefes[:3], "costo": res.get("costo_micro", 0),
                      "status": res.get("status")}
                if jefes:
                    r["hallazgo"] = _buscar(t, jefes[0]["nombre"], tarea["dominio"])
        except TopeAlcanzado:
            return hechas, "tope"
        except SinSaldo as e:
            return hechas, f"sin saldo ({e})"
        except httpx.HTTPError as e:
            r["error"] = type(e).__name__
        hechas.append(r)
        log(f"  · {tarea['tipo']:<9} {tarea['empresa'][:32]}")
    return hechas, ""


def informe(hechas: list[dict], t: Treg, corte: str) -> str:
    L = [f"# Prueba de Treg · {datetime.now():%Y-%m-%d %H:%M}", ""]
    usd = lambda m: f"US${m / 1e6:.4f}"  # noqa: E731

    def linea_hallazgo(h: dict) -> str:
        if h.get("status", 200) >= 400:
            return f"error {h['status']}"
        if not h.get("correo"):
            return "no lo encontró"
        extra = [h.get("veredicto") or "sin verificar", h.get("proveedor") or "?"]
        if str(h.get("coincide")).lower() == "false":
            extra.append("OJO: otro dominio (¿empleo anterior?)")
        return f"{h['correo']} · " + " · ".join(extra)

    precision = [h for h in hechas if h["tipo"] == "decisor" and h.get("publicado")]
    faltan = [h for h in hechas if h["tipo"] == "decisor" and not h.get("publicado")]
    verif = [h for h in hechas if h["tipo"] == "verificar"]
    equipo = [h for h in hechas if h["tipo"] == "equipo"]

    L += ["## 1. Precisión: decisores que ya publican su correo", ""]
    for h in precision:
        igual = "✓ el mismo" if h.get("correo") == h["publicado"].lower() else "✗ distinto"
        L.append(f"- **{h['empresa']}** · {h['persona']}: publicado `{h['publicado']}` → Treg: "
                 f"{linea_hallazgo(h)}" + (f" · {igual}" if h.get("correo") else ""))
    L += ["", "## 2. El correo del decisor donde hoy va a otro", ""]
    for h in faltan:
        L.append(f"- **{h['empresa']}** · {h['persona']} (hoy: `{h['para'] or '—'}`) → {linea_hallazgo(h)}")
    L += ["", "## 3. Verificación de los correos a los que escribiríamos", ""]
    for h in verif:
        L.append(f"- `{h['correo']}` ({h['empresa']}): " + (f"error {h['status']}" if h.get("status", 200) >= 400
                                                              else h.get("veredicto") or "sin respuesta clara"))
    L += ["", "## 4. Cobertura en candidatas sin investigar", ""]
    for h in equipo:
        if h.get("status", 200) >= 400:
            L.append(f"- **{h['empresa']}**: error {h['status']}")
            continue
        jefes = ", ".join(f"{p['nombre']} ({p['cargo'][:40]})" for p in h.get("decisores", []))
        L.append(f"- **{h['empresa']}**: {h.get('personas', 0)} personas en sus bases"
                 + (f"; decisores: {jefes}" if jefes else "; ningún decisor")
                 + (f" → {linea_hallazgo(h['hallazgo'])}" if h.get("hallazgo") else ""))

    hallados = [h for h in faltan + precision if h.get("correo")]
    validos = [h for h in hallados if h.get("veredicto") == "valid"]
    con_jefe = [h for h in equipo if h.get("decisores")]
    L += ["", "## Resumen", "",
          f"- Precisión: {sum(1 for h in precision if h.get('correo') == h['publicado'].lower())} de {len(precision)} iguales al publicado",
          f"- Correo del decisor encontrado: {len(hallados)} de {len(precision) + len(faltan)}, verificados como válidos {len(validos)}",
          "- Verificaciones: " + " · ".join(f"{v} {n}" for v, n in _contar(h.get("veredicto") or "?" for h in verif)),
          f"- Cobertura: {len(con_jefe)} de {len(equipo)} candidatas con algún decisor en sus bases",
          f"- Gasto de esta corrida: {usd(t.gastado)} en {t.llamadas} llamadas (lo repetido salió de la caché, gratis)"]
    if corte:
        L.append(f"- **Se paró antes de terminar: {corte}.** Lo hecho queda en caché; al volver a correr sigue donde quedó.")
    return "\n".join(L) + "\n"


def _contar(valores) -> list[tuple[str, int]]:
    c: dict[str, int] = {}
    for v in valores:
        c[v] = c.get(v, 0) + 1
    return sorted(c.items(), key=lambda x: -x[1])


# --- Comandos -------------------------------------------------------------------------

def conectar() -> int:
    from getpass import getpass
    config.cargar()
    print("\n  Conectar Treg (2 minutos)")
    print("    1. Entra en https://treg.to e inicia sesión (GitHub o correo). Te regalan US$1.")
    print("    2. En el dashboard crea una API key de tu equipo y cópiala.")
    print("       (Con la CLI también sirve: treg org agent-new prospector)\n")
    token = getpass("  Token (no se ve al escribir): ").strip()
    if not token:
        print("  Sin token no guardé nada.")
        return 1
    org = input("  Slug del equipo (Enter si la key es de equipo): ").strip()
    error = Treg(token, org).probar()
    if error:
        print(f"  ! {error}. No guardé nada.")
        return 1
    config.guardar({"TREG_TOKEN": token, **({"TREG_ORG": org} if org else {})})
    print("  ✓ Treg conectado. Guardado en .env.")
    print("\n  Siguiente: python prospector.py contactos")
    return 0


def prueba(tope: float, sin_preguntar: bool) -> int:
    config.cargar()
    token = config.texto("TREG_TOKEN")
    if not token:
        print("  Falta el token. Primero:  python prospector.py treg")
        return 1
    tareas = plan()
    if not tareas:
        print("  No hay nada que probar: ni borradores ni candidatas.")
        return 0
    n = _contar(t["tipo"] for t in tareas)
    print("\n  La prueba hará: " + " · ".join(f"{k} {v}" for k, v in n))
    print(f"  Tope de gasto: US${tope:.2f} (cada llamada, como mucho US${TOPE_LLAMADA}). No toca borradores ni la base.")
    if not sin_preguntar and input("  ¿Sigo? [s/N] ").strip().lower() not in ("s", "si", "sí"):
        print("  No hice nada.")
        return 0
    t = Treg(token, config.texto("TREG_ORG"), tope)
    hechas, corte = ejecutar(tareas, t)
    texto = informe(hechas, t, corte)
    INFORME.parent.mkdir(parents=True, exist_ok=True)
    INFORME.write_text(texto, encoding="utf-8")
    print("\n" + texto)
    print(f"  Guardado en {INFORME}")
    return 0
