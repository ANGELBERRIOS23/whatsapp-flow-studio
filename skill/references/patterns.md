# Recetas y patrones — WhatsApp Flows

Patrones probados a partir de los flows del usuario (Flow1–19). Todos son
**flows estáticos** (sin endpoint) salvo la última sección.

## 1. Pregunta visible arriba del input (patrón por defecto del usuario)

WhatsApp solo muestra el `label` pequeño dentro del campo. Para que la pregunta
se vea, va como `TextSubheading` antes del input:

```json
{ "type": "TextSubheading", "text": "👤 ¿Cuál es tu nombre?" },
{ "type": "TextInput", "input-type": "text", "label": "Escribe tu nombre",
  "name": "nombre_a1b2c3", "required": true }
```

En la spec basta con `{"text": "¿Cuál es tu nombre?", "label": "Escribe tu nombre"}`
y el builder inserta el subheading (con `question_as_subheading: true`).

## 2. Multi-pantalla con reenvío de datos (lo automatiza el builder)

Cada pantalla vuelve a **declarar** en `data` los campos previos y a **reenviarlos**
en el payload, para que lleguen todos al `complete` final.

- Pantalla 0 (`navigate`): payload solo con `${form.*}` de esa pantalla.
- Pantalla 1: `data` declara los campos de la 0; payload = `${form.*}` propios +
  `${data.*}` de la 0.
- Pantalla final (`complete`): payload con **todos** los campos acumulados.

Claves de payload que usa el builder de Meta: `screen_<índice>_<label_saneado>_<n>`.
No es obligatorio ese nombre exacto, pero el builder de Meta lo genera así y el
script lo replica para que se vea "nativo".

## 3. Opción "Otro (especificar)"

Dropdown/Radio con una opción "Otro" + un `TextInput` opcional debajo:

```json
{"dropdown": "Motivo", "label": "Selecciona", "options": ["Consulta", "Queja", "Otro (especificar abajo)"]},
{"text": "Especificar otro", "label": "Escribe aquí", "required": false, "helper": "Solo si elegiste 'Otro'"}
```

(En flows estáticos no se puede mostrar/ocultar según la selección sin endpoint;
por eso se deja el campo opcional con un helper. Ver receta 7 para condicional.)

## 4. Escala 1–10 / calificación

Dropdown con opciones "1".."10" (o Radio si son pocas). En la spec:

```json
{"dropdown": "Nivel de satisfacción (1–10)", "label": "Elige un número",
 "options": ["1","2","3","4","5","6","7","8","9","10"]}
```

## 5. Consentimiento + Términos y Condiciones (read more)

Label corto con `terms` → genera el "Read more" hacia una pantalla de solo texto:

```json
"blocks": [
  {"optin": "He leído y acepto los términos y condiciones", "terms": "TERMINOS"}
],
...
"terms_screens": [
  {"id": "TERMINOS", "title": "Términos y condiciones",
   "blocks": [{"heading": "Términos"}, {"body": "Texto legal largo..."}, {"image": "/ruta/logo.png"}]}
]
```

⚠ Esa pantalla de términos **va al final del array** y **no lleva Footer** (es un
callejón sin salida al que se entra con "Read more" y se sale con "atrás"). El
builder la coloca al final automáticamente. Ver `gotchas.md` regla Flow19.

## 6. Solo lectura / consentimiento antes de empezar

Primera pantalla sin inputs, solo `TextBody` + Footer `navigate` (Flow2):

```json
{"title": "📝 Consentimiento", "blocks": [{"subheading":"Introducción"},{"body":"..."}], "footer": "Continuar"}
```

## 7. Saltos de lógica / navegación condicional (gates) — v4+

"Si responde X, saltar a otra pantalla." En un flow **estático** (sin servidor)
esto se hace con el componente `If` conteniendo un `Footer` en **ambas** ramas
(then/else) que navegan a pantallas distintas.

