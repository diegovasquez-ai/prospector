#!/usr/bin/env python3
"""
Las pruebas del Prospector. Sin pytest, sin internet y sin enviar nada.

    python pruebas.py

Gmail se sustituye por un SMTP falso y todo se escribe en una carpeta
temporal: ni tus borradores ni tu lista negra se tocan.
"""

import http.client
import json
import os
import smtplib
import subprocess
import sys
import tempfile
import threading
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bs4 import BeautifulSoup

from prospector import analizar, base, cli, config, correos, envio, gmail, iniciar, nicho, panel, preparar, puente, whatsapp
from prospector.puente import exclusiones

_ok = _mal = 0


def comprobar(desc, obtenido, esperado):
    global _ok, _mal
    if obtenido == esperado:
        _ok += 1
        print(f"  ok    {desc}")
    else:
        _mal += 1
        print(f"  FALLA {desc}\n          esperaba {esperado!r}\n          obtuve   {obtenido!r}")


def seccion(titulo):
    print(f"\n{titulo}")


# --- todo a una carpeta temporal ---------------------------------------------
TMP = Path(tempfile.mkdtemp(prefix="prospector-"))
correos.CARPETA = TMP / "borradores"
envio.ESTADO = TMP / "envio.json"
gmail.FIRMA = TMP / "firma.txt"
panel.FICHAS = analizar.FICHAS = TMP / "fichas"
exclusiones.ARCHIVO = TMP / "lista-negra.txt"
base.ARCHIVO = TMP / "negocios.json"
nicho.ARCHIVO = TMP / "nicho.json"
nicho.guardar(nicho.ejemplo("inmobiliarias"))
iniciar.COMUNAS = TMP / "comunas-iniciar.txt"
os.environ.update(GMAIL_USUARIO="yo@gmail.com", GMAIL_CLAVE_APP="abcd efgh ijkl mnop",
                  ENVIO_MAX_DIA="2", ENVIO_HORARIO="9-18", ENVIO_PAUSA="6-18")
FIRMA_OK = "Ana Pérez\nMarca · marca.cl\nAv. Principal 123, Las Condes\n\nSi prefieres que no te escriba más, respóndeme «baja»."
gmail.FIRMA.write_text(FIRMA_OK, encoding="utf-8")
iniciar.NEGOCIO = TMP / "negocio.md"
iniciar.NEGOCIO.write_text("# Negocio de prueba", encoding="utf-8")


seccion("Autónomo y sin datos de nadie")
comprobar("el motor vive dentro del proyecto",
          Path(puente.descubrir.__code__.co_filename).is_relative_to(puente.RAIZ), True)
comprobar("no carga nada de una carpeta hermana",
          [m for m in sys.modules if m.split(".")[0] == "cazador"], [])
_n = nicho.ejemplo("inmobiliarias")
_t, _f = iniciar.redactar({"nombre": "Ana Pérez", "marca": "Marca", "web": "marca.cl", "ciudad": "Temuco"}, _n)
comprobar("sin experiencia no inventa clientes", ("llevo" in _t, "otros negocios" in _t), (False, False))
comprobar("no deja huecos ni en el negocio ni en la firma", (iniciar.HUECO.findall(_t), iniciar.HUECO.findall(_f)), ([], []))
comprobar("la firma lleva quién es y la baja", ("Ana Pérez" in _f, "Marca · marca.cl" in _f, "«baja»" in _f), (True, True, True))
_t, _ = iniciar.redactar({"nombre": "Ana", "ciudad": "Temuco", "tiempo": "dos años", "cuantas": "tres", "caso": "Un caso real."}, _n)
comprobar("con experiencia usa la suya", ("llevo dos años ayudando a tres corredoras de propiedades" in _t, "Un caso real." in _t), (True, True))
_f = gmail.firma()
comprobar("nada de esto pisa lo que ya existe", [x for x in iniciar.crear({"nombre": "Otra", "ciudad": "X"}, _n) if x != "comunas-iniciar.txt"], [])
comprobar("y la firma sigue igual", gmail.firma(), _f)
comprobar("con todo listo no falta nada", iniciar.pendiente(), "")

seccion("Sirve para cualquier rubro")
DENTAL = {"rubro": "clínicas dentales", "singular": "clínica", "pais": "MX",
          "busquedas": ["clinica dental", "dentista"], "confirman_en_nombre": ["dental", "odonto"],
          "confirman_en_web": ["implantes", "ortodoncia", "limpieza dental"],
          "descartar": [{"tipo": "laboratorio", "motivo": "fabrica prótesis, no atiende pacientes",
                         "en_categoria": ["laboratorio"], "en_web": ["laboratorio dental", "protesis para dentistas"], "min_web": 2}],
          "cadenas": ["dentalink"], "portales": {"Doctoralia": "doctoralia"}, "directorios": [],
          "sistemas": {"Dentalink": ["dentalink.healthatom"]},
          "catalogo": {"etiqueta": "tratamientos", "paginas": ["tratamientos"], "enlace_detalle": ["tratamiento"],
                       "conteo": ["tratamientos"], "minimo": 5},
          "paginas_equipo": ["doctores"],
          "textos": {"problema": "Pacientes que escriben de noche no reciben respuesta.", "resultado": "agendar pacientes al instante"}}
comprobar("un nicho bien armado se acepta", nicho.validar(DENTAL), [])
comprobar("sin búsquedas se rechaza", "busquedas" in " ".join(nicho.validar({"rubro": "x", "pais": "CL", "busquedas": []})), True)
comprobar("un país que no existe se rechaza", "país" in " ".join(nicho.validar({"rubro": "x", "pais": "ZZ", "busquedas": ["x"]})), True)
nicho.guardar(DENTAL)
_web = {"portada": "Implantes y ortodoncia para toda la familia"}
comprobar("reconoce a una clínica por su web", analizar.tipo_de({"nombre": "Sonrisa", "web": "https://s.mx"}, _web)[0], "objetivo")
comprobar("no acepta una corredora en este nicho",
          analizar.tipo_de({"nombre": "Propiedades Sol", "web": "https://p.mx"}, {"portada": "Arriendo y corretaje de casas"})[0], "dudosa")
comprobar("descarta lo parecido que no sirve",
          analizar.tipo_de({"nombre": "Prolab", "web": "https://l.mx"}, {"portada": "Laboratorio dental y protesis para dentistas"})[0], "laboratorio")
comprobar("la categoría de Maps también descarta",
          analizar.tipo_de({"nombre": "Prolab", "web": "https://l.mx", "categoria": "Laboratorio médico"}, _web)[0], "laboratorio")
comprobar("descarta las cadenas del rubro", analizar.tipo_de({"nombre": "DentaLink Centro", "web": "https://d.mx"}, _web)[0], "franquicia")
_h = ('<html><body>Implantes. <a href="/tratamientos/1">a</a><a href="/tratamientos/2">b</a>'
      '<a href="https://doctoralia.mx/x">perfil</a><script src="https://dentalink.healthatom.com/x.js"></script></body></html>')
