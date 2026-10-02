"""Password checks and PostgREST pantry calls. No network."""

from __future__ import annotations

import unittest

from src.db import PantryDB, hash_password, usable_supabase_config, verify_password


class FakeResponse:
    def __init__(self, status: int, payload: list | dict | None = None) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else []
        self.text = ""

    def json(self) -> list | dict:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.profiles: list[dict[str, str]] = []
        self.items: list[dict[str, str]] = []
        self.shopping: list[dict[str, str]] = []
        self.recipes: list[dict] = []
        self.last_recipe_headers: dict | None = None
        self.last_recipe_params: dict | None = None

    def get(self, url: str, params=None, headers=None, timeout=None) -> FakeResponse:
        params = params or {}
        if url.endswith("/profiles"):
            email = str(params.get("email", "")).removeprefix("eq.")
            return FakeResponse(200, [row for row in self.profiles if row["email"] == email])
        if url.endswith("/imported_recipes"):
            return self._read_recipes(params, headers)
        bucket = self._bucket(url)
        if bucket is None:
            return FakeResponse(404, {"message": "missing"})
        user_id = str(params.get("user_id", "")).removeprefix("eq.")
        rows = [row for row in bucket if row["user_id"] == user_id]
        return FakeResponse(200, [{"name": row["name"]} for row in rows])

    def post(self, url: str, json=None, headers=None, timeout=None, params=None) -> FakeResponse:
        payload = dict(json or {})
        if url.endswith("/imported_recipes"):
            return self._write_recipe(payload, headers, params)
        if url.endswith("/profiles"):
            if any(row["email"] == payload["email"] for row in self.profiles):
                return FakeResponse(409, {"message": "duplicate"})
            payload["id"] = "user-1"
            self.profiles.append(payload)
            return FakeResponse(201, [{"id": payload["id"], "email": payload["email"]}])
        bucket = self._bucket(url)
        if bucket is not None:
            bucket.append(payload)
            return FakeResponse(201, [payload])
        return FakeResponse(404, {"message": "missing"})

    def delete(self, url: str, params=None, headers=None, timeout=None) -> FakeResponse:
        params = params or {}
        bucket = self._bucket(url)
        if bucket is None:
            return FakeResponse(404, {"message": "missing"})
        user_id = str(params.get("user_id", "")).removeprefix("eq.")
        name = params.get("name")
        if name is None:
            kept = [row for row in bucket if row["user_id"] != user_id]
        else:
            target = str(name).removeprefix("eq.")
            kept = [
                row
                for row in bucket
                if not (row["user_id"] == user_id and row["name"] == target)
            ]
        if url.endswith("/shopping_list_items"):
            self.shopping = kept
        else:
            self.items = kept
        return FakeResponse(204, [])

    def _profile_header(self, headers) -> str:
        headers = headers or {}
        return str(headers.get("X-Profile-Id") or headers.get("x-profile-id") or "")

    def _read_recipes(self, params, headers) -> FakeResponse:
        user_id = str(params.get("user_id", "")).removeprefix("eq.")
        self.last_recipe_headers = dict(headers or {})
        if self._profile_header(headers) != user_id:
            return FakeResponse(200, [])
        return FakeResponse(200, [row for row in self.recipes if row["user_id"] == user_id])

    def _write_recipe(self, payload: dict, headers, params) -> FakeResponse:
        self.last_recipe_headers = dict(headers or {})
        self.last_recipe_params = dict(params or {})
        if self._profile_header(headers) != str(payload.get("user_id") or ""):
            return FakeResponse(401, {"message": "new row violates row-level security policy"})
        for index, row in enumerate(self.recipes):
            if row["user_id"] == payload["user_id"] and row["external_id"] == payload["external_id"]:
                self.recipes[index] = payload
                return FakeResponse(201, [payload])
        self.recipes.append(payload)
        return FakeResponse(201, [payload])

    def _bucket(self, url: str) -> list[dict[str, str]] | None:
        if url.endswith("/pantry_items"):
            return self.items
        if url.endswith("/shopping_list_items"):
            return self.shopping
        return None


class PasswordTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        stored = hash_password("pantry-secret")
        self.assertTrue(verify_password("pantry-secret", stored))
        self.assertFalse(verify_password("nope", stored))
        self.assertNotIn("pantry-secret", stored)