**El builder lo genera solo** con `gate` en un radio/dropdown:
```json
{"radio": "¿Seguir en contacto?", "label": "Tu respuesta", "key": "contacto",
 "options": ["Sí", "No", "Tal vez"], "gate": {"when": "No", "goto": "GRACIAS"}}
```
→ genera:
```json
{ "type": "If",
  "condition": "${form.contacto_ab12cd} == '1_No'",
  "then": [ {"type":"Footer","label":"Continuar","on-click-action":{"name":"navigate","next":{"name":"GRACIAS","type":"screen"},"payload":{ /* TODOS los campos, los futuros vacíos */ }}} ],
  "else": [ {"type":"Footer","label":"Continuar","on-click-action":{"name":"navigate","next":{"name":"P4","type":"screen"},"payload":{ /* incremental */ }}} ] }
```
Clave (lo automatiza el builder): la pantalla `goto` declara en su `data` **todos**
los campos del flujo, y **cada** camino que llega a ella debe enviarlos todos
(los aún no recogidos van vacíos `""`/`[]`). El validador avisa si algún camino
deja de enviar un campo declarado.

Reglas del `If`: anidar máx 3 niveles; un `Footer` dentro de un `If` debe estar en
`then` **y** `else` (por eso `else` se vuelve obligatorio y no puede haber otro
Footer fuera). Para mostrar/ocultar componentes (no navegar) usa `If`/`Switch` a
mano con `condition`/`cases`.

## 7b. Campos condicionales (mostrar/ocultar) — a mano

```json
{ "type": "If",
  "condition": "${form.tiene_mascota} == '0_si'",
  "then": [ { "type": "TextInput", "label": "Nombre de la mascota", "name": "mascota", "required": true } ],
  "else": [ ] }
```

## 8. Selección de fecha y hora

`DatePicker` para la fecha + dos `Dropdown` (hora 00–23, minutos) para la hora
(Flow4). No existe "time picker" nativo; se hace con dropdowns.

## 9. Subir foto o documento

```json
{ "type": "PhotoPicker", "label": "Sube tu comprobante", "name": "comprobante",
  "min-uploaded-photos": 1, "max-uploaded-photos": 3, "max-file-size-kb": 10240 }
```
(Requiere versión reciente y suele ir con endpoint para procesar el archivo.)

## 10. Flow con endpoint / "punto de conexión" (dinámico)

Habilita datos en tiempo real: **disponibilidad tipo booking** (horas/citas libres),
validación con mensaje de error, precios, y ramificación de pantallas según el
backend. Es lo que se necesita para "verificar disponibilidad y demás".

En el Flow JSON:
- `"data_api_version": "3.0"` al nivel raíz + URL del endpoint.
- Acción `data_exchange` (en vez de `navigate`/`complete`) en el botón/selección.
- El endpoint responde `{"version":"3.0","screen":"SIGUIENTE","data":{...}}` o
  `{"screen":"SUCCESS", "data":{...}}` para terminar.
- Declara en `screen.data` **todos** los campos que el endpoint pueda devolver.

Del lado servidor (esto es lo pesado — es un proyecto de backend, no solo JSON):
- **HTTPS público** con TLS válido que acepta POST (Node/Python/etc.).
- **Cifrado híbrido obligatorio**: generas un par de llaves RSA, subes la pública
  a Meta; cada request trae `encrypted_flow_data` + `encrypted_aes_key` +
  `initial_vector` que descifras (RSA-OAEP-SHA256 → AES-GCM) y vuelves a cifrar la
  respuesta (IV con XOR-flip, base64).
- Validar firma `X-Hub-Signature-256` (app secret) y responder al **health check**
  (`ping` → `{"status":"active"}`).
- Requisitos de **disponibilidad y latencia** (WhatsApp monitorea el endpoint).
- Esfuerzo típico: ~4–8 días (la mayoría es el "plumbing" de cifrado; hay ejemplos
  oficiales en Node/Python/PHP/Java/Go/C#).

La mayoría de los casos **no** necesitan esto: con `navigate` + `complete`
(estático) el webhook recibe todas las respuestas al final. Usa endpoint solo
cuando necesites datos/validación en vivo. Este builder genera flows **estáticos**;
un flow con endpoint hay que armarlo aparte junto con el servidor.
