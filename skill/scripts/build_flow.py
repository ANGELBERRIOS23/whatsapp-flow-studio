#!/usr/bin/env python3
"""
build_flow.py — Construye un WhatsApp Flow JSON válido a partir de una
especificación compacta (JSON). Automatiza lo que más rompe los Flows:

  • nombres únicos de cada input (name)
  • claves de payload  screen_<i>_<token>_<j>  (token = "key" o la pregunta)
  • reenvío acumulado de datos entre pantallas (${form.x} y ${data.x})
  • declaración de "data" con __example__ y type (string / array)
  • patrón del usuario: la PREGUNTA como TextSubheading ARRIBA del input
  • pantallas "read more" de OptIn colocadas al final (regla Flow19)
  • codificación base64 de imágenes (con reescalado si hay Pillow)
  • SALTOS DE LÓGICA (gates): "si respuesta == X, saltar a pantalla Y"
    usando el componente If con un Footer en ambas ramas (then/else).

Uso:
    python3 build_flow.py spec.json -o flow.json
    python3 build_flow.py spec.json            # imprime a stdout

Formato de la spec (ver también SKILL.md):
{
  "version": "7.3",
  "question_as_subheading": true,     // pregunta arriba del input (default true)
  "screens": [
    {
      "id": "INTRO", "title": "Barra superior",
      "blocks": [
        {"heading": "..."}, {"subheading": "..."}, {"body": "..."}, {"caption": "..."},
        {"image": "/ruta.png", "height": 300},
        {"text": "Pregunta", "label": "placeholder", "key": "nombre", "required": true, "helper": "..."},
        {"email": "..."}, {"phone": "..."}, {"number": "..."}, {"password": "..."}, {"passcode": "..."},
        {"textarea": "...", "label": "...", "helper": "..."},
        {"dropdown": "...", "label": "...", "options": ["a","b"], "key": "pais"},
        {"radio": "...", "options": [...], "key": "genero"},
        {"checkbox": "...", "options": [...], "min": 1, "max": 3, "key": "areas"},
        {"date": "...", "label": "..."},
        {"optin": "Acepto ...", "terms": "TERMS", "key": "acepto"},

        // GATE: en un radio/dropdown, salta a otra pantalla según la respuesta
        {"radio": "¿Seguir en contacto?", "label": "Tu respuesta", "key": "contacto",
         "options": ["Sí","No"], "gate": {"when": "No", "goto": "GRACIAS"}}
      ],
      "next": "SCREEN_2",             // opcional; por defecto encadena en orden
      "footer": "Continuar"
    }
  ],
  "terms_screens": [ {"id":"TERMS","title":"...","blocks":[{"body":"..."}]} ]
}

Notas:
- "key" fija el nombre del campo en los datos (recomendado para webhooks legibles).
- Las pantallas se encadenan en orden; la última recoge datos → "complete".
- El "goto" de un gate debe ser el id de una pantalla existente (típicamente la
  pantalla final de "Gracias"). Los datos aún no recogidos se envían vacíos.
"""
import base64
import hashlib
import json
import os
import re
import sys

TEXT_BLOCK = {
    "heading": "TextHeading",
    "subheading": "TextSubheading",
    "body": "TextBody",
    "caption": "TextCaption",
}
INPUT_TEXT_KINDS = ["text", "email", "phone", "number", "password", "passcode"]
DEFAULT_SEL_LABEL = {
    "Dropdown": "Selecciona",
    "RadioButtonsGroup": "Selecciona una opción",
    "CheckboxGroup": "Elige una o más",
    "ChipsSelector": "Elige una o más",
}


def _opt_id_by_title(options, title):
    for o in options:
        if o.get("title") == title:
            return o.get("id")
    return title