_s, _ = analizar.medir({"nombre": "X", "web": "https://x.mx"}, {"portada": ("https://x.mx/", _h)})
comprobar("cuenta su catálogo, sus portales y su sistema", (_s["catalogo_fichas"], _s["portales"], _s["sistemas"]), (2, ["Doctoralia"], ["Dentalink"]))
_s["correos"] = []
_s["catalogo_fichas"] = 6
comprobar("las señales hablan de su rubro", analizar.calificar({}, _s)["bloques"]["volumen"][0], "6 fichas de tratamientos enlazadas en su web")
comprobar("el país de búsqueda sale del nicho", nicho.pais().codigo, "MX")
_b = []
_orig = cli.descubrir
cli.descubrir = lambda consulta, comuna, pais, fuente, limite: _b.append((consulta, comuna, pais.codigo)) or []
_s_out = sys.stdout
import io  # noqa: E402
sys.stdout = io.StringIO()
cli.buscar(["Guadalajara"], 5, "maps")
sys.stdout = _s_out
cli.descubrir = _orig
comprobar("buscar usa las búsquedas y el país del nicho", _b, [("clinica dental", "Guadalajara", "MX"), ("dentista", "Guadalajara", "MX")])
_base_ant = base.cargar()
base.guardar({"sol.cl": {"nombre": "Sol", "web": "https://sol.cl", "estado": "candidata", "resenas": "10", "rating": "4"}})
_orig = cli.descubrir
cli.descubrir = lambda *a: [{"nombre": "Sol", "web": "https://sol.cl", "resenas": "130", "rating": "4.8"}]
_s_out, sys.stdout = sys.stdout, io.StringIO()
cli.buscar(["Las Condes"], 5, "maps")
sys.stdout = _s_out
cli.descubrir = _orig
_sol = base.cargar()["sol.cl"]
comprobar("repetir una búsqueda actualiza las reseñas y no toca el estado", (_sol["resenas"], _sol["estado"]), ("130", "candidata"))
base.guardar(_base_ant)
_n2, _f2 = iniciar.redactar({"nombre": "Luis", "ciudad": "Guadalajara"}, DENTAL)
comprobar("el correo habla de su rubro y su resultado", "ayudo a clínicas dentales a agendar pacientes al instante." in _n2, True)
comprobar("nada de corredoras en un negocio dental", "corredor" in _n2.lower() or "inmobiliari" in _n2.lower(), False)

# El asistente completo, sin red: Claude falso y preguntas respondidas.
_arch, _neg, _fir = nicho.ARCHIVO, iniciar.NEGOCIO, gmail.FIRMA
_guardado = config.guardar
config.guardar = lambda nuevas: None
nicho.ARCHIVO, iniciar.NEGOCIO, gmail.FIRMA = TMP / "n2.json", TMP / "neg2.md", TMP / "fir2.txt"
_resp = iter(["Luis Rojas", "", "", "MX", "Guadalajara", "clínicas dentales", "Agendo pacientes", "s", "n"])
_print = __builtins__.print if hasattr(__builtins__, "print") else print
comprobar("sin nicho, nada de investigar", "nicho" in iniciar.pendiente(), True)
sys.stdout = io.StringIO()
iniciar.asistente(lambda _: next(_resp), lambda r, p, o: DENTAL)
sys.stdout = _s_out
comprobar("el asistente deja nicho, negocio y firma", (nicho.existe(), iniciar.NEGOCIO.exists(), gmail.FIRMA.exists(), iniciar.pendiente()), (True, True, True, ""))
comprobar("guarda el nicho propuesto", nicho.actual()["busquedas"], ["clinica dental", "dentista"])
nicho.ARCHIVO.unlink()
iniciar.NEGOCIO.unlink()
gmail.FIRMA.unlink()
_resp = iter(["Ana", "", "", "CL", "Temuco", "inmobiliarias", "Mi oferta", "n"])
sys.stdout = io.StringIO()
iniciar.asistente(lambda _: next(_resp), lambda r, p, o: 1 / 0)
sys.stdout = _s_out
comprobar("para inmobiliarias usa el nicho de ejemplo", nicho.actual()["busquedas"], ["corredora de propiedades", "inmobiliaria"])
nicho.ARCHIVO.unlink()
iniciar.NEGOCIO.unlink()
gmail.FIRMA.unlink()
_resp = iter(["Eva", "", "", "CL", "Temuco", "gimnasios", "Mi oferta", "gimnasio, box crossfit", "musculacion, clases", "Se les van socios", "retener socios", "n"])
sys.stdout = io.StringIO()
iniciar.asistente(lambda _: next(_resp), lambda r, p, o: 1 / 0)
sys.stdout = _s_out
comprobar("si Claude falla, se hace a mano", nicho.actual()["busquedas"], ["gimnasio", "box crossfit"])
comprobar("y el problema queda en su negocio", "Se les van socios" in iniciar.NEGOCIO.read_text(encoding="utf-8"), True)
nicho.ARCHIVO, iniciar.NEGOCIO, gmail.FIRMA = _arch, _neg, _fir
config.guardar = _guardado
nicho.guardar(nicho.ejemplo("inmobiliarias"))

seccion("WhatsApp, a mano")
_cl = nicho.pais()
_html = ('<a href="https://wa.me/56912345678?text=hola">a</a><a href="https://api.whatsapp.com/send?phone=56912345678">b</a>'
         '<a href="https://wa.me/56987654321">c</a><a href="tel:+56222222222">fijo</a>').lower()
comprobar("saca los números de sus botones, el más usado primero", whatsapp.numeros_en(_html, _cl), ["+56912345678", "+56987654321"])
comprobar("un teléfono común no cuenta como WhatsApp", whatsapp.numeros_en('<a href="tel:+56912345678">x</a>', _cl), [])
_s, _ = analizar.medir({"nombre": "X", "web": "https://x.cl"}, {"portada": ("https://x.cl/", _html)})
comprobar("el análisis guarda el número", _s["whatsapp_numeros"][0], "+56912345678")
comprobar("el número se limpia", whatsapp.limpiar("+56 9 1234-5678"), "+56912345678")
_w = {"dominio": "w.cl", "web": "https://w.cl", "para": "ana@w.cl", "estado": "por revisar", "envios": [],
      "decisor": {"nombre": "Ana Rojas"}, "whatsapp": {"numero": "+56912345678", "de": "general"}}
comprobar("antes del correo no se puede", whatsapp.puede(_w), "Primero tiene que salir el correo 1")
_w.update(estado="enviando", envios=[{"paso": 0}])
comprobar("después del correo sí", whatsapp.puede(_w), "")
comprobar("el mensaje no da por hecho quién contesta", "Le escribí por correo a Ana" in whatsapp.mensaje_por_defecto(_w), True)
comprobar("no lleva enlaces ni venta", correos.VENDE.search(whatsapp.mensaje_por_defecto(_w)) is None and "http" not in whatsapp.mensaje_por_defecto(_w), True)
_w["whatsapp"]["de"] = "persona"
comprobar("si es su celular, le habla a ella", whatsapp.mensaje_por_defecto(_w).startswith("Hola Ana,"), True)
comprobar("el enlace lleva el número sin signos", whatsapp.vista(_w)["enlace"], "https://wa.me/56912345678")
comprobar("marcar enviado guarda la fecha", (whatsapp.accion(_w, {"accion": "enviado"}), len(_w["whatsapp_envios"])), ("", 1))
comprobar("un número malo se rechaza", "no parece" in whatsapp.accion({"estado": "enviando"}, {"numero": "123"}), True)
comprobar("responder por WhatsApp corta la secuencia",
          (whatsapp.accion(_w, {"accion": "respondio"}), _w["estado"], _w["respuesta_canal"], envio.seguimiento_pendiente(_w, datetime.now())),
          ("", "respondió", "whatsapp", None))
_x = {"dominio": "fuera-wa.cl", "web": "https://fuera-wa.cl", "para": "a@fuera-wa.cl", "estado": "enviando", "envios": [{"paso": 0}],
      "whatsapp": {"numero": "+56911112222"}}
exclusiones.anadir("+56911112222", "prueba")
comprobar("la lista negra bloquea por número", whatsapp.puede(_x), "Está en la lista negra")
_x["whatsapp"]["numero"] = "+56933334444"
exclusiones.anadir("fuera-wa.cl", "prueba")
comprobar("y por dominio", whatsapp.puede(_x), "Está en la lista negra")
_ve = {**_w, "estado": "descartada"}
comprobar("a una descartada no se le ofrece", whatsapp.vista(_ve)["mostrar"], False)


seccion("El nicho de ejemplo sigue filtrando igual")
_c = {"portada": "Corretaje y arriendo"}
comprobar("una corredora pasa", analizar.tipo_de({"nombre": "Lircay", "web": "https://l.cl"}, _c)[0], "objetivo")
comprobar("el nombre manda sobre la categoría",
          analizar.tipo_de({"nombre": "Propiedades Lircay", "web": "https://l.cl", "categoria": "Condominio"}, _c)[0], "objetivo")
