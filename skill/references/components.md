# Referencia de componentes — WhatsApp Flow JSON

Versión de referencia: **7.3** (usa siempre la más alta que soporte la cuenta).
Límites cruzados entre la documentación oficial de Meta, la librería `pywa` y
observación de campo en los flows del usuario. Cuando las fuentes discrepan, se
usa el valor **más seguro** (más estricto) para no exceder el tope real.

Regla general: **cualquier** propiedad de texto acepta binding dinámico
`${form.x}` / `${data.x}` / `${screen.ID.form.x}`. Máx **50 componentes** por
pantalla. **Sin `null`**: omite la propiedad o usa cadena vacía.

## Estructura de una pantalla

```json
{
  "id": "SCREEN_ID",              // único; "SUCCESS" reservado
  "title": "Barra superior",      // ~30 chars recomendado
  "terminal": true,               // opcional; exige Footer con complete
  "success": true,                // solo en terminal; default true
  "refresh_on_back": false,       // opcional
  "sensitive": ["campo1"],        // v5.1+; oculta campos en el resumen
  "data": { },                    // declaraciones JSON-Schema de datos entrantes
  "layout": {
    "type": "SingleColumnLayout", // único layout disponible
    "children": [
      { "type": "Form", "name": "flow_path", "children": [ /* ... */ ] }
    ]
  }
}
```

## Texto (display)

| Tipo | `type` | Límite texto | Propiedades |
|---|---|---|---|
| Título grande | `TextHeading` | **80** | `text`, `visible` |
| Subtítulo | `TextSubheading` | **80** | `text`, `visible` |
| Cuerpo | `TextBody` | **4096** | `text`, `font-weight`(bold/italic/bold_italic/normal), `strikethrough`, `markdown`(v5.1+), `visible` |
| Pie / leyenda | `TextCaption` | **4096** | igual que TextBody |
| Texto enriquecido | `RichText` (v5.1+) | — | `text` (string o array markdown: h1/h2, listas, **negrita**, tablas, imágenes base64, links) |

## Entradas de texto

**TextInput** (`type: "TextInput"`)
- `label` (req, **máx 20**), `name` (req), `input-type`
  (`text`|`number`|`email`|`password`|`passcode`|`phone`), `required`,
  `helper-text` (**máx 80**), `error-message` (**máx 30**), `min-chars`,
  `max-chars` (default 80), `pattern` (regex, v6.2+), `init-value`, `visible`.

**TextArea** (`type: "TextArea"`)
- `label` (req, **máx 20**), `name` (req), `required`, `helper-text` (**máx 80**),
  `max-length` (default **600**), `init-value`, `enabled`, `visible`.

## Selección

**Dropdown** (`type: "Dropdown"`)
- `label` (req, **máx 20**), `name` (req), `data-source` (req), `required`,
  `on-select-action`, `init-value`, `error-message`.
- Opciones: **mín 1, máx 200** (100 si llevan imágenes). Título de opción tolera
  ~**80** (se muestra en hoja; se trunca si es más largo).

**RadioButtonsGroup** (`type: "RadioButtonsGroup"`) — una sola selección, en línea.
- `label` (req en v4+, **máx 30**), `name` (req), `data-source` (req), `required`,
  `on-select-action`, `description`, `media-size`(regular/large, v5+), `init-value`.
- Opciones: **mín 1, máx 20**. Título de opción **máx 30**, description máx 300.

**CheckboxGroup** (`type: "CheckboxGroup"`) — multi selección.
- Igual que Radio + `min-selected-items`, `max-selected-items`.
- Opciones: **máx 20**. Título de opción **máx 30**.
- ⚠ En `data` se declara como **array**: `{"__example__": [], "items": {"type":"string"}, "type": "array"}`.

**ChipsSelector** (`type: "ChipsSelector"`, versiones recientes) — chips multi.
- `label` (**máx 80**), `description` (máx 300), `max-selected-items`,
  `on-select-action`, `on-unselect-action`. Opciones: **máx 20**.

Estructura de cada opción (`data-source`):
```json
{ "id": "id_unico", "title": "Texto visible", "description": "opcional (máx 300)", "metadata": "opcional (máx 20)" }
```
Los `id` deben ser **únicos** dentro del componente.

## Fecha

