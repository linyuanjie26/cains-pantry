"""Supabase PostgREST access for profiles and pantry items.

Passwords are bcrypt hashes on `profiles`. The anon key is enough for the
demo policies in supabase_profiles.sql and supabase_pantry.sql. Those
policies are permissive on purpose: do not use them for real accounts.

When secrets are missing, callers should keep the pantry in session state.
"""

from __future__ import annotations

from typing import Any

import bcrypt
import requests

_PLACEHOLDER_BITS = (
    "your-project",
    "your_project",
    "your_project_ref",
    "your-anon",
    "your_anon",
    "paste-",
)


def usable_supabase_config(url: str | None, key: str | None) -> bool:
    """True when both values look filled in, not blank or a placeholder."""
    if not url or not key:
        return False
    folded = f"{url} {key}".lower()
    if any(bit in folded for bit in _PLACEHOLDER_BITS):
        return False
    return url.startswith("http") and len(key) >= 20


def get_config() -> tuple[str, str] | None:
    """Read SUPABASE_URL and SUPABASE_ANON_KEY from Streamlit secrets."""
    try:
        import streamlit as st

        url = str(st.secrets["SUPABASE_URL"]).strip()
        key = str(st.secrets["SUPABASE_ANON_KEY"]).strip()
    except Exception:
        return None
    if not usable_supabase_config(url, key):
        return None
    return url, key


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class PantryDB:
    """Thin PostgREST client. Inject `session` in tests."""

    def __init__(self, url: str, key: str, session: requests.Session | None = None) -> None:
        self.base = url.rstrip("/") + "/rest/v1"
        self.session = session or requests.Session()
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def signup(self, email: str, password: str) -> tuple[dict[str, str] | None, str | None]:
        folded = email.strip().lower()
        existing = self._get(
            "profiles",
            {"email": f"eq.{folded}", "select": "id"},
        )
        if existing:
            return None, "An account with that email already exists."
        created = self._post(
            "profiles",
            {"email": folded, "password_hash": hash_password(password)},
        )
        if not created:
            return None, "Could not create the account."
        row = created[0]
        return {"id": str(row["id"]), "email": str(row["email"])}, None

    def login(self, email: str, password: str) -> tuple[dict[str, str] | None, str | None]:
        folded = email.strip().lower()
        rows = self._get(
            "profiles",
            {"email": f"eq.{folded}", "select": "id,email,password_hash"},
        )
        if not rows:
            return None, "Email or password does not match."
        row = rows[0]
        if not verify_password(password, str(row.get("password_hash") or "")):
            return None, "Email or password does not match."
        return {"id": str(row["id"]), "email": str(row["email"])}, None

    def list_pantry(self, user_id: str) -> list[str]:
        rows = self._get(
            "pantry_items",
            {
                "user_id": f"eq.{user_id}",
                "select": "name",
                "order": "created_at.asc",
            },
        )
        return [str(row["name"]) for row in rows]

    def add_pantry(self, user_id: str, name: str) -> None:
        self._post("pantry_items", {"user_id": user_id, "name": name})

    def remove_pantry(self, user_id: str, name: str) -> None:
        self._delete(
            "pantry_items",
            {"user_id": f"eq.{user_id}", "name": f"eq.{name}"},
        )

    def clear_pantry(self, user_id: str) -> None:
        self._delete("pantry_items", {"user_id": f"eq.{user_id}"})

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base}/{table}",
            params=params,
            headers=self.headers,
            timeout=8,
        )
        return self._rows(response)

    def _post(self, table: str, payload: dict[str, str]) -> list[dict[str, Any]]:
        headers = {**self.headers, "Prefer": "return=representation"}
        response = self.session.post(
            f"{self.base}/{table}",
            json=payload,
            headers=headers,
            timeout=8,
        )
        if response.status_code == 409:
            return []
        return self._rows(response)

    def _delete(self, table: str, params: dict[str, str]) -> None:
        response = self.session.delete(
            f"{self.base}/{table}",
            params=params,
            headers=self.headers,
            timeout=8,
        )
        if response.status_code in (200, 204):
            return
        self._raise(response)

    def _rows(self, response: requests.Response) -> list[dict[str, Any]]:
        if response.status_code in (200, 201):
            data = response.json()
            return data if isinstance(data, list) else []
        self._raise(response)
        return []

    def _raise(self, response: requests.Response) -> None:
        message = f"Supabase returned {response.status_code}"
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("message"):
                message = str(body["message"])
        except Exception:
            pass
        raise RuntimeError(message[:180])