comprobar("una constructora no", analizar.tipo_de({"nombre": "Lircay", "web": "https://l.cl", "categoria": "Constructora"}, _c)[0], "desarrolladora")
comprobar("quien vende en verde no",
          analizar.tipo_de({"nombre": "Lircay", "web": "https://l.cl"}, {"portada": "Sala de ventas, nuestros proyectos, en verde"})[0], "desarrolladora")
comprobar("una asesoría de inversión no",
          analizar.tipo_de({"nombre": "Inversiones Sur", "web": "https://l.cl"}, {"portada": "rentabilidad para inversionistas"})[0], "inversion")
comprobar("una franquicia no", analizar.tipo_de({"nombre": "RE/MAX Sur", "web": "https://l.cl"}, _c)[0], "franquicia")
comprobar("un portal no", analizar.tipo_de({"nombre": "X", "web": "https://www.toctoc.com/x"}, _c)[0], "portal")
comprobar("una web que no habla del rubro queda en duda", analizar.tipo_de({"nombre": "X", "web": "https://x.cl"}, {"portada": "Hola mundo"})[0], "dudosa")
iniciar.NEGOCIO.unlink()
comprobar("sin negocio.md no se redacta", "iniciar" in iniciar.pendiente(), True)
iniciar.NEGOCIO.write_text("Soy {NOMBRE}", encoding="utf-8")
comprobar("con huecos tampoco", "huecos" in iniciar.pendiente(), True)
iniciar.NEGOCIO.write_text("# Negocio de prueba", encoding="utf-8")


def borrador(dominio="corredora.cl", **extra):
    b = {
        "dominio": dominio, "nombre": "Corredora Uno", "comuna": "Las Condes",
        "web": f"https://www.{dominio}/", "estado": "por revisar", "motivo": "",
        "para": f"ana@{dominio}", "correo_estado": "verificado",
        "decisor": {"nombre": "Ana", "cargo": "Fundadora", "fuente": "https://x"},
        "investigacion": [{"dato": "Algo real", "fuente": "https://x"}],
        "comprobar": [], "comprobado": [], "envios": [],
        "correos": [
            {"dia": 0, "asunto": "consultas de Uno fuera de horario", "cuerpo": "Hola Ana,\n\nTexto."},
            {"dia": 3, "asunto": "", "cuerpo": "Ana, un caso."},
            {"dia": 7, "asunto": "", "cuerpo": "Ana, el último."},
        ],
    }
    b.update(extra)
    return b


# ------------------------------------------------------------ correos de la web
seccion("Clasificar los correos que publica su web")
dom = {"corredora.cl"}
comprobar("una persona en su dominio es verificado",
          analizar.clasificar_correo("ana.perez@corredora.cl", dom), ("persona", "verificado"))
comprobar("contacto@ es genérico y dudoso",
          analizar.clasificar_correo("contacto@corredora.cl", dom), ("generico", "dudoso"))
comprobar("area.legal@ es genérico aunque empiece por otra palabra",
          analizar.clasificar_correo("area.legal@corredora.cl", dom), ("generico", "dudoso"))
comprobar("el que repite la marca es genérico (marcauno@marcauno.cl)",
          analizar.clasificar_correo("marcauno@marcauno.cl", {"marcauno.cl"}), ("generico", "dudoso"))
comprobar("gerencia@ lo lee quien decide",
          analizar.clasificar_correo("gerencia@corredora.cl", dom), ("direccion", "verificado"))
comprobar("un gmail publicado es dudoso",
          analizar.clasificar_correo("corredora@gmail.com", dom), ("webmail", "dudoso"))
comprobar("el de la agencia que les hizo la web no se usa",
          analizar.clasificar_correo("hola@agenciaweb.cl", dom), ("ajeno", "no usar"))
html = ('<a href="mailto:%20contacto@corredoraprueba.cl">x</a>'
        '<a href="mailto:mirador@localhost:8080">y</a>')
comprobar("un mailto con %20 se limpia y uno roto se descarta",
          analizar._correos(BeautifulSoup(html, "lxml"), ""), ["contacto@corredoraprueba.cl"])
kommo = '<html><body>Corretaje y arriendo<script src="https://gso.kommo.com/js/button.js"></script></body></html>'
s, _ = analizar.medir({"nombre": "X", "web": "https://x.cl"}, {"portada": ("https://x.cl/", kommo)})
comprobar("el botón de Kommo cuenta como chat y como sistema", (s["chat"], s["sistemas"]), (["Kommo"], ["Kommo"]))
pie = '<html><body>Corretaje. Más de 200 propiedades en administración. (+56) 9 9309 9187 propiedades@x.cl</body></html>'
s, _ = analizar.medir({"nombre": "X", "web": "https://x.cl"}, {"portada": ("https://x.cl/", pie)})
comprobar("un teléfono pegado a propiedades@ no cuenta como 9187 propiedades", s["catalogo_texto"], 200)

# ------------------------------------------------------------ revisar borrador
seccion("Qué impide aprobar un borrador")
comprobar("un borrador completo no tiene problemas", correos.revisar(borrador())[0], [])
b = borrador()
b["correos"][1]["cuerpo"] = "{nombre}, un caso."
comprobar("un hueco {..} sin rellenar lo bloquea",
          any("hueco" in p for p in correos.revisar(b)[0]), True)
comprobar("un correo supuesto no se envía",
          any("supuesto" in p for p in correos.revisar(borrador(correo_estado="supuesto"))[0]), True)
b = borrador(comprobar=["Biblioteca de anuncios", "LinkedIn"], comprobado=[True])
comprobar("queda 1 cosa por comprobar a mano",
          [p for p in correos.revisar(b)[0] if "comprobar" in p], ["Te quedan 1 cosas por comprobar a mano"])
b["comprobado"] = [True, True]
comprobar("marcadas las dos, se puede aprobar", correos.revisar(b)[0], [])
comprobar("el contexto para cuando responda no bloquea",
          correos.revisar(borrador(contexto=["Reseñas sin leer", "Ya usan Kommo"]))[0], [])
largo = borrador()
largo["correos"][0]["cuerpo"] = "palabra " * 130
comprobar(f"pasar de {correos.MAX_PALABRAS} palabras avisa pero no bloquea",
          (correos.revisar(largo)[0], any(str(correos.MAX_PALABRAS) in a for a in correos.revisar(largo)[1])),
          ([], True))
vende = borrador()
vende["correos"][0]["cuerpo"] = "Hola Ana,\n\nEso resolvemos: un agente de IA conectado a un CRM. ¿Agendamos una reunión?"
comprobar("si el correo 1 vende la herramienta o pide reunión, avisa",
          next((a for a in correos.revisar(vende)[1] if "vende" in a), "")[:48],
          "El correo 1 vende (agente de IA, CRM, reunión): ")
vende["correos"][0]["cuerpo"] = "Hola Ana,\n\nEl Contactar de cada ficha abre el WhatsApp del agente. ¿Cuánto tardan?"
comprobar("el agente inmobiliario de su ficha no cuenta como vender",
          any("vende" in a for a in correos.revisar(vende)[1]), False)
uno = borrador("uno.cl", nombre="Corredora Uno")
uno["correos"][0]["asunto"] = "Ana, vi algo en Corredora Uno que te quería comentar"
dos = borrador("dos.cl", nombre="Corredora Dos")
dos["correos"][0]["asunto"] = "Beto, vi algo en Corredora Dos que te quería comentar"
correos.guardar(uno)
comprobar("dos asuntos que solo cambian los nombres avisan",
          any("Mismo asunto que Corredora Uno" in a for a in correos.revisar(dos)[1]), True)
dos["correos"][0]["asunto"] = "Beto, probé el tasador de Corredora Dos"
comprobar("con un gancho propio ya no son iguales",
          any("Mismo asunto" in a for a in correos.revisar(dos)[1]), False)
