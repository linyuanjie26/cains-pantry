"""Save and hydrate imported recipes, then Find In Book. No network."""

from __future__ import annotations

import html
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from web_recipes import SourcedRecipe, meal_to_recipe

_APP = Path(__file__).resolve().parents[1] / "app.py"
_SQL = Path(__file__).resolve().parents[1] / "supabase_imported_recipes.sql"


def _cards(app: AppTest) -> str:
    return html.unescape("\n".join(item.value for item in app.markdown))


class _Cloud:
    def __init__(self) -> None:
        self.pantry: list[str] = []
        self.shopping: list[str] = []
        self.recipes: list[dict] = []
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

    def list_imported_recipes(self, user_id: str) -> list[dict]:
        return [dict(row) for row in self.recipes]

    def save_imported_recipe(self, user_id: str, record: dict) -> None:
        for index, row in enumerate(self.recipes):
            if row.get("id") == record.get("id"):
                self.recipes[index] = dict(record)
                return
        self.recipes.append(dict(record))


def _config():
    return ("https://abcd.supabase.co", "k" * 24)


def _open() -> AppTest:
    app = AppTest.from_file(str(_APP), default_timeout=40)
    app.run()
    return app


def _account(app: AppTest, *, create: bool) -> None:
    app.text_input(key="account_email").set_value("cook@example.com")
    app.text_input(key="account_password").set_value("secret1")
    key = (
        "FormSubmitter:account_form-Create Account"
        if create
        else "FormSubmitter:account_form-Sign In"
    )
    app.button(key=key).click().run()


class SqlTests(unittest.TestCase):
    def test_policy_matches_the_profile_header(self) -> None:
        sql = _SQL.read_text(encoding="utf-8")
        policy = sql.split("create policy", 1)[1]
        self.assertIn("public.imported_recipes", sql)
        self.assertIn("enable row level security", sql)
        self.assertIn("source_kind in ('mealdb', 'url', 'manual')", sql)
        self.assertIn("private.request_profile_id()", policy)
        self.assertIn("= user_id", policy)
        self.assertNotIn("auth.uid()", policy)
        self.assertNotIn("using (true)", sql)


class LoggedOutImportTests(unittest.TestCase):
    def test_session_import_filters_and_does_not_survive_a_new_session(self) -> None:
        def fake_import(url: str) -> SourcedRecipe:
            return SourcedRecipe(
                id="web-session-stew-1",
                title="Session Stew",
                ingredients=("beans",),
                tags=("from-the-web",),
                steps="Simmer.",
                source_url=url,
                source_kind="url",
            )

        with patch("store.get_config", lambda: None), patch("ui.import_url", fake_import):
            app = AppTest.from_file(str(_APP), default_timeout=40)
            app.run()
            self.assertFalse(app.exception)
            app.text_input(key="web_url").set_value("https://example.com/stew")
            app.button(key="FormSubmitter:web_url_form-Import").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["web_recipes"][0]["title"], "Session Stew")
            self.assertEqual(app.session_state["web_recipes"][0]["source_kind"], "url")

            app.run()
            self.assertIn("Session Stew", _cards(app))
            self.assertIn("Simple Pancakes", _cards(app))

            app.text_input(key="find_in_book").set_value("Session Stew").run()
            blob = _cards(app)
            self.assertIn("Session Stew", blob)
            self.assertNotIn("Simple Pancakes", blob)

            app.text_input(key="find_in_book").set_value("Simple Pancakes").run()
            blob = _cards(app)
            self.assertIn("Simple Pancakes", blob)
            self.assertNotIn("Session Stew", blob)

            fresh = AppTest.from_file(str(_APP), default_timeout=40)
            fresh.run()
            self.assertNotIn("Session Stew", _cards(fresh))
            self.assertIn("Simple Pancakes", _cards(fresh))


