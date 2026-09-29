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
RESULTS_HEADER = "Recipes"
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
LOCAL_MODE = "Login is optional. This browser session holds the pantry until Supabase secrets are set."
EMAIL_LABEL = "Email"
PASSWORD_LABEL = "Password"
SIGN_IN = "Sign In"
SIGN_UP = "Create Account"
SIGN_OUT = "Sign Out"
SIGNED_IN = "Signed In As {email}"
