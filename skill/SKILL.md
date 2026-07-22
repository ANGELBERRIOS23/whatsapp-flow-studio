---
name: whatsapp-flow
version: 1.0.0
description: >-
  Construye formularios nativos de WhatsApp (WhatsApp Flows) generando el Flow
  JSON válido y sin errores, listo para importar en el Administrador de WhatsApp /
  Meta Flow Builder. Úsala cuando el usuario diga "crear/armar/hacer un flow de
  WhatsApp", "formulario de WhatsApp", "encuesta/registro/cita en WhatsApp",
  "arma este cuestionario para WhatsApp", pida un flow "grande y completo", o pase
  preguntas para convertirlas en un flow. Genera pantallas encadenadas, reenvío de
  datos entre pantallas, pantallas de "términos" (read more de OptIn), imágenes en
  base64, y valida límites de caracteres y estructura antes de entregar. Evita los
  errores típicos del constructor visual de Meta (que además no deja editar lo ya
  creado).
license: MIT
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# WhatsApp Flow Builder

Genera **WhatsApp Flow JSON** válido para formularios interactivos dentro de
WhatsApp. El objetivo es que el usuario pueda pegar el JSON en el
**Administrador de WhatsApp → Flows → Editor / Endpoint "..."→ Editar JSON** y
que **importe sin errores** a la primera.

## Por qué existe esta skill

El constructor visual de Meta es tedioso, y una vez que creas un Flow **no te
deja editarlo cómodamente**. Aquí describimos el flow en una **spec compacta** y
un script genera el JSON correcto (nombres, claves de payload, reenvío de datos,
declaraciones `data`) — que es justo donde se cometen los errores a mano.

## Modelo mental (lee esto primero)

- Un Flow es un array de **pantallas** (`screens`). Cada pantalla es un
  formulario de una sola columna (`SingleColumnLayout`) con un `Form` dentro.
- **Flows estáticos (lo normal aquí):** sin servidor/endpoint. Los datos van de
  pantalla en pantalla con la acción `navigate` y al final se entregan todos
  juntos con la acción `complete` (llegan al webhook/chat). **Todos los ejemplos
  del usuario (Flow1–19) son de este tipo.** No uses `data_exchange`,
  `routing_model` ni `data_api_version` salvo que el usuario pida un endpoint.
- La **última** pantalla que recoge datos es `terminal: true` y su botón (Footer)
  usa `complete`. Las demás usan `navigate` a la siguiente.
- **Reenvío de datos:** cada pantalla debe volver a declarar en su `data` los
  campos que vienen de pantallas anteriores y volver a pasarlos en el payload.
  Esto es 100 % automático con el script — hazlo con el script, no a mano.

## ⭐ Patrón de estilo del usuario (IMPORTANTE)

En WhatsApp, el input solo muestra un `label` pequeño (tipo placeholder) y **la
pregunta no queda visible afuera**. Por eso el usuario pone **la pregunta como un
`TextSubheading` ARRIBA de cada input**, y usa el `label` como pista corta.

El script hace esto por defecto (`question_as_subheading: true`): por cada input
con `q`/pregunta genera un `TextSubheading` con la pregunta y luego el input con
un `label` corto. **Mantén este patrón** salvo que el usuario diga lo contrario.

## Flujo de trabajo

1. **Reúne los requisitos.** Pregunta lo mínimo necesario: pantallas, preguntas,
   tipos de campo, opciones, cuáles son obligatorias, si hay imágenes, si quiere
   pantalla de términos y condiciones, y qué texto va en el botón final. Si el
   usuario ya dio todo, no preguntes de más.
2. **Escribe la spec compacta** (JSON) siguiendo el formato de abajo. Guárdala en
   el scratchpad o junto al proyecto.
3. **Genera el JSON** con el builder:
   ```bash
   python3 ~/.claude/skills/whatsapp-flow/scripts/build_flow.py spec.json -o flow.json
   ```
   El builder **valida automáticamente** al terminar.
4. **Si hay ERRORES**, corrígelos y vuelve a generar. Si solo hay **advertencias**,
   revísalas: casi siempre son límites de caracteres (el Flow suele importar
   igual, pero conviene acortar).
5. **Entrega** el contenido de `flow.json` al usuario + instrucciones de importación
   (abajo). No pegues base64 gigante en el chat: entrega la ruta del archivo.

Para flows simples de 1 pantalla puedes escribir el JSON a mano, pero **siempre**
pásalo por el validador antes de entregar:
```bash
python3 ~/.claude/skills/whatsapp-flow/scripts/validate_flow.py flow.json
```

