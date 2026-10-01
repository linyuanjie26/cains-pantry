# Cain's Pantry

**Resume one-liner:** Cain's Pantry — Log what's in your kitchen; get recipes ranked Ready, Almost (missing 1–2), or Need more.

Log what is already in the kitchen. `recipes.json` sorts into **Ready**, **Almost** (missing one or two required ingredients), and **Need More**. Optional ingredients never change the rank. Names fold through aliases (`mayo` / `mayonnaise`, `garbanzo beans` / `chickpeas`, `scallion` / `green onion`).

Branding is original: a text wordmark, cream paper, charcoal type, and one blood-orange accent. No game art, sprites, fonts, or trademarked lines.

## Run locally

No API keys. With no Supabase secrets, the pantry and shopping list stay in the browser session.

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## Demo

The pantry starts empty. Chips keep the casing you type. Two checks:

1. **Try Eggs, Milk, And Flour**, or add `eggs, milk, flour`. **Simple Pancakes** should sit in **Ready** at the top. Open **Cook This** for the method.
2. For the full starter bag, paste `starter_pantry` from `recipes.json` (`onion, garlic, eggs, pasta, rice, canned tomatoes, chickpeas, black beans, olive oil, salt, butter, bread, potato, cheese, cumin, black pepper`). **Cain's Toast Hash** is **Ready**. Other recipes land in **Almost** or a collapsed **Need More**.
3. A fresh session already ranks a large **From The Web** catalog with Cain's recipes. You do not need to search first. **Find In Book** narrows that list. **Add From Web** still adds a link or a TheMealDB search on top of the catalog.

```bash
python3 matching.py
```

That prints the same ranking from the starter pantry. The first line should be Ready for Cain's Toast Hash.

## Layout

| Path | Role |
| --- | --- |
| `app.py` | Streamlit entry. Two columns: pantry, then ranked recipes. |
| `matching.py` | Alias map and Ready / Almost / Need More. `python3 matching.py` prints the starter ranking. |
| `recipes.json` | Seed recipes plus `starter_pantry`, including Simple Pancakes. |
| `data/web_catalog.json` | Bundled TheMealDB catalog. No API key. Loaded with the seed book. |
| `web_recipes.py` | Catalog load, recipe URL import, and TheMealDB search. |
| `docs/matching-spec.md` | Rank rules. |
| `cains_copy.py` | Title Case labels. Not named `copy.py`, so it does not shadow the Python stdlib. |
| `theme.css` | Cream, charcoal, and blood-orange. |
| `ui.py` | Header, pantry chips, recipe cards, Add From Web. |
| `store.py` | Session pantry and shopping list. Both sync to Supabase after login; session-only when logged out or secrets are missing. |
| `src/db.py` | PostgREST signup, login, pantry CRUD, and shopping-list CRUD. |
| `supabase_profiles.sql` | `profiles` (email + bcrypt hash). Demo anon policy. |
| `supabase_pantry.sql` | `pantry_items` (user_id, name, created_at). Demo anon policy. |
| `supabase_shopping.sql` | `shopping_list_items` (same shape as pantry). Demo anon policy. |
| `tests/` | Ranking rules and the secrets gate. |

```bash
python3 -m unittest discover -s tests -t .
```

## Sign-in and deploy

Login is optional. With no secrets file, **Account** says so and the pantry and shopping list stay in the browser session.

To save a pantry and shopping list per person, create a Supabase project and run these in the SQL editor, in order:

1. `supabase_profiles.sql`
2. `supabase_pantry.sql`
3. `supabase_shopping.sql`

The policies are demo-grade: the anon key can read and write every row, including password hashes. Do not use them for real personal accounts.

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in placeholders with your own project values. Never commit that file, and never put the secret key in it.

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
```

Open **Account**, choose **Create Account**, then add ingredients. Pantry rows land on `pantry_items` and shopping rows on `shopping_list_items` for that profile; both load again on the next **Sign In**. Logged out (or with no secrets), both lists stay session-only.

### Streamlit Cloud

1. Push this repo and open [share.streamlit.io](https://share.streamlit.io).
2. Create an app from this repo, branch `main`, main file `app.py`.
3. In the app settings, open **Secrets** and paste the same `SUPABASE_URL` and `SUPABASE_ANON_KEY` block. Use your project's URL and anon key.
4. Deploy. The cream, charcoal, and blood-orange UI is unchanged. With secrets missing, Cloud still runs the local-style session pantry and shopping list.

## Roadmap

**Done in this app.** Session pantry, alias matching, themed Ready / Almost / Need More sections, an optional Supabase profile plus `pantry_items` and `shopping_list_items`, a bundled TheMealDB catalog, free URL import and search, and a shopping list.

## Shopping list

**Shopping List** sits under the pantry. When you are signed in with Supabase secrets, it syncs to `shopping_list_items`. Logged out or with no secrets, it stays in the browser session.

- Type ingredients the same way as the pantry (`lime, flour`). Commas split. Repeats are ignored by case.
- On an **Almost** or **Need More** card, **Add Missing To List** adds that recipe's required gaps. Optional ingredients stay off the list.
- **Got It** removes the row and adds it to the pantry. **×** removes it only. **Clear List** empties the list after a confirm.


## Recipe catalog

A new session ranks Cain's recipes together with `data/web_catalog.json`. That file is a snapshot of [TheMealDB](https://www.themealdb.com/) meals whose names start with a–z (`search.php?f=a` through `f=z`). No API key. The app reads the file first, so the list is there offline.

Each catalog card is labeled **From The Web**. The group heading shows the full count. The page draws Cain's recipes plus a short preview of the catalog so the browser stays usable. **Find In Book** reaches the rest.

While the app is running it may refresh TheMealDB in the background and add meals that were not in the file. That refresh does not remove Cain's recipes or anything you imported in this session.

Rebuild the snapshot with:

```bash
python -c "from web_recipes import write_bundled_catalog; print(write_bundled_catalog())"
```

## Add from the web

**Add From Web** sits above the ranked list and adds to the catalog. It does not replace it.

- **Recipe URL** then **Import**. The page is read with `recipe-scrapers`, and schema.org Recipe data is the fallback. A bad link, an unsupported page, or a network failure shows a short message.
- **Search Dishes** then **Search**. That calls TheMealDB (`themealdb.com`) with no API key. Pick a result to add it.

Ingredient lines lose amounts and a few prep words, then fold through the same aliases as the pantry (`olive oil`, `chili flakes`, `parmesan`, `canned tomatoes`). `recipes.json` is unchanged. Imported dishes are kept in the browser session for this version.
