#!/usr/bin/env python3
"""
validate_flow.py — Validador de WhatsApp Flow JSON.

Uso:
    python3 validate_flow.py flow.json
    python3 validate_flow.py flow.json --strict   # warnings cuentan como fallo

Filosofía de severidad (para NO dar falsas alarmas en flows que ya funcionan):
  ERROR   = rompe la importación / ejecución del Flow en Meta. Hay que corregirlo.
  WARNING = pasa los límites documentados o va contra buenas prácticas, pero
            el builder normalmente lo tolera. Revísalo.

Devuelve exit code 0 si no hay ERRORES (aunque haya warnings), 1 si hay errores.
Con --strict, cualquier warning también da exit 1.

Puede importarse:  from validate_flow import validate
"""
import json
import re
import sys

# ── Límites (cruzados entre docs oficiales de Meta, pywa y observación de campo) ──
TEXT_LIMITS = {
    "TextHeading": 80,
    "TextSubheading": 80,
    "TextBody": 4096,
    "TextCaption": 4096,
    "RichText": 4096,
}
LABEL_LIMITS = {
    "TextInput": 20,
    "TextArea": 20,
    "Dropdown": 20,
    "RadioButtonsGroup": 30,
    "CheckboxGroup": 30,
    "DatePicker": 40,
    "CalendarPicker": 40,
    "ChipsSelector": 80,
    "PhotoPicker": 80,
    "DocumentPicker": 80,
    "NavigationList": 80,
}
HELPER_LIMIT = 80
ERROR_MSG_LIMIT = 30
OPTIN_LABEL = 120         # oficial 120; el builder tolera más (Flow19 usó ~300) -> warning
FOOTER_LABEL = 35
FOOTER_CAPTION = 15
EMBEDDEDLINK_TEXT = 25
# El título de opción: Radio/Checkbox se muestran en línea (máx 30 documentado).
# Dropdown y ChipsSelector se muestran en hoja y toleran mucho más (campo: ~80).
OPTION_TITLE = {
    "RadioButtonsGroup": 30,
    "CheckboxGroup": 30,
    "Dropdown": 80,
    "ChipsSelector": 80,
}
OPTION_DESC = 300
OPTION_METADATA = 20
MAX_OPTIONS = {
    "RadioButtonsGroup": 20,
    "CheckboxGroup": 20,
    "ChipsSelector": 20,
    "Dropdown": 200,
    "NavigationList": 20,
}
MAX_PER_SCREEN = {"Image": 3, "OptIn": 5, "EmbeddedLink": 2, "NavigationList": 2, "Footer": 1}
MAX_COMPONENTS_PER_SCREEN = 50

INPUT_TYPES = {"TextInput", "TextArea", "DatePicker", "CalendarPicker", "Dropdown",
               "RadioButtonsGroup", "CheckboxGroup", "ChipsSelector", "OptIn",
               "PhotoPicker", "DocumentPicker"}
TEXTINPUT_INPUT_TYPES = {"text", "number", "email", "password", "passcode", "phone"}
KNOWN_TYPES = set(TEXT_LIMITS) | INPUT_TYPES | {
    "Image", "ImageCarousel", "EmbeddedLink", "Footer", "Form", "If", "Switch",
    "NavigationList",
}
KNOWN_ACTIONS = {"navigate", "complete", "data_exchange", "update_data", "open_url"}

# Rango amplio de emojis (para detectar emoji en el Footer, que NO los acepta)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F000-\U0001F0FF"
    "\U00002700-\U000027BF"
    "❤⭐✅❌"
    "]+",
    flags=re.UNICODE,
)
REF_RE = re.compile(r"\$\{(form|data|screen)\.([^}]+)\}")


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def _walk_components(children):
    """Recorre children incluyendo los que están dentro de If/Switch/Form."""
    for c in children or []:
        if not isinstance(c, dict):
            continue
        yield c
        t = c.get("type")
        if t == "Form":
            yield from _walk_components(c.get("children"))
        elif t == "If":
            yield from _walk_components(c.get("then"))
            yield from _walk_components(c.get("else"))
        elif t == "Switch":
            for arr in (c.get("cases") or {}).values():
                yield from _walk_components(arr)