def _apply_default(comp, blk, options=None, is_arr=False, is_bool=False):
    d = blk.get("default")
    if d is None or d == "":
        return
    if is_bool:
        comp["init-value"] = (d is True or d == "true")
        return
    if options is not None:
        if is_arr:
            vals = d if isinstance(d, list) else [d]
            comp["init-value"] = [_opt_id_by_title(options, t) for t in vals]
        else:
            comp["init-value"] = _opt_id_by_title(options, d)
        return
    comp["init-value"] = d


def sanitize(label):
    """Conserva [A-Za-z0-9_], espacios->_, descarta el resto (acentos, símbolos).
    Los guiones bajos de las 'key' del usuario se preservan (nombres legibles)."""
    out = []
    for ch in (label or ""):
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            out.append(ch)
        elif ch == " ":
            out.append("_")
    s = re.sub(r"_+", "_", "".join(out)).strip("_")
    return s or "campo"


def short_hash(*parts):
    h = hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return h[:6]


_ALPHA = "abcdefghijklmnopqrstuvwxyz"


def alpha_hash(*parts, n=6):
    """Hash SOLO letras (para ids de pantalla, que no admiten dígitos)."""
    h = int(hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest(), 16)
    out = []
    for _ in range(n):
        out.append(_ALPHA[h % 26]); h //= 26
    return "".join(out)


def safe_screen_id(raw, used, seed):
    """id de pantalla válido para Meta: solo [A-Za-z_], único, ≠ SUCCESS."""
    s = "".join(ch for ch in (raw or "") if (ch.isascii() and ch.isalpha()) or ch == "_")
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "screen_" + alpha_hash(seed)
    base, i = s, 0
    while s in used or s == "SUCCESS":
        s = f"{base}_{_ALPHA[i % 26]}"; i += 1
    used.add(s)
    return s


def encode_image(src, max_kb=250):
    """Devuelve base64 SIN prefijo data-uri. Reescala con Pillow si está disponible."""
    if not isinstance(src, str):
        return None
    if src.startswith("data:"):
        return src.split(",", 1)[1]
    if not os.path.exists(src):
        return src  # asumimos base64 crudo
    with open(src, "rb") as f:
        raw = f.read()
    try:
        from io import BytesIO
        from PIL import Image  # type: ignore
        img = Image.open(BytesIO(raw))
        fmt = "PNG" if (img.mode in ("RGBA", "P") or (img.format or "").upper() == "PNG") else "JPEG"
        w, h = img.size
        data = raw
        for scale in (1.0, 0.8, 0.6, 0.5, 0.4, 0.3):
            im2 = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
            if fmt == "JPEG" and im2.mode in ("RGBA", "P"):
                im2 = im2.convert("RGB")
            buf = BytesIO()
            im2.save(buf, format=fmt, optimize=True, quality=82)
            data = buf.getvalue()
            if len(data) <= max_kb * 1024:
                break
        raw = data
    except Exception:
        pass
    return base64.b64encode(raw).decode("ascii")


def norm_options(opts):
    out, used = [], set()
    for i, o in enumerate(opts or []):
        if isinstance(o, str):
            item = {"id": f"{i}_{sanitize(o)}", "title": o}
        elif isinstance(o, dict):
            title = o.get("title", f"Opción {i}")
            item = {"id": o.get("id") or f"{i}_{sanitize(title)}", "title": title}
            if o.get("description"):
                item["description"] = o["description"]
        else:
            continue
        base_id, n = item["id"], 1
        while item["id"] in used:
            item["id"] = f"{base_id}_{n}"; n += 1
        used.add(item["id"])
        out.append(item)
    return out