### Flow Studio (app completa) y Visor (lite)

`scripts/studio.html` — **WhatsApp Flow Studio**: app autónoma (offline, sin
dependencias, un solo archivo) con **constructor visual** + **editor JSON en
vivo** + **vista previa** premium (toggles Android/iOS y claro/oscuro, simulación
de llenado/envío, validación en vivo). Incluye un port en JS del generador
`spec→Flow JSON` (mismo comportamiento que `build_flow.py`: nombres, payloads,
reenvío de datos, saltos `If`, ids válidos). Es la herramienta pensada para
publicar en GitHub (abrir `index.html` o vía GitHub Pages).

`scripts/viewer.html` — visor **lite** (solo vista previa + simulación), por si
quieres algo mínimo. Ambos renderizan cualquier Flow JSON **como se ve en
WhatsApp**, evalúan los saltos `If` en vivo, validan obligatorios y al completar
muestran el payload que recibiría el webhook.

Para entregar un visor con un flow ya cargado, inyecta el JSON en el bloque
`<script id="flowData" type="application/json">…</script>` (reemplaza `null`):
```bash
python3 - <<'PY'
import json
v=open('scripts/viewer.html',encoding='utf-8').read()
flow=json.load(open('flow.json',encoding='utf-8'))
emb=json.dumps(flow,ensure_ascii=False).replace('</','<\\/')
open('visor.html','w',encoding='utf-8').write(
  v.replace('<script id="flowData" type="application/json">null</script>',
            '<script id="flowData" type="application/json">'+emb+'</script>'))
PY
```
El usuario abre el `.html` en el navegador. También carga/pega JSON desde la barra
y acepta `?platform=ios&theme=dark&screen=ID` para abrir en un estado concreto.

## Formato de la spec compacta

```json
{
  "version": "7.3",
  "question_as_subheading": true,
  "screens": [
    {
      "id": "INTRO",
      "title": "Barra superior (máx ~30)",
      "blocks": [
        {"heading": "Título grande (máx 80)"},
        {"subheading": "Subtítulo (máx 80)"},
        {"body": "Texto largo (máx 4096)"},
        {"caption": "Texto pequeño (máx 4096)"},
        {"divider": true},
        {"image": "/ruta/foto.png", "height": 300, "scale-type": "contain"},

        {"text":     "¿Tu nombre?", "label": "Escribe tu nombre", "required": true, "helper": "..."},
        {"email":    "Correo",      "label": "correo@dominio.com"},
        {"phone":    "Teléfono",    "label": "+502 ..."},
        {"number":   "Edad",        "label": "Escribe tu edad"},
        {"password": "Clave",       "label": "••••"},
        {"passcode": "Código",      "label": "Código de acceso"},
        {"textarea": "Comentarios", "label": "Escribe aquí", "required": false},

        {"dropdown": "¿Ciudad?", "label": "Selecciona", "options": ["Guatemala", "Xela"], "default": "Xela"},
        {"radio":    "¿Sexo?",   "options": ["Masculino", "Femenino"]},
        {"checkbox": "Intereses","options": ["A", "B", "C"], "min": 1, "max": 2},
        {"chips":    "Intereses (chips)", "options": ["A", "B", "C"], "min": 1, "max": 2},
        {"date":     "Fecha de la cita", "label": "Selecciona fecha"},
        {"calendar": "Fechas de estadía", "mode": "range", "min-days": 1, "max-days": 14},
        {"email":    "Correo", "pattern": "[^@]+@[^@]+\\.[^@]+", "error": "Correo no válido", "default": "a@b.com"},

        {"optin": "Acepto los términos y condiciones", "terms": "TERMS"},

        {"text": "¿Tu nombre?", "label": "Escribe", "key": "nombre"},
        {"radio": "¿Seguir en contacto?", "label": "Tu respuesta", "key": "contacto",
         "options": ["Sí", "No"], "gate": {"when": "No", "goto": "GRACIAS"}}
      ],
      "footer": "Continuar"
    }
  ],
  "terms_screens": [
    {"id": "TERMS", "title": "Términos", "blocks": [{"body": "Texto legal..."}, {"image": "..."}]}
  ]
}
```

Reglas del formato:
- Las pantallas se **encadenan en el orden del array** (cada una navega a la
  siguiente). La última recoge datos → `complete`. Puedes forzar destino con
  `"next": "ID"`.
- `id` y `version` son opcionales (se autogeneran / default `7.3`).
- **`key`** (recomendado): fija el nombre del campo en los datos que llegan al
  webhook (`screen_0_nombre_1`). Sin `key`, se deriva de la pregunta.
