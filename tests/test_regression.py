import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_flow import build, norm_options  # noqa: E402
from validate_flow import (  # noqa: E402
    arreglar_tipos,
    EMBEDDEDLINK_TEXT,
    FOOTER_LABEL,
    LABEL_LIMITS,
    OPTIN_LABEL,
    OPTION_TITLE,
    validate,
)


class FlowStudioRegressionTests(unittest.TestCase):
    def test_project_character_limits_stay_authoritative(self):
        """Estos son los límites verificados por el proyecto, no los de PyWa."""
        self.assertEqual(LABEL_LIMITS["TextInput"], 20)
        self.assertEqual(LABEL_LIMITS["Dropdown"], 20)
        self.assertEqual(LABEL_LIMITS["RadioButtonsGroup"], 30)
        self.assertEqual(LABEL_LIMITS["ChipsSelector"], 80)
        self.assertEqual(LABEL_LIMITS["PhotoPicker"], 80)
        self.assertEqual(OPTION_TITLE["Dropdown"], 80)
        self.assertEqual(OPTIN_LABEL, 120)
        self.assertEqual(EMBEDDEDLINK_TEXT, 25)
        self.assertEqual(FOOTER_LABEL, 35)

    def test_option_normalization_preserves_supported_metadata(self):
        option = {
            "id": "playa",
            "title": "Playa",
            "description": "Siete noches",
            "metadata": "premium",
            "image": "AAAA",
            "alt-text": "Una playa",
        }
        self.assertEqual(norm_options([option])[0], option)

    def test_builder_output_remains_valid_and_keeps_option_fields(self):
        spec = {
            "version": "7.3",
            "question_as_subheading": True,
            "screens": [
                {
                    "id": "REGISTRO",
                    "title": "Registro",
                    "footer": "Enviar",
                    "blocks": [
                        {"text": "¿Tu nombre?", "label": "Nombre", "key": "nombre"},
                        {
                            "radio": "¿Plan?",
                            "label": "Elige",
                            "key": "plan",
                            "options": [
                                {
                                    "id": "pro",
                                    "title": "Pro",
                                    "description": "Para equipos",
                                    "metadata": "ventas",
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        flow = build(copy.deepcopy(spec))
        report = validate(flow)
        self.assertEqual(report.errors, [])
        form = flow["screens"][0]["layout"]["children"][0]
        radio = next(c for c in form["children"] if c.get("type") == "RadioButtonsGroup")
        self.assertEqual(radio["data-source"][0]["description"], "Para equipos")
        self.assertEqual(radio["data-source"][0]["metadata"], "ventas")

    def test_deployed_and_skill_studio_are_identical(self):
        self.assertEqual(
            (ROOT / "index.html").read_bytes(),
            (SCRIPTS / "studio.html").read_bytes(),
        )

    def test_ui_safety_features_remain_present(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="mobilePreview"',
            'var DRAFT_KEY="wfs_draft_v1"',
            'className="psearch"',
            '_rootRaw:rootRaw',
            'function mergeMissing(base,raw)',
            'function setMobilePane(preview)',
            '.sc-head .acts{display:flex',
            '.screen-settings .f.full{grid-column:auto}',
            'var collapsedBlocks=new WeakSet()',
            'data-v="real" class="active"><span data-i="eye"></span>Realista',
            'M17.472 14.382c-.297-.149',
            '--shadow:none',
        ):
            self.assertIn(marker, html)
        self.assertNotIn('👁 Realista', html)
        self.assertIn(
            "var LIM={heading:80,subheading:80,body:4096,caption:4096,footer:35,optin:120,helper:80,title:30}",
            html,
        )
        self.assertIn(
            "var LL={TextInput:20,Dropdown:20,RadioButtonsGroup:30,CheckboxGroup:30,ChipsSelector:80,CalendarPicker:40}",
            html,
        )


class TiposEntrePantallasTests(unittest.TestCase):
    """Meta rechaza al guardar: «Schema of dynamic data '${form.DPI}' is not matching schema of data model
    field ... Property is expecting 'string' but got 'number'» (formulario de MAIPA, nov-2026). Un campo que
    pasa a otra pantalla tiene que declararse con el tipo de su valor."""

    SPEC = {"screens": [
        {"id": "DATOS", "title": "Datos", "blocks": [
            {"text": "Nombre", "label": "Tu nombre", "key": "nombre"},
            {"number": "DPI", "label": "Tu DPI", "key": "dpi"},
            {"optin": "Acepto los términos", "termsText": "Texto legal"},
            {"radio": "¿Seguimos?", "key": "seguir", "options": ["Sí", "No"], "gate": {"when": "No", "goto": "FIN"}},
        ]},
        {"id": "MAS", "title": "Más", "blocks": [{"checkbox": "Intereses", "key": "intereses", "options": ["A", "B"]}]},
        {"id": "FIN", "title": "Fin", "blocks": [{"text": "Comentario", "label": "Comentario", "key": "comentario"}]},
    ]}

    def _data(self, flow, sid):
        return next(s for s in flow["screens"] if s["id"] == sid)["data"]

    def test_el_builder_declara_el_tipo_del_valor(self):
        flow = build(copy.deepcopy(self.SPEC))
        mas = self._data(flow, "MAS")
        tipos = {k.split("_")[2]: v["type"] for k, v in mas.items()}
        self.assertEqual(tipos["dpi"], "number")
        self.assertEqual(mas[next(k for k in mas if "_dpi_" in k)]["__example__"], 0)
        self.assertIn("boolean", tipos.values())                       # el OptIn
        self.assertEqual(tipos["nombre"], "string")
        report = validate(flow)
        self.assertEqual(report.errors, [], report.errors)

    def test_los_saltos_mandan_vacios_del_tipo_correcto(self):
        flow = build(copy.deepcopy(self.SPEC))
        payloads = [a["on-click-action"]["payload"] for s in flow["screens"] if s["id"] == "MAS"
                    for a in [s["layout"]["children"][0]["children"][-1]] if "on-click-action" in a]
        blob = json.dumps(flow, ensure_ascii=False)
        self.assertNotIn('"intereses_1": ""', blob)
        report = validate(flow)
        self.assertFalse([e for e in report.errors if "expecting" in e], report.errors)

    def _flow_dpi_como_texto(self):
        return {"version": "7.3", "screens": [
            {"id": "DATOS", "data": {}, "layout": {"type": "SingleColumnLayout", "children": [{"type": "Form", "name": "f", "children": [
                {"type": "TextInput", "name": "dpi", "label": "Tu DPI", "input-type": "number", "required": True},
                {"type": "Footer", "label": "Continuar", "on-click-action": {"name": "navigate", "next": {"type": "screen", "name": "FIN"},
                                                                          "payload": {"dpi_1": "${form.dpi}"}}}]}]}},
            {"id": "FIN", "terminal": True, "data": {"dpi_1": {"type": "string", "__example__": "Example"}},
             "layout": {"type": "SingleColumnLayout", "children": [{"type": "Form", "name": "f", "children": [
                 {"type": "Footer", "label": "Enviar", "on-click-action": {"name": "complete", "payload": {"dpi": "${data.dpi_1}"}}}]}]}},
        ]}

    def test_el_validador_detecta_el_error_de_meta(self):
        report = validate(self._flow_dpi_como_texto())
        self.assertTrue(any("expecting 'string' but got 'number'" in e for e in report.errors), report.errors)

    def test_ejemplo_de_tipo_distinto_al_declarado(self):
        flow = self._flow_dpi_como_texto()
        flow["screens"][1]["data"]["dpi_1"] = {"type": "number", "__example__": "Example"}
        self.assertTrue(any('"__example__" es string' in e for e in validate(flow).errors))

    def test_arreglar_tipos_lo_corrige(self):
        flow = self._flow_dpi_como_texto()
        self.assertEqual(arreglar_tipos(flow), [("FIN", "dpi_1", "string", "number")])
        self.assertEqual(flow["screens"][1]["data"]["dpi_1"], {"__example__": 0, "type": "number"})
        self.assertEqual(validate(flow).errors, [])

    def test_ejemplos_del_proyecto_sin_errores(self):
        for ruta in (ROOT / "examples" / "encuesta-egresados.json", ROOT / "skill" / "assets" / "ejemplo_completo.json"):
            report = validate(json.loads(ruta.read_text(encoding="utf-8")))
            self.assertEqual(report.errors, [], f"{ruta.name}: {report.errors}")


if __name__ == "__main__":
    unittest.main()