def describe_input(si, input_idx, blk):
    """Descriptor de un bloque de input (o None). Mismo cálculo en pre-pass y generación."""
    def tok(text):
        return (sanitize(blk.get("key") or text)[:60]) or "campo"

    for k in INPUT_TEXT_KINDS:
        if k in blk:
            q = blk[k]
            t = tok(q)
            return {"kind": "textinput", "input_type": ("text" if k == "text" else k),
                    "question": q, "label": blk.get("label", q), "token": t,
                    "name": f"{t}_{short_hash(si, input_idx, q)}",
                    "pkey": f"screen_{si}_{t}_{input_idx}", "dtype": "string", "blk": blk}
    if "textarea" in blk:
        q = blk["textarea"]; t = tok(q)
        return {"kind": "textarea", "question": q, "label": blk.get("label", q), "token": t,
                "name": f"{t}_{short_hash(si, input_idx, q)}",
                "pkey": f"screen_{si}_{t}_{input_idx}", "dtype": "string", "blk": blk}
    if "date" in blk:
        q = blk["date"]; t = tok(q)
        return {"kind": "date", "question": q, "label": blk.get("label", q), "token": t,
                "name": f"{t}_{short_hash(si, input_idx, q)}",
                "pkey": f"screen_{si}_{t}_{input_idx}", "dtype": "string", "blk": blk}
    if "calendar" in blk:
        q = blk["calendar"]; t = tok(q); rng = (blk.get("mode") == "range")
        return {"kind": "calendar", "range": rng, "question": q, "label": blk.get("label", q), "token": t,
                "name": f"{t}_{short_hash(si, input_idx, q)}",
                "pkey": f"screen_{si}_{t}_{input_idx}", "dtype": "object" if rng else "string", "blk": blk}
    for sel_key, ctype, is_arr in (("dropdown", "Dropdown", False),
                                   ("radio", "RadioButtonsGroup", False),
                                   ("checkbox", "CheckboxGroup", True),
                                   ("chips", "ChipsSelector", True)):
        if sel_key in blk:
            q = blk[sel_key]; t = tok(q)
            return {"kind": "select", "ctype": ctype, "is_arr": is_arr,
                    "question": q, "label": blk.get("label"), "token": t,
                    "name": f"{t}_{short_hash(si, input_idx, q)}",
                    "pkey": f"screen_{si}_{t}_{input_idx}",
                    "dtype": "array" if is_arr else "string", "blk": blk}
    if "optin" in blk:
        q = blk["optin"]; t = tok(q)
        return {"kind": "optin", "question": q, "label": q, "token": t,
                "name": f"{t}_{short_hash(si, input_idx, q)}",
                "pkey": f"screen_{si}_{t}_{input_idx}", "dtype": "string", "blk": blk}
    return None


def plan_all_fields(in_screens):
    """Lista ordenada (pkey, dtype) de TODOS los inputs — para payloads de gates."""
    fields = []
    for si, s in enumerate(in_screens):
        idx = 0
        for blk in s.get("blocks", []):
            d = describe_input(si, idx, blk)
            if d:
                fields.append((d["pkey"], d["dtype"]))
                idx += 1
    return fields


