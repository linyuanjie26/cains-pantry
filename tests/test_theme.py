"""Theme hides Streamlit's Enter-to-submit chrome without touching the form."""

from __future__ import annotations

import unittest
from pathlib import Path

import cains_copy as cp

_ROOT = Path(__file__).resolve().parents[1]


class ThemeTests(unittest.TestCase):
    def test_input_instructions_are_hidden(self) -> None:
        css = (_ROOT / "theme.css").read_text(encoding="utf-8")
        self.assertIn('[data-testid="InputInstructions"]', css)
        self.assertIn("display: none", css)
        self.assertIn("visibility: hidden", css)
        self.assertIn("clip-path: inset(50%)", css)
        self.assertIn("stBaseButton-primaryFormSubmit", css)
        self.assertIn("white-space: nowrap", css)
        self.assertIn("min-width: 4.75rem", css)
        self.assertIn("writing-mode: horizontal-tb", css)

    def test_pantry_placeholder_is_obvious(self) -> None:
        self.assertEqual(cp.PANTRY_PLACEHOLDER, "Type An Ingredient (Eggs, Rice…)")

    def test_theme_injection_prefers_st_html(self) -> None:
        source = (_ROOT / "ui.py").read_text(encoding="utf-8")
        self.assertIn("st.html", source)
        self.assertIn("unsafe_allow_html=True", source)


if __name__ == "__main__":
    unittest.main()
