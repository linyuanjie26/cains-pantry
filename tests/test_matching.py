"""Kai's matcher: aliases, and starter pantry → Cain's Toast Hash Ready."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from matching import (
    ALMOST,
    NEED_MORE,
    READY,
    Recipe,
    canonical,
    match_all,
    match_recipe,
    pantry_set,
)

_BOOK = Path(__file__).resolve().parents[1] / "recipes.json"


def load_book() -> tuple[list[Recipe], list[str]]:
    payload = json.loads(_BOOK.read_text(encoding="utf-8"))
    recipes = [
        Recipe(
            id=item["id"],
            title=item["title"],
            ingredients=tuple(item["ingredients"]),
            optional=tuple(item.get("optional", [])),
            tags=tuple(item.get("tags", [])),
            steps=item.get("steps", ""),
        )
        for item in payload["recipes"]
    ]
    return recipes, list(payload["starter_pantry"])


class AliasTests(unittest.TestCase):
    def test_book_aliases(self) -> None:
        self.assertEqual(canonical("garbanzo beans"), canonical("chickpeas"))
        self.assertEqual(canonical("mayo"), canonical("mayonnaise"))
        self.assertEqual(canonical("tomato"), canonical("canned tomatoes"))
        self.assertEqual(canonical("scallions"), canonical("green onion"))
        self.assertEqual(canonical("oil"), canonical("olive oil"))
        self.assertEqual(canonical("  Eggs "), canonical("egg"))


class RankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recipes, cls.starter = load_book()

    def test_book_size(self) -> None:
        titles = [recipe.title for recipe in self.recipes]
        self.assertGreaterEqual(len(self.recipes), 10)
        self.assertIn("Cain's Toast Hash", titles)
        self.assertIn("Simple Pancakes", titles)
        blob = _BOOK.read_text(encoding="utf-8").lower()
        for banned in ("tainted", "isaac", "binding of isaac"):
            self.assertNotIn(banned, blob)

    def test_starter_pantry_puts_toast_hash_ready(self) -> None:
        ranked = match_all(self.recipes, self.starter)
        top = ranked[0]
        self.assertEqual(top.recipe.title, "Cain's Toast Hash")
        self.assertEqual(top.status, READY)
        self.assertEqual(top.missing, [])

        statuses = [match.status for match in ranked]
        self.assertEqual(
            statuses,
            sorted(statuses, key=lambda status: {READY: 0, ALMOST: 1, NEED_MORE: 2}[status]),
        )
        self.assertIn(ALMOST, statuses)
        self.assertIn(NEED_MORE, statuses)
        ready = [match for match in ranked if match.status == READY]
        self.assertEqual([match.recipe.title for match in ready], ["Cain's Toast Hash"])

    def test_eggs_milk_flour_puts_pancakes_first(self) -> None:
        ranked = match_all(self.recipes, ["eggs", "milk", "flour"])
        top = ranked[0]
        self.assertEqual(top.recipe.title, "Simple Pancakes")
        self.assertEqual(top.status, READY)
        self.assertEqual(top.missing, [])

    def test_optional_ingredient_does_not_block_ready(self) -> None:
        recipe = next(item for item in self.recipes if item.id == "jarred-pepper-pasta")
        match = match_recipe(recipe, pantry_set(recipe.ingredients))
        self.assertEqual(match.status, READY)
        self.assertIn("parmesan", match.optional_missing)

    def test_almost_and_need_more_thresholds(self) -> None:
        recipe = Recipe(id="t", title="Test", ingredients=("a", "b", "c", "d"))
        almost = match_recipe(recipe, pantry_set(["a", "b"]))
        self.assertEqual(almost.status, ALMOST)
        self.assertEqual(len(almost.missing), 2)
        need = match_recipe(recipe, pantry_set(["a"]))
        self.assertEqual(need.status, NEED_MORE)
        self.assertGreaterEqual(len(need.missing), 3)

    def test_empty_pantry_is_not_ready(self) -> None:
        ranked = match_all(self.recipes, [])
        self.assertTrue(all(match.status != READY for match in ranked))


if __name__ == "__main__":
    unittest.main()
