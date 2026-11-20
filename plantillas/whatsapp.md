# Prospección por WhatsApp: el método

Es un canal aparte del correo: cada negocio va por **uno solo**. Por correo, los
investigados a fondo; por WhatsApp, los que publican un WhatsApp y no un correo (o
quedaron flojos en el Radar).

El objetivo NO es vender. Es:

1. Que responda al primer contacto.
2. Que te dé permiso para mandarle algo de valor.
3. Mandarle un Loom que lo califica.
4. Llevarlo a una llamada de diagnóstico (no de venta).

La venta ocurre en la llamada de diagnóstico o después, nunca en el primer contacto.

**Esto es una plantilla: reescríbela con tus palabras antes de prender nada.** El panel y
el agente leen los textos de los bloques de abajo, tal cual. Están en un español neutro
que tira a chileno: ajústalos al de tu país (si escribes de vos, de usted o con otros
modismos, cámbialos aquí).

Lo que está entre llaves se rellena solo:

| Llave | Qué pone |
|---|---|
| `{yo}` | tu nombre (`GMAIL_NOMBRE` o la primera línea de `firma.txt`) |
| `{negocio}` | el nombre corto del negocio al que le escribes |
| `{nombre}` | la persona, solo si la escribiste a mano (variación C) |
| `{rubro}`, `{singular}` | de `nicho.json` |
| `{problema}`, `{resultado}` | `textos.problema` y `textos.resultado` de `nicho.json` |
| `{loom}` | el enlace del video que pegas en el panel |
| `{demo}` | `DEMO_URL`, si tienes una demo que se pueda probar |
| `{dia}`, `{dia_siguiente}` | los próximos días hábiles |
| `{horarios}` | `REUNION_HORARIOS` (por defecto "a las 11 de la mañana o a las 4 de la tarde") |
| `{reunion}` | "por videollamada", o "por videollamada o, si prefieres, voy a verlos a la oficina" si su dirección calza con `REUNION_PRESENCIAL` |

Una llave que no se puede rellenar (por ejemplo `{demo}` sin `DEMO_URL`) queda a la vista y
ese mensaje no sale: si no tienes demo, reescribe `seguimiento_3` e `info` sin ella.

Van generales, sin el nombre de la persona: casi nunca se sabe quién contesta el WhatsApp
de un negocio.

Mejores horarios para el mensaje 1 (lo respeta el envío, `WA_VENTANAS`): martes 10:00,
miércoles 17:00, jueves 10:00 o 17:00 y sábado de 10 a 12. Evita lunes, viernes en la
tarde y domingos.

## conexion_a · Fase 1 · mensaje de conexión (variación A)

Texto corto de 3 líneas. Sin pitch, sin venta, sin explicación: solo abrir la puerta.
Que entre en la vista previa de WhatsApp (~90 caracteres), 0 o 1 emoji. Si no
responde, no se insiste con este mensaje.

```
Hola, buen día
Por acá te escribe {yo}
Te quería hacer una consulta
```

## conexion_b · Fase 1 · variación B (casual)

```
Hola, qué tal
Soy {yo}, te escribo por algo puntual
¿Te puedo hacer una consulta?
```

## conexion_c · Fase 1 · variación C (con nombre)

Solo cuando sabes el nombre de la persona que contesta ese WhatsApp.

```
Hola {nombre}, buen día
Por acá te escribe {yo}
Te quería hacer una consulta puntual
```

## pitch · Fase 2 · cuando responde: el pitch (audio de 40-45 s o texto), igual para todos

Son dos mensajes: el saludo y este. La estructura es siempre la misma: por qué le
escribes, el problema que tiene la mayoría del rubro, lo que haces (qué resuelve y qué
deja listo) y el pedido: permiso para mandar un video. Va general, así el audio sirve para
todos. Solo cifras que estén en `negocio.md`, y sin nombrar clientes.

El panel alterna audio y texto entre prospectos para medir cuál consigue más videos
aceptados. Si te toca audio: grábalo desde el celular con audífonos, sin eco,
conversando y no leyendo. En audio puedes partir saludando ("Hola, ¿cómo estás?"); en
texto no, porque ya se saludaron y se lee como un mensaje pegado.

Este texto sale de `nicho.json`; lo normal es que lo reescribas entero con tu oferta.

```
Gracias por responder.
Te escribo porque trabajo con {rubro} y estuve viendo lo que hacen ustedes.
La mayoría tiene el mismo problema: {problema}.
Lo que hago es ayudarles a {resultado}.
Si te hace sentido, ¿te parece que te mande un video corto mostrando cómo funciona?
```

## seguimiento_pitch · Fase 2 · 6 h después del pitch, si no contestó

Uno solo, y solo si después del pitch no escribió una persona. Sale en horario de
seguimientos (`WA_HORARIO_SEGUIMIENTOS`), con el agente activo y el chat encendido. Si no
contesta, no se insiste más.

```
Hola, ¿pudiste ver mi mensaje?
```

## decisor · Si quien contesta no decide

Ese WhatsApp casi nunca lo atiende el dueño. El video se puede reenviar: úsalo.

