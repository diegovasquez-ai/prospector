# Prospector: instrucciones del agente

Correo frío B2B, para cualquier rubro: hasta 20 al día desde el Gmail del usuario,
cada uno como si alguien hubiera pasado dos horas mirando el negocio. El código hace
lo medible (buscar, visitar webs, contar señales, enviar a ritmo humano). Tú
investigas y redactas. Los correos salen aprobados en el panel: por el usuario o, si
te lo pide, por ti (ver Fases 8 y 9).

Lee `negocio.md` y `nicho.json` al empezar cada sesión: quién es, qué ofrece, a qué
rubro le vende y qué problema busca. Si no existen, dile que corra
`python prospector.py iniciar` antes de redactar nada: nunca escribas experiencia,
clientes ni resultados que no estén en `negocio.md`.

## Comandos

```
python prospector.py iniciar                             la primera vez: nicho, negocio.md y firma.txt (interactivo: lo corre el usuario)
python prospector.py buscar "Providencia" Vitacura       Fase 2
python prospector.py analizar                            Fases 3-5 (solo los nuevos)
python prospector.py lista                               candidatos por puntaje
python prospector.py preparar -n 20                      investiga y redacta sin sesión (claude -p)
python prospector.py panel                               Fases 7-9: aprobar, afinar, enviar
python prospector.py baja ana@negocio.cl                 lista negra
python prospector.py gmail                               conectar Gmail (interactivo: lo corre el usuario)
python prospector.py diario -n 20                        lo de cada mañana: preparar en modo rápido, subir y rastrear si faltan
python prospector.py subir                               sube los borradores nuevos al servidor (SERVIDOR_URL)
python prospector.py automatizar [--quitar]              diario 07:00 L-V + panel al encender (Windows)
python prospector.py metricas                            Fase 10
python prospector.py whatsapp                            busca el WhatsApp de los borradores que no lo tienen (no contacta a nadie)
python prospector.py whatsapp --detener                  apaga los puentes de WhatsApp que queden corriendo
python prospector.py treg                                conectar Treg (interactivo: lo corre el usuario)
python prospector.py contactos                           PRUEBA de Treg: ¿encuentra el correo del decisor? (gasta ≤ US$0,80, no toca nada)
python pruebas.py                                        comprobaciones, sin red
```

`preparar` y los subagentes hacen lo mismo con el mismo brief: el primero
corre solo (es lo que programa `automatizar`), los segundos dentro de una sesión.

Datos en `datos/negocios.json`, fichas en `fichas/<dominio>.md`, borradores en
`borradores/<dominio>.json`. El motor de búsqueda es una copia del Cazador 2.0 en
`prospector/cazador/` (MIT): el proyecto no depende de nada fuera de su carpeta. Se
usa a través de `prospector/puente.py`. `negocio.md`, `nicho.json`, `firma.txt`,
`comunas.txt`, `.env`, `datos/`, `fichas/` y `borradores/` son personales y no se
suben al repo.

## El nicho (`nicho.json`)

Lo propio del rubro no está en el código: qué buscar en Maps, qué palabras confirman
que un negocio sirve, a quién descartar, portales, software del rubro y qué publican.
Si el usuario quiere afinarlo, mira `python prospector.py lista --todas` y las
descartadas: una palabra muy común deja pasar a cualquiera y una muy rara descarta
buenos negocios. El campo `confirman_en_web` va sin acentos y en minúscula.
`nichos/inmobiliarias.json` es un ejemplo completo. Después de cambiarlo,
`python prospector.py analizar --todas` vuelve a medir la base.

## Quién vale la pena

`analizar` no aprueba por tener una web bonita. `analizar.calificar` suma evidencia de
clientes (reseñas de Maps, catálogo, sedes), capacidad de pago (software, anuncios, equipo),
trabajo manual y momento, y exige 2 puntos o más entre clientes y pago. Después
`prospector/filtro.py` le pasa la web a un modelo chico (`FILTRO_MODELO`, por defecto haiku):
aparta redes, otros rubros y a quien trabaja solo, y solo afirma que no sirve con una cita que
el código comprueba. Lo que aparta queda como floja, con el motivo, y se puede mandar a
investigar desde el Radar. Si Claude falla, el negocio sigue. No siempre responde igual: es
una primera lectura. Los umbrales son `resenas` y `equipo_minimo` en `nicho.json`.