correos.ruta("uno.cl").unlink()
comprobar("la tanda rota las fórmulas de asunto: nunca dos iguales seguidas",
          all(preparar.FORMULAS[i] != preparar.FORMULAS[(i + 1) % len(preparar.FORMULAS)]
              for i in range(len(preparar.FORMULAS))), True)
gmail.FIRMA.write_text("Ana\n{DIRECCIÓN POSTAL}", encoding="utf-8")
comprobar("sin dirección en la firma no sale nada",
          any("firma.txt" in p for p in correos.revisar(borrador())[0]), True)
gmail.FIRMA.write_text(FIRMA_OK, encoding="utf-8")
exclusiones.anadir("bloqueada.cl", "prueba")
comprobar("la lista negra bloquea por dominio",
          "Está en la lista negra" in correos.revisar(borrador("bloqueada.cl"))[0], True)
comprobar("el dominio de la URL no puede salirse de la carpeta",
          correos.ruta("../../windows/x").parent, correos.CARPETA)

# ------------------------------------------------------------------------ gmail
seccion("Gmail (con un SMTP falso)")
capturado = {}


class SMTPFalso:
    def __init__(self, host, puerto, context=None, timeout=None):
        capturado["servidor"] = (host, puerto)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def login(self, usuario, clave):
        capturado["login"] = (usuario, clave)

    def send_message(self, msg):
        capturado["msg"] = msg


smtplib.SMTP_SSL = SMTPFalso
mid = gmail.enviar("ana@corredora.cl", "consultas de Uno", "Hola Ana, ¿cuánto tardan?", responde_a="<1@x>")
msg = capturado["msg"]
comprobar("sale por smtp.gmail.com:465", capturado["servidor"], ("smtp.gmail.com", 465))
comprobar("la contraseña de aplicación va sin espacios", capturado["login"], ("yo@gmail.com", "abcdefghijklmnop"))
comprobar("el seguimiento cae en el mismo hilo", (msg["In-Reply-To"], msg["References"]), ("<1@x>", "<1@x>"))
comprobar("devuelve el Message-ID que puso", msg["Message-ID"], mid)
comprobar("lleva el botón de baja de Gmail", msg["List-Unsubscribe"], "<mailto:yo@gmail.com?subject=baja>")
comprobar("las tildes llegan enteras", msg.get_content().strip(), "Hola Ana, ¿cuánto tardan?")
comprobar("IMAP quiere el mes en inglés", gmail._fecha_imap(date(2026, 10, 28)), "28-Oct-2026")
comprobar("Auto-Submitted es una respuesta automática", gmail.es_automatica(b"Subject: Re: hola\r\nAuto-Submitted: auto-replied\r\n\r\n"), True)
comprobar("un asunto de fuera de oficina también", gmail.es_automatica("Subject: Respuesta automática: hola\r\n\r\n".encode()), True)
comprobar("una respuesta normal no lo es", gmail.es_automatica(b"Subject: Re: Ana, vi algo\r\nAuto-Submitted: no\r\n\r\n"), False)


class IMAPBandeja:
    """Bandeja de mentira: una lista de cabeceras, todas de su dominio."""
    mensajes: list[bytes] = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def login(self, *a):
        pass

    def select(self, *a, **k):
        pass

    def search(self, _, *criterios):
        if "mailer-daemon" in criterios[1]:
            return "OK", [b""]
        return "OK", [" ".join(str(i) for i in range(len(self.mensajes))).encode()]

    def fetch(self, num, _):
        return "OK", [(b"cabeceras", self.mensajes[int(num)]), b")"]


import imaplib as _imap  # noqa: E402
_imap_real = _imap.IMAP4_SSL
_imap.IMAP4_SSL = IMAPBandeja
AUTO, HUMANO = b"Subject: Out of office\r\n\r\n", b"Subject: Re: hola\r\n\r\n"
IMAPBandeja.mensajes = [AUTO]
comprobar("solo una respuesta automática: la secuencia sigue", gmail.revisar("a@x.cl", datetime(2026, 11, 3)), "")
IMAPBandeja.mensajes = [AUTO, HUMANO]
comprobar("si además contestó alguien: respondió", gmail.revisar("a@x.cl", datetime(2026, 11, 3)), "respondió")
IMAPBandeja.mensajes = [b""]
comprobar("sin cabeceras legibles cuenta como respuesta", gmail.revisar("a@x.cl", datetime(2026, 11, 3)), "respondió")
_imap.IMAP4_SSL = _imap_real

# ----------------------------------------------------------------------- envío
seccion("La cola de envío")
LUNES = datetime(2026, 11, 2, 10, 0)
comprobar("lunes a las 10 se envía", envio.en_horario(LUNES), True)
comprobar("sábado no", envio.en_horario(datetime(2026, 10, 31, 10, 0)), False)
comprobar("a las 18:00 ya no", envio.en_horario(LUNES.replace(hour=18)), False)

enviados, respuesta = [], {"valor": ""}


def enviar_falso(para, asunto, cuerpo, responde_a=""):
    enviados.append({"para": para, "asunto": asunto, "cuerpo": cuerpo, "responde_a": responde_a})
    return f"<{len(enviados)}@prueba>"


gmail.enviar = enviar_falso
gmail.revisar = lambda para, desde: respuesta["valor"]
envio.guardar_estado({"activo": True, "proximo": "", "error": ""})
for i, d in enumerate(("uno.cl", "dos.cl", "tres.cl")):
    correos.guardar(borrador(d, estado="aprobado", aprobado_en=f"2026-11-0{i + 1}T09:00:00"))

motor = envio.Envio()
motor.ciclo(LUNES)
comprobar("sale primero el aprobado más antiguo", enviados[-1]["para"], "ana@uno.cl")
uno = correos.leer("uno.cl")
comprobar("queda 'enviando' con su Message-ID", (uno["estado"], uno["envios"][0]["message_id"]),
          ("enviando", "<1@prueba>"))
comprobar("el cuerpo sale con la firma al final", enviados[-1]["cuerpo"].endswith("respóndeme «baja»."), True)

motor.ciclo(LUNES + timedelta(minutes=3))
comprobar("no sale otro antes de la pausa", len(enviados), 1)
motor.ciclo(LUNES + timedelta(minutes=19))
comprobar("pasada la pausa sale el siguiente", enviados[-1]["para"], "ana@dos.cl")
motor.ciclo(LUNES + timedelta(minutes=40))
comprobar("con ENVIO_MAX_DIA=2 el tercero espera a mañana", len(enviados), 2)

JUEVES = LUNES + timedelta(days=3, minutes=5)
motor.ciclo(JUEVES)
comprobar("el día 3 sale el seguimiento antes que los nuevos", enviados[-1]["para"], "ana@uno.cl")
comprobar("como respuesta al correo 1", (enviados[-1]["asunto"], enviados[-1]["responde_a"]),
          ("Re: consultas de Uno fuera de horario", "<1@prueba>"))

respuesta["valor"] = "respondió"
motor.ciclo(JUEVES + timedelta(minutes=30))
comprobar("si contestó, no se le manda el seguimiento",
          (correos.leer("dos.cl")["estado"], [e["para"] for e in enviados].count("ana@dos.cl")), ("respondió", 1))
comprobar("el jueves hay cupo nuevo: sale el tercero", enviados[-1]["para"], "ana@tres.cl")
respuesta["valor"] = ""

envio.guardar_estado({"activo": False, "proximo": "", "error": ""})
antes = len(enviados)
motor.ciclo(JUEVES + timedelta(hours=2))
comprobar("con los envíos pausados no sale nada", len(enviados), antes)

envio.guardar_estado({"activo": True, "proximo": "", "error": ""})
correos.guardar(borrador("cuatro.cl", estado="aprobado", aprobado_en="2026-11-05T09:00:00"))
gmail.FIRMA.write_text("Ana\n{DIRECCIÓN POSTAL}", encoding="utf-8")
motor.ciclo(JUEVES + timedelta(hours=3))
cuatro = correos.leer("cuatro.cl")
comprobar("si algo se rompió tras aprobar, vuelve a revisión sin salir",
          (cuatro["estado"], "firma.txt" in cuatro["motivo"], len(enviados)), ("por revisar", True, antes))