class CloudImportTests(unittest.TestCase):
    def test_sign_in_uploads_a_session_import_when_the_cloud_is_empty(self) -> None:
        cloud = _Cloud()

        def factory(url: str, key: str) -> _Cloud:
            return cloud

        with patch("store.get_config", _config), patch("store.PantryDB", factory):
            app = _open()
            app.session_state["web_recipes"] = [{
                "id": "web-local-stew-1",
                "title": "Local Stew",
                "ingredients": ["beans"],
                "optional": [],
                "tags": ["from-the-web"],
                "steps": "Simmer.",
                "source_url": "https://example.com/stew",
                "source_kind": "url",
            }]
            _account(app, create=True)
            self.assertFalse(app.exception)
            self.assertEqual(cloud.recipes[0]["title"], "Local Stew")
            self.assertEqual(cloud.recipes[0]["source_url"], "https://example.com/stew")

    def test_import_survives_a_new_session_and_still_filters(self) -> None:
        cloud = _Cloud()

        def factory(url: str, key: str) -> _Cloud:
            return cloud

        def fake_import(url: str) -> SourcedRecipe:
            return SourcedRecipe(
                id="web-cloud-pancakes-abc",
                title="Cloud Pancakes",
                ingredients=("flour", "milk", "eggs"),
                optional=("salt",),
                tags=("from-the-web",),
                steps="Whisk.",
                source_url=url,
                source_kind="url",
            )

        with (
            patch("store.get_config", _config),
            patch("store.PantryDB", factory),
            patch("ui.import_url", fake_import),
        ):
            app = _open()
            _account(app, create=True)
            app.text_input(key="web_url").set_value("https://example.com/pancakes")
            app.button(key="FormSubmitter:web_url_form-Import").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(cloud.recipes[0]["title"], "Cloud Pancakes")
            self.assertEqual(cloud.recipes[0]["source_kind"], "url")
            self.assertEqual(cloud.recipes[0]["source_url"], "https://example.com/pancakes")
            self.assertEqual(cloud.recipes[0]["optional"], ["salt"])

            fresh = _open()
            self.assertNotIn("Cloud Pancakes", _cards(fresh))
            _account(fresh, create=False)
            self.assertFalse(fresh.exception)
            self.assertEqual(fresh.session_state["web_recipes"][0]["title"], "Cloud Pancakes")
            self.assertIn("Cloud Pancakes", _cards(fresh))
            self.assertIn("Simple Pancakes", _cards(fresh))

            fresh.session_state["pantry"] = ["eggs", "milk", "flour"]
            fresh.text_input(key="find_in_book").set_value("Cloud Pancakes").run()
            self.assertFalse(fresh.exception)
            blob = _cards(fresh)
            self.assertIn("Cloud Pancakes", blob)
            self.assertNotIn("Simple Pancakes", blob)
            self.assertIn("cp-badge-ready", blob)

            fresh.text_input(key="find_in_book").set_value("Simple Pancakes").run()
            blob = _cards(fresh)
            self.assertIn("Simple Pancakes", blob)
            self.assertNotIn("Cloud Pancakes", blob)
            self.assertIn("cp-badge-ready", blob)

    def test_mealdb_add_saves_source_and_filters(self) -> None:
        cloud = _Cloud()

        def factory(url: str, key: str) -> _Cloud:
            return cloud

        def fake_search(query: str):
            return [meal_to_recipe({
                "idMeal": "900001",
                "strMeal": "Signed In Garlic Penne",
                "strInstructions": "Boil the pasta.",
                "strIngredient1": "garlic",
                "strMeasure1": "3 cloves",
                "strIngredient2": "penne",
                "strMeasure2": "1 pound",
            })]

        with (
            patch("store.get_config", _config),
            patch("store.PantryDB", factory),
            patch("ui.search_meals", fake_search),
        ):
            app = _open()
            _account(app, create=True)
            app.text_input(key="web_query").set_value("Arrabiata")
            app.button(key="FormSubmitter:web_search_form-Search").click().run()
            self.assertFalse(app.exception)
            hits = list(app.session_state["web_hits"])
            self.assertEqual(hits[0]["source_kind"], "mealdb")
            app.button(key=f"web-add-{hits[0]['id']}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(cloud.recipes[0]["source_kind"], "mealdb")
            self.assertEqual(
                cloud.recipes[0]["source_url"],
                "https://www.themealdb.com/meal/900001",
            )
            self.assertIn("Signed In Garlic Penne", _cards(app))

            app.text_input(key="find_in_book").set_value("Signed In Garlic").run()
            blob = _cards(app)
            self.assertIn("Signed In Garlic Penne", blob)
            self.assertNotIn("Simple Pancakes", blob)

            app.text_input(key="find_in_book").set_value("Simple Pancakes").run()
            blob = _cards(app)
            self.assertIn("Simple Pancakes", blob)
            self.assertNotIn("Signed In Garlic Penne", blob)


if __name__ == "__main__":
    unittest.main()