El filtro es una primera lectura y no reemplaza la investigación: si esta lo contradice,
manda la investigación. El trabajo manual que cita sirve para escribir, pero apenas ordena.

## Cuando el usuario pida "prepárame los correos de hoy"

1. `python prospector.py lista`. Toma los candidatos por orden de puntaje que
   aún no tengan `borradores/<dominio>.json`, hasta 20. Si quedan pocos,
   avísale de que toca `buscar` en otra comuna o ciudad.
2. Investiga cada uno con **un subagente por negocio** (herramienta Agent,
   tipo general-purpose), de 5 en 5 en paralelo. A cada uno dale la carpeta
   del proyecto, el dominio y la orden de seguir `plantillas/investigacion.md`
   al pie de la letra, y que no envíe ni contacte nada. Reparte las
   fórmulas de asunto (A, B, C, D de `plantillas/secuencia.md`) rotando, una
   por subagente, para que la tanda no salga con asuntos iguales. El brief dice qué
   investigar, cómo elegir la observación y el formato del JSON.
3. Cuando terminen, valida que cada JSON cargue y resume al usuario en pocas
   líneas: cuántos quedaron por revisar, cuáles se descartaron y por qué, y
   lo que haya que saber (p. ej. "el gerencia@ es de la gerente, no de la fundadora").
4. Si hay servidor (`SERVIDOR_URL` en `.env.local`), corre `python prospector.py subir`:
   sube los borradores nuevos al servidor, que es donde se aprueban y salen. Dile
   cuántos subieron y que los revise en esa dirección. Si no hay servidor, dile que
   abra el panel: `python prospector.py panel`.

Investigar a fondo cuesta unos 7-12 minutos y bastantes tokens por negocio.
Es el precio de que no parezca una plantilla. Si el usuario quiere ir más rápido,
que lo pida.

## Reglas de redacción

- **El correo frío solo busca que respondan, y tiene que sonar humano.** El correo 1
  puede decir con sinceridad y en palabras simples qué hace quien escribe (la frase de
  Experiencia), pero sin jerga de producto (nada de agente de IA, CRM ni chatbot), no
  pide reunión ni llamada y no ofrece diagnóstico: cierra con un solo pedido, la frase
  de cierre de `negocio.md` (lo que vio va como afirmación, no como pregunta). Nada de
  frases de folleto: si no lo diría una persona en un café, se reescribe.
  Sí lleva la experiencia, tal cual la sección Experiencia de
  `negocio.md`, sin números que no estén medidos ahí. Los correos 2 y 3
  son recordatorios cortos, sin caso ni venta. La herramienta, el detalle
  del caso y la reunión van cuando responden (`plantillas/respuestas.md`).
  Estructura en `plantillas/secuencia.md`.
- **El correo 1 abre con un halago sincero**: algo real y específico de su negocio y por
  qué habla bien de ellos, antes de decir quién escribe. Un dato neutro o con doble lectura
  ("muchas sedes para un equipo tan chico") no es un halago. Ejemplos en
  `plantillas/investigacion.md`.
- **Cada dato del correo sale de la investigación, con su fuente.** Si no
  está, no va.
- Diferencia lo medido de lo declarado. "+ de 200 clientes" es lo que ellos
  dicen: se cita como suyo.
- **Píxel de Meta o etiqueta de Google Ads no significa anuncios activos.**
  Solo escribe "tienen anuncios activos" si se comprobó en la Biblioteca de anuncios.
- No les digas que les falta algo que ya tienen: si ya tienen WhatsApp, la duda
  pasa a ser quién responde fuera de horario.
- Nada técnico que suene a que les revisaste el código ("píxel", "tag", "GTM").
- Una reseña que se queja se usa para elegir el ángulo, nunca se cita ni se le
  echa en cara.