gmail.FIRMA.write_text(FIRMA_OK, encoding="utf-8")

# ----------------------------------------------------------------------- panel
seccion("El panel")
servidor = panel.Servidor(("127.0.0.1", 0), panel.Manejador)
puerto = servidor.server_address[1]
threading.Thread(target=servidor.serve_forever, daemon=True).start()
correos.guardar(borrador("panel.cl"))


def pedir(ruta, cuerpo=None, cabeceras=None):
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    cab = {"Content-Type": "application/json", "X-Panel": "1"} | (cabeceras or {})
    if cuerpo is None:
        c.request("GET", ruta, headers=cabeceras or {})
    else:
        c.request("POST", ruta, body=json.dumps(cuerpo), headers=cab)
    r = c.getresponse()
    datos = r.read()
    try:
        return r.status, json.loads(datos)
    except json.JSONDecodeError:
        return r.status, datos.decode("utf-8")


comprobar("la página carga", "Prospector" in pedir("/")[1], True)
comprobar("lista los borradores",
          "panel.cl" in [b["dominio"] for b in pedir("/api/borradores")[1]], True)
comprobar("un POST sin la cabecera X-Panel se rechaza",
          pedir("/api/borradores/panel.cl/aprobar", {}, {"X-Panel": "0"})[0], 403)
comprobar("una web ajena (otro Host) no entra",
          pedir("/api/borradores", None, {"Host": "evil.example"})[0], 403)
nuevo = borrador("panel.cl")["correos"]
nuevo[0]["cuerpo"] = "Hola Ana,\n\nTexto editado en el panel."
pedir("/api/borradores/panel.cl", {"correos": nuevo})
comprobar("lo que editas se guarda", correos.leer("panel.cl")["correos"][0]["cuerpo"],
          "Hola Ana,\n\nTexto editado en el panel.")
comprobar("una acción inventada no existe",
          pedir("/api/borradores/panel.cl/responder", {})[0], 404)
gmail.FIRMA.write_text("{MARCA}", encoding="utf-8")
codigo, r = pedir("/api/borradores/panel.cl/aprobar", {})
comprobar("no deja aprobar con la firma a medias", (codigo, "firma.txt" in r["error"]), (400, True))
gmail.FIRMA.write_text(FIRMA_OK, encoding="utf-8")
codigo, r = pedir("/api/borradores/panel.cl/aprobar", {})
comprobar("con todo en orden, a la cola", (codigo, r["estado"]), (200, "aprobado"))
codigo, r = pedir("/api/borradores/panel.cl/prueba", {})
comprobar("la prueba te manda los 3 a ti, en un hilo",
          [(e["para"], e["asunto"][:9]) for e in enviados[-3:]],
          [("yo@gmail.com", "[Prueba] "), ("yo@gmail.com", "[Prueba] "), ("yo@gmail.com", "[Prueba] ")])
comprobar("y la prueba no lo saca de la cola", r["estado"], "aprobado")
correos.guardar(borrador("contesto.cl", estado="respondió"))
correos.guardar(borrador("wa-panel.cl", estado="enviando", envios=[{"paso": 0, "fecha": "2026-11-02T10:00:00", "message_id": "<x>", "para": "ana@wa-panel.cl"}]))
_c, _d = pedir("/api/borradores/wa-panel.cl/whatsapp", {"numero": "+56 9 1234 5678", "mensaje": "Hola"})
comprobar("el panel guarda número y mensaje", (_c, _d["whatsapp_vista"]["numero"], _d["whatsapp_vista"]["mensaje"], _d["whatsapp_vista"]["bloqueo"]), (200, "+56912345678", "Hola", ""))
_c, _d = pedir("/api/borradores/wa-panel.cl/whatsapp", {"accion": "enviado"})
comprobar("el panel marca el envío", (_c, len(_d["whatsapp_vista"]["enviados"])), (200, 1))
_c, _d = pedir("/api/borradores/wa-panel.cl/whatsapp", {"accion": "respondio"})
comprobar("y la respuesta por WhatsApp", (_c, _d["estado"], _d["respuesta_canal"]), (200, "respondió", "whatsapp"))
correos.ruta("wa-panel.cl").unlink()
pedir("/api/borradores/contesto.cl/respuesta", {"tipo": "baja"})
comprobar("'no me interesa' lo manda a la lista negra",
          (correos.leer("contesto.cl")["estado"], exclusiones.esta_bloqueado({"web": "https://contesto.cl"})),
          ("baja", True))

from http.server import SimpleHTTPRequestHandler  # noqa: E402

ajeno = ThreadingHTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)  # otro proyecto sirviendo archivos
threading.Thread(target=ajeno.serve_forever, daemon=True).start()
nuevo, p = panel.elegir_puerto(ajeno.server_address[1])
comprobar("si el puerto lo tiene otro programa, abre el panel en el siguiente",
          (nuevo is not None, p != ajeno.server_address[1]), (True, True))
nuevo.server_close()
ajeno.shutdown()
comprobar("si el puerto lo tiene un panel, no abre otro (dos colas = correos dobles)",
          panel.elegir_puerto(puerto), (None, puerto))
servidor.shutdown()

# -------------------------------------------------------------- conectar gmail
seccion("Conectar Gmail")
config.RAIZ = TMP
(TMP / ".env.example").write_text("# Tu Gmail\nGMAIL_USUARIO=\nGMAIL_CLAVE_APP=\n# Ritmo\nENVIO_MAX_DIA=20\n",
                                  encoding="utf-8")
config.guardar({"GMAIL_USUARIO": "ana@gmail.com", "GMAIL_CLAVE_APP": "abcdefghijklmnop"})
env = (TMP / ".env").read_text(encoding="utf-8")
comprobar("el .env nace del ejemplo, con sus comentarios",
          ("# Tu Gmail" in env, "GMAIL_USUARIO=ana@gmail.com" in env, "ENVIO_MAX_DIA=20" in env), (True, True, True))
config.guardar({"GMAIL_CLAVE_APP": "otraclave"})
env = (TMP / ".env").read_text(encoding="utf-8")
comprobar("volver a conectar reemplaza la clave, no la duplica",
          (env.count("GMAIL_CLAVE_APP="), "GMAIL_USUARIO=ana@gmail.com" in env), (1, True))


class SMTPRechaza(SMTPFalso):
    def login(self, usuario, clave):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")


_antes = envio.leer_estado()
e = {"activo": True}
envio.frenar_por_rebotes(e, [{"rebotes": [{}]}])
comprobar("los rebotes de antes no frenan", (e["activo"], e["rebotes_base"]), (True, 1))
comprobar("un rebote nuevo tampoco", envio.frenar_por_rebotes(e, [{"rebotes": [{}]}, {"estado": "rebotó"}]), False)
dos = [{"rebotes": [{}]}, {"estado": "rebotó"}, {"estado": "rebotó"}]
comprobar("el segundo pausa y lo explica", (envio.frenar_por_rebotes(e, dos), e["activo"], "2 correos" in e["error"]), (True, False, True))
e["activo"] = True
comprobar("al reactivar no frena por los mismos", envio.frenar_por_rebotes(e, dos), False)
envio.guardar_estado(_antes)


class IMAPFalso:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def login(self, usuario, clave):
        pass


import imaplib  # noqa: E402

imaplib.IMAP4_SSL = IMAPFalso
smtplib.SMTP_SSL = SMTPRechaza
comprobar("una clave mala se explica, no revienta",
          "contraseña de aplicación" in gmail.probar("x@gmail.com", "mala"), True)
smtplib.SMTP_SSL = SMTPFalso
comprobar("una clave buena pasa por SMTP e IMAP", gmail.probar("x@gmail.com", "abcd efgh ijkl mnop"), "")

