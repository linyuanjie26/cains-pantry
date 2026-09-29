"""Cain's Pantry — Streamlit UI.

Original branding only. Labels live in cains_copy.py; colors live in theme.css.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Callable

import streamlit as st

import cains_copy as cp
from matching import ALMOST, NEED_MORE, READY, MatchResult
import store

_CSS_PATH = Path(__file__).with_name("theme.css")
_BADGE_CLASS = {
    READY: "cp-badge-ready",
    ALMOST: "cp-badge-almost",
    NEED_MORE: "cp-badge-need",
}


def inject_theme() -> None:
    css = _CSS_PATH.read_text(encoding="utf-8")
    # st.html keeps <style> in the document more reliably than markdown.
    block = f"<style>{css}</style>"
    if hasattr(st, "html"):
        st.html(block)
    else:
        st.markdown(block, unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(
        f'<p class="cp-wordmark">{html.escape(cp.APP_NAME)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="cp-subtitle">{html.escape(cp.APP_SUBTITLE)}</p>',
        unsafe_allow_html=True,
    )


def render_badge(status: str) -> str:
    css = _BADGE_CLASS.get(status, "cp-badge-need")
    return f'<span class="cp-badge {css}">{html.escape(status)}</span>'


def render_account() -> None:
    """Email and password when Supabase is configured. Otherwise a short note."""
    with st.expander(cp.ACCOUNT_HEADER, expanded=False):
        warning = store.cloud_warning()
        if warning:
            st.warning(warning)
            return
        if store.read_supabase_config() is None:
            st.caption(cp.LOCAL_MODE)
            return

        email = store.signed_in_email()
        if email:
            st.write(cp.SIGNED_IN.format(email=email))
            if st.button(cp.SIGN_OUT, key="sign_out"):
                store.sign_out()
                st.rerun()
            return

        with st.form("account_form", clear_on_submit=False):
            entered_email = st.text_input(cp.EMAIL_LABEL, key="account_email")
            password = st.text_input(cp.PASSWORD_LABEL, type="password", key="account_password")
            sign_in, sign_up = st.columns(2)
            do_sign_in = sign_in.form_submit_button(cp.SIGN_IN, use_container_width=True)
            do_sign_up = sign_up.form_submit_button(cp.SIGN_UP, use_container_width=True)

        if do_sign_in or do_sign_up:
            action = store.sign_in if do_sign_in else store.sign_up
            message = action(entered_email, password)
            if message and message.startswith("Account created"):
                st.success(message)
            elif message:
                st.error(message)
            else:
                st.rerun()


def render_pantry_panel() -> list[str]:
    """Add field, chips with remove, clear, and the pancake demo shortcut."""
    items = store.pantry()
    st.subheader(cp.PANTRY_HEADER)

    with st.form("add_pantry_form", clear_on_submit=True):
        # Keep Add wide enough that the label stays horizontal in the
        # narrow left column (a 4:1 split was squeezing letters vertical).
        field, action = st.columns([3, 1.2], gap="small")
        with field:
            new_item = st.text_input(
                cp.PANTRY_HEADER,
                placeholder=cp.PANTRY_PLACEHOLDER,
                label_visibility="collapsed",
                key="pantry_input",
            )
        with action:
            submitted = st.form_submit_button(
                cp.ADD_BUTTON,
                use_container_width=True,
                type="primary",
            )
        if submitted:
            store.add_entry(new_item)

    notice = st.session_state.pop("notice", None)
    if notice:
        level, text = notice
        if level == "ok":
            st.success(text)
        elif level == "warn":
            st.warning(text)
        else:
            st.info(text)

    if not items:
        st.info(f"**{cp.EMPTY_PANTRY}**  \n{cp.EMPTY_PANTRY_HINT}")
    else:
        for index, item in enumerate(list(items)):
            label, remove = st.columns([5, 1])
            label.markdown(
                f'<div class="cp-chip">{html.escape(item)}</div>',
                unsafe_allow_html=True,
            )
            slug = "".join(ch if ch.isalnum() else "-" for ch in item)[:32]
            if remove.button("×", key=f"rm-{index}-{slug}", help=f"Remove {item}"):
                store.remove_item(item)
                st.rerun()

        if st.button(cp.CLEAR_ALL, key="clear_pantry"):
            st.session_state.confirm_clear = True
            st.rerun()
        if st.session_state.get("confirm_clear"):
            st.warning(cp.CLEAR_CONFIRM)
            yes, no = st.columns(2)
            if yes.button(cp.CONFIRM_CLEAR, key="confirm_clear_yes"):
                store.clear()
                st.session_state.confirm_clear = False
                st.rerun()
            if no.button(cp.CANCEL, key="confirm_clear_no"):
                st.session_state.confirm_clear = False
                st.rerun()

    if st.button(cp.TRY_DEMO, key="try_demo", use_container_width=True):
        store.add_entry("Eggs, Milk, Flour")
        st.rerun()

    return store.pantry()


def render_recipe_card(match: MatchResult, *, nest_steps: bool = False) -> None:
    recipe = match.recipe
    have_n, total = match.on_hand_count
    badge = render_badge(match.status)

    missing_html = ""
    if match.missing:
        chips = " ".join(
            f'<span class="cp-missing-chip">{_pretty(name)}</span>' for name in match.missing
        )
        missing_html = f'<div class="cp-meta">{html.escape(cp.NEED_PREFIX)} {chips}</div>'

    optional_html = ""
    if match.optional_missing:
        chips = " ".join(
            f'<span class="cp-missing-chip">{_pretty(name)}</span>'
            for name in match.optional_missing
        )
        optional_html = (
            '<div class="cp-meta" style="margin-top:0.25rem">'
            f"{html.escape(cp.NICE_TO_HAVE_PREFIX)} {chips}</div>"
        )

    st.markdown(
        f"""
        <div class="cp-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.75rem">
            <p class="cp-card-title">{html.escape(recipe.title)}</p>
            {badge}
          </div>
          <div class="cp-meta">{html.escape(cp.ON_HAND_FMT.format(have=have_n, total=total))}</div>
          {missing_html}
          {optional_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if recipe.steps:
        # Streamlit expanders cannot nest. Need More lives in one expander,
        # so its steps use a plain disclosure instead of a second expander.
        if nest_steps:
            _cook_details(recipe)
        else:
            with st.expander(cp.COOK_THIS, expanded=(match.status == READY)):
                st.write(recipe.steps)
                if recipe.tags:
                    st.caption(" · ".join(tag.replace("-", " ").title() for tag in recipe.tags))


def render_results(groups: dict[str, list]) -> None:
    st.subheader(cp.RESULTS_HEADER)
    order = [READY, ALMOST, NEED_MORE]
    labels = {
        READY: cp.SECTION_READY,
        ALMOST: cp.SECTION_ALMOST,
        NEED_MORE: cp.SECTION_NEED_MORE,
    }
    any_cards = False
    # Collapse Need More once Ready or Almost is on screen. If it is the
    # only group, leave it open so an empty pantry still shows the book.
    fold_need_more = bool(groups.get(READY) or groups.get(ALMOST))
    for status in order:
        items = groups.get(status) or []
        if not items:
            continue
        any_cards = True
        header = f"{labels[status]} ({len(items)})"
        if status == NEED_MORE and fold_need_more:
            with st.expander(header, expanded=False):
                for match in items:
                    render_recipe_card(match, nest_steps=True)
            continue
        st.markdown(
            f'<div class="cp-section-label">{html.escape(header)}</div>',
            unsafe_allow_html=True,
        )
        for match in items:
            render_recipe_card(match)

    if not any_cards:
        st.info(f"**{cp.NO_RECIPES}**  \n{cp.NO_MATCHES_HINT}")


def page_shell(render_body: Callable[[], None]) -> None:
    st.set_page_config(
        page_title=cp.APP_NAME,
        page_icon="🍳",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_theme()
    render_header()
    render_body()


def _pretty(name: str) -> str:
    return html.escape(name.strip().title())


def _cook_details(recipe) -> None:
    tags = ""
    if recipe.tags:
        label = " · ".join(tag.replace("-", " ").title() for tag in recipe.tags)
        tags = f'<p class="cp-meta">{html.escape(label)}</p>'
    st.markdown(
        (
            '<details class="cp-cook">'
            f"<summary>{html.escape(cp.COOK_THIS)}</summary>"
            f"<p>{html.escape(recipe.steps)}</p>"
            f"{tags}</details>"
        ),
        unsafe_allow_html=True,
    )
