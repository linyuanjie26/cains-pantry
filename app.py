"""Cain's Pantry — Streamlit entrypoint.

Loads recipes.json, then hands the session pantry to matching.match_all.
Find In Book filters that ranked list before the Ready / Almost / Need More groups render.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import cains_copy as cp
import store
from book_filter import filter_matches
from matching import Recipe, group_by_status, match_all
from ui import (
    page_shell,
    render_account,
    render_pantry_panel,
    render_results,
    render_shopping_panel,
    render_web_import,
)
from web_recipes import catalog_recipes, merge_recipes, recipes_from_records, start_catalog_refresh

_RECIPE_PATH = Path(__file__).resolve().with_name("recipes.json")


def load_recipes(path: Path | None = None) -> list[Recipe]:
    """Build Recipe objects from recipes.json. Not a hard-coded book."""
    source = path or _RECIPE_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Recipe file is not valid JSON: {source}") from exc
    rows = payload.get("recipes") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("Recipe file must contain a recipes list.")
    recipes: list[Recipe] = []
    for item in rows:
        recipes.append(
            Recipe(
                id=item["id"],
                title=item["title"],
                ingredients=tuple(item["ingredients"]),
                optional=tuple(item.get("optional", [])),
                tags=tuple(item.get("tags", [])),
                steps=item.get("steps", ""),
            )
        )
    return recipes


def main() -> None:
    def body() -> None:
        render_account()
        try:
            recipes = load_recipes()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error("Could not load the recipe book. Check recipes.json.")
            st.caption(str(exc))
            return

        imported = recipes_from_records(store.web_recipes())
        book = merge_recipes(recipes, catalog_recipes(), imported)
        start_catalog_refresh()
        left, right = st.columns([1, 2], gap="large")
        with left:
            pantry = render_pantry_panel()
            render_shopping_panel()
        with right:
            render_web_import()
            query = st.text_input(
                cp.FIND_IN_BOOK,
                placeholder=cp.FIND_IN_BOOK_PLACEHOLDER,
                key="find_in_book",
            )
            matched = filter_matches(match_all(book, pantry), query)
            if query.strip() and not matched:
                st.subheader(cp.RESULTS_HEADER)
                st.info(cp.FIND_IN_BOOK_EMPTY)
            else:
                render_results(group_by_status(matched))

    page_shell(body)


if __name__ == "__main__":
    main()
