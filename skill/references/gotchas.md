# Errores comunes y cómo evitarlos (WhatsApp Flows)

Lista de lo que rompe un Flow o hace que se vea mal. El validador
(`scripts/validate_flow.py`) detecta casi todo esto. **ERROR** = rompe la
importación; **⚠** = importa pero se ve/comporta mal.

## 🔴 La regla Flow19: la pantalla de "más información" va AL FINAL

El usuario lo descubrió a la mala. Una pantalla de **solo lectura** (cuerpo,
título, imágenes) **sin Footer** — típicamente el destino "Read more" de un
`OptIn`, o una pantalla de "Más información" — **debe ser la última** del array
`screens`.

> Cita del usuario: *"SI METES ESTA PANTALLA DE MÁS INFORMACIÓN [en medio] NO
> PUEDES METER OTRA PANTALLA DE LAS GENERALES, TE LA BOTARÁ EL FORM O DARÁ ERROR.
> ESTO DEBE DE SER LO ÚLTIMO EN SALIR."*

Porque no tiene Footer, no es una pantalla "navegable normal": es un callejón sin
salida al que se entra con "Read more" y se sale con el botón atrás. Si dejas
pantallas normales **después** de ella, el enrutamiento automático de Meta falla.
El builder compacto la coloca al final por ti (sección `terms_screens`).

## 🔴 El label del Footer NO acepta emojis

