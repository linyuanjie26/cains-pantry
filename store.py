"""Pantry persistence.

Session state is always the list the UI reads. When Streamlit secrets include
SUPABASE_URL and SUPABASE_ANON_KEY, sign-in loads and saves pantry_items,
shopping_list_items, and imported_recipes. Missing secrets leave login optional
and keep those lists in the current session.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

import cains_copy as cp
from src.db import PantryDB, get_config
from web_recipes import source_kind_for

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
    """Buy list. Session state, plus shopping_list_items when signed in."""
    if "shopping_list" not in st.session_state:
        st.session_state.shopping_list = []
        _hydrate_shopping_once()
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
        _remote_shop_insert(item)

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
    _remote_shop_delete(item)
    if not quiet:
        st.session_state.shop_notice = ("info", cp.SHOP_REMOVED.format(item=item))


def web_recipes() -> list[dict[str, Any]]:
    """Imported recipes. Session state, plus imported_recipes when signed in."""
    if "web_recipes" not in st.session_state:
        st.session_state.web_recipes = []
        _hydrate_recipes_once()
    rows = st.session_state.web_recipes
    if not isinstance(rows, list):
        st.session_state.web_recipes = []
    return st.session_state.web_recipes


def remember_imported_recipe(record: dict[str, Any]) -> tuple[bool, str | None]:
    """Keep one import in the session and, when signed in, in Supabase.

    Returns whether an existing id was replaced, and a short cloud warning.
    """
    clean = _clean_imported(record)
    if clean is None:
        return False, "This site did not share a recipe we could read."
    rows = [row for row in web_recipes() if isinstance(row, dict)]
    replaced = False
    for index, row in enumerate(rows):
        if row.get("id") == clean["id"]:
            rows[index] = clean
            replaced = True
            break
    if not replaced:
        rows.append(clean)
    st.session_state.web_recipes = rows
    return replaced, _remote_recipe_save(clean)


def clear_shopping_list() -> None:
    st.session_state.shopping_list = []
    _remote_shop_clear()
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
    current = st.session_state.get("shop_notice")
    if not (isinstance(current, tuple) and current and current[0] == "warn"):
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
    _adopt_remote_shopping()
    _adopt_remote_recipes()
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
    _adopt_remote_shopping()
    _adopt_remote_recipes()
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


def _hydrate_shopping_once() -> None:
    if not signed_in_email():
        return
    remote = _fetch_shopping()
    if remote is not None:
        st.session_state.shopping_list = remote


def _adopt_remote_shopping() -> None:
    remote = _fetch_shopping()
    local = list(st.session_state.get("shopping_list") or [])
    if remote:
        st.session_state.shopping_list = remote
        return
    st.session_state.shopping_list = local
    for name in local:
        _remote_shop_insert(name)


def _hydrate_recipes_once() -> None:
    if not signed_in_email():
        return
    remote = _fetch_recipes()
    if remote is not None:
        st.session_state.web_recipes = remote


def _adopt_remote_recipes() -> None:
    remote = _fetch_recipes()
    local = [row for row in (st.session_state.get("web_recipes") or []) if isinstance(row, dict)]
    if remote is None:
        return
    if remote:
        st.session_state.web_recipes = remote
        return
    st.session_state.web_recipes = local
    for record in local:
        _remote_recipe_save(record)


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


def _fetch_shopping() -> list[str] | None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return None
    try:
        return db.list_shopping(user_id)
    except Exception as exc:
        st.session_state.shop_notice = ("warn", _short_error(exc))
        return None


def _remote_shop_insert(name: str) -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.add_shopping(user_id, name)
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate" in text or "23505" in text:
            return
        st.session_state.shop_notice = (
            "warn",
            "Saved in this session. Cloud shopping list did not update.",
        )


def _remote_shop_delete(name: str) -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.remove_shopping(user_id, name)
    except Exception:
        st.session_state.shop_notice = (
            "warn",
            "Removed here. Cloud shopping list did not update.",
        )


def _fetch_recipes() -> list[dict[str, Any]] | None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return None
    try:
        return db.list_imported_recipes(user_id)
    except Exception as exc:
        st.session_state.web_notice = ("warn", _short_error(exc))
        return None


def _remote_recipe_save(record: dict[str, Any]) -> str | None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return None
    try:
        db.save_imported_recipe(user_id, record)
    except Exception as exc:
        text = str(exc).lower()
        if "duplicate" in text or "23505" in text:
            return None
        return "Saved in this session. Cloud recipe book did not update."
    return None


def _clean_imported(record: dict[str, Any]) -> dict[str, Any] | None:
    title = " ".join(str(record.get("title") or "").split())
    ingredients: list[str] = []
    seen: set[str] = set()
    for raw in record.get("ingredients") or []:
        name = " ".join(str(raw).split())
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        ingredients.append(name)
    if not title or not ingredients:
        return None
    recipe_id = str(record.get("id") or "").strip() or title
    optional: list[str] = []
    opt_seen: set[str] = set()
    for raw in record.get("optional") or []:
        name = " ".join(str(raw).split())
        key = name.casefold()
        if not name or key in seen or key in opt_seen:
            continue
        opt_seen.add(key)
        optional.append(name)
    tags: list[str] = []
    tag_seen: set[str] = set()
    for raw in record.get("tags") or []:
        tag = str(raw).strip()
        if not tag or tag.casefold() in tag_seen:
            continue
        tag_seen.add(tag.casefold())
        tags.append(tag)
    return {
        "id": recipe_id,
        "title": title,
        "ingredients": ingredients,
        "optional": optional,
        "tags": tags,
        "steps": str(record.get("steps") or ""),
        "source_url": str(record.get("source_url") or "").strip(),
        "source_kind": source_kind_for(recipe_id, str(record.get("source_kind") or "")),
    }


def _remote_shop_clear() -> None:
    db = _db()
    user_id = _user_id()
    if db is None or not user_id:
        return
    try:
        db.clear_shopping(user_id)
    except Exception:
        st.session_state.shop_notice = (
            "warn",
            "Cleared here. Cloud shopping list did not update.",
        )


def _short_error(exc: Exception) -> str:
    message = str(exc).strip().splitlines()
    return message[0][:180] if message else "Something went wrong."
