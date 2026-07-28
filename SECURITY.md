# Política de seguridad

## Reportar una vulnerabilidad

Si encuentras un problema de seguridad, por favor **no abras un issue público**.
Repórtalo de forma privada por medio de **[GitHub Security Advisories](https://github.com/ANGELBERRIOS23/whatsapp-flow-studio/security/advisories/new)**
(pestaña *Security → Report a vulnerability*). Intentaré responder lo antes posible.

Incluye, si puedes: pasos para reproducir, impacto y una prueba de concepto.

## Alcance

WhatsApp Flow Studio es una **app 100 % del lado del cliente** (un solo archivo HTML,
sin backend). Puntos relevantes de su modelo de seguridad:

- **Sin ejecución de código arbitrario.** Las condiciones de los saltos de lógica (`If`)
  se evalúan con un mini-parser propio que solo admite literales y los operadores
  `== != < > <= >= && || !` y paréntesis. **Cargar un Flow JSON de terceros no puede
  ejecutar código** en tu navegador.
- **Imágenes** restringidas a `data:image/…`.
- **Sin peticiones de red** salvo, si el usuario lo activa explícitamente, al proveedor
  de IA que configure. La app **no tiene servidor propio**.
- **API keys del Asistente IA**: se guardan **solo** en el `localStorage` del navegador
  del usuario y las llamadas van **directo** del navegador al proveedor (OpenAI, Google,
  Anthropic, etc.). **No pasan por ningún servidor** —ni de este proyecto ni de nadie—.
  Existe un botón para borrarlas.

## Buenas prácticas para quien lo usa

- No publiques tu API key ni la subas a ningún repo.
- Si ejecutas los scripts de línea de comandos de la carpeta `skill/` (`build_flow.py`),
  hazlo solo con especificaciones de **origen confiable** (pueden incrustar imágenes desde
  rutas locales).