- De tú al decisor y de ustedes a la empresa, en el español natural de su país
  (`pais` en `nicho.json`): nada de "vosotros" fuera de España ni modismos de otro
  país. Correo 1 de 50 a 90 palabras y sin enlaces (la única excepción la pone el envío, no
  tú: la prueba A/B de la demo, `envio.demo_linea`, si hay `DEMO_URL`, en la mitad de los correos hasta
  `PRUEBA_DEMO_META`; no la escribas en el borrador), sin las muletillas de "Lo que
  delata a la IA" (`plantillas/secuencia.md`; el panel avisa con `correos.SUENA_IA`). Asunto con su nombre y distinto
  en cada negocio: una de las cuatro fórmulas de `plantillas/secuencia.md`, de
  preferencia con un gancho suyo ("Laura, probé el cotizador de Lircay"). Orden del
  correo: el halago, lo que notaste, quién escribe y la puerta.
- El caso real lleva resultado solo si está en `negocio.md`.
- **Sin firma en el cuerpo.** La firma vive en `firma.txt` y el panel la pone al enviar.
- Nunca deduzcas un correo por patrón: es *supuesto* y el panel no deja enviarlo.
  Lo que encuentre Treg (`contactos`) es una prueba: no se copia a los
  borradores hasta que el usuario decida, con el informe en `datos/treg-prueba.md`.

## Fase 7: el panel

`python prospector.py panel` abre http://127.0.0.1:8765. El usuario ve cada
borrador junto a la investigación, edita, pide cambios ("Afinar con Claude"
llama a `claude -p` con la nota), marca lo poco que había que comprobar a mano
(solo lo que haría falso el correo; el resto es `contexto` y no bloquea) y aprueba.
"Enviarme prueba" le manda los tres correos a sí mismo en un hilo.

El panel no deja aprobar si: falta la firma o tiene huecos `{...}`, queda
algo sin comprobar, el correo es supuesto, hay huecos sin rellenar o está en la lista negra.

La pestaña **Radar** (`prospector/radar.py`) muestra toda la base ordenada
por oportunidad, con su ficha. Desde ahí se puede rastrear una comuna o ciudad
(buscar + analizar en un hilo) o mandar a investigar un negocio concreto
(`preparar.investigar`, con el mismo brief). Nunca investiga uno que ya tenga
borrador, porque lo pisaría.

## Fases 8 y 9: envío y respuestas (lo hace el panel)

- Sale por SMTP de su Gmail con contraseña de aplicación (`.env`).
  Todo sale por la cola del panel: nunca con el conector de Gmail ni por SMTP directo.
  Si el usuario prendió `ENVIO_AUTO_APROBAR=si`, el panel aprueba solo los correos que
  `correos.revisar` deja pasar sin ningún problema, hasta el tope del día
  (`envio.auto_aprobar`); `python prospector.py diario` investiga en modo rápido, sube y
  rastrea más comunas si al WhatsApp le quedan pocos negocios. Lo que tiene algo que
  comprobar espera al usuario.
  **Puedes aprobar y enviar correos solo si el usuario te lo pide**: apruébalos por la API
  del panel (`/api/borradores/<dominio>/aprobar`) y, si la cola está apagada, enciéndela
  (`/api/envio`). Sigue valiendo todo lo que el panel exige: solo apruebas lo que pasa
  `correos.revisar` sin problemas, nunca marcas "comprobado" algo que no comprobaste, y no
  subes `max_dia` ni cambias el ritmo ni el horario por tu cuenta. Al terminar, dile cuáles
  aprobaste, a quién van y cuándo salen.
- **La demo es opcional** (`DEMO_URL`). Si existe, el envío la agrega en la mitad de los
  correos 1 (prueba A/B, `envio.demo_linea`, hasta `PRUEBA_DEMO_META` por grupo): no la
  escribas tú en el borrador. Es también el único enlace que puede mandar el agente.
