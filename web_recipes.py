"""Import recipes from a page URL or a free TheMealDB search.

Results use the same Recipe shape as recipes.json. Matching rules stay in
matching.py. Nothing here needs an API key. Imported recipes live in the
browser session unless the caller stores them.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
import sys
import threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from matching import ALIASES, Recipe, canonical, normalize

MEALDB_SEARCH = "https://www.themealdb.com/api/json/v1/1/search.php"
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "web_catalog.json"
_UA = "Mozilla/5.0 (compatible; CainsPantry/1.0)"
_MAX_CHARS = 1_500_000
_STEP_LIMIT = 2500

_DROP = {
    "cup", "cups", "tablespoon", "tablespoons", "tbsp", "tbs",
    "teaspoon", "teaspoons", "tsp", "ounce", "ounces", "oz",
    "pound", "pounds", "lb", "lbs", "gram", "grams", "g", "kg",
    "ml", "l", "liter", "liters", "litre", "litres",
    "clove", "cloves", "pinch", "pinches", "dash", "dashes",
    "can", "cans", "tin", "tins", "package", "packages", "pkg",
    "packet", "packets", "bunch", "bunches", "slice", "slices",
    "piece", "pieces", "head", "heads", "sprig", "sprigs",
    "stalk", "stalks", "leaf", "leaves", "large", "small", "medium",
    "whole", "extra", "virgin", "of", "a", "an", "or", "to", "taste",
    "fresh", "dried", "ground", "chopped", "minced", "sliced", "diced",
    "crushed", "grated", "peeled", "seeded", "finely", "roughly",
    "about", "plus", "optional", "sprinkling", "for", "serving",
    "garnish", "into", "inch", "inches", "serve",
}

_SALT = {"kosher salt", "sea salt", "table salt"}


class WebRecipeError(Exception):
    """A short message safe to show in the UI."""


def recipe_record(recipe: Recipe) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "ingredients": list(recipe.ingredients),
        "optional": list(recipe.optional),
        "tags": list(recipe.tags),
        "steps": recipe.steps,
    }


def recipes_from_records(rows: list[dict[str, Any]] | None) -> list[Recipe]:
    recipes: list[Recipe] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        ingredients = [str(name) for name in row.get("ingredients") or [] if str(name).strip()]
        if not title or not ingredients:
            continue
        recipes.append(
            Recipe(
                id=str(row.get("id") or make_id("web", title, title)),
                title=title,
                ingredients=tuple(ingredients),
                optional=tuple(str(name) for name in row.get("optional") or []),
                tags=tuple(str(tag) for tag in row.get("tags") or ()),
                steps=str(row.get("steps") or ""),
            )
        )
    return recipes


def import_url(url: str, *, fetch: Callable[[str], str] | None = None) -> Recipe:
    """Fetch a recipe page and return one Recipe. Raises WebRecipeError."""
    target = _check_url(url)
    try:
        html = fetch(target) if fetch else _http_text(target)
    except WebRecipeError:
        raise
    except requests.RequestException:
        raise WebRecipeError("Could not reach that page. Check the link and try again.") from None
    if not html or not html.strip():
        raise WebRecipeError("This site did not share a recipe we could read.")
    return parse_html(html, target)


def parse_html(html: str, url: str) -> Recipe:
    scraped = _from_scraper(html, url)
    if scraped is not None:
        return scraped
    return _from_json_ld(html, url)


def search_meals(query: str, *, fetch_json: Callable[[str], Any] | None = None) -> list[Recipe]:
    """Free TheMealDB search. No API key. Empty list when nothing matches."""
    name = " ".join((query or "").split())
    if not name:
        raise WebRecipeError("Type a dish name to search.")
    try:
        payload = fetch_json(name) if fetch_json else _mealdb_json(name)
    except WebRecipeError:
        raise
    except requests.RequestException:
        raise WebRecipeError("Could not reach TheMealDB. Try again.") from None
    meals = payload.get("meals") if isinstance(payload, dict) else None
    if not meals:
        return []
    found: list[Recipe] = []
    for meal in meals:
        if not isinstance(meal, dict):
            continue
        try:
            found.append(meal_to_recipe(meal))
        except WebRecipeError:
            continue
        if len(found) >= 8:
            break
    return found


def meal_to_recipe(meal: dict[str, Any]) -> Recipe:
    title = str(meal.get("strMeal") or "").strip()
    raw: list[str] = []
    for index in range(1, 21):
        ingredient = str(meal.get(f"strIngredient{index}") or "").strip()
        measure = str(meal.get(f"strMeasure{index}") or "").strip()
        if not ingredient:
            continue
        raw.append(f"{measure} {ingredient}".strip())
    source = str(meal.get("idMeal") or title)
    recipe = build_recipe(title, raw, str(meal.get("strInstructions") or ""), source, "mealdb")
    category = str(meal.get("strCategory") or "").strip().casefold().replace(" ", "-")
    if not category:
        return recipe
    return Recipe(
        id=recipe.id,
        title=recipe.title,
        ingredients=recipe.ingredients,
        optional=recipe.optional,
        tags=(*recipe.tags, category),
        steps=recipe.steps,
    )


def names_from_line(raw: str) -> list[str]:
    """Turn one scraped ingredient line into a short pantry-style name."""
    text = _plain(raw).replace("–", " ").replace("—", " ").replace("-", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("chilli", "chili").replace("chile", "chili")
    if re.search(r"\bsalt and pepper\b", text, flags=re.IGNORECASE):
        return [_align("salt"), _align("pepper")]
    words: list[str] = []
    for token in text.split():
        cleaned = token.strip(".,;:").lower()
        if not cleaned or _is_amount(cleaned) or cleaned in _DROP:
            continue
        words.append(cleaned)
    if not words:
        return []
    phrase = " ".join(words)
    if phrase in _SALT:
        phrase = "salt"
    aligned = _align(phrase)
    return [aligned] if aligned else []


def build_recipe(
    title: str,
    raw_ingredients: list[str],
    steps: str,
    source: str,
    prefix: str,
) -> Recipe:
    required: list[str] = []
    optional: list[str] = []
    seen: set[str] = set()
    for raw in raw_ingredients:
        is_optional = "optional" in raw.lower()
        for name in names_from_line(raw):
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            (optional if is_optional else required).append(name)
    clean_title = " ".join((title or "").split())
    if not clean_title or not required:
        raise WebRecipeError("This site did not share a recipe we could read.")
    return Recipe(
        id=make_id(prefix, clean_title, source),
        title=clean_title,
        ingredients=tuple(required),
        optional=tuple(optional),
        tags=("from-the-web",),
        steps=_clean_steps(steps),
    )


def make_id(prefix: str, title: str, source: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:36] or "recipe"
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:6]
    return f"{prefix}-{slug}-{digest}"


def _align(phrase: str) -> str:
    """Prefer an existing alias name so the matcher can see it."""
    folded = " ".join(phrase.lower().split())
    if not folded:
        return ""
    canon = canonical(folded)
    for key in ALIASES:
        if normalize(key) == canon:
            return key
    best_key = ""
    best_len = 0
    padded = f" {folded} "
    for key, aliases in ALIASES.items():
        for alias in {key, *aliases}:
            needle = " ".join(alias.lower().split())
            if needle and f" {needle} " in padded and len(needle) > best_len:
                best_key = key
                best_len = len(needle)
    return best_key or folded


def _is_amount(token: str) -> bool:
    if any(char in token for char in "¼½¾⅓⅔⅛⅜⅝⅞"):
        return True
    if re.fullmatch(r"\d+([./]\d+)?", token):
        return True
    return re.fullmatch(r"\d+[a-z]+", token) is not None


def _plain(text: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(stripped.replace("\xa0", " ").split())


def _clean_steps(steps: str) -> str:
    lines = [" ".join(line.split()) for line in (steps or "").splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:_STEP_LIMIT]


def _check_url(url: str) -> str:
    target = (url or "").strip()
    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebRecipeError("Paste a full recipe link, starting with http.")
    return target


def _http_text(url: str) -> str:
    response = requests.get(url, timeout=12, headers={"User-Agent": _UA})
    if response.status_code >= 400:
        raise WebRecipeError("That page returned an error.")
    return response.text[:_MAX_CHARS]


def _mealdb_json(query: str) -> Any:
    response = requests.get(
        MEALDB_SEARCH,
        params={"s": query},
        timeout=12,
        headers={"User-Agent": _UA},
    )
    if response.status_code >= 400:
        raise WebRecipeError("Could not reach TheMealDB. Try again.")
    return response.json()


def _from_scraper(html: str, url: str) -> Recipe | None:
    try:
        from recipe_scrapers import scrape_html
    except ImportError:
        return None
    try:
        scraper = scrape_html(html, url, supported_only=False)
        title = scraper.title()
        ingredients = list(scraper.ingredients() or [])
        steps = scraper.instructions() or ""
    except Exception:
        return None
    if not title or not ingredients:
        return None
    try:
        return build_recipe(title, ingredients, steps, url, "web")
    except WebRecipeError:
        return None


def _from_json_ld(html: str, url: str) -> Recipe:
    for node in _json_ld_nodes(html):
        if not _is_recipe(node):
            continue
        title = str(node.get("name") or "").strip()
        raw = node.get("recipeIngredient") or node.get("ingredients") or []
        if isinstance(raw, str):
            raw = [raw]
        ingredients = [str(item) for item in raw]
        try:
            return build_recipe(title, ingredients, _steps_text(node.get("recipeInstructions")), url, "web")
        except WebRecipeError:
            continue
    raise WebRecipeError("This site did not share a recipe we could read.")


def _json_ld_nodes(html: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for blob in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(blob.strip())
        except json.JSONDecodeError:
            continue
        nodes.extend(_walk(payload))
    return nodes


def _walk(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_walk(item))
        return found
    if not isinstance(node, dict):
        return found
    found.append(node)
    for key in ("@graph", "graph"):
        if key in node:
            found.extend(_walk(node[key]))
    return found


def _is_recipe(node: dict[str, Any]) -> bool:
    kind = node.get("@type") or node.get("type")
    if isinstance(kind, list):
        return any(str(item).lower().endswith("recipe") for item in kind)
    return str(kind or "").lower().endswith("recipe")


def _steps_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_steps_text(item) for item in value) if part)
    if isinstance(value, dict):
        if value.get("text"):
            return str(value["text"]).strip()
        if "itemListElement" in value:
            return _steps_text(value["itemListElement"])
    return ""


# Bundled TheMealDB catalog. First paint reads the file. A background
# refresh can add meals that were not in the file; it does not touch
# session imports.

_catalog_lock = threading.Lock()
_catalog_refresh_started = False
_catalog_overlay: list[dict[str, Any]] = []


def load_web_catalog(path: Path | None = None) -> list[Recipe]:
    """Read the committed catalog. Missing or broken files yield an empty list."""
    source = path or CATALOG_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("recipes") if isinstance(payload, dict) else None
    return _as_catalog(recipes_from_records(rows if isinstance(rows, list) else None))


def catalog_recipes() -> list[Recipe]:
    """Bundled catalog plus any meals a soft refresh has added."""
    with _catalog_lock:
        extra = list(_catalog_overlay)
    return merge_recipes(load_web_catalog(), _as_catalog(recipes_from_records(extra)))


def _as_catalog(recipes: list[Recipe]) -> list[Recipe]:
    """Mark bundled meals so the UI can tell them from a recipe you just imported."""
    tagged: list[Recipe] = []
    for recipe in recipes:
        tags = tuple(recipe.tags)
        if "from-the-web" not in tags:
            tags = (*tags, "from-the-web")
        if "web-catalog" not in tags:
            tags = (*tags, "web-catalog")
        if tags == recipe.tags:
            tagged.append(recipe)
            continue
        tagged.append(
            Recipe(
                id=recipe.id,
                title=recipe.title,
                ingredients=recipe.ingredients,
                optional=recipe.optional,
                tags=tags,
                steps=recipe.steps,
            )
        )
    return tagged


def merge_recipes(*groups: list[Recipe]) -> list[Recipe]:
    """Keep the first recipe for each id. Later groups only add new ids."""
    seen: set[str] = set()
    chosen: list[Recipe] = []
    for group in groups:
        for recipe in group:
            if recipe.id in seen:
                continue
            seen.add(recipe.id)
            chosen.append(recipe)
    return chosen


def fetch_mealdb_catalog(*, fetch_json: Callable[[str], Any] | None = None) -> list[dict[str, Any]]:
    """Download TheMealDB meals for letters a–z. No API key."""
    meals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for letter in string.ascii_lowercase:
        try:
            payload = fetch_json(letter) if fetch_json else _mealdb_letter(letter)
        except (WebRecipeError, requests.RequestException):
            continue
        batch = payload.get("meals") if isinstance(payload, dict) else None
        if not batch:
            continue
        for meal in batch:
            if not isinstance(meal, dict):
                continue
            meal_id = str(meal.get("idMeal") or "")
            if not meal_id or meal_id in seen:
                continue
            seen.add(meal_id)
            meals.append(meal)
    records = []
    titles: set[str] = set()
    for meal in meals:
        title_key = str(meal.get("strMeal") or "").strip().casefold()
        if title_key and title_key in titles:
            continue
        try:
            recipe = meal_to_recipe(meal)
        except WebRecipeError:
            continue
        if title_key:
            titles.add(title_key)
        records.append(recipe_record(recipe))
    records.sort(key=lambda row: row["title"].casefold())
    return records


def write_bundled_catalog(path: Path | None = None) -> int:
    """Refresh data/web_catalog.json from TheMealDB. Used to rebuild the seed file."""
    records = fetch_mealdb_catalog()
    target = path or CATALOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "TheMealDB",
        "source_url": "https://www.themealdb.com/api/json/v1/1/search.php?f=",
        "note": "Free public recipes. No API key. Bundled so the app works offline.",
        "recipes": records,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(records)


def start_catalog_refresh() -> None:
    """Fetch letters a–z once per process. Failures leave the bundled file in place."""
    global _catalog_refresh_started
    if "unittest" in sys.modules:
        return
    with _catalog_lock:
        if _catalog_refresh_started:
            return
        _catalog_refresh_started = True
    threading.Thread(target=_refresh_catalog_worker, name="cains-catalog", daemon=True).start()


def _refresh_catalog_worker() -> None:
    try:
        records = fetch_mealdb_catalog()
    except Exception:
        return
    if len(records) < 50:
        return
    with _catalog_lock:
        _catalog_overlay[:] = records


def _mealdb_letter(letter: str) -> Any:
    response = requests.get(
        MEALDB_SEARCH,
        params={"f": letter},
        timeout=12,
        headers={"User-Agent": _UA},
    )
    if response.status_code >= 400:
        raise WebRecipeError("Could not reach TheMealDB. Try again.")
    return response.json()
