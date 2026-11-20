# Prospector

Correo frío B2B escrito uno a uno, para el rubro que elijas. Busca negocios en
Google Maps, **descarta los que no valen la pena**, investiga cada uno con Claude,
redacta tres correos que no parecen plantilla y te los deja en un panel. Tú los lees,
los corriges y los apruebas. Después salen desde tu Gmail, a ritmo de persona.

**Por defecto, nada sale sin tu clic.** Si después quieres que corra solo (correos que se
aprueban solos, saludos de WhatsApp a negocios verificados, un agente que contesta), cada
cosa se prende aparte en el `.env`: ver [Todos los días, solo](#todos-los-días-solo) y
[WhatsApp](#whatsapp-un-canal-aparte).

Le dices a qué rubro le vendes (clínicas dentales, gimnasios, inmobiliarias...) y
Claude propone qué buscar y a quién descartar. **El repo viene vacío de datos**: tu
nicho, quién eres, tu firma, tus comunas y tus prospectos los creas tú (`iniciar`) y nunca
se suben. Las plantillas de `plantillas/` son un punto de partida para que las reescribas
con tu oferta y tu tono, y `nichos/inmobiliarias.json` es solo un ejemplo de nicho armado
(ver [Ajustar tu nicho](#ajustar-tu-nicho)).

## Qué necesitas

| | |
|---|---|
| **Python 3.10 o más nuevo** | [python.org/downloads](https://www.python.org/downloads/). En Windows, marca "Add Python to PATH" al instalar |
| **Claude Code**, con tu plan de Claude | [claude.com/claude-code](https://claude.com/claude-code). Es quien investiga y redacta. Inicia sesión una vez con el comando `claude` |
| **Un Gmail** con verificación en dos pasos | Para enviar. Puedes preparar los correos sin él |
| **Node.js 22.13 o más** (opcional) | [nodejs.org](https://nodejs.org). Solo para enviar por WhatsApp desde tus números |

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

## CRM: después de que responden

Cuando alguien contesta, por correo o por WhatsApp, aparece en la pestaña **CRM** con su
próximo paso. Desde ahí el trabajo es tuyo: mensajes, audios, Looms y llamadas. El CRM
te dice qué toca hoy y con quién, y Claude te deja el guion.

Las etapas siguen el método de `plantillas/whatsapp.md`, venga por correo o por WhatsApp,
y la ficha te deja el texto de la fase que toca, listo para copiar o enviar:

| Etapa | Próximo paso que sugiere |
|---|---|
| Respondió | El pitch corto (audio o texto) que ofrece un video |
| Pitch enviado | Si acepta, confirmarle |
| Aceptó el video | Mandarle el Loom de 60-90 s antes de 24 h |
| Video enviado | Hasta 3 seguimientos, a las 24, 48 y 72 h (se agendan solos) |
| Llamada de diagnóstico | El audio (o texto) que la propone: ¿te acomoda esta semana? |
| Reunión agendada | La llamada de diagnóstico |
| Propuesta enviada | Seguimiento de la propuesta (cada 3 días) |
| Cliente · Perdido · Retomar más adelante | |

**Si llegó por correo** es distinto: ya leyó quién eres y qué haces en el correo 1, así
que no se le manda otro pitch. La ficha te muestra qué contestarle según lo que dijo
(los textos de `plantillas/respuestas.md`, con su nombre y su empresa puestos): si
quiere saber más, la llamada con dos horarios; si duda, le ofreces el Loom; si pregunta
el precio, cómo cobras. Lo copias, lo adaptas y respondes en el mismo hilo de Gmail;
**Ya le contesté esto** lo anota y avanza la etapa. Después del Loom van 2 seguimientos,
no 3.

- **Para hoy** junta lo atrasado y lo que vence hoy. La barra de arriba te avisa cuántos hay.
- **Próximo paso**: qué (mensaje, audio, Loom, llamada, correo, propuesta), fecha, hora y
  nota. **Hecho ✓** lo anota en el historial.
- **Guion con Claude** escribe el mensaje, los puntos del audio, el guion del Loom (por
  bloques de tiempo y qué mostrar en pantalla) o la pauta de la llamada, con lo que se
  investigó de ese negocio y lo que respondió. Tú grabas y envías: nada sale solo.
- La ficha te dice desde cuál de tus números se habló por WhatsApp y abre el hilo en Gmail.
- Si llegó por WhatsApp, **Enviar por WhatsApp** manda el texto de la fase desde ese mismo
  número, con tu clic, y deja todo en el historial. Si lo mandaste desde el celular (un
  audio), **Ya lo mandé** lo anota y avanza la etapa igual.
- **Audio contra texto**: el pitch se alterna entre prospectos (a uno le toca audio, al
  siguiente texto) y el CRM muestra cuántos aceptaron el video con cada uno.
- **Perdido** pide el motivo. Si pidió que no le escribas más, va a la lista negra.

## Cómo decide quién vale la pena

Cualquier scraper te trae todo lo que hay en Maps, sirva o no. Este decide antes de que
gastes tiempo en un negocio:

1. **Busca** en Google Maps y guarda su nota y cuántas reseñas tiene.
2. **Mide** hasta 5 páginas de su web, sin opinar.
3. **Exige evidencia.** Una señal débil no alcanza:

   | Pregunta | Señal | Puntos |
   |---|---|---|
   | ¿Le llegan clientes? | Muchas reseñas en Google | 2 a 4 |
   | | Lo que publica en su web, sucursales | 1 |
   | ¿Puede pagar? | Ya paga software, o tiene 5 o más personas con correo | 2 |
   | | Píxel de Meta, etiqueta de Google Ads, portales | 1 |
   | ¿Hay trabajo manual? | Varios WhatsApp, solo formulario, lo que cita Claude | 1 |
   | ¿Está creciendo? | Busca gente | 1 |

   Para seguir necesita 2 puntos o más entre clientes y pago. "No tiene chat" no suma:
   lo cumplen casi todos, así que no distingue a nadie.
4. **Claude lee su web** con un modelo chico, en segundos. Aparta a redes, otros rubros y
   a quien trabaja solo, y solo afirma que no sirve con una **cita de la web que el programa
   comprueba**. Lo que aparta queda en `lista --todas` y en el Radar con el motivo: si se
   equivocó, lo mandas a investigar desde el Radar. Si Claude falla, el negocio sigue adelante.
   No siempre responde igual, así que míralo como una primera lectura.
5. **La investigación completa** es solo para las que pasan, porque es lo que cuesta caro.

**Las señales no prueban que te vayan a responder.** Después de unos 100 envíos,
`python prospector.py metricas` te muestra qué señales terminan en respuesta. Si alguna no
sirve en tu rubro, ajústala en vez de creerle al puntaje.

Si un negocio con muchas reseñas no publica correo, queda como "sin correo" en el Radar:
puedes mandarlo a investigar a mano.

## Todos los días, solo

`python prospector.py diario -n 20` hace lo de cada mañana: investiga 20 negocios en modo
rápido (unos 3 minutos cada uno, menos profundo), los sube al servidor si tienes uno y, si al
WhatsApp le quedan menos de `WA_RESERVA_MIN` (200) negocios por saludar, rastrea 3 comunas más
de `comunas.txt` (una por línea). En Windows, `python prospector.py automatizar` lo programa de
lunes a viernes a las 7:00 (si el PC estaba apagado, parte al encenderlo).

Con `ENVIO_AUTO_APROBAR=si`, el panel aprueba solo los correos que pasan su revisión sin ningún
problema, hasta el tope del día. Lo que tiene algo que comprobar a mano te espera igual.
**Préndelo cuando ya hayas revisado unas cuantas tandas** y confíes en lo que escribe.

**Prueba A/B de tu demo** (opcional): si tienes una demo que el prospecto puede probar solo,
pon su enlace en `DEMO_URL`. La mitad de los correos 1 sale con una línea que lleva a ella y la
otra mitad sin ella, hasta 100 de cada uno (`PRUEBA_DEMO_META`). La barra de arriba del panel
muestra la tasa de respuesta de cada grupo. Ojo: un enlace en un correo frío puede bajar un
poco la entrega; mira los rebotes.

## WhatsApp: un canal aparte

> **Va por una API NO oficial (Baileys).** Meta puede banear el número sin aviso y sin
> vuelta atrás, sobre todo si escribe en frío. Usa números que puedas perder: nunca
> tu personal ni el principal de tu negocio.

Cada negocio va por **un solo canal**: por correo, las candidatas que se investigan
a fondo; por WhatsApp, las que publican un WhatsApp y no un correo, o quedaron flojas.
El método completo, con los textos, está en `plantillas/whatsapp.md`. **Es una plantilla:
reescribe el pitch y las respuestas con tu oferta y tu forma de hablar antes de prender nada**,
y completa en `negocio.md` la sección "Cómo escribo por WhatsApp" (el agente la lee).

| Fase | Cuándo | Qué |
|---|---|---|
| 1 | Primer contacto | 3 líneas sin venta: "Hola, buen día / Por acá te escribe {tu nombre} / Te quería hacer una consulta". Rotan 3 variaciones |
| 2 | Responde | El pitch corto, igual para todos (audio de 40-45 s o texto): el problema que tiene la mayoría del rubro, lo que haces y la consulta: si le puedes mandar un video |
| 3 | Acepta | Confirmación: el video llega en 24 h |
| 4 | Dentro de 24 h | Loom de 60-90 s con su caso + mensaje con el enlace |
| 5 | Si aceptó el Loom | Hasta 3 seguimientos: 24, 48 y 72 h |
| 6 | Vio el Loom y le interesa | Audio de llamada de **diagnóstico** (nunca "de venta"): ¿te acomoda esta semana? |
| 7 | Agenda | Reunión agendada |

**Instalar el puente (una vez).** Necesitas [Node.js](https://nodejs.org) 22.13 o más
(en el servidor ya viene en la imagen de Docker):

```
cd whatsapp
npm install
```

**Conectar tus números.** En el panel, pestaña **WhatsApp**: lee y acepta el aviso,
toca **Conectar** en cada número y escanea el QR desde el celular de ese número
(WhatsApp → Dispositivos vinculados → Vincular un dispositivo). Hasta 3 números
(`WA_NUMEROS` en el `.env`).

**Cómo se usa.**

1. Abajo, en **Para escribir por WhatsApp**, marcas a quién (mira el motivo de las
   flojas) y aprietas **Preparar mensajes**. No sale nada.
2. Arriba, en **Por aprobar**, revisas cada mensaje y lo apruebas **uno por uno**. Si
   sabes el nombre de quien contesta, lo pones y el mensaje pasa a la variación con nombre.
3. Con **Activar WhatsApp** encendido, lo aprobado sale solo en las mejores horas
   (martes 10, miércoles 17, jueves 10 y 17, sábado 10-12: `WA_VENTANAS`), con 4 a 12
   minutos al azar entre mensajes de un mismo número y rotando entre tus números.
4. Si responde, pasa solo al **CRM** con la fase 2 lista. Desde ahí, cada mensaje del
   método sale con tu clic (**Enviar por WhatsApp**), desde el mismo número; los audios
   los grabas tú en el celular. Al mandar el Loom, el CRM agenda los seguimientos.
5. Si a los 5 días no respondió, queda **sin respuesta** y no se le insiste.

- **El Loom**: quien acepta el video aparece arriba en el CRM, en **Esperan tu Loom**.
  Grabas el video, abres su ficha y pegas el enlace: sale el mensaje ("acá está el video
  que te había comentado… ¿cuándo crees que lo puedas ver?") y ahí mismo apruebas los
  seguimientos de las 24, 48 y 72 h. Salen solos, de lunes a sábado en horario, solo si
  no ha respondido; si contesta cualquier cosa, los que falten se cancelan y el CRM te
  avisa para que respondas tú.
- **Tu demo** (`DEMO_URL`, si tienes una) es el último seguimiento del Loom y la respuesta a
  "mándame información". Nunca va en el saludo ni en el pitch. Sin demo, reescribe esos dos
  textos en la plantilla.
- **Nunca contesta al segundo**: si el cliente acaba de escribir, tu respuesta espera hasta
  que pasen 30 segundos desde su último mensaje (`WA_ESPERA_RESPUESTA`), por si escribe en
  varios ("hola" y después "sí, dime"). Si en esa espera manda algo más, la respuesta no
  sale: queda en la caja y el panel te avisa para que leas lo nuevo antes de contestar.
- **Apagar lo automático**, en Conversaciones: **Pausar todo** detiene los saludos y los
  seguimientos de todos; **Apagar en este chat** deja a ese cliente solo en tus manos (no
  le sale ningún seguimiento). Tú puedes seguir escribiendo igual. Al volver a encender,
  los seguimientos atrasados salen de a uno por día, nunca juntos.
- **Respuestas rápidas**: si pregunta cuánto vale, si quiere reunirse (siempre dos
  horarios el próximo día hábil, `REUNION_HORARIOS`; si su dirección calza con
  `REUNION_PRESENCIAL`, también ofrece ir a su oficina), si no puede a esa hora (el día
  siguiente) y la confirmación. Están en la ficha y en Conversaciones.
- **El agente contesta solo** (`WA_AUTO_RESPONDER=si`): cuando un prospecto escribe, lee
  ese chat y responde según el método, con tu tono: el pitch (en audio o texto, según le
  toque), la confirmación del video, el precio (sin dar un número), de dónde sacaste el
  número, si es un bot, la demo si pide información y los horarios para la llamada. Tú
  solo pegas el Loom en el CRM y, cuando elige horario, le mandas el enlace de la reunión.
  Lo que no sabe contestar, o lo que no pasa los controles (precios, enlaces, más de 8
  mensajes al día en un chat), no sale: queda marcado con ⚠ en Conversaciones y en el CRM
  como "para hoy", para que lo contestes tú. Respeta los dos interruptores y contesta de
  8 a 22 (`WA_HORARIO_AGENTE`).
- **✨ Sugerir respuesta**, en Conversaciones: Claude lee el chat y redacta la respuesta
  con tu tono (la sección "Cómo escribo por WhatsApp" de `negocio.md`). No se envía: queda
  en la caja para que la revises y la mandes tú.
- **Topes por número**: `WA_TOPE_1=25` deja un número ya caliente con un tope fijo;
  `WA_RAMPA_2=5:3:25` hace que otro parta en 5 y suba 3 por cada día en que envió, hasta 25.
- **Preparación automática** (`WA_AUTO_PREPARAR=si`): cada día quedan en **Por aprobar** los
  saludos que caben en el tope, del mejor prospecto al peor (primero las "sin correo",
  después las de pocas señales; lo que el filtro apartó por no ser de tu rubro lo
  eliges tú). Tú apruebas o descartas cada uno; si descartas, se repone otro.
- **Saludos sin tu clic** (`WA_AUTO_APROBAR=si`): se aprueban y salen solos, pero solo a
  negocios verificados de tu rubro. Pasan dos filtros: reglas fijas (fuera cámaras, gremios,
  comparadores, directorios y lo que pongas en `verificar` de `nicho.json`) y Claude, que
  lee su web y tiene que confirmar con una frase que exista ahí que es de tu rubro, con el
  criterio de `verificar`. Ajústalo bien antes: Maps trae cursos, proveedores y gremios
  mezclados con los negocios que buscas. Lo que no pasa, o no se pudo leer, se queda en **Por aprobar** con el
  motivo: no sale solo. Respeta el tope de cada número, las horas de envío y los dos
  interruptores. Los correos siguen pidiendo tu aprobación.
- **Calentamiento**: un número nuevo parte con 8 mensajes de conexión al día, la semana
  2 sube a 15 y desde la 3 a 20 (`WA_CALENTAMIENTO=8,15,20`). Antes de prospectar, usa
  cada número unos días como una persona: foto, nombre, algunos chats.
- Solo a números que el negocio **publica como WhatsApp** (un botón o enlace en su web).
- Si un envío queda **en duda** (se cortó la conexión), no se reintenta: miras el chat
  en el celular y marcas si salió.
- Un saludo automático de WhatsApp Business o un "fuera de horario" no cuentan como
  respuesta: el panel te los muestra por si acaso.
- **Conversaciones** muestra los chats con tus prospectos, y solo esos: el panel nunca
  pide las demás conversaciones de tus números. Desde ahí respondes (sale con tu clic, por
  el mismo número) o insertas el texto de la fase que toca.
- Si uno de los números es el de tu negocio, desmarca **Mandar mensajes en frío desde
  este número**: queda solo para conversar y los mensajes de conexión salen por el otro.

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
| `resenas` | Cuántas reseñas son "bueno" y "muy_bueno" en tu rubro: un restaurante junta muchas más que una notaría |
| `equipo_minimo` | Desde cuántas personas te sirve un negocio. Pon 1 si también le vendes a quien trabaja solo |
| `pais` | Dónde se busca (CL, MX, AR, CO, ES...) |
| `textos` | El problema que resuelves y qué logras: el pitch de WhatsApp parte de aquí (`{problema}`, `{resultado}`) |
| `verificar` | Quién es de tu rubro para los saludos automáticos de WhatsApp: qué tiene que ser, qué no, y raíces en el nombre o la categoría de Maps que lo confirman o lo descartan |

**Lo que propone Claude es un punto de partida.** Después de tu primera búsqueda,
mira `python prospector.py lista --todas`. Si pasan negocios que no sirven, o se
descartan algunos buenos, corrige el archivo o pídeselo a Claude, y vuelve a medir
con `python prospector.py analizar --todas`. Si tu base es anterior a las reseñas, repite
antes `buscar` en la misma zona: las actualiza sin duplicar nada. El detalle de quién eres y
qué problema buscas está en `negocio.md`: si escribes mejor ese problema, los correos mejoran
y el filtro de Claude acierta más.

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

## Desplegarlo en tu servidor (Coolify)

En un VPS el sistema queda encendido siempre: los correos y los WhatsApp salen aunque
tu PC esté apagado, y el panel lo abres desde cualquier lado con tu contraseña. Todo
corre en un solo contenedor (`Dockerfile`): el panel, el envío, el puente de WhatsApp y
Claude Code.

1. **Tu copia del código en GitHub** (un fork o un repo tuyo). Si le agregas una carpeta
   `semilla/` con tu `negocio.md`, `nicho.json` o `firma.txt` para que el servidor parta con
   ellos, ese repo tiene que ser **privado**.
2. **En Coolify**: *+ New → Private Repository (GitHub App)* → elige el repo →
   *Build Pack: Dockerfile* → *Ports Exposes: 8765* → pon tu dominio
   (por ejemplo `prospeccion.tu-dominio.com`). Coolify le pone HTTPS solo.
3. **Storage**: agrega un volumen persistente montado en **`/data`**. Ahí viven tus
   prospectos, borradores, el CRM, `negocio.md`, la firma y las sesiones de WhatsApp.
   Sin el volumen, cada deploy los borra.
4. **Health check**: ruta `/salud`.
5. **Variables de entorno** (márcalas como secretas):

   | Variable | Qué va |
   |---|---|
   | `PANEL_CLAVE` | La contraseña del panel. Larga y única. **Obligatoria** |
   | `PANEL_USUARIO` | El correo para entrar al panel. Si lo pones, se piden correo y contraseña |
   | `GMAIL_USUARIO`, `GMAIL_CLAVE_APP`, `GMAIL_NOMBRE` | Tu Gmail y su contraseña de aplicación |
   | `CLAUDE_CODE_OAUTH_TOKEN` | Para investigar con tu suscripción: en tu PC corre `claude setup-token` y copia el token |
   | `WA_NUMEROS`, `WA_CALENTAMIENTO`, `ENVIO_MAX_DIA`... | Opcionales, como en `.env.example` |

   La zona horaria viene en Chile (`TZ=America/Santiago`). Si estás en otro país, agrega la
   variable `TZ` con la tuya (por ejemplo `America/Mexico_City`): los horarios de envío la usan.
6. **Deploy.** Después, en la *Terminal* del contenedor en Coolify, una sola vez:
   `python prospector.py iniciar` (quién eres, tu nicho y tu firma).
7. **Scheduled Task** en Coolify para investigar cada mañana:
   `python prospector.py preparar -n 20 --paralelo 2`, con *timeout* de 10800 segundos (3 horas).
   El cron de Coolify va en la hora del servidor (normalmente UTC): calcula tus 7:00 en UTC.
8. Entra a tu dominio con la contraseña, pestaña **WhatsApp** → acepta el aviso →
   **Conectar** y escanea el QR de cada número.

### Investigar en tu PC, enviar desde el servidor (la forma barata)

Investigar es lo único que cuesta. Si lo haces en tu PC con tu suscripción de Claude,
el servidor no gasta API en eso:

1. En tu PC, en la carpeta del proyecto: abre `claude` y pídele *"prepárame los correos
   de hoy"*. Investiga y redacta como siempre, y al final sube los borradores.
   (A mano: `python prospector.py subir`.)
2. En el servidor, los apruebas desde el panel (también desde el celular) y salen solos.

`subir` usa `SERVIDOR_URL`, `PANEL_USUARIO_SERVIDOR` y `PANEL_CLAVE_SERVIDOR` de tu
`.env.local`. Nunca pisa en el servidor un borrador que ya aprobaste o que ya salió, y
respeta su lista negra. En Coolify deja desactivada la tarea programada de `preparar`.

Para que te alcance: la investigación corre varias instancias de Claude a la vez.
Con 2 GB de RAM usa `--paralelo 2`; con 4 GB, el valor por defecto (3).

## Qué es tuyo y no se sube

`.env`, `negocio.md`, `nicho.json`, `firma.txt`, `comunas.txt`, `datos/`, `fichas/`,
`borradores/` y `.whatsapp/` (las sesiones de tus números) están en `.gitignore`. Son tus claves y datos de contacto de personas
reales: no los subas a ningún repo público ni se los pases a nadie.

## Qué mide el código de cada negocio

| Señal | Cómo | Ojo |
|---|---|---|
| WhatsApp, chat, formulario | Enlaces `wa.me`, widgets conocidos, `<form>` | Un chat cargado tarde por JavaScript se escapa |
| Reseñas | Cuántas tiene en Google Maps | Indican clientes de forma indirecta y varían mucho por rubro |
| Anuncios | Píxel de Meta, etiqueta de Google Ads | Instalado no significa activo: el correo no lo afirma sin comprobarlo |
| Si busca gente | "Trabaja con nosotros" y parecidos | Puede ser solo un enlace antiguo en el menú |
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
| "Falta instalar el puente de WhatsApp" | `cd whatsapp` y `npm install`, y vuelve a abrir el panel |
| Un número dice "Sesión cerrada" | Lo desvinculaste desde el celular o WhatsApp lo bloqueó. Abre WhatsApp en ese celular: si está bloqueado, no lo reconectes |
| El QR no aparece | Espera 10 segundos. Si sigue igual, toca **Reconectar**. El detalle está en `.whatsapp/numero-N/asistente.log` |
| Quedaron puentes corriendo | `python prospector.py whatsapp --detener` |

## Licencia y créditos

Licencia MIT: ver [LICENSE](LICENSE). Úsalo, modifícalo y compártelo. Se entrega
sin garantías, y lo que envíes con él es responsabilidad tuya.

El motor de búsqueda es una copia del [Cazador 2.0](https://github.com/diegovasquez-ai/Cazador-2.0)
(licencia MIT), en `prospector/cazador/`. No hay que instalar nada aparte.

WhatsApp funciona con el [WhatsApp Assistant](https://github.com/IgnacioMiranda6/whatsapp-assistant)
(licencia MIT), fijado a una versión en `whatsapp/package.json`.
