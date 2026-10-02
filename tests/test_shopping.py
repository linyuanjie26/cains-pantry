"""Session shopping list, plus mocked Supabase sync. No network."""

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


class _Cloud:
    def __init__(self) -> None:
        self.pantry: list[str] = []
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
        return list(self.pantry)

    def add_pantry(self, user_id: str, name: str) -> None:
        if name not in self.pantry:
            self.pantry.append(name)

    def remove_pantry(self, user_id: str, name: str) -> None:
        self.pantry = [item for item in self.pantry if item != name]

    def clear_pantry(self, user_id: str) -> None:
        self.pantry.clear()

    def list_shopping(self, user_id: str) -> list[str]:
        return list(self.shopping)

    def add_shopping(self, user_id: str, name: str) -> None:
        if name not in self.shopping:
            self.shopping.append(name)

    def remove_shopping(self, user_id: str, name: str) -> None:
        self.shopping = [item for item in self.shopping if item != name]

    def clear_shopping(self, user_id: str) -> None:
        self.shopping.clear()

    def list_imported_recipes(self, user_id: str) -> list:
        return []

    def save_imported_recipe(self, user_id: str, record: dict) -> None:
        return None


class ShoppingCloudTests(unittest.TestCase):
    def test_sign_in_adopts_remote_and_got_it_syncs_both(self) -> None:
        cloud = _Cloud()

        def cfg():
            return ("https://abcd.supabase.co", "k" * 24)

        def factory(url, key):
            return cloud

        with patch("store.get_config", cfg), patch("store.PantryDB", factory):
            app = AppTest.from_file(str(_APP), default_timeout=40)
            app.run()
            app.text_input(key="account_email").set_value("cook@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Create Account").click().run()

            app.text_input(key="shopping_input").set_value("Lime")
            app.button(key="FormSubmitter:add_shopping_form-Add").click().run()
            self.assertEqual(cloud.shopping, ["Lime"])

            app.button(key="got-0-Lime").click().run()
            self.assertEqual(cloud.shopping, [])
            self.assertEqual(cloud.pantry, ["Lime"])
            self.assertIn("Lime", list(app.session_state["pantry"]))
            self.assertEqual(list(app.session_state["shopping_list"]), [])

            app.button(key="sign_out").click().run()
            cloud.shopping = ["Flour"]
            app.session_state["shopping_list"] = ["Basil"]
            app.text_input(key="account_email").set_value("cook@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Sign In").click().run()
            self.assertEqual(list(app.session_state["shopping_list"]), ["Flour"])

            app.button(key="sign_out").click().run()
            cloud.shopping = []
            app.session_state["shopping_list"] = ["Basil"]
            app.text_input(key="account_email").set_value("cook@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Sign In").click().run()
            self.assertEqual(cloud.shopping, ["Basil"])
            self.assertEqual(list(app.session_state["shopping_list"]), ["Basil"])


if __name__ == "__main__":
    unittest.main()
