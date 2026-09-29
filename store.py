"""Pantry persistence.

Session state is always the list the UI reads. When Streamlit secrets include
SUPABASE_URL and SUPABASE_ANON_KEY, sign-in loads and saves pantry_items.
Missing secrets leave login optional and keep the current session pantry.
"""

from __future__ import annotations

import streamlit as st

import cains_copy as cp
from src.db import PantryDB, get_config

_USER_KEY = "cp_user"


def split_pantry_entry(raw: str) -> list[str]:
    """Split a comma-separated pantry field. Matching stays in matching.py."""
    found: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        item = " ".join(part.strip().split())
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        found.append(item)
    return found


def read_supabase_config() -> tuple[str, str] | None:
    return get_config()


def signed_in_email() -> str | None:
    saved = st.session_state.get(_USER_KEY)
    if not saved:
        return None
    return saved.get("email") or None


def pantry() -> list[str]:
    if "pantry" not in st.session_state:
        st.session_state.pantry = []
        _hydrate_once()
    return st.session_state.pantry


def add_entry(raw: str) -> None:
    """Add one field, splitting on commas. Skips names already in the pantry."""
    incoming = split_pantry_entry(raw)
    if not incoming:
        st.session_state.notice = ("warn", "Enter an ingredient name.")
        return

    items = pantry()
    added: list[str] = []
    already: list[str] = []
    for item in incoming:
        if any(existing.casefold() == item.casefold() for existing in items):
            already.append(item)
            continue
        items.append(item)
        added.append(item)
        _remote_insert(item)

    if added and already:
        st.session_state.notice = (
            "ok",
            f"Added {', '.join(added)}. Already had {', '.join(already)}.",
        )
    elif added:
        st.session_state.notice = ("ok", f"Added {', '.join(added)}.")
    else:
        st.session_state.notice = ("info", f"Already in the pantry: {', '.join(already)}.")


def remove_item(item: str) -> None:
    st.session_state.pantry = [name for name in pantry() if name != item]
    _remote_delete(item)
    st.session_state.notice = ("info", f"Removed {item}.")


def clear() -> None:
    st.session_state.pantry = []
    _remote_clear()
    st.session_state.notice = ("info", "Pantry cleared.")


def shopping_list() -> list[str]:
    """Session-only buy list. Not written to Supabase."""
    if "shopping_list" not in st.session_state:
        st.session_state.shopping_list = []
    return st.session_state.shopping_list


def add_to_shopping_list(raw: str | list[str]) -> None:
    """Add names, splitting commas. Casefold duplicates stay out."""
    incoming = _shopping_names(raw)
    if not incoming:
        st.session_state.shop_notice = ("warn", cp.SHOP_NEED_NAME)
        return

    items = shopping_list()
    added: list[str] = []
    already: list[str] = []
    for item in incoming:
        if any(existing.casefold() == item.casefold() for existing in items):
            already.append(item)
            continue
        items.append(item)
        added.append(item)

    if added and already:
        st.session_state.shop_notice = (
            "ok",
            cp.SHOP_ADDED_SOME.format(added=", ".join(added), already=", ".join(already)),
        )
    elif added:
        st.session_state.shop_notice = ("ok", cp.SHOP_ADDED.format(items=", ".join(added)))
    else:
        st.session_state.shop_notice = ("info", cp.SHOP_ALREADY.format(items=", ".join(already)))


def remove_from_shopping_list(item: str, *, quiet: bool = False) -> None:
    key = item.casefold()
    st.session_state.shopping_list = [
        name for name in shopping_list() if name.casefold() != key
    ]
    if not quiet:
        st.session_state.shop_notice = ("info", cp.SHOP_REMOVED.format(item=item))


def clear_shopping_list() -> None:
    st.session_state.shopping_list = []
    st.session_state.shop_notice = ("info", cp.SHOP_CLEARED)


