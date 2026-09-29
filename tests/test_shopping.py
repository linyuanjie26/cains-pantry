"""Session shopping list. No network."""

from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

_APP = Path(__file__).resolve().parents[1] / "app.py"


class ShoppingListTests(unittest.TestCase):
    def test_manual_add_and_missing_ingredients(self) -> None:
        app = AppTest.from_file(str(_APP), default_timeout=40)
        app.run()
        self.assertFalse(app.exception)

        app.text_input(key="shopping_input").set_value("Lime, lime, Flour")
        app.button(key="FormSubmitter:add_shopping_form-Add").click().run()
        self.assertEqual(list(app.session_state["shopping_list"]), ["Lime", "Flour"])

        app.button(key="miss-jarred-pepper-pasta").click().run()
        listed = list(app.session_state["shopping_list"])
        self.assertIn("pasta", listed)
        self.assertIn("garlic", listed)
        self.assertIn("salt", listed)
        self.assertNotIn("parmesan", listed)
        self.assertEqual(sum(1 for name in listed if name.casefold() == "lime"), 1)

        app.button(key="got-0-Lime").click().run()
        self.assertFalse(app.exception)
        self.assertNotIn("Lime", list(app.session_state["shopping_list"]))
        self.assertIn("Lime", list(app.session_state["pantry"]))

    def test_missing_dedupes_and_bought_does_not_duplicate_pantry(self) -> None:
        app = AppTest.from_file(str(_APP), default_timeout=40)
        app.run()
        app.session_state["shopping_list"] = ["Flour"]
        app.session_state["pantry"] = []
        app.button(key="miss-simple-pancakes").click().run()
        names = [item.casefold() for item in app.session_state["shopping_list"]]
        self.assertEqual(names.count("flour"), 1)
        self.assertIn("milk", names)
        self.assertIn("eggs", names)

        app.session_state["shopping_list"] = ["Eggs"]
        app.session_state["pantry"] = ["eggs"]
        app.run()
        app.button(key="got-0-Eggs").click().run()
        self.assertEqual(list(app.session_state["shopping_list"]), [])
        self.assertEqual([item.casefold() for item in app.session_state["pantry"]], ["eggs"])


if __name__ == "__main__":
    unittest.main()