El botón inferior no renderiza emojis (el usuario lo confirmó: *"Continuar aquí no
deja emojis"*). Deja el label en texto plano: `"Continuar"`, `"Enviar"`,
`"Generar código"`. Los emojis **sí** funcionan en títulos, cuerpos, labels de
input y opciones — solo el Footer los rechaza.

## 🔴 Pantalla terminal sin Footer / con navigate

- `terminal: true` **obliga** a tener un `Footer`.
- El Footer de una terminal debe usar `complete` (o `data_exchange` con endpoint),
  **nunca** `navigate`.
- Debe existir al menos un `complete` en todo el Flow, o nunca termina.

## 🔴 Referencias rotas: `${form.X}` y `${data.X}`

- `${form.NOMBRE}` debe usar exactamente el `name` de un input **en esa misma
  pantalla**. Si te equivocas de nombre, el dato llega vacío o da error.
- `${data.CLAVE}` debe estar **declarado** en el objeto `data` de esa pantalla,
  con `__example__` y `type`. Olvidar declararlo es el error #1 al hacer flows
  multi-pantalla a mano → **usa el builder**, que lo hace solo.

## 🔴 Reenvío incompleto entre pantallas

Si un dato de la pantalla 0 lo necesitas en el `complete` de la pantalla 3, tiene
que **viajar** por cada pantalla intermedia (declararse en `data` y reenviarse en
el payload de cada `navigate`). Saltarse una pantalla = dato perdido. El builder
acumula todo automáticamente.

## 🔴 CheckboxGroup se declara como array

Cuando reenvías un `CheckboxGroup` (multi-selección) entre pantallas, su
declaración en `data` es de tipo **array**, no string:
```json
"clave": { "__example__": [], "items": {"type": "string"}, "type": "array" }
```
Radio, Dropdown, TextInput, DatePicker → `string`.

## 🔴 id de pantalla: SOLO letras y guion bajo (¡sin dígitos!)

El `id` de cada pantalla debe cumplir el patrón **`[A-Za-z_]+`** — solo letras
(mayúsculas o minúsculas) y guion bajo. **NADA de dígitos** ni otros símbolos.
Meta rechaza el Flow entero con *"Flow JSON is not valid"* señalando `screens[N].id`.

- ❌ `P2_EXPERIENCIA_1`, `screen_e92f00`, `pantalla2` (tienen dígitos)
- ✅ `QUESTION_ONE`, `EXPERIENCIA_PLAN`, `GRACIAS`, `screen_mdvoev`, `WELCOME_SCREEN`

Ojo: los **nombres de campos** (`name`) y las **claves de payload/data**
(`screen_0_pais_0`) SÍ pueden tener dígitos — la restricción es **solo** para el
`id` de pantalla. El builder ya genera ids sin dígitos y remapea las referencias;
el validador marca ERROR si encuentra uno inválido.

## 🔴 id de pantalla duplicados / "SUCCESS"

Los `id` deben ser únicos. **`SUCCESS` está reservado** por Meta — no lo uses como
id de pantalla.

## 🔴 Imágenes: base64 sin prefijo, y pesan

- `src` va con base64 **crudo** (empieza en `iVBORw0K...` para PNG), **sin** el
  prefijo `data:image/png;base64,`.
- Máx **3 imágenes** por pantalla; cada una idealmente < 300 KB; el total de la
  pantalla < 1 MB, y el JSON completo < 10 MB.
- Instala **Pillow** (`pip install pillow`) para que el builder reescale las
  imágenes automáticamente y no te pases del límite.

## ⚠ Límites de caracteres (los que más se exceden)

| Elemento | Límite |
|---|---|
| Título de pantalla | ~30 |
| TextHeading / TextSubheading | 80 |
| TextBody / TextCaption | 4096 |
| label de TextInput / TextArea / Dropdown | **20** |
| label de Radio / Checkbox | 30 |
| helper-text | 80 |
| título de opción Radio/Checkbox | 30 |
| título de opción Dropdown | ~80 (se trunca) |
| label de Footer | 35 |
| caption de Footer | 15 |
| label de OptIn | 120 (oficial) |
| EmbeddedLink | 25 |

Pasarse **no siempre** rompe la importación (el builder tolera de más, p. ej. el
OptIn de 188–300 chars de Flow19), pero el texto se **trunca** en pantalla. Mejor
acortar.

## ⚠ OptIn largo → usa "Read more"

No metas los términos completos en el `label` del OptIn. Pon una frase corta
("Acepto los términos y condiciones") y enlaza el texto completo con
`on-click-action` → pantalla de términos (`terms` en la spec).

## ⚠ Componentes interactivos fuera de un Form

Desde v4, los inputs (TextInput, Dropdown, DatePicker, etc.) deben ir **dentro**
de un `Form` (`"name": "flow_path"`). El builder los envuelve solo.

## ⚠ No hay componente separador/divisor nativo

WhatsApp Flows **no tiene** un componente "Divider"/"Separator"/"Spacer". Las
líneas finas que a veces se ven entre elementos las dibuja WhatsApp solo (no se
controlan). Para forzar una separación visual (p. ej. antes de un mensaje de
"Gracias"), se simula con una `TextCaption` que contiene una línea de caracteres
`─` (box-drawing). En la spec: `{"divider": true}` (o `{"divider": "──────"}`).
Ojo: si la línea es muy larga puede envolverse en pantallas angostas.

## ⚠ Emojis con tono de piel

Los emojis de personas/manos salen en amarillo por defecto (👩 👋 🙌). Para un tono
de piel específico, añade el modificador: medio = 🏽 (U+1F3FD) → 👩🏽 👋🏽 🙌🏽. El
color de pelo por defecto ya es oscuro/negro. Emojis de objeto/símbolo (🎓 📊 💚 ✨)
no llevan tono. Evita el emoji 🤝 con tono (soporte irregular); usa uno sin piel.

## ⚠ Versión del Flow

Usa `"version": "7.3"` (o la más alta disponible). Versiones viejas (≤5.0) ya no
se pueden publicar. Componentes nuevos (CalendarPicker v6.1, RichText v5.1,
`update_data`/`open_url` v6.0) exigen versión suficiente.

## Checklist final antes de entregar

1. `python3 scripts/validate_flow.py flow.json` → **0 errores**.
2. Última pantalla de datos: `terminal:true` + Footer `complete`.
3. Pantallas de "más información"/términos: al final, sin Footer.
4. Footer sin emojis.
5. Imágenes < 300 KB, base64 sin prefijo.
6. Revisadas las advertencias de límites de caracteres.
