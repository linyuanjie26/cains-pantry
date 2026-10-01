"""Bundled TheMealDB catalog. No network."""

from __future__ import annotations

import unittest

from matching import READY, Recipe, match_all
from web_recipes import fetch_mealdb_catalog, load_web_catalog, merge_recipes

_ARRABIATA = {
    "idMeal": "52771",
    "strMeal": "Spicy Arrabiata Penne",
    "strCategory": "Pasta",
    "strInstructions": "Boil the pasta.",
    "strIngredient1": "penne rigate",
    "strMeasure1": "1 pound",
    "strIngredient2": "olive oil",
    "strMeasure2": "1/4 cup",
}


class CatalogTests(unittest.TestCase):
    def test_bundled_file_loads_without_a_key(self) -> None:
        catalog = load_web_catalog()
        self.assertGreaterEqual(len(catalog), 100)
        self.assertTrue(all(recipe.ingredients for recipe in catalog))
        self.assertTrue(all("from-the-web" in recipe.tags for recipe in catalog))
        self.assertTrue(all("web-catalog" in recipe.tags for recipe in catalog))
        titles = [recipe.title.casefold() for recipe in catalog]
        self.assertEqual(len(titles), len(set(titles)))

    def test_catalog_ranks_with_cains_recipes(self) -> None:
        pancakes = Recipe(
            id="simple-pancakes",
            title="Simple Pancakes",
            ingredients=("flour", "milk", "eggs"),
        )
        book = merge_recipes([pancakes], load_web_catalog())
        ranked = match_all(book, ["eggs", "milk", "flour"])
        match = next(item for item in ranked if item.recipe.id == "simple-pancakes")
        self.assertEqual(match.status, READY)
        self.assertTrue(any("web-catalog" in item.recipe.tags for item in ranked))
        self.assertGreater(len(book), len(load_web_catalog()))

    def test_letter_fetch_dedupes_without_network(self) -> None:
        def fetch_json(letter: str) -> dict:
            if letter == "a":
                return {"meals": [_ARRABIATA, dict(_ARRABIATA)]}
            return {"meals": None}

        records = fetch_mealdb_catalog(fetch_json=fetch_json)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Spicy Arrabiata Penne")
        self.assertIn("olive oil", records[0]["ingredients"])
        self.assertIn("from-the-web", records[0]["tags"])


if __name__ == "__main__":
    unittest.main()