def emit_component(d, q_as_sub, children):
    """Agrega el/los componente(s) de un input a `children`. Devuelve (pkey, name, dtype)."""
    k = d["kind"]
    blk = d["blk"]
    if k in ("textinput", "textarea", "date", "calendar"):
        if q_as_sub and d["question"] and d["question"] != d["label"]:
            children.append({"type": "TextSubheading", "text": d["question"]})
        if k == "textinput":
            comp = {"type": "TextInput", "input-type": d["input_type"], "label": d["label"],
                    "name": d["name"], "required": blk.get("required", True)}
            if blk.get("max-chars"):
                comp["max-chars"] = blk["max-chars"]
            if blk.get("min-chars"):
                comp["min-chars"] = blk["min-chars"]
            if blk.get("pattern"):
                comp["pattern"] = blk["pattern"]
            if blk.get("error"):
                comp["error-message"] = blk["error"]
        elif k == "textarea":
            comp = {"type": "TextArea", "label": d["label"], "name": d["name"],
                    "required": blk.get("required", True)}
            if blk.get("error"):
                comp["error-message"] = blk["error"]
        elif k == "date":
            comp = {"type": "DatePicker", "label": d["label"], "name": d["name"],
                    "required": blk.get("required", True)}
            if blk.get("min-date"):
                comp["min-date"] = blk["min-date"]
            if blk.get("max-date"):
                comp["max-date"] = blk["max-date"]
        else:  # calendar
            comp = {"type": "CalendarPicker", "label": d["label"], "name": d["name"],
                    "required": blk.get("required", True),
                    "mode": "range" if d["range"] else "single"}
            if blk.get("title"):
                comp["title"] = blk["title"]
            if blk.get("min-date"):
                comp["min-date"] = blk["min-date"]
            if blk.get("max-date"):
                comp["max-date"] = blk["max-date"]
            if d["range"]:
                if blk.get("min-days") is not None:
                    comp["min-days"] = blk["min-days"]
                if blk.get("max-days") is not None:
                    comp["max-days"] = blk["max-days"]
        if blk.get("helper"):
            comp["helper-text"] = blk["helper"]
        _apply_default(comp, blk)
        children.append(comp)

    elif k == "select":
        if q_as_sub:
            children.append({"type": "TextSubheading", "text": d["question"]})
            label = d["label"] or DEFAULT_SEL_LABEL.get(d["ctype"], "Selecciona")
        else:
            label = d["label"] or d["question"]
        options = norm_options(blk["options"])
        comp = {"type": d["ctype"], "label": label, "name": d["name"],
                "required": blk.get("required", True), "data-source": options}
        if d["ctype"] in ("CheckboxGroup", "ChipsSelector"):
            if blk.get("min") is not None:
                comp["min-selected-items"] = blk["min"]
            if blk.get("max") is not None:
                comp["max-selected-items"] = blk["max"]
        _apply_default(comp, blk, options, d["is_arr"])
        children.append(comp)
        d["_options"] = options  # para resolver el id del gate

    elif k == "optin":
        comp = {"type": "OptIn", "label": d["label"], "name": d["name"],
                "required": d["blk"].get("required", True)}
        if d["blk"].get("terms"):
            comp["on-click-action"] = {"name": "navigate",
                                       "next": {"name": d["blk"]["terms"], "type": "screen"},
                                       "payload": {}}
        _apply_default(comp, d["blk"], is_bool=True)
        children.append(comp)

    return (d["pkey"], d["name"], d["dtype"])