# -------------------------------------------------------------------- preparar
seccion("Preparar los correos del día")
preparar.COMUNAS = TMP / "comunas.txt"
preparar.COMUNAS.write_text("# santiago\nLas Condes\nProvidencia   # la siguiente\n\nÑuñoa\n", encoding="utf-8")
base.guardar({
    "a.cl": {"nombre": "A", "web": "https://a.cl", "comuna": "Las Condes", "estado": "candidata", "puntaje": 3},
    "b.cl": {"nombre": "B", "web": "https://b.cl", "comuna": "Las Condes", "estado": "candidata", "puntaje": 7},
    "c.cl": {"nombre": "C", "web": "https://c.cl", "comuna": "Las Condes", "estado": "floja", "puntaje": 9},
    "panel.cl": {"nombre": "P", "web": "https://panel.cl", "comuna": "Las Condes", "estado": "candidata", "puntaje": 9},
})
comprobar("pendientes: solo candidatas sin borrador, la de más puntaje primero",
          [l["nombre"] for l in preparar.pendientes(base.cargar())], ["B", "A"])
comprobar("las comunas ya barridas y los comentarios no cuentan",
          preparar.comunas_por_barrer(base.cargar()), ["Providencia", "Ñuñoa"])

barridas = []


def buscar_falso(comunas, limite, fuente):
    barridas.extend(comunas)
    b_ = base.cargar()
    for i in range(2):
        b_[f"{comunas[0][:3].lower()}{i}.cl"] = {"nombre": f"{comunas[0]} {i}", "web": f"https://{comunas[0][:3].lower()}{i}.cl",
                                                  "comuna": comunas[0], "estado": "nueva", "puntaje": 0}
    base.guardar(b_)


def analizar_falso(b_, log=print):
    for l in b_.values():
        if l["estado"] == "nueva":
            l.update(estado="candidata", puntaje=4)


cli.buscar, preparar.analizar = buscar_falso, analizar_falso
preparar.rellenar(5, log=lambda *a: None)
comprobar("con 2 candidatas y n=5 barre Providencia y después Ñuñoa", barridas, ["Providencia", "Ñuñoa"])
barridas.clear()
preparar.rellenar(50, log=lambda *a: None)
comprobar("sin comunas por barrer se para en vez de dar vueltas", barridas, [])
correos.guardar(borrador("red.cl", estado="descartada", motivo="Es una red de 18 oficinas", correos=[]))
correos.guardar(borrador("sinmotivo.cl", estado="descartada", motivo="", correos=[]))
comprobar("una descartada con motivo es un buen resultado, sin motivo no",
          (preparar.valido("red.cl"), preparar.valido("sinmotivo.cl"), preparar.valido("noexiste.cl")),
          (True, False, False))

# ----------------------------------------------------------------------- radar
seccion("El radar")
import time  # noqa: E402

from prospector import radar  # noqa: E402

servidor = ThreadingHTTPServer(("127.0.0.1", 0), panel.Manejador)
puerto = servidor.server_address[1]
threading.Thread(target=servidor.serve_forever, daemon=True).start()
b_ = base.cargar()
b_["fuera.cl"] = {"nombre": "Fuera", "web": "https://fuera.cl", "comuna": "Las Condes",
                  "estado": "descartada", "motivo": "Es una desarrolladora", "puntaje": 0}
base.guardar(b_)


def esperar(condicion, segundos=5):
    limite = time.time() + segundos
    while time.time() < limite and not condicion():
        time.sleep(0.05)


codigo, r = pedir("/api/radar")
claves = [f["clave"] for f in r["filas"]]
comprobar("lista todas: candidatas primero, de más a menos oportunidad",
          (codigo, claves[:2], claves[-2:]), (200, ["panel.cl", "b.cl"], ["c.cl", "fuera.cl"]))
comprobar("marca las que ya tienen borrador",
          next(f["borrador"] for f in r["filas"] if f["clave"] == "panel.cl"), "aprobado")
comprobar("una que no existe da 404", pedir("/api/radar/noexiste.cl")[0], 404)
comprobar("no investiga una que ya tiene borrador (lo pisaría)",
          pedir("/api/radar/panel.cl/investigar", {})[1].get("error", "")[:17], "Ya tiene borrador")
comprobar("ni una descartada", pedir("/api/radar/fuera.cl/investigar", {})[0], 400)
comprobar("investigar sin la cabecera X-Panel se rechaza",
          pedir("/api/radar/b.cl/investigar", {}, {"X-Panel": "0"})[0], 403)

suelta = threading.Event()


def investigar_falso(lead, exe, modelo=""):
    suelta.wait(5)
    correos.guardar(borrador(base.clave(lead)))
    return "por revisar", "listo"


preparar.investigar, correos.claude_disponible = investigar_falso, lambda: "claude"
codigo, _ = pedir("/api/radar/b.cl/investigar", {})
comprobar("investigar arranca en segundo plano y vuelve al tiro", codigo, 200)
comprobar("mientras corre no se lanza dos veces",
          pedir("/api/radar/b.cl/investigar", {})[1].get("error"), "Ya la estoy investigando")
suelta.set()
esperar(lambda: not radar.trabajos()["investigando"])
comprobar("al terminar deja su borrador y lo cuenta",
          (correos.ruta("b.cl").exists(), [(x["clave"], x["estado"]) for x in radar.trabajos()["terminadas"]]),
          (True, [("b.cl", "por revisar")]))

radar.analizar = analizar_falso
comprobar("rastrear sin comuna no arranca", pedir("/api/radar/rastrear", {"comuna": " "})[0], 400)
codigo, _ = pedir("/api/radar/rastrear", {"comuna": "Vitacura"})
esperar(lambda: radar.trabajos()["busqueda"]["fase"] in ("listo", "error"))
comprobar("rastrear una comuna busca, analiza y cuenta las nuevas",
          (codigo, radar.trabajos()["busqueda"]["fase"], radar.trabajos()["busqueda"]["mensaje"]),
          (200, "listo", "2 nuevas en Vitacura · 2 candidatas"))
comprobar("y aparecen en el radar",
          {"vit0.cl", "vit1.cl"} <= {f["clave"] for f in pedir("/api/radar")[1]["filas"]}, True)
servidor.shutdown()

# ------------------------------------------------------------------------ treg
seccion("Treg (con un Treg falso: sin red y sin gastar)")
import httpx  # noqa: E402

from prospector import contactos  # noqa: E402

contactos.CACHE = TMP / "treg.json"
contactos.INFORME = TMP / "treg-prueba.md"
pedidas = []


def treg_falso(req):
    pedidas.append((req.url.path, req.headers.get("X-Treg-Route-Verify")))
    if req.url.path == "/tools":
        return httpx.Response(200 if req.headers["X-Treg-Token"] == "bueno" else 401, json=[])
    cuerpo = json.loads(req.content or b"{}")
    herramienta = req.url.path.removeprefix("/call/")
    if herramienta == "treg.people.email.find" and cuerpo["full_name"] == "Ana Uno":
        return httpx.Response(200, headers={"X-Treg-Cost-Micro": "24500", "X-Treg-Served-By": "hunter"},
                              json={"output": {"email": "Ana@uno.cl"},
                                    "_treg": {"verification": {"verdict": "valid"}, "domain_match": True}})
    if herramienta == "treg.people.email.find":
        return httpx.Response(200, headers={"X-Treg-Cost-Micro": "0"}, json={"output": {}})
    if herramienta == "treg.people.email.verify":
        return httpx.Response(200, headers={"X-Treg-Cost-Micro": "3000"},
                              json={"output": {"valid": False, "status": "accept_all"}})
    if herramienta == "treg.people.search":
        return httpx.Response(200, headers={"X-Treg-Cost-Micro": "1000"},
                              json={"output": {"people": [{"full_name": "Ana Uno", "title": "Socia fundadora"},
                                                          {"name": "Pedro", "title": "Corredor asociado"}]}})
    return httpx.Response(404, json={})


