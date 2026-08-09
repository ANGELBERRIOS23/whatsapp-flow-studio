import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_flow import build, norm_options  # noqa: E402
from validate_flow import (  # noqa: E402
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
        ):
            self.assertIn(marker, html)
        self.assertIn(
            "var LIM={heading:80,subheading:80,body:4096,caption:4096,footer:35,optin:120,helper:80,title:30}",
            html,
        )
        self.assertIn(
            "var LL={TextInput:20,Dropdown:20,RadioButtonsGroup:30,CheckboxGroup:30,ChipsSelector:80,CalendarPicker:40}",
            html,
        )


if __name__ == "__main__":
    unittest.main()