def build(spec):
    version = spec.get("version", "7.3")
    q_as_sub = spec.get("question_as_subheading", True)
    in_screens = spec.get("screens", [])
    terms_in = spec.get("terms_screens", [])

    # ── ids de pantalla válidos (solo letras/_) + remapeo de referencias ──
    used_ids, id_map = set(), {}
    for i, s in enumerate(in_screens):
        orig = s.get("id") or ("QUESTION_ONE" if i == 0 else None)
        fid = safe_screen_id(orig, used_ids, ("scr", i, s.get("title", "")))
        if s.get("id"):
            id_map[s["id"]] = fid
        s["id"] = fid
    for j, ts in enumerate(terms_in):
        orig = ts.get("id")
        fid = safe_screen_id(orig, used_ids, ("terms", j, ts.get("title", "")))
        if orig:
            id_map[orig] = fid
        ts["id"] = fid
    # remapear referencias que el usuario escribió (next, gate.goto, optin.terms)
    for s in in_screens:
        if s.get("next") in id_map:
            s["next"] = id_map[s["next"]]
        for blk in s.get("blocks", []):
            if not isinstance(blk, dict):
                continue
            if isinstance(blk.get("gate"), dict) and blk["gate"].get("goto") in id_map:
                blk["gate"]["goto"] = id_map[blk["gate"]["goto"]]
            if blk.get("terms") in id_map:
                blk["terms"] = id_map[blk["terms"]]

    all_fields = plan_all_fields(in_screens)
    n_main = len(in_screens)
    screens_out = []
    carried = []  # (pkey, dtype) acumulado de pantallas previas

    def full_payload(current_fields):
        """Payload para un gate hacia la pantalla final: TODOS los campos.
        Los ya recogidos por referencia; los futuros, vacíos ('' o [])."""
        cur = {pk: name for pk, name, _dt in current_fields}
        carr = {pk for pk, _dt in carried}
        payload = {}
        for pk, dt in all_fields:
            if pk in cur:
                payload[pk] = f"${{form.{cur[pk]}}}"
            elif pk in carr:
                payload[pk] = f"${{data.{pk}}}"
            else:
                payload[pk] = [] if dt == "array" else ({} if dt == "object" else "")
        return payload

    for si, s in enumerate(in_screens):
        children = []
        input_fields = []
        input_idx = 0
        gate = None

        for blk in s.get("blocks", []):
            # separador (WhatsApp no tiene divisor nativo: se simula con una línea fina)
            if "divider" in blk:
                line = blk["divider"] if isinstance(blk["divider"], str) else "────────────────────"
                children.append({"type": "TextCaption", "text": line})
                continue
            done = False
            for key, ctype in TEXT_BLOCK.items():
                if key in blk:
                    children.append({"type": ctype, "text": blk[key]})
                    done = True
                    break
            if done:
                continue
            if "image" in blk:
                comp = {"type": "Image", "src": encode_image(blk["image"]),
                        "height": blk.get("height", 300),
                        "scale-type": blk.get("scale-type", "contain")}
                if blk.get("alt-text"):
                    comp["alt-text"] = blk["alt-text"]
                children.append(comp)
                continue

            d = describe_input(si, input_idx, blk)
            if d is None:
                continue
            pk_name_dt = emit_component(d, q_as_sub, children)
            input_fields.append(pk_name_dt)
            # detectar gate (en radio/dropdown)
            if blk.get("gate") and d["kind"] == "select":
                g = blk["gate"]
                opt_id = None
                for o in d.get("_options", []):
                    if o["title"] == g.get("when"):
                        opt_id = o["id"]; break
                gate = {"field": d["name"], "option_id": opt_id or sanitize(g.get("when", "")),
                        "goto": g["goto"], "current": list(input_fields)}
            input_idx += 1

        # ── payloads ──
        is_last = (si == n_main - 1)
        explicit_next = s.get("next")
        footer_label = s.get("footer", "Enviar" if is_last else "Continuar")

        normal_payload = {}
        for pk, name, _dt in input_fields:
            normal_payload[pk] = f"${{form.{name}}}"
        for pk, _dt in carried:
            normal_payload[pk] = f"${{data.{pk}}}"

        if gate:
            # then = respuesta coincide → salto a la pantalla goto (payload completo)
            # else = flujo normal a la siguiente pantalla (payload incremental)
            gate_payload = full_payload(gate["current"])
            then_footer = {"type": "Footer", "label": footer_label,
                           "on-click-action": {"name": "navigate",
                                               "next": {"name": gate["goto"], "type": "screen"},
                                               "payload": gate_payload}}
            else_target = explicit_next or (in_screens[si + 1]["id"] if not is_last else None)
            if else_target:
                else_action = {"name": "navigate", "next": {"name": else_target, "type": "screen"},
                               "payload": normal_payload}
            else:
                else_action = {"name": "complete", "payload": normal_payload}
            else_footer = {"type": "Footer", "label": footer_label, "on-click-action": else_action}
            children.append({
                "type": "If",
                "condition": f"${{form.{gate['field']}}} == '{gate['option_id']}'",
                "then": [then_footer],
                "else": [else_footer],
            })
        else:
            if is_last and not explicit_next:
                action = {"name": "complete", "payload": normal_payload}
            else:
                target = explicit_next or in_screens[si + 1]["id"]
                action = {"name": "navigate", "next": {"name": target, "type": "screen"},
                          "payload": normal_payload}
            children.append({"type": "Footer", "label": footer_label, "on-click-action": action})

        data_decl = {}
        for pk, dt in carried:
            if dt == "array":
                data_decl[pk] = {"__example__": [], "items": {"type": "string"}, "type": "array"}
            elif dt == "object":
                data_decl[pk] = {"__example__": {"start-date": "2024-01-01", "end-date": "2024-01-05"}, "type": "object"}
            else:
                data_decl[pk] = {"__example__": "Example", "type": "string"}

        screen_obj = {
            "id": s["id"], "title": s.get("title", ""), "data": data_decl,
            "layout": {"type": "SingleColumnLayout",
                       "children": [{"type": "Form", "name": "flow_path", "children": children}]},
        }
        if is_last and not explicit_next and not gate:
            screen_obj["terminal"] = True
            screen_obj["success"] = True
        screens_out.append(screen_obj)

        for pk, _name, dt in input_fields:
            carried.append((pk, dt))

    # marcar como terminal la pantalla destino de "complete" si aún ninguna lo es
    # (cuando hay gates, la última pantalla suele ser la de Gracias sin inputs)
    if not any(s.get("terminal") for s in screens_out):
        # la última pantalla del array es la terminal
        last = screens_out[-1]
        foot = _find_footer(last)
        if foot is None:
            # sin footer: añadir uno de complete que reenvía todo lo acumulado
            payload = {pk: f"${{data.{pk}}}" for pk, _dt in carried}
            last["layout"]["children"][0]["children"].append(
                {"type": "Footer", "label": spec.get("footer_final", "Finalizar"),
                 "on-click-action": {"name": "complete", "payload": payload}})
        else:
            foot["on-click-action"] = {"name": "complete",
                                       "payload": foot["on-click-action"].get("payload", {})}
        last["terminal"] = True
        last["success"] = True

    # ── pantallas 'read more' de OptIn / de "Gracias" declaradas aparte ──
    for ts in terms_in:
        children = []
        for blk in ts.get("blocks", []):
            done = False
            for key, ctype in TEXT_BLOCK.items():
                if key in blk:
                    children.append({"type": ctype, "text": blk[key]}); done = True; break
            if done:
                continue
            if "image" in blk:
                children.append({"type": "Image", "src": encode_image(blk["image"]),
                                 "height": blk.get("height", 300),
                                 "scale-type": blk.get("scale-type", "contain")})
        screens_out.append({
            "id": ts["id"], "title": ts.get("title", ""), "data": {},
            "layout": {"type": "SingleColumnLayout",
                       "children": [{"type": "Form", "name": "flow_path", "children": children}]},
        })

    return {"version": version, "screens": screens_out}


def _find_footer(screen):
    for c in screen["layout"]["children"][0]["children"]:
        if c.get("type") == "Footer":
            return c
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("uso: python3 build_flow.py spec.json [-o flow.json]")
        sys.exit(2)
    with open(args[0], "r", encoding="utf-8") as f:
        spec = json.load(f)
    flow = build(spec)
    text = json.dumps(flow, ensure_ascii=False, indent=2)
    out_path = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else None
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✅ Flow escrito en {out_path}  ({len(flow['screens'])} pantallas)")
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from validate_flow import validate
            r = validate(flow)
            if r.errors:
                print(f"❌ {len(r.errors)} error(es):")
                for e in r.errors:
                    print("   •", e)
            if r.warnings:
                print(f"⚠️  {len(r.warnings)} advertencia(s):")
                for w in r.warnings:
                    print("   •", w)
            if not r.errors and not r.warnings:
                print("✅ Validación: sin problemas.")
        except Exception as e:
            print("(no se pudo validar automáticamente:", e, ")")
    else:
        print(text)


if __name__ == "__main__":
    main()