- **WhatsApp es un canal aparte** (`prospector/wa_prospeccion.py`, envío en
  `whatsapp.py`, puente en `wa_puente.py`): cada negocio va por UN canal. Por WhatsApp,
  los que publican uno y no tienen correo o quedaron flojos (prospectos en
  `datos/whatsapp/`); el correo no lleva WhatsApp. El método y sus textos están en
  `plantillas/whatsapp.md` (7 fases: saludo de 3 líneas → cuando responde, el pitch corto
  e igual para todos, en audio o texto (se alternan para medir) → confirmación → Loom →
  hasta 3 seguimientos solo si aceptó el Loom → llamada de diagnóstico → agenda). Esa
  plantilla es un punto de partida: el usuario la reescribe con su oferta y su tono.
  Por defecto, cada saludo lo aprueba el usuario uno por uno en la pestaña WhatsApp; salen
  en `WA_VENTANAS`, con `WA_PAUSA` minutos entre mensajes de un mismo número y
  `WA_PAUSA_TOTAL` entre un saludo y el siguiente contando todos los números, rotando y sin
  pasar del calentamiento (`WA_CALENTAMIENTO`, `WA_TOPE_n`, `WA_RAMPA_n`). Si no responde
  en `WA_SIN_RESPUESTA` días, no se le insiste. Reglas que no se negocian, aunque el
  usuario las pida como atajo (explícale que es lo que hace banear los números):
  - con `WA_AUTO_APROBAR=si` (lo prende el usuario, después de leer el riesgo) el saludo sale
    sin su clic, pero SOLO a negocios verificados por `wa_filtro.py`: reglas fijas sobre el
    nombre y la categoría (fuera cámaras, gremios, comparadores, directorios y lo que diga
    `verificar` en `nicho.json`) y además Claude lee su web y lo confirma con una cita que
    exista. Lo que no pasa, o no se pudo leer, no sale solo: espera su decisión en "Por
    aprobar". No aflojes ese filtro, no lo saltes y no subas los topes por tu cuenta;
  - con `WA_AUTO_RESPONDER=si` las respuestas a lo que escribe el cliente las da el agente
    (`prospector/agente.py`): el usuario solo pega el Loom y entra a la reunión. El agente
    sigue el método, usa los textos de la plantilla para los pasos fijos y, para el resto,
    las respuestas del usuario y la sección "Cómo escribo por WhatsApp" de `negocio.md`
    como modelo. Controles que no se quitan: solo el chat de ese prospecto, nunca un precio
    ni una cifra, ningún enlace salvo `DEMO_URL`, nada con huecos, como mucho `MAX_POR_DIA`
    mensajes al día por chat, `WA_ESPERA_RESPUESTA` segundos desde el último mensaje del
    cliente, horario `WA_HORARIO_AGENTE`, y los dos interruptores. Si uno de sus números
    también es el de su negocio, el agente solo atiende prospectos a los que se les mandó el
    saludo, y si ese chat ya existía antes del saludo (`contacto_previo`) no se mete; tampoco
    sale un saludo en frío a un número con el que ya hay un chat. No lo amplíes a otros
    chats. Lo que no sabe contestar (preguntas fuera de `negocio.md`, quejas, audios,
    referencias) lo "escala": no manda nada y le deja el chat al usuario en el CRM como
    "para hoy". Cuando eligen horario, confirma y le avisa para que mande el enlace. A
    CUALQUIER respuesta al saludo (persona, saludo automático, menú, "fuera de horario") le
    manda el pitch, sin pasar por Claude; la excepción es un mensaje que dice que es un bot o
    un asistente virtual: ese chat se descarta (`agente.primera_respuesta`,
    `whatsapp.bot_declarado`). Si después del pitch le piden sus datos (nombre y RUT o DNI,
    correo), no contesta: apaga el bot de ese chat y se lo deja (`agente.pide_datos`). A
    quien recibió el pitch y no le escribió una persona, UN seguimiento
    (`seguimiento_pitch`, `WA_SEGUIMIENTO_PITCH_HORAS`), en horario de seguimientos; nada
    más. No le agregues pasos que comprometan al usuario (precios, descuentos, fechas de
    entrega, nombres de clientes) ni le quites el escalamiento. Sin `WA_AUTO_RESPONDER`,
    "Sugerir respuesta" solo deja el texto en la caja. No existen recordatorios a quien no
    respondió el saludo ni reintentos solos de un envío en duda. Los seguimientos del Loom
    (24, 48 y 72 h) salen porque el usuario los aprobó al pegar el enlace;
  - el aviso de riesgo del panel se queda y hay que aceptarlo antes de conectar;
  - solo a números que el negocio publica como WhatsApp, nunca a un teléfono suelto;
  - **tú nunca envías WhatsApp**: ni con el puente ni de otra forma.
  Si te pide textos para WhatsApp, parte de `plantillas/whatsapp.md`: sin cifras que no
  estén en `negocio.md`, de tú y en el español de su país, generales (sin el nombre de la
  persona) y sin nombrar clientes. Sesiones en `.whatsapp/` (no se suben ni se leen).
  La sección Conversaciones (`whatsapp.conversaciones`) lee SOLO el chat de cada prospecto
  al que ya se le escribió (`wa_puente.conversacion`, por número): no la amplíes a las
  demás conversaciones de sus números. Tampoco leas esos chats para "sacar su tono": que
  pegue mensajes suyos en `negocio.md`. Un número con "prospectar" apagado no manda
  mensajes en frío.
  El usuario puede apagar lo automático por chat (`bot_apagado`, `whatsapp.bot_chat`) o
  todo (`activo`): no agregues ningún envío que se salte esos dos interruptores.
  `WA_AUTO_PREPARAR` sin `WA_AUTO_APROBAR` solo deja saludos en "Por aprobar". La lista
  trae cursos, gremios, proveedores y webs abandonadas mezclados con los negocios que
  busca: por eso lo automático pasa siempre por `wa_filtro`, y nunca hay un "aprobar todos".
