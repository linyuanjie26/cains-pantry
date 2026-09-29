"""Cain's Pantry — pantry → recipe matching (Ready / Almost / Need More).

Pure logic, no Streamlit. Drop into the scaffold when the repo lands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Exact badge strings (match Possy UI brief).
READY = "Ready"
ALMOST = "Almost"
NEED_MORE = "Need More"

# Missing at most this many required ingredients → Almost (optional ingredients ignored).
ALMOST_MAX_MISSING = 2

# Canonical name → aliases users might type.
ALIASES: dict[str, set[str]] = {
    "chickpeas": {"garbanzo", "garbanzo beans", "garbanzos"},
    "green onion": {"scallion", "scallions", "spring onion", "green onions"},
    "canned tomatoes": {"tomato sauce", "crushed tomatoes", "diced tomatoes", "tomato"},
    "broth": {"stock", "bouillon", "chicken broth", "veggie broth", "vegetable broth"},
    "parmesan": {"parmigiano", "parm"},
    "mayonnaise": {"mayo"},
    "black pepper": {"pepper", "ground pepper"},
    "pita": {"pita bread"},
    "bread": {"toast", "loaf"},
    "spinach": {"greens", "kale", "chard"},
    "lime": {"lime juice"},
    "lemon": {"lemon juice"},
    "hot sauce": {"chili sauce", "sriracha"},
    "chili flakes": {"red pepper flakes", "crushed red pepper"},
    "olive oil": {"oil"},
    "noodles": {"ramen", "instant noodles"},
}


def normalize(name: str) -> str:
    s = name.strip().lower()
    s = " ".join(s.split())
    # light plural trim for simple English pantry nouns
    if len(s) > 3 and s.endswith("oes"):
        s = s[:-2]  # tomatoes → tomato (then alias may map)
    elif len(s) > 3 and s.endswith("ies"):
        s = s[:-3] + "y"
    elif len(s) > 3 and s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def _alias_map() -> dict[str, str]:
    """Map every alias + canonical → canonical normalize() key."""
    m: dict[str, str] = {}
    for canon, aliases in ALIASES.items():
        c = normalize(canon)
        m[c] = c
        for a in aliases:
            m[normalize(a)] = c
    return m


_ALIAS_TO_CANON = _alias_map()


def canonical(name: str) -> str:
    n = normalize(name)
    return _ALIAS_TO_CANON.get(n, n)


@dataclass(frozen=True)
class Recipe:
    id: str
    title: str
    ingredients: tuple[str, ...]  # required
    optional: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    steps: str = ""


@dataclass
class MatchResult:
    recipe: Recipe
    status: str
    have: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    optional_have: list[str] = field(default_factory=list)
    optional_missing: list[str] = field(default_factory=list)

    @property
    def on_hand_count(self) -> tuple[int, int]:
        total = len(self.have) + len(self.missing)
        return len(self.have), total


def pantry_set(items: Iterable[str]) -> set[str]:
    return {canonical(x) for x in items if x and str(x).strip()}


def match_recipe(recipe: Recipe, pantry: set[str]) -> MatchResult:
    have, missing = [], []
    for ing in recipe.ingredients:
        c = canonical(ing)
        (have if c in pantry else missing).append(ing)

    opt_have, opt_missing = [], []
    for ing in recipe.optional:
        c = canonical(ing)
        (opt_have if c in pantry else opt_missing).append(ing)

    if not missing:
        status = READY
    elif len(missing) <= ALMOST_MAX_MISSING:
        status = ALMOST
    else:
        status = NEED_MORE

    return MatchResult(
        recipe=recipe,
        status=status,
        have=have,
        missing=missing,
        optional_have=opt_have,
        optional_missing=opt_missing,
    )


_STATUS_ORDER = {READY: 0, ALMOST: 1, NEED_MORE: 2}


def match_all(recipes: Iterable[Recipe], pantry_items: Iterable[str]) -> list[MatchResult]:
    pantry = pantry_set(pantry_items)
    results = [match_recipe(r, pantry) for r in recipes]
    # Ready → Almost → Need More; within bucket, fewer missing first, then title.
    results.sort(
        key=lambda m: (
            _STATUS_ORDER[m.status],
            len(m.missing),
            -len(m.have),
            m.recipe.title.lower(),
        )
    )
    return results


def group_by_status(results: Iterable[MatchResult]) -> dict[str, list[MatchResult]]:
    groups = {READY: [], ALMOST: [], NEED_MORE: []}
    for m in results:
        groups[m.status].append(m)
    return groups


if __name__ == "__main__":
    # smoke test with demo pantry from sample-recipes.md
    import json
    from pathlib import Path

    data = json.loads(Path(__file__).with_name("recipes.json").read_text())
    recipes = [
        Recipe(
            id=r["id"],
            title=r["title"],
            ingredients=tuple(r["ingredients"]),
            optional=tuple(r.get("optional", [])),
            tags=tuple(r.get("tags", [])),
            steps=r.get("steps", ""),
        )
        for r in data["recipes"]
    ]
    pantry = data["starter_pantry"]
    results = match_all(recipes, pantry)
    for m in results:
        have_n, total = m.on_hand_count
        miss = f" missing={m.missing}" if m.missing else ""
        print(f"{m.status:9} {have_n}/{total}  {m.recipe.title}{miss}")
