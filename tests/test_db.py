"""Password checks and PostgREST pantry/shopping calls. No network."""

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

    def get(self, url: str, params=None, headers=None, timeout=None) -> FakeResponse:
        params = params or {}
        if url.endswith("/profiles"):
            email = str(params.get("email", "")).removeprefix("eq.")
            return FakeResponse(200, [row for row in self.profiles if row["email"] == email])
        if url.endswith("/pantry_items"):
            user_id = str(params.get("user_id", "")).removeprefix("eq.")
            rows = [row for row in self.items if row["user_id"] == user_id]
            return FakeResponse(200, [{"name": row["name"]} for row in rows])
        if url.endswith("/shopping_list_items"):
            user_id = str(params.get("user_id", "")).removeprefix("eq.")
            rows = [row for row in self.shopping if row["user_id"] == user_id]
            return FakeResponse(200, [{"name": row["name"]} for row in rows])
        return FakeResponse(404, {"message": "missing"})

    def post(self, url: str, json=None, headers=None, timeout=None) -> FakeResponse:
        payload = dict(json or {})
        if url.endswith("/profiles"):
            if any(row["email"] == payload["email"] for row in self.profiles):
                return FakeResponse(409, {"message": "duplicate"})
            payload["id"] = "user-1"
            self.profiles.append(payload)
            return FakeResponse(201, [{"id": payload["id"], "email": payload["email"]}])
        if url.endswith("/pantry_items"):
            self.items.append(payload)
            return FakeResponse(201, [payload])
        if url.endswith("/shopping_list_items"):
            self.shopping.append(payload)
            return FakeResponse(201, [payload])
        return FakeResponse(404, {"message": "missing"})

    def delete(self, url: str, params=None, headers=None, timeout=None) -> FakeResponse:
        params = params or {}
        user_id = str(params.get("user_id", "")).removeprefix("eq.")
        name = params.get("name")
        bucket = self.items if url.endswith("/pantry_items") else self.shopping
        if name is None:
            kept = [row for row in bucket if row["user_id"] != user_id]
        else:
            target = str(name).removeprefix("eq.")
            kept = [
                row
                for row in bucket
                if not (row["user_id"] == user_id and row["name"] == target)
            ]
        if url.endswith("/pantry_items"):
            self.items = kept
        else:
            self.shopping = kept
        return FakeResponse(204, [])


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
    def test_signup_login_pantry_and_shopping(self) -> None:
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
        db.add_shopping(signed["id"], "Butter")
        self.assertEqual(db.list_shopping(signed["id"]), ["Lime", "Butter"])
        db.remove_shopping(signed["id"], "Butter")
        self.assertEqual(db.list_shopping(signed["id"]), ["Lime"])
        db.clear_shopping(signed["id"])
        self.assertEqual(db.list_shopping(signed["id"]), [])


if __name__ == "__main__":
    unittest.main()