- Ritmo: como mucho 20 nuevos al día, de lunes a viernes de 9 a 18, con
  6-18 minutos al azar entre uno y otro. Seguimientos el día 3 y el 7 en el
  mismo hilo. Solo corre mientras el panel está abierto.
- Antes de cada seguimiento mira la bandeja por IMAP: si alguien de su
  dominio respondió, la secuencia se para y queda "respondió".
- El usuario clasifica la respuesta en el panel: sí → diagnóstico de una página
  + llamada de 20 min. Info → el diagnóstico, no un PDF. Ahora no → retomar
  en 60 días. No / baja → lista negra, para siempre (`datos/exclusiones.txt`).
- Si pide ayuda para contestar, parte de `plantillas/respuestas.md`: propone
  horarios concretos y busca una decisión clara, sin insistirle a quien dijo que no.

## En el servidor

Se despliega con el `Dockerfile` (en Coolify o cualquier Docker, ver README). Lo personal vive en el
volumen `/data` (el entrypoint lo enlaza). Fuera de 127.0.0.1 el panel exige
`PANEL_CLAVE` y una sesión (`prospector/acceso.py`): no lo debilites (nada de abrir
rutas de la API sin sesión, ni desactivar la cabecera X-Panel). Nunca pidas ni escribas
en el chat contraseñas, tokens ni llaves SSH: van en las variables de entorno del servidor.

## Después de que responden: el CRM

`prospector/crm.py`, pestaña CRM del panel, dentro de cada borrador o prospecto de
WhatsApp en `"crm"`. Etapas (el método de `plantillas/whatsapp.md`): respondió → pitch
enviado → aceptó el video → video enviado (Loom de 60-90 s, hasta 3 seguimientos) → llamada de
diagnóstico → reunión agendada → propuesta enviada → cliente / perdido / retomar.
Quien llega por correo ya leyó el pitch en el correo 1: no pasa por «pitch enviado» y la
ficha le muestra las respuestas de `plantillas/respuestas.md` (`wp.pasos_correo`): la
llamada si quiere saber más, el Loom solo si duda, y 2 seguimientos como mucho.
Cada uno tiene un próximo paso con fecha. Los audios, Looms y llamadas los hace el
usuario; tú solo escribes guiones ("Guion con Claude" usa `crm.guion`, sin herramientas)
con lo investigado, lo que respondió y `negocio.md`, sin inventar casos ni cifras. Si te
pide un guion en la sesión, sigue el mismo criterio y lee `borradores/<dominio>.json`.

## Fase 10: medir

Cada semana: tasa de respuesta, respuestas positivas, diagnósticos
entregados y llamadas. Se cambia una sola variable por vez (asunto, tipo de
observación o CTA). Si pide el informe, sácalo de `borradores/*.json`
(estados y fechas de `envios`).
