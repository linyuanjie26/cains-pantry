"""Logged-in pantry sync through the Streamlit app. No network."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

_APP = Path(__file__).resolve().parents[1] / "app.py"


class Mem:
    def __init__(self) -> None:
        self.items: list[str] = []
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


class AccountFlowTests(unittest.TestCase):
    def test_login_loads_remote_and_pushes_local_when_empty(self) -> None:
        mem = Mem()

        def cfg():
            return ("https://abcd.supabase.co", "k" * 24)

        def factory(url, key):
            return mem

        with patch("store.get_config", cfg), patch("store.PantryDB", factory):
            app = AppTest.from_file(str(_APP), default_timeout=40)
            app.run()
            self.assertFalse(app.exception)
            captions = [item.value for item in app.caption]
            self.assertFalse(any("Login is optional" in text for text in captions))

            app.text_input(key="account_email").set_value("Cook@Example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Create Account").click().run()
            self.assertEqual(app.session_state["cp_user"]["email"], "cook@example.com")

            app.text_input(key="pantry_input").set_value("Eggs, Milk")
            app.button(key="FormSubmitter:add_pantry_form-Add").click().run()
            self.assertEqual(mem.items, ["Eggs", "Milk"])

            app.button(key="sign_out").click().run()
            mem.items = ["Flour"]
            app.text_input(key="account_email").set_value("cook@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Sign In").click().run()
            self.assertEqual(list(app.session_state["pantry"]), ["Flour"])

            app.button(key="sign_out").click().run()
            mem.items = []
            app.session_state["pantry"] = ["Butter"]
            app.text_input(key="account_email").set_value("cook@example.com")
            app.text_input(key="account_password").set_value("secret1")
            app.button(key="FormSubmitter:account_form-Sign In").click().run()
            self.assertEqual(mem.items, ["Butter"])
            self.assertEqual(list(app.session_state["pantry"]), ["Butter"])


if __name__ == "__main__":
    unittest.main()
