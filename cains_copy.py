"""Cain's Pantry — UI copy (Title Case labels). Original branding only.

Named cains_copy so it does not shadow the Python stdlib `copy` module.
"""

APP_NAME = "Cain's Pantry"
APP_SUBTITLE = "Cook What You've Got"

# Inputs / actions
PANTRY_HEADER = "Pantry"
PANTRY_PLACEHOLDER = "Type An Ingredient (Eggs, Rice…)"
ADD_BUTTON = "Add"
CLEAR_ALL = "Clear All"
CLEAR_CONFIRM = "Remove All Pantry Items?"
CONFIRM_CLEAR = "Remove All"
CANCEL = "Cancel"
EMPTY_PANTRY = "What's In The Kitchen?"
EMPTY_PANTRY_HINT = "Add a few staples to see what you can cook."
TRY_DEMO = "Try Eggs, Milk, And Flour"

# Results
FIND_IN_BOOK = "Find In Book"
FIND_IN_BOOK_PLACEHOLDER = "Title, Tag, Or Ingredient"
FIND_IN_BOOK_EMPTY = "Nothing In The Book Matches That."
RESULTS_HEADER = "Recipes"
CATALOG_NOTE = "Cain's recipes, plus a catalog from the web."
FROM_THE_WEB = "From The Web"
CATALOG_MORE = "{count} more in this group. Use Find In Book to narrow."
SECTION_READY = "Ready"
SECTION_ALMOST = "Almost"
SECTION_NEED_MORE = "Need More"
NEED_PREFIX = "Need:"
NICE_TO_HAVE_PREFIX = "Nice To Have:"
ON_HAND_FMT = "{have}/{total} On Hand"
COOK_THIS = "Cook This"
NO_RECIPES = "No Recipes Yet"
NO_MATCHES_HINT = "Add Pantry Items To Rank Recipes."

# Badges (must match matching.py)
BADGE_READY = "Ready"
BADGE_ALMOST = "Almost"
BADGE_NEED_MORE = "Need More"

# Account. Sign-in stays quiet until Supabase secrets exist.
ACCOUNT_HEADER = "Account"
LOCAL_MODE = "Login is optional. This browser session holds the pantry and shopping list until Supabase secrets are set."
EMAIL_LABEL = "Email"
PASSWORD_LABEL = "Password"
SIGN_IN = "Sign In"
SIGN_UP = "Create Account"
SIGN_OUT = "Sign Out"
SIGNED_IN = "Signed In As {email}"

# Add From Web. Free sources only; no API key.
WEB_HEADER = "Add From Web"
WEB_HINT = "The book already includes a web catalog. Paste a link or search to add more. No API key."
WEB_URL_LABEL = "Recipe URL"
WEB_URL_PLACEHOLDER = "https://…"
WEB_IMPORT = "Import"
WEB_SEARCH_LABEL = "Search Dishes"
WEB_SEARCH_PLACEHOLDER = "Arrabiata"
WEB_SEARCH = "Search"
WEB_ADDED = "Added {title}."
WEB_UPDATED = "Updated {title}."

# Shopping list. Session only.
SHOP_HEADER = "Shopping List"
SHOP_PLACEHOLDER = "Type An Ingredient (Lime, Flour…)"
SHOP_EMPTY = "Nothing To Buy Yet"
SHOP_EMPTY_HINT = "Add missing ingredients from a recipe, or type them here."
SHOP_CLEAR = "Clear List"
SHOP_CLEAR_CONFIRM = "Remove All Shopping Items?"
SHOP_GOT_IT = "Got It"
SHOP_ADD_MISSING = "Add Missing To List"
SHOP_NEED_NAME = "Enter an ingredient name."
SHOP_ADDED = "Added {items}."
SHOP_ADDED_SOME = "Added {added}. Already on the list: {already}."
SHOP_ALREADY = "Already on the list: {items}."
SHOP_REMOVED = "Removed {item}."
SHOP_CLEARED = "Shopping list cleared."
SHOP_BOUGHT = "Got It. {item} is in the pantry."
