"""Find In Book: substring filter over title, tags, and ingredient names."""

from __future__ import annotations

import html
import unittest
from pathlib import Path

import cains_copy as cp
from book_filter import filter_matches
from matching import ALMOST, NEED_MORE, READY, MatchResult, Recipe
from streamlit.testing.v1 import AppTest

_ROOT = Path(__file__).resolve().parents[1]


def _match(
    title: str,
    *,
    tags: tuple[str, ...] = (),
    ingredients: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    status: str = NEED_MORE,
    steps: str = "",
    recipe_id: str = "",
) -> MatchResult:
    recipe = Recipe(
        id=recipe_id or title.lower().replace(" ", "-"),
        title=title,
        ingredients=ingredients,
        optional=optional,
        tags=tags,
        steps=steps,
    )
    return MatchResult(recipe=recipe, status=status)


class BookFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pancakes = _match(
            "Simple Pancakes",
            tags=("breakfast", "three-ingredients"),
            ingredients=("flour", "milk", "eggs", "chickpeas"),
            status=READY,
            steps="Whisk until smooth.",
            recipe_id="simple-pancakes",
        )
        self.hash = _match(
            "Cain's Toast Hash",
            tags=("breakfast", "uses-leftover-bread"),
            ingredients=("bread", "eggs", "black pepper"),
            status=ALMOST,
        )
        self.pasta = _match(
            "Jarred Pepper Pasta",
            tags=("15-min", "pantry-pasta"),
            ingredients=("pasta", "garlic", "olive oil"),
            optional=("parmesan", "mayonnaise"),
            status=NEED_MORE,
            steps="A secret-step-token lives only here.",
            recipe_id="hidden-id-token",
        )
        self.matches = [self.pancakes, self.hash, self.pasta]

    def test_title_tag_and_ingredient_hits(self) -> None:
        self.assertEqual(filter_matches(self.matches, "toast"), [self.hash])
        self.assertEqual(filter_matches(self.matches, "15-min"), [self.pasta])
        self.assertEqual(filter_matches(self.matches, "flour"), [self.pancakes])
        self.assertEqual(filter_matches(self.matches, "parmesan"), [self.pasta])

    def test_case_insensitive_substring(self) -> None:
        self.assertEqual(filter_matches(self.matches, "PANCAKE"), [self.pancakes])
        self.assertEqual(filter_matches(self.matches, "Black Pepper"), [self.hash])
        self.assertEqual(
            filter_matches(self.matches, "egg"),
            [self.pancakes, self.hash],
        )

    def test_empty_query_returns_input_unchanged(self) -> None:
        self.assertIs(filter_matches(self.matches, ""), self.matches)
        self.assertIs(filter_matches(self.matches, "   \t\n"), self.matches)

    def test_no_match_returns_empty(self) -> None:
        self.assertEqual(filter_matches(self.matches, "no-such-dish"), [])

    def test_preserves_order_status_and_does_not_mutate(self) -> None:
        before = [(match.recipe.title, match.status) for match in self.matches]
        filtered = filter_matches(self.matches, "egg")
        self.assertEqual(
            [(match.recipe.title, match.status) for match in filtered],
            [("Simple Pancakes", READY), ("Cain's Toast Hash", ALMOST)],
        )
        self.assertIs(filtered[0], self.pancakes)
        self.assertIs(filtered[1], self.hash)
        self.assertEqual(
            [(match.recipe.title, match.status) for match in self.matches],
            before,
        )

    def test_ignores_steps_ids_and_aliases(self) -> None:
        self.assertEqual(filter_matches(self.matches, "secret-step-token"), [])
        self.assertEqual(filter_matches(self.matches, "hidden-id-token"), [])
        self.assertEqual(filter_matches(self.matches, "garbanzo"), [])
        self.assertEqual(filter_matches(self.matches, "chickpeas"), [self.pancakes])
        self.assertEqual(filter_matches(self.matches, "pepper"), [self.hash, self.pasta])

    def test_copy_and_app_wire(self) -> None:
        self.assertEqual(cp.FIND_IN_BOOK, "Find In Book")
        self.assertEqual(cp.FIND_IN_BOOK_PLACEHOLDER, "Title, Tag, Or Ingredient")
        self.assertTrue(cp.FIND_IN_BOOK_EMPTY.strip())
        source = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertLess(source.index("filter_matches"), source.index("group_by_status"))
        self.assertIn("cp.FIND_IN_BOOK", source)
        self.assertNotIn("filter_matches", (_ROOT / "matching.py").read_text(encoding="utf-8"))
        self.assertNotIn("filter_matches", (_ROOT / "web_recipes.py").read_text(encoding="utf-8"))


def _cards(app: AppTest) -> str:
    return html.unescape("\n".join(item.value for item in app.markdown))


class FindInBookAppTests(unittest.TestCase):
    def test_filter_hides_cards_and_keeps_badges(self) -> None:
        app = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=40)
        app.session_state["pantry"] = ["eggs", "milk", "flour"]
        app.run()
        self.assertFalse(app.exception)

        field = app.text_input(key="find_in_book")
        self.assertEqual(field.label, cp.FIND_IN_BOOK)
        self.assertEqual(field.placeholder, cp.FIND_IN_BOOK_PLACEHOLDER)
        blob = _cards(app)
        self.assertIn("Simple Pancakes", blob)
        self.assertIn("Cain's Toast Hash", blob)
        self.assertIn("cp-badge-ready", blob)

        app.text_input(key="find_in_book").set_value("toast hash").run()
        self.assertFalse(app.exception)
        blob = _cards(app)
        self.assertIn("Cain's Toast Hash", blob)
        self.assertNotIn("Simple Pancakes", blob)
        self.assertIn("cp-badge-need", blob)
        self.assertNotIn("cp-badge-ready", blob)

        app.text_input(key="find_in_book").set_value("pancake").run()
        self.assertFalse(app.exception)
        blob = _cards(app)
        self.assertIn("Simple Pancakes", blob)
        self.assertNotIn("Cain's Toast Hash", blob)
        self.assertIn("cp-badge-ready", blob)
        self.assertNotIn("cp-badge-need", blob)

        app.text_input(key="find_in_book").set_value("   ").run()
        self.assertFalse(app.exception)
        blob = _cards(app)
        self.assertIn("Simple Pancakes", blob)
        self.assertIn("Cain's Toast Hash", blob)

        app.text_input(key="find_in_book").set_value("no-such-dish-zzz").run()
        self.assertFalse(app.exception)
        self.assertIn(cp.FIND_IN_BOOK_EMPTY, [item.value for item in app.info])
        blob = _cards(app)
        self.assertNotIn("Simple Pancakes", blob)
        self.assertNotIn("Cain's Toast Hash", blob)


if __name__ == "__main__":
    unittest.main()