def _iter_ifs(children):
    for c in children or []:
        if isinstance(c, dict) and c.get("type") == "If":
            yield c


def _count_footer_slots(children):
    """Cuenta 'ranuras' de Footer: los de ramas then/else de un mismo If cuentan 1."""
    n = 0
    for c in children or []:
        if not isinstance(c, dict):
            continue
        t = c.get("type")
        if t == "Footer":
            n += 1
        elif t == "Form":
            n += _count_footer_slots(c.get("children"))
        elif t == "If":
            branch_has = any(x.get("type") == "Footer" for x in (c.get("then") or [])) or \
                any(x.get("type") == "Footer" for x in (c.get("else") or []))
            if branch_has:
                n += 1
        elif t == "Switch":
            if any(any(x.get("type") == "Footer" for x in arr)
                   for arr in (c.get("cases") or {}).values()):
                n += 1
    return n


def _clen(text):
    return len(text) if isinstance(text, str) else 0


def _has_dynamic(v):
    return isinstance(v, str) and "${" in v


def validate(flow):
    r = Report()

    if not isinstance(flow, dict):
        r.err("root", "el documento no es un objeto JSON")
        return r
    if "version" not in flow:
        r.err("root", 'falta "version" (usa "7.3")')
    if "screens" not in flow or not isinstance(flow["screens"], list) or not flow["screens"]:
        r.err("root", 'falta "screens" o está vacío')
        return r

    screens = flow["screens"]
    screen_ids = []
    for s in screens:
        if isinstance(s, dict) and "id" in s:
            screen_ids.append(s["id"])

    # ids duplicados
    seen = set()
    for sid in screen_ids:
        if sid in seen:
            r.err("root", f'id de pantalla duplicado: "{sid}"')
        seen.add(sid)
    id_set = set(screen_ids)

    navigate_targets = set()   # a qué pantallas se navega
    optin_targets = set()      # pantallas destino de un "read more" de OptIn
    terminal_screens = []
    has_complete = False
    incoming = {}              # target_id -> [(origen, set(payload_keys))]
    screen_by_id = {s["id"]: s for s in screens if isinstance(s, dict) and "id" in s}

    for si, s in enumerate(screens):
        where = f'pantalla[{si}] "{s.get("id", "?")}"'
        if not isinstance(s, dict):
            r.err(where, "no es un objeto")
            continue
        if "id" not in s:
            r.err(where, 'falta "id"')
        if s.get("id") == "SUCCESS":
            r.err(where, '"SUCCESS" es un id reservado, usa otro')
        sid_val = s.get("id")
        if sid_val and not re.match(r"^[A-Za-z_]+$", sid_val):
            motivo = "tiene dígitos" if any(c.isdigit() for c in sid_val) else "tiene caracteres no permitidos"
            r.err(where, f'id "{sid_val}" inválido ({motivo}): Meta solo acepta LETRAS y guion bajo '
                         f"en el id de pantalla (patrón [A-Za-z_]+). Renómbralo.")
        if "title" not in s:
            r.warn(where, 'sin "title" (barra superior vacía)')
        layout = s.get("layout")
        if not isinstance(layout, dict):
            r.err(where, 'falta "layout"')
            continue
        if layout.get("type") != "SingleColumnLayout":
            r.warn(where, f'layout.type = {layout.get("type")!r} (se espera "SingleColumnLayout")')

        top_children = layout.get("children", [])
        comps = list(_walk_components(top_children))

        # ¿Hay Form? Los componentes interactivos deben ir dentro de un Form (v4+)
        forms = [c for c in top_children if isinstance(c, dict) and c.get("type") == "Form"]
        in_form_names = set()
        for f in forms:
            if "name" not in f:
                r.warn(where, 'el Form no tiene "name" (usa p.ej. "flow_path")')
            for c in _walk_components(f.get("children")):
                if c.get("name"):
                    in_form_names.add(c["name"])

        # conteo por tipo en la pantalla
        type_counts = {}
        footers = []
        for c in comps:
            t = c.get("type")
            type_counts[t] = type_counts.get(t, 0) + 1
            if t == "Footer":
                footers.append(c)
        # footer "principal" para chequeos de terminal/deadend (el de nivel superior)
        top_footer = next((c for c in top_children
                           if isinstance(c, dict) and c.get("type") == "Footer"), None)
        footer = top_footer or (footers[0] if footers else None)

        if len(comps) > MAX_COMPONENTS_PER_SCREEN:
            r.warn(where, f"{len(comps)} componentes (máx {MAX_COMPONENTS_PER_SCREEN} por pantalla)")

        # Footer: ramas then/else de un mismo If cuentan como 1 (son excluyentes)
        footer_slots = _count_footer_slots(top_children)
        if footer_slots > 1:
            r.err(where, f"{footer_slots} Footers efectivos (máx 1 por pantalla)")
        # un Footer dentro de un If debe existir en AMBAS ramas
        for cif in _iter_ifs(top_children):
            then_has = any(x.get("type") == "Footer" for x in (cif.get("then") or []))
            else_has = any(x.get("type") == "Footer" for x in (cif.get("else") or []))
            if then_has != else_has:
                r.err(where, "Footer dentro de un If debe existir en AMBAS ramas (then y else)")

        for t, mx in MAX_PER_SCREEN.items():
            if t == "Footer":
                continue
            if type_counts.get(t, 0) > mx:
                r.warn(where, f"{type_counts[t]} × {t} (máx {mx} por pantalla)")

        # validación por componente
        input_names = []
        for c in comps:
            t = c.get("type")
            cwhere = f"{where} → {t}"
            if t not in KNOWN_TYPES:
                r.warn(cwhere, f"tipo desconocido {t!r}")

            # límites de texto
            if t in TEXT_LIMITS:
                txt = c.get("text", "")
                if not _has_dynamic(txt) and _clen(txt) > TEXT_LIMITS[t]:
                    r.warn(cwhere, f'"text" tiene {_clen(txt)} chars (máx {TEXT_LIMITS[t]})')
                if "text" not in c:
                    r.err(cwhere, 'falta "text"')

            # labels
            if t in LABEL_LIMITS:
                lbl = c.get("label", "")
                if not _has_dynamic(lbl) and _clen(lbl) > LABEL_LIMITS[t]:
                    r.warn(cwhere, f'"label" tiene {_clen(lbl)} chars (máx {LABEL_LIMITS[t]})')

            if t in ("TextInput", "TextArea", "DatePicker"):
                ht = c.get("helper-text", "")
                if not _has_dynamic(ht) and _clen(ht) > HELPER_LIMIT:
                    r.warn(cwhere, f'"helper-text" tiene {_clen(ht)} chars (máx {HELPER_LIMIT})')

            if t == "TextInput":
                it = c.get("input-type", "text")
                if it not in TEXTINPUT_INPUT_TYPES:
                    r.warn(cwhere, f'input-type {it!r} no reconocido {sorted(TEXTINPUT_INPUT_TYPES)}')

            # nombre requerido en inputs
            if t in INPUT_TYPES:
                if "name" not in c:
                    r.err(cwhere, 'componente de entrada sin "name"')
                else:
                    input_names.append(c["name"])
                    if forms and c["name"] not in in_form_names:
                        r.warn(cwhere, f'"{c["name"]}" no está dentro de un Form')

            # opciones
            if t in MAX_OPTIONS and t != "NavigationList":
                ds = c.get("data-source", [])
                if not isinstance(ds, list) or len(ds) < 1:
                    r.err(cwhere, "data-source vacío (mínimo 1 opción)")
                elif len(ds) > MAX_OPTIONS[t]:
                    r.warn(cwhere, f"{len(ds)} opciones (máx {MAX_OPTIONS[t]})")
                for oi, opt in enumerate(ds or []):
                    if not isinstance(opt, dict) or "id" not in opt or "title" not in opt:
                        r.err(cwhere, f"opción[{oi}] necesita 'id' y 'title'")
                        continue
                    tmax = OPTION_TITLE.get(t, 30)
                    if _clen(opt.get("title")) > tmax:
                        r.warn(cwhere, f"opción[{oi}] title {_clen(opt['title'])} chars (máx {tmax})")
                    if _clen(opt.get("description", "")) > OPTION_DESC:
                        r.warn(cwhere, f"opción[{oi}] description > {OPTION_DESC}")
                ids = [o.get("id") for o in ds if isinstance(o, dict)]
                if len(ids) != len(set(ids)):
                    r.err(cwhere, "hay ids de opción duplicados en data-source")

            if t == "OptIn":
                lbl = c.get("label", "")
                if not _has_dynamic(lbl) and _clen(lbl) > OPTIN_LABEL:
                    r.warn(cwhere, f'OptIn label {_clen(lbl)} chars (oficial máx {OPTIN_LABEL}; '
                                   "mejor usa 'read more' a una pantalla de términos)")
                act = c.get("on-click-action")
                if act:
                    nxt = act.get("next", {}).get("name")
                    if nxt:
                        navigate_targets.add(nxt)
                        optin_targets.add(nxt)

            if t == "EmbeddedLink":
                if _clen(c.get("text", "")) > EMBEDDEDLINK_TEXT and not _has_dynamic(c.get("text", "")):
                    r.warn(cwhere, f'EmbeddedLink text > {EMBEDDEDLINK_TEXT}')

            if t == "Image":
                if "src" not in c:
                    r.err(cwhere, 'Image sin "src"')
                else:
                    approx_kb = len(str(c["src"])) * 3 / 4 / 1024
                    if approx_kb > 300:
                        r.warn(cwhere, f"imagen ~{approx_kb:.0f}KB (recomendado <300KB; total pantalla <1MB)")
                st = c.get("scale-type")
                if st and st not in ("cover", "contain"):
                    r.warn(cwhere, f'scale-type {st!r} (usa "cover" o "contain")')

            # acciones (Footer, OptIn, on-select-action)
            for akey in ("on-click-action", "on-select-action"):
                act = c.get(akey)
                if not isinstance(act, dict):
                    continue
                aname = act.get("name")
                if aname not in KNOWN_ACTIONS:
                    r.err(f"{cwhere}.{akey}", f"acción {aname!r} desconocida {sorted(KNOWN_ACTIONS)}")
                if aname == "navigate":
                    nxt = act.get("next", {})
                    tgt = nxt.get("name") if isinstance(nxt, dict) else None
                    if not tgt:
                        r.err(f"{cwhere}.{akey}", "navigate sin next.name")
                    else:
                        navigate_targets.add(tgt)
                        incoming.setdefault(tgt, []).append(
                            (where, set((act.get("payload") or {}).keys())))
                        if tgt not in id_set:
                            r.err(f"{cwhere}.{akey}", f'navega a "{tgt}" que no existe')
                if aname == "complete":
                    # marca de complete se cuenta abajo con el footer
                    pass

        # Footer / terminal
        for foot in footers:
            lbl = foot.get("label", "")
            if _clen(lbl) > FOOTER_LABEL and not _has_dynamic(lbl):
                r.warn(f"{where} → Footer", f'label {_clen(lbl)} chars (máx {FOOTER_LABEL})')
            if EMOJI_RE.search(lbl or ""):
                r.warn(f"{where} → Footer", 'el label del Footer suele NO renderizar emojis; quítalos')
            for cap in ("left-caption", "center-caption", "right-caption"):
                if _clen(foot.get(cap, "")) > FOOTER_CAPTION:
                    r.warn(f"{where} → Footer", f'{cap} > {FOOTER_CAPTION} chars')
            if foot.get("on-click-action", {}).get("name") == "complete":
                has_complete = True
        if s.get("terminal") and top_footer and \
                top_footer.get("on-click-action", {}).get("name") == "navigate":
            r.err(where, "una pantalla terminal no puede tener Footer con 'navigate' (usa 'complete')")

        if s.get("terminal"):
            terminal_screens.append(s.get("id"))
            if not footer:
                r.err(where, "pantalla terminal SIN Footer (obligatorio)")
            elif footer.get("on-click-action", {}).get("name") not in ("complete", "data_exchange"):
                r.err(where, "el Footer de una pantalla terminal debe usar 'complete' (o 'data_exchange')")

        # ¿pantalla sin salida y no es destino de OptIn read-more?
        out = footer.get("on-click-action", {}).get("name") if footer else None
        is_deadend = footer is None and not s.get("terminal")
        s["_deadend"] = is_deadend  # marca temporal
        s["_index"] = si

        # referencias ${form.x} / ${data.x}
        declared = set((s.get("data") or {}).keys())
        blob = json.dumps(s.get("layout", {}), ensure_ascii=False)
        for kind, path in REF_RE.findall(blob):
            field = path.split(".")[0]
            if kind == "form":
                if field not in input_names:
                    r.err(where, f'${{form.{field}}} no coincide con ningún "name" de input en esta pantalla')
            elif kind == "data":
                if field not in declared:
                    r.err(where, f'${{data.{field}}} no está declarado en "data" de esta pantalla')

        # data declarations bien formadas
        for k, v in (s.get("data") or {}).items():
            if not isinstance(v, dict) or "__example__" not in v or "type" not in v:
                r.err(where, f'data["{k}"] debe tener "__example__" y "type"')

    # ── validaciones globales ──
    if not terminal_screens:
        r.err("root", "ningún screen tiene \"terminal\": true (el Flow nunca termina)")
    if not has_complete:
        # sólo error si tampoco hay endpoint (data_exchange)
        blob_all = json.dumps(flow, ensure_ascii=False)
        if '"data_exchange"' not in blob_all:
            r.err("root", "ningún Footer usa la acción 'complete' (el Flow no puede finalizar)")

    # alcanzabilidad: cada pantalla (salvo la primera) debería ser destino de navigate
    for si, s in enumerate(screens):
        sid = s.get("id")
        if si == 0:
            continue
        if sid not in navigate_targets:
            r.warn(f'pantalla "{sid}"', "no es destino de ninguna acción navigate (inalcanzable)")

    # consistencia de payloads: cada navigate hacia una pantalla debe enviar TODOS
    # los campos que esa pantalla declara en su "data" (si no, ese campo llega vacío
    # en ese camino — típico bug de reenvío en flujos con saltos de lógica)
    for tgt_id, arrivals in incoming.items():
        tgt = screen_by_id.get(tgt_id)
        if not tgt:
            continue
        declared = set((tgt.get("data") or {}).keys())
        for src_where, keys in arrivals:
            missing = declared - keys
            if missing:
                sample = ", ".join(sorted(missing)[:3]) + ("…" if len(missing) > 3 else "")
                r.warn(src_where, f'navigate a "{tgt_id}" no envía {len(missing)} campo(s) '
                                  f'que esa pantalla declara en data: {sample}')

    # regla Flow19: pantallas 'read more' de OptIn (sin footer) deben ir al final
    for si, s in enumerate(screens):
        if s.get("id") in optin_targets and s.get("_deadend"):
            later_normal = [
                x for x in screens[si + 1:]
                if not x.get("_deadend") and x.get("id") not in optin_targets
            ]
            if later_normal:
                r.warn(f'pantalla "{s.get("id")}"',
                       "es una pantalla 'read more' de OptIn (sin Footer) pero hay pantallas "
                       "normales después. Muévela al FINAL del array o el Flow puede dar error.")

    # limpiar marcas temporales
    for s in screens:
        s.pop("_deadend", None)
        s.pop("_index", None)

    return r


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    strict = "--strict" in sys.argv
    if not args:
        print("uso: python3 validate_flow.py flow.json [--strict]")
        sys.exit(2)
    path = args[0]
    try:
        with open(path, "r", encoding="utf-8") as f:
            flow = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON inválido en {path}: {e}")
        sys.exit(1)

    r = validate(flow)
    print(f"\n📋 Validación de {path}")
    print(f"   versión: {flow.get('version', '?')}   pantallas: {len(flow.get('screens', []))}")
    if r.errors:
        print(f"\n❌ {len(r.errors)} ERROR(es) — rompen el Flow:")
        for e in r.errors:
            print(f"   • {e}")
    if r.warnings:
        print(f"\n⚠️  {len(r.warnings)} advertencia(s) — revisar:")
        for w in r.warnings:
            print(f"   • {w}")
    if not r.errors and not r.warnings:
        print("\n✅ Sin problemas. Flow válido y dentro de límites.")
    elif not r.errors:
        print("\n✅ Sin errores estructurales. El Flow debería importar bien (revisa las advertencias).")

    sys.exit(1 if r.errors or (strict and r.warnings) else 0)


if __name__ == "__main__":
    main()