- Cada opción puede ser texto `"Sí"` u objeto `{"title": "Sí", "id": "si", "description": "..."}`.
- `optin.terms` apunta al `id` de una pantalla en `terms_screens` → genera el
  "Read more". Esas pantallas van **al final** automáticamente (regla obligatoria,
  ver gotchas).

### Saltos de lógica (gates) — navegación condicional sin servidor

Un `radio`/`dropdown` puede llevar `"gate": {"when": "<título opción>", "goto": "<id pantalla>"}`.
El builder genera un componente `If` con un `Footer` en **ambas** ramas:
- si la respuesta == `when` → navega a `goto` (típicamente la pantalla final "Gracias");
- si no → sigue el flujo normal a la siguiente pantalla.

El builder se encarga de lo difícil: la pantalla `goto` recibe **todos** los campos
del flujo (los aún no recogidos se envían vacíos `""`/`[]`), de modo que el
`complete` final es consistente por cualquier camino. Requiere Flow JSON v4+.
`question_as_subheading: false` + bloques `subheading` explícitos = control 1:1
sobre dónde va cada pregunta (útil cuando la pregunta no cabe en el label).

## Reglas de oro para NO tener errores

Estas son las que rompen la importación (el validador las marca como **ERROR**):

1. La pantalla `terminal: true` **debe** tener un `Footer` con acción `complete`.
   Una terminal **no puede** usar `navigate`.
2. Debe existir al menos una acción `complete` (si no, el Flow nunca termina).
3. Todo `${form.X}` debe coincidir con el `name` de un input en **esa** pantalla.
4. Todo `${data.X}` debe estar declarado en el `data` de **esa** pantalla.
5. `navigate.next.name` debe apuntar a un `id` de pantalla que exista.
6. `id` únicos; **"SUCCESS" está reservado**, no lo uses.
7. Un solo `Footer` por pantalla. Componentes de entrada dentro de un `Form`.

Y estas causan mal render aunque "importen" (el validador las marca **⚠**):

8. **El label del Footer NO renderiza emojis** — déjalo en texto ("Continuar",
   "Enviar"). (El usuario lo confirmó en campo.)
9. Respeta límites de caracteres (ver `references/components.md`). Los más
   apretados: TextInput/TextArea/Dropdown `label` = 20, Radio/Checkbox `label` =
   30, opción de Radio/Checkbox = 30, Footer = 35, título opción Dropdown ≈ 80.
10. **OptIn:** el label oficial es máx 120. Para términos largos, usa un label
    corto + `terms` (pantalla read more), no metas 300 caracteres en el label.
11. Máx **3 imágenes** por pantalla, cada una idealmente < 300 KB (el builder las
    reescala si tienes Pillow instalado). Base64 sin el prefijo `data:image/...`.

## Referencias (cárgalas cuando las necesites)

- `references/components.md` — tabla exhaustiva de **cada componente**, sus
  propiedades y **todos los límites de caracteres** (Meta v7.3).
- `references/patterns.md` — recetas: multi-pantalla con reenvío, opción "Otro"
  con campo de texto, escala 1–10, términos y condiciones, campos condicionales
  (If/Switch), selección de fecha/hora, flows con endpoint (data_exchange).
- `references/gotchas.md` — la lista completa de errores que el usuario ya vivió
  (incluida la regla Flow19 de la pantalla de "más información") y cómo evitarlos.
- `assets/ejemplo_completo.json` — un flow **grande y completo** de referencia
  (todos los tipos de componente), sin base64, listo para estudiar o adaptar.

## Cómo importar el Flow (dile esto al usuario)

1. Entra a **business.facebook.com** → **Administrador de WhatsApp** →
   **Herramientas para cuentas** → **Flows** (o **WhatsApp Manager → Flows**).
2. **Crear flow** → dale un nombre → categoría (p. ej. *Registro de contactos*,
   *Encuesta*, *Otro*) → **Crear**.
3. En el editor, arriba a la derecha usa **"⋯" → Editar JSON** (o el botón
   `</> Editor`), **borra** el JSON de ejemplo y **pega** el contenido de
   `flow.json`. No debe salir ningún error en el panel derecho.
4. **Guardar** → **Vista previa** para probarlo en el simulador.
5. Cuando esté listo: **Publicar**. Ya podrás enviarlo en un mensaje o adjuntarlo
   a un botón/plantilla.

> Si Meta marca un error al pegar, cópiale el mensaje al usuario y vuelve a pasar
> el `flow.json` por `validate_flow.py`; casi siempre es un límite de caracteres
> o una referencia `${data.X}` no declarada.
