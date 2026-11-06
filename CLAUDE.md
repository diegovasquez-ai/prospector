# Prospector: instrucciones del agente

Correo frío B2B, para cualquier rubro: hasta 20 al día desde el Gmail del usuario,
cada uno como si alguien hubiera pasado dos horas mirando el negocio. El código hace
lo medible (buscar, visitar webs, contar señales, enviar a ritmo humano). Tú
investigas y redactas. El usuario aprueba cada correo en el panel antes de que salga.

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
python prospector.py automatizar [--quitar]              preparar 07:00 L-V + panel al encender (Windows)
python prospector.py metricas                            Fase 10
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
4. Dile que abra el panel: `python prospector.py panel`.

Investigar a fondo cuesta unos 7-12 minutos y bastantes tokens por negocio.
Es el precio de que no parezca una plantilla. Si el usuario quiere ir más rápido,
que lo pida.

## Reglas de redacción

- **El correo frío solo busca que respondan.** El correo 1 no nombra la
  herramienta (nada de agente de IA, CRM, automatizar ni chatbot), no pide
  reunión y no ofrece diagnóstico: cierra con un solo pedido, la frase de cierre de
  `negocio.md` (lo que vio va como afirmación, no como pregunta).
  Sí lleva la experiencia, tal cual la sección Experiencia de
  `negocio.md`, sin números que no estén medidos ahí. Los correos 2 y 3
  son recordatorios cortos, sin caso ni venta. La herramienta, el detalle
  del caso y la reunión van cuando responden (`plantillas/respuestas.md`).
  Estructura en `plantillas/secuencia.md`.
- **El correo 1 abre con la prueba**: algo real y específico de su negocio y por
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
  país. Correo 1 de 80 a 120 palabras y sin enlaces. Asunto con su nombre y distinto
  en cada negocio: una de las cuatro fórmulas de `plantillas/secuencia.md`, de
  preferencia con un gancho suyo ("Laura, probé el cotizador de Lircay"). Orden del
  correo: la prueba, la señal, quién escribe y la puerta.
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
  **Tú nunca envías correos**: ni con el conector de Gmail ni de otra forma.
  Todo sale por la cola del panel, después de que el usuario apruebe.
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

## Fase 10: medir

Cada semana: tasa de respuesta, respuestas positivas, diagnósticos
entregados y llamadas. Se cambia una sola variable por vez (asunto, tipo de
observación o CTA). Si pide el informe, sácalo de `borradores/*.json`
(estados y fechas de `envios`).
