# Cain's Pantry

**Resume one-liner:** Cain's Pantry — Log what's in your kitchen; get recipes ranked Ready, Almost (missing 1–2), or Need more.

Log what is already in the kitchen. `recipes.json` sorts into **Ready**, **Almost** (missing one or two required ingredients), and **Need More**. Optional ingredients never change the rank. Names fold through aliases (`mayo` / `mayonnaise`, `garbanzo beans` / `chickpeas`, `scallion` / `green onion`).

Branding is original: a text wordmark, cream paper, charcoal type, and one blood-orange accent. No game art, sprites, fonts, or trademarked lines.

## Run locally

No API keys. With no Supabase secrets, the pantry stays in the browser session.

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
| `docs/matching-spec.md` | Rank rules. |
| `cains_copy.py` | Title Case labels. Not named `copy.py`, so it does not shadow the Python stdlib. |
| `theme.css` | Cream, charcoal, and blood-orange. |
| `ui.py` | Header, pantry chips, recipe cards. |
| `store.py` | Session pantry. Syncs to Supabase after login. |
| `src/db.py` | PostgREST signup, login, and pantry CRUD. |
| `supabase_profiles.sql` | `profiles` (email + bcrypt hash). Demo anon policy. |
| `supabase_pantry.sql` | `pantry_items` (user_id, name, created_at). Demo anon policy. |
| `tests/` | Ranking rules and the secrets gate. |

```bash
python3 -m unittest discover -s tests -t .
```

## Sign-in and deploy

Login is optional. With no secrets file, **Account** says so and the pantry stays in the browser session.

To save a pantry per person, create a Supabase project and run these in the SQL editor, in order:

1. `supabase_profiles.sql`
2. `supabase_pantry.sql`

The policies are demo-grade: the anon key can read and write every row, including password hashes. Do not use them for real personal accounts.

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in placeholders with your own project values. Never commit that file, and never put the secret key in it.

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
```

Open **Account**, choose **Create Account**, then add ingredients. They are stored on `pantry_items` for that profile and loaded again on the next **Sign In**.

### Streamlit Cloud

1. Push this repo and open [share.streamlit.io](https://share.streamlit.io).
2. Create an app from this repo, branch `main`, main file `app.py`.
3. In the app settings, open **Secrets** and paste the same `SUPABASE_URL` and `SUPABASE_ANON_KEY` block. Use your project's URL and anon key.
4. Deploy. The cream, charcoal, and blood-orange UI is unchanged. With secrets missing, Cloud still runs the local-style session pantry.

## Roadmap

**Done in this app.** Session pantry, alias matching, themed Ready / Almost / Need More sections, and an optional Supabase profile plus `pantry_items` table.

**Shopping list.** Turn Almost recipes into one deduped list of missing ingredients.

**Recipe API.** Optional cookbook source behind the same recipe shape. `recipes.json` stays the offline default. Keys would live in secrets, never in the repo.