def mark_bought(item: str) -> None:
    """Drop the row from the list and put that ingredient in the pantry."""
    name = " ".join((item or "").split())
    if not name:
        return
    remove_from_shopping_list(name, quiet=True)
    items = pantry()
    if not any(existing.casefold() == name.casefold() for existing in items):
        items.append(name)
        _remote_insert(name)
    st.session_state.shop_notice = ("ok", cp.SHOP_BOUGHT.format(item=name))


def _shopping_names(raw: str | list[str]) -> list[str]:
    if isinstance(raw, str):
        return split_pantry_entry(raw)
    found: list[str] = []
    seen: set[str] = set()
    for part in raw:
        for item in split_pantry_entry(str(part)):
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append(item)
    return found


def sign_in(email: str, password: str) -> str | None:
    problem = _validate(email, password)
    if problem:
        return problem
    db = _db()
    if db is None:
        return "Login is optional and stays off until Supabase secrets are set."
    try:
        user, message = db.login(email, password)
    except Exception as exc:
        return _short_error(exc)
    if user is None:
        return message or "Email or password does not match."
    _remember(user)
    _adopt_remote_pantry()
    return None


def sign_up(email: str, password: str) -> str | None:
    problem = _validate(email, password)
    if problem:
        return problem
    db = _db()
    if db is None:
        return "Login is optional and stays off until Supabase secrets are set."
    try:
        user, message = db.signup(email, password)
    except Exception as exc:
        return _short_error(exc)
    if user is None:
        return message or "Could not create the account."
    _remember(user)
    _adopt_remote_pantry()
    return None


def sign_out() -> None:
    st.session_state.pop(_USER_KEY, None)


def cloud_warning() -> str | None:
    if get_config() is None:
        return None
    try:
        import bcrypt  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        return "Supabase secrets are set. Install bcrypt and requests to turn on login."
    return None


def _validate(email: str, password: str) -> str | None:
    if "@" not in email or " " in email.strip() or not password:
        return "Enter an email and a password."
    if len(password) < 6:
        return "Use at least 6 characters."
    if len(password.encode("utf-8")) > 72:
        return "Use at most 72 characters."
    return None


def _hydrate_once() -> None:
    if not signed_in_email():
        return
    remote = _fetch_names()
    if remote is not None:
        st.session_state.pantry = remote


def _adopt_remote_pantry() -> None:
    remote = _fetch_names()
    local = list(st.session_state.get("pantry") or [])
    if remote:
        st.session_state.pantry = remote
        return
    st.session_state.pantry = local
    for name in local:
        _remote_insert(name)


def _remember(user: dict[str, str]) -> None:
    st.session_state[_USER_KEY] = {"id": user["id"], "email": user["email"]}


def _db() -> PantryDB | None:
    config = get_config()
    if config is None:
        return None
    try:
        import bcrypt  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        return None
    url, key = config
    return PantryDB(url, key)


def _user_id() -> str | None:
    saved = st.session_state.get(_USER_KEY)
    if not saved:
        return None
    return saved.get("id")


def _fetch_names() -> list[str] | None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return None
    try:
        return db.list_pantry(user_id)
    except Exception as exc:
        st.session_state.notice = ("warn", _short_error(exc))
        return None


def _remote_insert(name: str) -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.add_pantry(user_id, name)
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate" in text or "23505" in text:
            return
        st.session_state.notice = ("warn", "Saved in this session. Cloud pantry did not update.")


def _remote_delete(name: str) -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.remove_pantry(user_id, name)
    except Exception:
        st.session_state.notice = ("warn", "Removed here. Cloud pantry did not update.")


def _remote_clear() -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.clear_pantry(user_id)
    except Exception:
        st.session_state.notice = ("warn", "Cleared here. Cloud pantry did not update.")


def _short_error(exc: Exception) -> str:
    message = str(exc).strip().splitlines()
    return message[0][:180] if message else "Something went wrong."