def cliente(manejador=treg_falso):
    return httpx.Client(transport=httpx.MockTransport(manejador))


comprobar("un token malo se explica", contactos.Treg("malo", http=cliente()).probar(), "Treg no acepta ese token")
tr = contactos.Treg("bueno", http=cliente())
tareas = [
    {"tipo": "decisor", "dominio": "uno.cl", "empresa": "Uno", "persona": "Ana Uno", "para": "ana@uno.cl", "publicado": "ana@uno.cl"},
    {"tipo": "decisor", "dominio": "dos.cl", "empresa": "Dos", "persona": "Beto Dos", "para": "contacto@dos.cl", "publicado": ""},
    {"tipo": "verificar", "dominio": "dos.cl", "empresa": "Dos", "correo": "contacto@dos.cl"},
    {"tipo": "equipo", "dominio": "uno.cl", "empresa": "Uno"},
]
pedidas.clear()
hechas, corte = contactos.ejecutar(tareas, tr, log=lambda *a: None)
comprobar("lee el correo, el veredicto y el proveedor",
          (hechas[0]["correo"], hechas[0]["veredicto"], hechas[0]["proveedor"]), ("ana@uno.cl", "valid", "hunter"))
comprobar("buscar pide verificar en la misma llamada", pedidas[0], ("/call/treg.people.email.find", "true"))
comprobar("del equipo se queda con quien decide, no con el corredor",
          [p["nombre"] for p in hechas[3]["decisores"]], ["Ana Uno"])
comprobar("lo ya preguntado sale de la caché: no se paga dos veces",
          (tr.llamadas, tr.gastado, hechas[3]["hallazgo"]["correo"]), (4, 28500, "ana@uno.cl"))
comprobar("el informe mide la precisión contra el correo publicado",
          "Precisión: 1 de 1 iguales al publicado" in contactos.informe(hechas, tr, corte), True)

contactos.CACHE = TMP / "treg-2.json"
hechas, corte = contactos.ejecutar(tareas[:2], contactos.Treg("bueno", tope_usd=0.02, http=cliente()), log=lambda *a: None)
comprobar("al pasar el tope se para", (len(hechas), corte), (1, "tope"))
contactos.CACHE = TMP / "treg-3.json"
sin_saldo = cliente(lambda req: httpx.Response(402, json={"error": "insufficient_balance", "topup_url": "https://treg.to/x"}))
hechas, corte = contactos.ejecutar(tareas[:1], contactos.Treg("bueno", http=sin_saldo), log=lambda *a: None)
comprobar("sin saldo se para y lo dice", (hechas, corte.startswith("sin saldo")), ([], True))

plan = contactos.plan()
comprobar("el plan: primero los borradores (decisor y verificar), sin flojas ni descartadas",
          ([t["tipo"] for t in plan[:4]], {t["dominio"] for t in plan if t["tipo"] == "equipo"} & {"c.cl", "fuera.cl", "b.cl"}),
          (["decisor", "verificar", "decisor", "verificar"], set()))
comprobar("usa el correo publicado del decisor para medir precisión",
          next(t["publicado"] for t in plan if t["tipo"] == "decisor" and t["dominio"] == "panel.cl"), "ana@panel.cl")

seccion("Calificar: quién vale la pena")
from types import SimpleNamespace  # noqa: E402

from prospector import filtro  # noqa: E402
from prospector.cazador.fuentes import maps as _maps  # noqa: E402

_ficha = [None] * 40
_ficha[11], _ficha[4] = "Corredora Sol", [None] * 9
_ficha[4][7], _ficha[4][8] = 4.8, 130
comprobar("Maps trae la cantidad de reseñas", _maps._a_negocio(_ficha, "X", "y")["resenas"], "130")


def senales_vacias(**extra):
    return {"catalogo_fichas": 0, "catalogo_texto": 0, "sucursales": False, "sistemas": [], "correos": [],
            "meta_pixel": False, "google_ads": False, "portales": [], "whatsapp": True, "chat": [],
            "whatsapp_numeros": [], "formulario": False, "copyright": None, "bots": [], "contratando": "", **extra}


nicho.guardar(nicho.ejemplo("inmobiliarias"))
_cal = analizar.calificar
comprobar("muchas reseñas bastan", _cal({"resenas": "130"}, senales_vacias())["suficiente"], True)
comprobar("una señal débil no basta", _cal({}, senales_vacias(meta_pixel=True))["suficiente"], False)
comprobar("dos señales débiles sí", _cal({}, senales_vacias(meta_pixel=True, google_ads=True))["suficiente"], True)
comprobar("pagar software cuenta como señal fuerte", _cal({}, senales_vacias(sistemas=["Kommo"]))["suficiente"], True)
comprobar("no tener chat no suma nada: lo cumplen casi todos",
          sum(_cal({}, senales_vacias(whatsapp=False))["puntos"].values()), 0)
comprobar("buscar gente suma", _cal({}, senales_vacias(contratando="Trabaja con nosotros"))["puntos"]["momento"], 1)
comprobar("varios WhatsApp se ven como atención repartida",
          _cal({}, senales_vacias(whatsapp_numeros=["+1", "+2"]))["bloques"]["manual"], ["atiende por 2 WhatsApp distintos"])
comprobar("un bot instalado es una contra", _cal({}, senales_vacias(bots=["Landbot"]))["contras"], ["ya usa un bot: Landbot"])
_viejo = date.today().year - 5
comprobar("un copyright viejo con pocas reseñas es una contra",
          len(_cal({"resenas": "3"}, senales_vacias(copyright=_viejo))["contras"]), 1)
comprobar("con muchas reseñas el negocio sigue vivo aunque su web no",
          _cal({"resenas": "90"}, senales_vacias(copyright=_viejo))["contras"], [])
_citas = {"filtro": {"trabajo_manual": [{"tarea": "a", "cita": "x"}, {"tarea": "b", "cita": "y"}]}}
comprobar("el trabajo manual se muestra entero y suma un punto",
          (len(_cal(_citas, senales_vacias())["bloques"]["manual"]), _cal(_citas, senales_vacias())["puntos"]["manual"]), (2, 1))
nicho.guardar({**DENTAL, "resenas": {"bueno": 50, "muy_bueno": 200}})
comprobar("lo que son muchas reseñas depende del rubro", _cal({"resenas": "40"}, senales_vacias())["suficiente"], False)
_s, _ = analizar.medir({"nombre": "X", "web": "https://x.mx"}, {"portada": ("https://x.mx/", "<p>Hola</p>")})
comprobar("la Biblioteca de anuncios busca en su país", "country=MX" in _s["biblioteca_meta"], True)
nicho.guardar(nicho.ejemplo("inmobiliarias"))

_e = analizar._elegir_enlaces('<a href="/trabaja-con-nosotros">Trabaja con nosotros</a>'
                              '<a href="/quienes-somos">Quiénes somos</a>', "https://x.cl")
comprobar("lee quiénes son, no la página de empleo", ("quienes-somos" in " ".join(_e.values()), "trabaja" in " ".join(_e.values())), (True, False))
_s, _ = analizar.medir({"nombre": "X", "web": "https://x.cl"}, {"portada": ("https://x.cl/", "<a href='/e'>Trabaja con nosotros</a>")})
comprobar("nota que busca gente", _s["contratando"], "Trabaja con nosotros")


seccion("El filtro de Claude")
WEB = {"empresa": "Somos una red de corredores independientes. Te contactaremos en 24 horas."}
_vistos = []


def claude_falso(respuesta, codigo=0):
    def correr(orden, **k):
        _vistos.append((orden, k))
        return SimpleNamespace(returncode=codigo, stdout=json.dumps({"result": respuesta}).encode("utf-8"))
    return correr


def respuesta(**extra):
    return json.dumps({"veredicto": "sirve", "tipo": "empresa", "personas": None, "motivo": "m", "cita": "",
                       "trabajo_manual": [], **extra}, ensure_ascii=False)


