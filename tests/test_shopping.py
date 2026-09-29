"""Shopping list session behavior and cloud sync. No network."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_logged_out_stays_session_only(self) -> None:
        """Without secrets / sign-in, shopping never hits remote helpers."""
        app = AppTest.from_file(str(_APP), default_timeout=40)
        app.run()
        app.text_input(key="shopping_input").set_value("Lime")
        app.button(key="FormSubmitter:add_shopping_form-Add").click().run()
        self.assertEqual(list(app.session_state["shopping_list"]), ["Lime"])
        self.assertNotIn("cp_user", app.session_state)


class ShoppingCloudMem:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.shopping: list[str] = []
        self.created: tuple[str, str] | None = None

    def signup(self, email: str, password: str):
        folded = email.strip().lower()
        self.created = (folded, password)
        return {"id": "u1", "email": folded}, None

    def login(self, email: str, password: str):
        folded = email.strip().lower()
        if self.created != (folded, password):
            return None, "Email or password does not match."
        return {"id": "u1", "email": folded}, None

    def list_pantry(self, user_id: str) -> list[str]:
        return list(self.items)

    def add_pantry(self, user_id: str, name: str) -> None:
        if name not in self.items:
            self.items.append(name)

    def remove_pantry(self, user_id: str, name: str) -> None:
        self.items = [item for item in self.items if item != name]

    def clear_pantry(self, user_id: str) -> None:
        self.items.clear()

    def list_shopping(self, user_id: str) -> list[str]:
        return list(self.shopping)

    def add_shopping(self, user_id: str, name: str) -> None:
        if name not in self.shopping:
            self.shopping.append(name)

    def remove_shopping(self, user_id: str, name: str) -> None:
        self.shopping = [item for item in self.shopping if item != name]

    def clear_shopping(self, user_id: str) -> None:
        self.shopping.clear()


class ShoppingCloudTests(unittest.TestCase):
    def test_signed_in_shopping_sync_and_mark_bought(self) -> None:
        mem = ShoppingCloudMem()

        def cfg():
            return ("https://abcd.supabase.co", "k" * 24)

        def factory(url, key):
            return mem

        with patch("store.get_config", cfg), patch("store.PantryDB", factory):
            app = AppTest.from_file(str(_APP), default_timeout=40)
            app.run()
            app.text_input(key="account_email").set_value("shop@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Create Account").click().run()

            app.text_input(key="shopping_input").set_value("Lime, Flour")
            app.button(key="FormSubmitter:add_shopping_form-Add").click().run()
            self.assertEqual(mem.shopping, ["Lime", "Flour"])
            self.assertEqual(list(app.session_state["shopping_list"]), ["Lime", "Flour"])

            app.button(key="got-0-Lime").click().run()
            self.assertEqual(mem.shopping, ["Flour"])
            self.assertIn("Lime", mem.items)
            self.assertNotIn("Lime", list(app.session_state["shopping_list"]))
            self.assertIn("Lime", list(app.session_state["pantry"]))

            app.button(key="clear_shopping").click().run()
            app.button(key="confirm_clear_shop_yes").click().run()
            self.assertEqual(list(app.session_state["shopping_list"]), [])
            self.assertEqual(mem.shopping, [])


if __name__ == "__main__":
    unittest.main()