```
¿Con quién conviene que lo vea? Si quieres te mando el video y se lo reenvías.
```

## cierre · Si dice que no le interesa

No se insiste. Después pásalo a Perdido en el CRM.

```
Perfecto, gracias por responder. Que tengan buena semana.
```

## confirmacion · Fase 3 · cuando acepta el video

Solo si responde "sí, dale", "mándalo" o algo parecido.

```
Genial.
El video me toma un poco de tiempo porque lo armo para ustedes, así que en las próximas 24 horas te lo envío.
Cuando lo veas vas a entender rápido si esto aplica o no a cómo trabajan hoy.
```

## loom_guion · Fase 4 · el Loom (2-3 min, personalizado)

No se envía: es tu guion para grabar.

```
0:00-0:15  Tu cara: "Hola, soy {yo}. Te explico rápido lo que te mencioné de {negocio}."
0:15-0:50  Pantalla: su web, o donde se ve el problema en su caso.
0:50-1:50  Lo que haces, aplicado a ellos: cómo se vería con su negocio.
1:50-2:30  Qué deja listo y cómo se mide.
2:30-3:00  Cierre: "Si te hace sentido, agendamos una llamada corta de 15 a 20 minutos."
```

## envio_loom · Fase 4 · el mensaje con el Loom

En el panel pegas el enlace y sale este mensaje. Ahí mismo apruebas los seguimientos:
después salen solos si no responde.

```
Mira, acá está el video que te había comentado:
{loom}
Dura unos 3 minutos y muestra cómo se vería en el caso de ustedes.
¿Cuándo crees que lo puedas ver?
```

## seguimiento_1 · Fase 5 · 24 h después del Loom

Los seguimientos son SOLO para quien aceptó el Loom. Si no respondió al mensaje 1, no
se insiste. Si respondió pero no aceptó el video, no se presiona. Máximo 3.

```
Hola 🙂
¿Pudiste ver el video?
```

## seguimiento_2 · Fase 5 · 48 h después del Loom

Rompe el patrón del mensaje formal: se nota que eres una persona y no un embudo.

```
👋
```

## seguimiento_3 · Fase 5 · 72 h después del Loom: la demo

El último no insiste con lo mismo: le da algo nuevo y más rápido que el video. Necesita
`DEMO_URL`; si no tienes demo, reescríbelo (por ejemplo, una pregunta corta sobre su caso).

```
Por si no alcanzaste a ver el video, te dejo algo más rápido: acá lo puedes probar tú mismo.
{demo}
Toma un minuto. Si te hace sentido, me cuentas.
```

## info · Si pide que le mandes información

Nada de PDF ni folleto: algo que pueda probar. Solo cuando ya hay conversación, nunca
en el saludo ni en el pitch (un enlace en frío es lo que más se reporta).

```
Mejor que mandarte un PDF: acá lo puedes probar tú mismo.
{demo}
Toma un minuto. Me cuentas qué te parece.
```

## cta_audio · Fase 6 · si vio el Loom y respondió con interés: audio de 25-30 s (o texto)

Nunca digas "llamada de venta": es una llamada de diagnóstico de 15 a 20 minutos.
Siempre con dos horarios.

```
Si te parece, podemos tener una llamada corta de diagnóstico.
No es una llamada de venta: es para entender bien cómo trabajan hoy y ver si tiene sentido aplicar algo así o no.
Son 15 a 20 minutos, {reunion}.
¿Te viene bien el {dia} {horarios}?
```

## precio · Si pregunta cuánto vale

No se da un número por escrito: depende de su caso y sale de la llamada.

```
Mira, depende de cómo trabajan hoy y del tamaño del equipo, así que no quiero tirarte un número suelto.
Lo más rápido es que lo veamos en una llamada corta de 15 a 20 minutos, y ahí podría decirte un valor más aproximado.
¿Te viene bien el {dia} {horarios}?
```

## numero · Si pregunta de dónde sacaste su número

Corto y sin disculparse: es un número que publican.

```
El número lo saqué de su página web.
```

## ya_tienen · Si dice que ya tienen algo parecido

No se critica lo que tienen.

```
Buenísimo, eso ayuda harto. No se trata de reemplazar lo que ya usan: en el video ves en un par de minutos si les suma o no.
¿Te lo mando igual?
```

## bot · Si pregunta si es un bot

```
Jajaja no, soy yo. Escribo yo mismo. ¿Por qué parezco un bot?
```

## agenda · Si quiere reunirse: dos horarios

```
Buenísimo. Son 15 a 20 minutos.
¿Te viene bien el {dia} {horarios}?
```

## agenda_otro · Si no puede a esa hora: el día siguiente

```
Sin problema. ¿Y el {dia_siguiente}, a esas mismas horas?
```

## agendado · Cuando elige horario

```
Perfecto, quedamos así. Te mando el enlace de la videollamada por acá.
```

## Fase 7 · la agenda

Cuando elija, mándale el enlace de Meet o Zoom (o pídele la dirección, si vas a su
oficina). Al confirmar, el CRM lo pasa a "Reunión agendada". Recuérdaselo el día
anterior con un mensaje corto.
