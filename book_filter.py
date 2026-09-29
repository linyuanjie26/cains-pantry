"""Find In Book — local text filter over recipes already in memory.

Does not rank, alias, or fetch anything. Ready / Almost / Need More stay as
match_all left them.
"""

from __future__ import annotations

from matching import MatchResult


def filter_matches(matches: list[MatchResult], query: str) -> list[MatchResult]:
    """Keep matches whose title, tags, or ingredient names contain query.

    Match is a case-insensitive substring. Empty or whitespace-only query
    returns the same list object. Order and match badges are left as given.
    """
    needle = query.strip().lower()
    if not needle:
        return matches
    return [match for match in matches if _hit(match, needle)]


def _hit(match: MatchResult, needle: str) -> bool:
    recipe = match.recipe
    fields = (recipe.title, *recipe.tags, *recipe.ingredients, *recipe.optional)
    return any(needle in field.lower() for field in fields)
