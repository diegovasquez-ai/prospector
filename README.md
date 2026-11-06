# Prospector

Correo frío B2B escrito uno a uno, para el rubro que elijas. Busca negocios en
Google Maps, investiga cada uno con Claude, redacta tres correos que no parecen
plantilla y te los deja en un panel. Tú los lees, los corriges y los apruebas.
Después salen desde tu Gmail, a ritmo de persona.

**Nada sale sin tu clic.**

Le dices a qué rubro le vendes (clínicas dentales, gimnasios, inmobiliarias...) y
Claude propone qué buscar y a quién descartar. Inmobiliarias en Chile es el caso
donde más se ha usado; en otros rubros, cuenta con ajustar el filtro (ver
[Ajustar tu nicho](#ajustar-tu-nicho)).

## Qué necesitas

| | |
|---|---|
| **Python 3.10 o más nuevo** | [python.org/downloads](https://www.python.org/downloads/). En Windows, marca "Add Python to PATH" al instalar |
| **Claude Code**, con tu plan de Claude | [claude.com/claude-code](https://claude.com/claude-code). Es quien investiga y redacta. Inicia sesión una vez con el comando `claude` |
| **Un Gmail** con verificación en dos pasos | Para enviar. Puedes preparar los correos sin él |

Investigar de verdad consume bastante de tu plan: unos 10 minutos y del orden de
150 mil tokens por negocio. Parte con pocos. Si te topas con el límite, pon
`PREPARAR_MODELO=sonnet` en el `.env` o baja `-n`.

## Instalar

Abre una terminal en la carpeta del proyecto:

```
pip install -r requirements.txt
python prospector.py iniciar
python prospector.py gmail
```

- **`iniciar`** te pregunta quién eres, a qué rubro le vendes y qué ofreces, y crea
  tu nicho, tu experiencia y tu firma. **Responde solo cosas verdaderas**: es lo que
  van a leer tus prospectos. Si todavía no tienes clientes, también sirve: el correo
  dice lo que haces, sin inventar nada.
- **`gmail`** te pide tu correo y una contraseña de aplicación, comprueba que
  funciona y la guarda en `.env`. Se crea en
  [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords);
  no es tu contraseña normal y la puedes revocar cuando quieras. **No la pegues
  en el chat de Claude**: corre el comando y escríbela ahí.

En Mac o Linux, quizás sea `python3` y `pip3`.

Para comprobar que quedó bien: `python pruebas.py` (sin red y sin enviar nada).

## Usarlo

```
python prospector.py buscar "Providencia"    # negocios de tu rubro ahí, desde Google Maps, gratis
python prospector.py analizar                # señales, filtro y correos publicados
python prospector.py lista                   # quién vale la pena, de más a menos
python prospector.py preparar -n 5           # Claude investiga y redacta
python prospector.py panel                   # abre el panel en tu navegador
```

También puedes abrir `claude` en esta carpeta y pedirle "prepárame los correos de hoy".

En el panel:

1. **Lee cada correo.** Corrígelo a mano o con **Afinar con Claude** ("más corto",
   "menciona su Instagram"). Tiene botón de deshacer.
2. **Enviarme prueba**: te llegan los tres a ti, tal como los recibiría el negocio.
3. **Aprobar → cola.**
4. **Activar envíos**, arriba a la derecha. Sin esto no sale nada.

La pestaña **Radar** muestra todo lo que trajo `buscar`, ordenado por oportunidad,
con la ficha de cada negocio. Desde ahí puedes rastrear otra zona o mandar a
investigar un negocio concreto.

Cuando alguien responde, su secuencia se detiene sola y te aparece en
**Respondieron**. Para contestar, apóyate en [plantillas/respuestas.md](plantillas/respuestas.md)
o pídele ayuda a Claude.

## Ajustar tu nicho

Todo lo propio de tu rubro vive en `nicho.json`:

| Campo | Para qué |
|---|---|
| `busquedas` | Lo que se escribe en Google Maps |
| `confirman_en_web` | Palabras, sin acentos, que confirman que el negocio es de tu rubro |
| `confirman_en_nombre` | Lo mismo, en su nombre |
| `descartar` | Negocios parecidos que no sirven (en inmobiliarias, las constructoras) |
| `cadenas` | Franquicias y marcas grandes del rubro |
| `portales` | Directorios del rubro: aparecer ahí indica que pueden pagar |
| `sistemas` | Software del rubro que se puede detectar en su web |
| `catalogo` | Qué publican (propiedades, tratamientos...) y desde cuánto cuenta como señal |
| `pais` | Dónde se busca (CL, MX, AR, CO, ES...) |

**Lo que propone Claude es un punto de partida.** Después de tu primera búsqueda,
mira `python prospector.py lista --todas`. Si pasan negocios que no sirven, o se
descartan algunos buenos, corrige el archivo o pídeselo a Claude, y vuelve a medir
con `python prospector.py analizar --todas`. El detalle de quién eres y qué problema
buscas está en `negocio.md`: si escribes mejor ese problema, los correos mejoran.

Quizás necesites otro ángulo: el correo está hecho para decir "vi esto en tu negocio
y sé resolverlo", y se apoya en cómo les llegan los clientes. Si tu oferta es otra
cosa, ajusta `plantillas/secuencia.md`.

[nichos/inmobiliarias.json](nichos/inmobiliarias.json) es un ejemplo completo. Si
armas uno bueno para otro rubro, guárdalo en `nichos/` para reutilizarlo.

## Cómo salen los correos

- **Desde tu Gmail**: aparecen en tus Enviados y las respuestas llegan a tu bandeja.
- Como mucho 20 nuevos al día, de lunes a viernes de 9 a 18, con 6 a 18 minutos al
  azar entre uno y otro. Se ajusta en el `.env`. **Parte con 10 al día**, sobre todo
  si la cuenta es nueva.
- Los recordatorios (día 3 y día 7) van en el mismo hilo y se detienen si alguien
  de su dominio responde. Una respuesta automática de "fuera de oficina" no cuenta.
- Si rebotan 2 correos nuevos, los envíos se pausan y el panel te avisa.
- **Solo envía con el panel abierto.** Si lo cierras, nada sale, y al abrirlo sigue
  donde quedó.

**En Windows** puedes dejarlo andando solo: `python prospector.py automatizar`
investiga cada mañana a las 07:00 y abre el panel al encender el PC. Gasta de tu
plan todos los días. Para quitarlo: `python prospector.py automatizar --quitar`.

## Antes de enviar en serio

**Tu Gmail se juega su reputación.** Si te marcan como spam, afecta a la cuenta que
usas para todo. Si es tu correo principal, considera enviar desde otro.

**"Verificado" significa publicado, no que el buzón exista.** Un correo que el
negocio tiene en su propia web igual puede rebotar. Si quieres comprobarlo antes
de enviar, necesitas un verificador externo (`treg` y `contactos` son una prueba
opcional, de pago).

**Tú eres el remitente y el responsable.** Las reglas de correo comercial y datos
personales cambian según el país: revisa las del tuyo y las de quien recibe. En
Chile, por ejemplo, la Ley 19.496 (art. 28 B) pide identificar a quien envía y dar
una forma de darse de baja, y la Ley 21.719 regula los datos personales. Por eso
cada correo lleva tu firma y la línea de baja, y el panel no deja aprobar sin ellas.
Esto no es asesoría legal.

**Quien pide la baja no vuelve a recibir nada.** `python prospector.py baja ana@negocio.cl`,
o el botón del panel. Queda en `datos/exclusiones.txt`: si cambias de computador,
llévate ese archivo.

**Los correos son un borrador, no una verdad.** Claude investiga en webs públicas y
puede equivocarse. Por eso apruebas cada uno: revisa los datos con sus fuentes.

## Qué es tuyo y no se sube

`.env`, `negocio.md`, `nicho.json`, `firma.txt`, `comunas.txt`, `datos/`, `fichas/` y
`borradores/` están en `.gitignore`. Son tus claves y datos de contacto de personas
reales: no los subas a ningún repo público ni se los pases a nadie.

## Qué mide el código de cada negocio

| Señal | Cómo | Ojo |
|---|---|---|
| WhatsApp, chat, formulario | Enlaces `wa.me`, widgets conocidos, `<form>` | Un chat cargado tarde por JavaScript se escapa |
| Anuncios | Píxel de Meta, etiqueta de Google Ads | Instalado no significa activo: el correo no lo afirma sin comprobarlo |
| Sistema | HubSpot, Salesforce y el software de tu nicho | Si ya usan uno, cambia el ángulo |
| Tamaño | Lo que publican, su texto, correos del equipo | Lo que dicen de sí mismos se cita como suyo |
| Correos | Todos los publicados, clasificados | Nunca se deduce un correo por patrón |

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `Falta nicho.json` o `negocio.md` | `python prospector.py iniciar` |
| No aparece ningún candidato | Mira `lista --todas` y ajusta tu nicho: quizás el filtro es muy estricto. Ten en cuenta que un negocio sin correo publicado no se puede contactar |
| `No encuentro el comando 'claude'` | Instala Claude Code y corre `claude` una vez para iniciar sesión |
| `No module named ...` | `pip install -r requirements.txt` |
| Gmail rechaza la clave | Crea otra contraseña de aplicación y vuelve a correr `python prospector.py gmail` |
| El panel abre en otro puerto | Normal si el 8765 está ocupado: usa la dirección que muestra la terminal |

## Licencia y créditos

Licencia MIT: ver [LICENSE](LICENSE). Úsalo, modifícalo y compártelo. Se entrega
sin garantías, y lo que envíes con él es responsabilidad tuya.

El motor de búsqueda es una copia del [Cazador 2.0](https://github.com/diegovasquez-ai/Cazador-2.0)
(licencia MIT), en `prospector/cazador/`. No hay que instalar nada aparte.