**DatePicker** (`type: "DatePicker"`)
- `label` (req, **máx 40**), `name` (req), `helper-text` (**máx 80**),
  `error-message` (máx 80), `min-date`, `max-date`, `unavailable-dates`,
  `required`, `on-select-action` (solo `data_exchange`), `init-value`.
- Formato: `"YYYY-MM-DD"` (v5+) o timestamp ms (antes).

**CalendarPicker** (`type: "CalendarPicker"`, v6.1+) — un día o rango.
- `label` (**máx 40**), `title` (máx 80), `description` (máx 300), `name` (req),
  `mode` (`single`|`range`), `min-date`, `max-date`, `unavailable-dates`,
  `include-days`, `min-days`, `max-days` (rango), `helper-text`, `required`.

## Consentimiento y navegación

**OptIn** (`type: "OptIn"`) — casilla de aceptación.
- `label` (req, **oficial máx 120**), `name` (req), `required`, `init-value`,
  `on-click-action` (activa el enlace **"Read more"** → navega a otra pantalla).
- **Máx 5** por pantalla.
- Para términos largos: label corto + `on-click-action navigate` a una pantalla
  de "más información" (ver gotchas: esa pantalla va al final).

**EmbeddedLink** (`type: "EmbeddedLink"`)
- `text` (req, **máx 25**), `on-click-action` (req), `visible`. **Máx 2** por pantalla.

**Footer** (`type: "Footer"`) — botón inferior. **Máx 1** por pantalla.
- `label` (req, **máx 35**, **SIN emojis**), `on-click-action` (req),
  `left-caption` / `center-caption` / `right-caption` (**máx 15** c/u), `enabled`.

**NavigationList** (`type: "NavigationList"`) — lista navegable. `label` (máx 80),
1–20 items. **Máx 2** por pantalla.

## Media

**Image** (`type: "Image"`)
- `src` (req, **base64 SIN prefijo** `data:...`), `width`, `height`,
  `scale-type` (`cover`|`contain`, default contain), `aspect-ratio`, `alt-text`.
- **Máx 3 por pantalla**, recomendado < 300 KB c/u, payload total pantalla < 1 MB.
  Formatos JPEG/PNG.

**PhotoPicker** (`type: "PhotoPicker"`) / **DocumentPicker** (`type: "DocumentPicker"`)
- `label` (**máx 80**), `name` (req), `description`, `photo-source`
  (camera/gallery), `min-uploaded-photos`/`max-uploaded-photos`,
  `max-file-size-kb`, `allowed-mime-types` (DocumentPicker).

**ImageCarousel** (`type: "ImageCarousel"`) — carrusel de imágenes con `scale-type`.

## Lógica (v4+)

**If** — `condition` (bool: `==`,`!=`,`&&`,`||`,`!`,`>`,`>=`,`<`,`<=`,`()`),
`then` (array), `else` (array). Anidación máx 3 niveles. Un `Footer` dentro de un
`If` debe aparecer en **ambas** ramas (then y else) y solo en el primer nivel.

**Switch** — `value` (req), `cases` (mapa `valor → array de componentes`, no vacío).

## Acciones (`on-click-action` / `on-select-action`)

| Acción | Uso | Notas |
|---|---|---|
| `navigate` | Ir a otra pantalla | `next: {name, type:"screen"}` + `payload` |
| `complete` | Terminar el Flow y enviar datos | Solo en pantalla terminal |
| `data_exchange` | Enviar al endpoint; el servidor decide | Requiere endpoint + `data_api_version: "3.0"` |
| `update_data` (v6+) | Actualiza estado de la pantalla sin navegar | |
| `open_url` (v6+) | Abre una URL en el navegador | |

Payload: `{"clave_destino": "${form.nombre_input}"}` o `"${data.clave_previa}"`.

## Binding de datos

- `${form.NAME}` — valor que escribió el usuario (usa el `name` del input).
- `${data.KEY}` — dato recibido por la pantalla (declarado en `screen.data`).
- `${screen.SCREEN_ID.form.NAME}` / `${screen.SCREEN_ID.data.KEY}` — referencia
  global entre pantallas (v4+).

Declaración en `data` (JSON Schema con `__example__` obligatorio):
```json
"data": {
  "nombre": { "type": "string", "__example__": "Juan" },
  "intereses": { "type": "array", "items": {"type": "string"}, "__example__": [] }
}
```
