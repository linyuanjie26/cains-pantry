# Cain's Pantry — matching logic (Kai)

Drop-in files for when scaffold `bc-f274b513` lands:
- `matching.py` — pure Python matcher
- `recipes.json` — 10 seed recipes + starter pantry

## Status rules
| Status | Rule |
|--------|------|
| **Ready** | All *required* ingredients present (optionals ignored) |
| **Almost** | Missing 1–2 required (`ALMOST_MAX_MISSING = 2`) |
| **Need More** | Missing 3+ required |

Optional ingredients never change status; UI can still show "nice to have".

Badge strings match Possy brief: `Ready` · `Almost` · `Need More`.

## Normalization
1. Lowercase, trim, collapse whitespace
2. Light English plural trim
3. Alias map (`chickpeas` ↔ garbanzo beans, `green onion` ↔ scallion, etc.)

Pantry chips keep user-typed casing in the UI; matching uses `canonical()`.

## Sort order
Ready → Almost → Need More; within a bucket, fewer missing first, then more on-hand, then title.

## API sketch for Streamlit
```python
from matching import match_all, group_by_status, READY, ALMOST, NEED_MORE
import json

data = json.load(open("recipes.json"))
recipes = [...]  # build Recipe dataclasses
results = match_all(recipes, pantry_chips)
groups = group_by_status(results)
```

## README one-liner (recommended)
> **Cain’s Pantry** — Log what’s in your kitchen; get recipes ranked Ready, Almost (missing 1–2), or Need more.

## Smoke
```bash
python matching.py
```
With `starter_pantry`, Cain's Toast Hash is Ready. Other recipes land in Almost or Need More, so a demo can show all three buckets.
