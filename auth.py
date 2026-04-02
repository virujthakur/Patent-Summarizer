import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from ui_theme import get_active_theme, inject_theme_css, render_theme_toggle

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    supabase_url: str
    supabase_key: str
    redirect_uri: str
    email_enabled: bool


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@st.cache_resource(show_spinner=False)
def _get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_ANON_KEY in .env")
    return create_client(supabase_url, supabase_key)


def load_auth_config() -> AuthConfig:
    return AuthConfig(
        enabled=_env_bool("AUTH_ENABLED", "true"),
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=os.getenv("SUPABASE_ANON_KEY", "").strip(),
        redirect_uri=os.getenv("AUTH_REDIRECT_URI", "http://localhost:8501").strip(),
        email_enabled=_env_bool("AUTH_EMAIL_ENABLED", "true"),
    )


def _build_user_profile(user: Any) -> dict[str, Any]:
    metadata = getattr(user, "user_metadata", None) or {}
    return {
        "user_id": getattr(user, "id", ""),
        "provider": getattr(user, "app_metadata", {}).get("provider", "email"),
        "provider_subject": getattr(user, "id", ""),
        "email": getattr(user, "email", None),
        "display_name": metadata.get("full_name") or metadata.get("name") or getattr(user, "email", None),
        "avatar_url": metadata.get("avatar_url"),
    }


def get_current_user() -> dict[str, Any]:
    return st.session_state.get("auth_user", {})


def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_user"))


def sign_in(email: str, password: str) -> tuple[bool, str]:
    try:
        client = _get_supabase_client()
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        if response and getattr(response, "user", None):
            st.session_state["auth_user"] = _build_user_profile(response.user)
            st.session_state["auth_session"] = {
                "access_token": getattr(response.session, "access_token", None),
                "refresh_token": getattr(response.session, "refresh_token", None),
            }
            return True, "Signed in successfully."
        return False, "Sign in failed. Check your email and password."
    except Exception as exc:
        return False, f"Sign in error: {exc}"


def sign_up(email: str, password: str) -> tuple[bool, str]:
    try:
        client = _get_supabase_client()
        redirect_uri = load_auth_config().redirect_uri
        payload = {
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": redirect_uri,
            },
        }
        response = client.auth.sign_up(payload)
        if response and getattr(response, "user", None):
            return True, "Account created. You can now sign in."
        return False, "Sign up failed."
    except Exception as exc:
        return False, f"Sign up error: {exc}"


def sign_out(redirect_to: str | None = None) -> None:
    try:
        client = _get_supabase_client()
        client.auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("auth_user", None)
    st.session_state.pop("auth_session", None)
    if redirect_to:
        st.switch_page(redirect_to)
        st.stop()
    st.rerun()


def render_auth_gate() -> None:
    config = load_auth_config()
    inject_theme_css(get_active_theme())

    if not config.enabled:
        st.info("Authentication is disabled. Set AUTH_ENABLED=true in .env to enable Supabase email sign-in.")
        return

    st.markdown(
        """
<style>
.block-container {
    padding-top: 0.35rem !important;
}

.auth-title {
  text-align: center;
  margin-bottom: 0.25rem;
}

.brand-title {
    text-align: center;
    margin: 0 0 0.1rem 0;
}

.brand-subtitle {
    text-align: center;
    color: #5f697a;
    margin: 0 0 0.7rem 0;
}

.auth-subtitle {
  text-align: center;
  color: #5f697a;
  margin-bottom: 0.5rem;
}

.auth-note {
  text-align: center;
  color: #5f697a;
  font-size: 0.95rem;
  margin-top: 0.6rem;
}

.auth-header-row {
    margin-bottom: 0.0rem;
}

.brand-wrap {
  text-align: center;
}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='auth-header-row'>", unsafe_allow_html=True)
    _, header_center, header_right = st.columns([1.2, 6.0, 1.2])
    with header_right:
        st.markdown("<div style='display:flex; justify-content:flex-end;'>", unsafe_allow_html=True)
        render_theme_toggle(current_user=None, key="theme_toggle_auth")
        st.markdown("</div>", unsafe_allow_html=True)

    with header_center:
        st.markdown("<div class='brand-wrap'>", unsafe_allow_html=True)
        st.markdown("<h1 class='brand-title'>Patent Studio</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p class='brand-subtitle'>Upload Excel links, download patents locally, auto-summarize, and open each patent for deep Q&A.</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<h3 class='auth-title'>Sign in to continue</h3>", unsafe_allow_html=True)
        st.markdown("<p class='auth-subtitle'>Use your Supabase email and password.</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    left_col, center_col, right_col = st.columns([2.2, 3.6, 2.2])
    with center_col:
        auth_card = st.container(border=True)

    if not config.email_enabled:
        with center_col:
            st.warning("Email sign-in is disabled in your auth settings.")
        return

    with center_col:
        with auth_card:
            tab_sign_in, tab_sign_up = st.tabs(["Sign In", "Sign Up"])

            with tab_sign_in:
                with st.form("supabase_sign_in_form"):
                    email = st.text_input("Email address", key="signin_email")
                    password = st.text_input("Password", type="password", key="signin_password")
                    _, sign_in_btn_col, _ = st.columns([1.2, 1.0, 1.2])
                    with sign_in_btn_col:
                        submitted = st.form_submit_button("Sign In", use_container_width=True)
                    if submitted:
                        if not email or not password:
                            st.error("Please enter both email and password.")
                        else:
                            success, message = sign_in(email.strip().lower(), password)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

            with tab_sign_up:
                st.markdown("<h4 style='margin: 0 0 0.75rem 0;'>Create your account</h4>", unsafe_allow_html=True)
                with st.form("supabase_sign_up_form"):
                    email = st.text_input("Email address", key="signup_email")
                    password = st.text_input("Password", type="password", key="signup_password")
                    confirm = st.text_input("Confirm password", type="password", key="signup_password_confirm")
                    _, sign_up_btn_col, _ = st.columns([1.2, 1.0, 1.2])
                    with sign_up_btn_col:
                        submitted = st.form_submit_button("Create Account", use_container_width=True)
                    if submitted:
                        if not email or not password or not confirm:
                            st.error("Please fill in all fields.")
                        elif password != confirm:
                            st.error("Passwords do not match.")
                        elif len(password) < 6:
                            st.error("Password must be at least 6 characters.")
                        else:
                            success, message = sign_up(email.strip().lower(), password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)

        st.markdown("<p class='auth-note'>Secure sign-in powered by Supabase Auth.</p>", unsafe_allow_html=True)


def show_login_page() -> None:
    render_auth_gate()


def show_sign_out_button() -> None:
    if is_authenticated():
        user = get_current_user()
        email = user.get("email") or user.get("display_name") or user.get("user_id") or "User"
        st.sidebar.write(f"Signed in as: **{email}**")
        if st.sidebar.button("Sign Out"):
            sign_out()