_which, filtro.shutil.which = filtro.shutil.which, lambda _: "claude"
_rev = lambda r, **k: filtro.revisar({"nombre": "X"}, WEB, correr=claude_falso(r, **k))  # noqa: E731
_red = {"veredicto": "no_sirve", "tipo": "red"}
comprobar("afirma que no sirve si cita la web de verdad",
          _rev(respuesta(**_red, cita="una red de corredores independientes"))["veredicto"], "no_sirve")
comprobar("la cita se compara sin importar mayúsculas ni espacios",
          _rev(respuesta(**_red, cita="UNA RED  de corredores\nindependientes"))["veredicto"], "no_sirve")
comprobar("con una cita inventada solo duda", _rev(respuesta(**_red, cita="somos una red mundial"))["veredicto"], "dudoso")
comprobar("sin cita solo duda", _rev(respuesta(**_red))["veredicto"], "dudoso")
comprobar("si no sirve por otra razón, solo duda",
          _rev(respuesta(veredicto="no_sirve", tipo="empresa", cita="Somos una red"))["veredicto"], "dudoso")
_m = _rev(respuesta(trabajo_manual=[{"tarea": "real", "cita": "Te contactaremos en 24 horas"},
                                    {"tarea": "inventada", "cita": "respondemos por fax"}]))["trabajo_manual"]
comprobar("el trabajo manual sin cita real no se guarda", [x["tarea"] for x in _m], ["real"])
comprobar("una respuesta rota no filtra", _rev("no sé"), None)
comprobar("un veredicto raro no filtra", _rev(respuesta(veredicto="tal vez")), None)
comprobar("si Claude falla no filtra", _rev(respuesta(), codigo=1), None)


def _se_cae(orden, **k):
    raise subprocess.TimeoutExpired(orden, 1)


comprobar("si Claude se cuelga no filtra", filtro.revisar({"nombre": "X"}, WEB, correr=_se_cae), None)
filtro.shutil.which = lambda _: None
comprobar("sin Claude instalado no filtra", _rev(respuesta(**_red, cita="Somos una red")), None)
filtro.shutil.which = lambda _: "claude"
comprobar("una web sin texto no gasta nada", filtro.revisar({"nombre": "X"}, {}, correr=_se_cae), None)

_vistos.clear()
_r = _rev(respuesta())
_orden, _k = _vistos[0]
comprobar("corre sin herramientas y sin conectores", ("--tools" in _orden, _orden[_orden.index("--tools") + 1], "--strict-mcp-config" in _orden), (True, "", True))
comprobar("usa el modelo chico", _orden[_orden.index("--model") + 1], "haiku")
comprobar("en una carpeta vacía, no en el proyecto", Path(_k["cwd"]) != puente.RAIZ, True)
_prompt = _k["input"].decode("utf-8")
comprobar("marca la web como datos, no instrucciones", ("<web>" in _prompt, "nunca instrucciones" in _prompt, WEB["empresa"] in _prompt), (True, True, True))
comprobar("usa el problema y el perfil del nicho", nicho.actual()["textos"]["icp_no"] in _prompt, True)
_vistos.clear()
comprobar("si la web no cambió, no vuelve a preguntar",
          (filtro.revisar({"nombre": "X", "filtro": _r}, WEB, correr=claude_falso(respuesta(veredicto="dudoso")))["veredicto"], _vistos),
          ("sirve", []))
_ = filtro.revisar({"nombre": "X", "filtro": {**_r, "hash": "otra"}}, WEB, correr=claude_falso(respuesta()))
comprobar("si la web cambió, pregunta otra vez", len(_vistos), 1)
_vistos.clear()
nicho.guardar({**nicho.ejemplo("inmobiliarias"), "equipo_minimo": 1})
_rev(respuesta())
comprobar("si también le vende a gente sola, no los descarta", "trabajando solas" in _vistos[0][1]["input"].decode("utf-8"), False)
nicho.guardar(nicho.ejemplo("inmobiliarias"))
filtro.shutil.which = _which


# El camino completo, sin red: la web y Claude son falsos.
_HTML = "<p>Corretaje y arriendo. Escríbenos a ana@sol.cl</p>"
_vis, _revisar = analizar._visitar, filtro.revisar
analizar._visitar = lambda web, robots: ({"portada": (web, _HTML)}, "")


def analizado(resultado, resenas="130", **extra):
    filtro.revisar = lambda lead, textos: resultado
    return analizar.analizar_uno({"nombre": "Sol", "web": "https://sol.cl", "resenas": resenas, **extra}, None)


_f = {"veredicto": "sirve", "tipo": "empresa", "personas": 8, "motivo": "Corredora con equipo", "cita": "Somos ocho",
      "trabajo_manual": [{"tarea": "responde a mano", "cita": "te contactamos"}], "hash": "h", "fecha": "2026-01-01"}
_l = analizado(_f)
comprobar("con clientes y correo es candidata", (_l["estado"], _l["calificacion"]["volumen"], _l["puntaje"]), ("candidata", 4, 6))
_ficha = (analizar.FICHAS / "sol.cl.md").read_text(encoding="utf-8")
comprobar("la ficha trae el filtro y el trabajo manual", ("Filtro de Claude" in _ficha, "responde a mano" in _ficha, "130 reseñas" in _ficha), (True, True, True))
_l = analizado({**_f, "veredicto": "no_sirve", "tipo": "red", "motivo": "Es una red", "cita": "somos una red"})
comprobar("el filtro la aparta y deja la prueba", (_l["estado"], "somos una red" in _l["motivo"]), ("floja", True))
comprobar("y se puede mandar a investigar igual desde el Radar", _l["estado"] in radar.INVESTIGABLES, True)
_l = analizado({**_f, "veredicto": "dudoso", "tipo": "red", "motivo": "Parece una red", "cita": ""})
comprobar("si duda de que sea una red, también la aparta", (_l["estado"], _l["motivo"]), ("floja", "Claude: Parece una red"))
_l = analizado(None)
comprobar("si el filtro no responde sigue siendo candidata", _l["estado"], "candidata")
_l = analizado({**_f, "veredicto": "dudoso", "motivo": "No queda claro"})
comprobar("si duda de otra cosa sigue, con el aviso", (_l["estado"], _l["motivo"]), ("candidata", "Claude duda: No queda claro"))
_l = analizado({**_f, "personas": 2, "motivo": "Son dos"})
comprobar("una dupla queda para que la mire una persona", (_l["estado"], "2 persona" in _l["motivo"]), ("floja", True))
nicho.guardar({**nicho.ejemplo("inmobiliarias"), "equipo_minimo": 1})
comprobar("salvo que su oferta también sirva a gente sola", analizado({**_f, "personas": 1})["estado"], "candidata")
nicho.guardar(nicho.ejemplo("inmobiliarias"))
_l = analizado(_f, resenas="2")
comprobar("sin volumen ni pago es floja y no gasta en el filtro", (_l["estado"], _l.get("filtro")), ("floja", None))
analizar._visitar, filtro.revisar = _vis, _revisar

base.guardar({"m.cl": {"nombre": "M", "web": "https://m.cl", "calificacion": {"volumen": 3, "capacidad": 0, "manual": 1, "momento": 0}}})
_s_out, sys.stdout = sys.stdout, io.StringIO()
cli._metricas_por_senal([{"dominio": "m.cl", "estado": "respondió"}, {"dominio": "nadie.cl", "estado": "enviando"}])
_salida, sys.stdout = sys.stdout.getvalue(), _s_out
comprobar("las métricas cruzan señales con respuestas", ("le llegan clientes" in _salida, "1 de 1 · 0 de 0" in _salida), (True, True))
comprobar("y avisa que con pocos envíos no se concluye nada", "no alcanza para concluir" in _salida, True)

# ------------------------------------------------------------------------- fin
print(f"\n{'=' * 52}")
print(f"  {_ok} pasan, {_mal} fallan")
print("=" * 52)
sys.exit(1 if _mal else 0)