class ConfigTests(unittest.TestCase):
    def test_placeholders_stay_local(self) -> None:
        self.assertFalse(usable_supabase_config("", ""))
        self.assertFalse(
            usable_supabase_config(
                "https://YOUR_PROJECT_REF.supabase.co",
                "YOUR_ANON_KEY_placeholder_value",
            )
        )


class PostgrestTests(unittest.TestCase):
    def test_signup_login_and_pantry(self) -> None:
        session = FakeSession()
        db = PantryDB("https://example.supabase.co", "a" * 24, session=session)
        user, error = db.signup("Cook@Example.com", "pantry-secret")
        self.assertIsNone(error)
        assert user is not None
        self.assertEqual(user["email"], "cook@example.com")
        self.assertNotIn("password_hash", user)

        again, taken = db.signup("cook@example.com", "pantry-secret")
        self.assertIsNone(again)
        self.assertIn("already exists", taken or "")

        signed, message = db.login("cook@example.com", "pantry-secret")
        self.assertIsNone(message)
        assert signed is not None
        bad, mismatch = db.login("cook@example.com", "wrong-password")
        self.assertIsNone(bad)
        self.assertEqual(mismatch, "Email or password does not match.")

        db.add_pantry(signed["id"], "Eggs")
        db.add_pantry(signed["id"], "Flour")
        self.assertEqual(db.list_pantry(signed["id"]), ["Eggs", "Flour"])
        db.remove_pantry(signed["id"], "Flour")
        self.assertEqual(db.list_pantry(signed["id"]), ["Eggs"])
        db.clear_pantry(signed["id"])
        self.assertEqual(db.list_pantry(signed["id"]), [])

        db.add_shopping(signed["id"], "Lime")
        db.add_shopping(signed["id"], "Flour")
        self.assertEqual(db.list_shopping(signed["id"]), ["Lime", "Flour"])
        db.remove_shopping(signed["id"], "Flour")
        self.assertEqual(db.list_shopping(signed["id"]), ["Lime"])
        self.assertEqual(db.list_pantry(signed["id"]), [])
        db.clear_shopping(signed["id"])
        self.assertEqual(db.list_shopping(signed["id"]), [])

    def test_imported_recipes_round_trip_and_header(self) -> None:
        session = FakeSession()
        db = PantryDB("https://example.supabase.co", "a" * 24, session=session)
        user, error = db.signup("cook@example.com", "pantry-secret")
        self.assertIsNone(error)
        assert user is not None
        record = {
            "id": "web-cloud-pancakes-abc",
            "title": "Cloud Pancakes",
            "ingredients": ["flour", "milk"],
            "optional": ["salt"],
            "tags": ["from-the-web"],
            "steps": "Whisk.",
            "source_url": "https://example.com/pancakes",
            "source_kind": "url",
        }
        db.save_imported_recipe(user["id"], record)
        assert session.last_recipe_headers is not None
        self.assertEqual(session.last_recipe_headers.get("X-Profile-Id"), user["id"])
        assert session.last_recipe_params is not None
        self.assertEqual(session.last_recipe_params.get("on_conflict"), "user_id,external_id")
        self.assertIn("resolution=merge-duplicates", session.last_recipe_headers.get("Prefer", ""))

        listed = db.list_imported_recipes(user["id"])
        self.assertEqual(listed, [{
            "id": "web-cloud-pancakes-abc",
            "title": "Cloud Pancakes",
            "ingredients": ["flour", "milk"],
            "optional": ["salt"],
            "tags": ["from-the-web"],
            "steps": "Whisk.",
            "source_url": "https://example.com/pancakes",
            "source_kind": "url",
        }])
        self.assertEqual(db.list_imported_recipes("someone-else"), [])

        record["title"] = "Cloud Pancakes Updated"
        db.save_imported_recipe(user["id"], record)
        again = db.list_imported_recipes(user["id"])
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["title"], "Cloud Pancakes Updated")

        blocked = session.get(
            "https://example.supabase.co/rest/v1/imported_recipes",
            params={"user_id": f"eq.{user['id']}"},
            headers={"X-Profile-Id": "someone-else"},
        )
        self.assertEqual(blocked.json(), [])
        denied = session.post(
            "https://example.supabase.co/rest/v1/imported_recipes",
            json={"user_id": user["id"], "external_id": "other", "title": "Nope"},
            headers={"X-Profile-Id": "someone-else"},
        )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(len(session.recipes), 1)


if __name__ == "__main__":
    unittest.main()
