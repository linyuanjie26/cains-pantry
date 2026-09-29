"""URL and TheMealDB imports. No network."""

from __future__ import annotations

import unittest

import requests

from matching import READY, match_all
from web_recipes import (
    WebRecipeError,
    import_url,
    meal_to_recipe,
    names_from_line,
    parse_html,
    search_meals,
)

_PANCAKES = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Recipe","name":"Web Pancakes",
 "recipeIngredient":["1 cup flour","1 cup milk","2 eggs","1 tsp salt (optional)"],
 "recipeInstructions":[{"@type":"HowToStep","text":"Whisk and cook."}]}
</script>
</head><body></body></html>
"""

_ARRABIATA = {
    "idMeal": "52771",
    "strMeal": "Spicy Arrabiata Penne",
    "strInstructions": "Boil the pasta. Simmer the sauce.",
    "strIngredient1": "penne rigate",
    "strMeasure1": "1 pound",
    "strIngredient2": "olive oil",
    "strMeasure2": "1/4 cup",
    "strIngredient3": "garlic",
    "strMeasure3": "3 cloves",
    "strIngredient4": "chopped tomatoes",
    "strMeasure4": "1 tin",
    "strIngredient5": "red chilli flakes",
    "strMeasure5": "1/2 teaspoon",
    "strIngredient6": "Parmigiano-Reggiano",
    "strMeasure6": "sprinkling",
}


class CleanTests(unittest.TestCase):
    def test_strips_amounts_and_uses_aliases(self) -> None:
        self.assertEqual(names_from_line("1 cup flour"), ["flour"])
        self.assertEqual(names_from_line("2 eggs"), ["eggs"])
        self.assertEqual(names_from_line("1/4 cup olive oil"), ["olive oil"])
        self.assertEqual(names_from_line("1 tin chopped tomatoes"), ["canned tomatoes"])
        self.assertEqual(names_from_line("1/2 teaspoon red chilli flakes"), ["chili flakes"])
        self.assertEqual(names_from_line("sprinkling Parmigiano-Reggiano"), ["parmesan"])
        self.assertEqual(names_from_line("mayo"), ["mayonnaise"])


class ParseTests(unittest.TestCase):
    def test_json_ld_pancakes_rank_ready(self) -> None:
        recipe = parse_html(_PANCAKES, "https://example.com/pancakes")
        self.assertEqual(recipe.title, "Web Pancakes")
        self.assertEqual(recipe.ingredients, ("flour", "milk", "eggs"))
        self.assertEqual(recipe.optional, ("salt",))
        ranked = match_all([recipe], ["eggs", "milk", "flour"])
        self.assertEqual(ranked[0].status, READY)
        self.assertEqual(ranked[0].missing, [])

    def test_plain_page_is_a_clear_error(self) -> None:
        with self.assertRaises(WebRecipeError) as caught:
            parse_html("<html><body>No recipe here</body></html>", "https://example.com/nope")
        self.assertIn("did not share a recipe", str(caught.exception))

    def test_import_url_uses_the_fetcher(self) -> None:
        recipe = import_url("https://example.com/pancakes", fetch=lambda url: _PANCAKES)
        self.assertEqual(recipe.title, "Web Pancakes")

    def test_bad_url_does_not_fetch(self) -> None:
        def fetch(url: str) -> str:
            raise AssertionError("should not fetch")

        with self.assertRaises(WebRecipeError) as caught:
            import_url("not a link", fetch=fetch)
        self.assertIn("http", str(caught.exception))

    def test_network_failure_is_a_clear_error(self) -> None:
        def fetch(url: str) -> str:
            raise requests.ConnectionError("down")

        with self.assertRaises(WebRecipeError) as caught:
            import_url("https://example.com/pancakes", fetch=fetch)
        self.assertIn("Could not reach", str(caught.exception))


class MealDbTests(unittest.TestCase):
    def test_arrabiata_becomes_a_ranked_recipe(self) -> None:
        recipe = meal_to_recipe(_ARRABIATA)
        self.assertEqual(recipe.title, "Spicy Arrabiata Penne")
        self.assertIn("olive oil", recipe.ingredients)
        self.assertIn("canned tomatoes", recipe.ingredients)
        self.assertIn("chili flakes", recipe.ingredients)
        self.assertIn("parmesan", recipe.ingredients)
        self.assertTrue(recipe.id.startswith("mealdb-"))
        ranked = match_all([recipe], ["garlic", "olive oil", "pasta"])
        self.assertEqual(len(ranked), 1)
        self.assertIn(ranked[0].status, {"Ready", "Almost", "Need More"})

    def test_search_reads_meals_and_empty_results(self) -> None:
        found = search_meals("Arrabiata", fetch_json=lambda query: {"meals": [_ARRABIATA]})
        self.assertEqual(found[0].title, "Spicy Arrabiata Penne")
        self.assertEqual(search_meals("missing", fetch_json=lambda query: {"meals": None}), [])

    def test_blank_search_is_a_clear_error(self) -> None:
        with self.assertRaises(WebRecipeError):
            search_meals("  ")


if __name__ == "__main__":
    unittest.main()
