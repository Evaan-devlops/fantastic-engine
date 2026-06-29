"""Generic authentication page classification helpers."""
from __future__ import annotations

from enum import Enum
from typing import Any


class AuthBranch(str, Enum):
    USERNAME_PASSWORD = "USERNAME_PASSWORD"
    PASSWORD_ONLY = "PASSWORD_ONLY"
    SSO_REDIRECT = "SSO_REDIRECT"
    MANUAL_AUTH_REQUIRED = "MANUAL_AUTH_REQUIRED"
    ALREADY_AUTHENTICATED = "ALREADY_AUTHENTICATED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    UNKNOWN_PAGE = "UNKNOWN_PAGE"


async def classify_auth_branch(page: Any) -> AuthBranch:
    """Classify common authentication pages without application-specific selectors.

    Precedence (highest first):
    1. Authentication error — clear error text
    2. Already authenticated — success indicators
    3. SSO redirect — URL path signals (high confidence, checked before body text)
    4. Username + password — both fields visible
    5. Password only — only password field visible
    6. Manual auth required — MFA / explicit auth-required prompts (not just SSO text)
    7. Unknown page — fallback
    """
    url = page.url.lower()
    text = ""
    try:
        text = (await page.locator("body").inner_text(timeout=1000)).lower()
    except Exception:
        pass

    # 1. Authentication error
    if any(marker in text for marker in (
        "invalid password", "authentication failed", "sign in failed",
        "incorrect password", "wrong password",
    )):
        return AuthBranch.AUTHENTICATION_ERROR

    # 2. Already authenticated
    if any(marker in text for marker in ("dashboard", "signed in", "log out", "logout", "sign out")):
        return AuthBranch.ALREADY_AUTHENTICATED

    # 3. SSO redirect — URL takes precedence over body text so SSO pages with
    #    "single sign-on" in the body are not misclassified as MANUAL_AUTH_REQUIRED.
    if any(marker in url for marker in ("sso", "saml", "oauth", "openid", "/auth/redirect", "/identity")):
        return AuthBranch.SSO_REDIRECT

    # 4 & 5. Field-based classification (username includes email inputs)
    _USERNAME_SELECTOR = (
        "input[type='text'], input[type='email'], "
        "input[name*='user' i], input[id*='user' i], "
        "input[name*='email' i], input[id*='email' i], "
        "input[name*='login' i], input[id*='login' i]"
    )
    username = await _count_visible(page, _USERNAME_SELECTOR)
    password = await _count_visible(page, "input[type='password']")
    if username and password:
        return AuthBranch.USERNAME_PASSWORD
    if password:
        return AuthBranch.PASSWORD_ONLY

    # 6. Manual auth required — MFA / explicit challenges only (not generic SSO mention)
    if any(marker in text for marker in (
        "complete authentication", "mfa", "multi-factor",
        "two-factor", "2fa", "verify your identity", "enter your code",
    )):
        return AuthBranch.MANUAL_AUTH_REQUIRED

    return AuthBranch.UNKNOWN_PAGE


async def _count_visible(page: Any, selector: str) -> int:
    try:
        loc = page.locator(selector)
        count = await loc.count()
        visible = 0
        for index in range(count):
            if await loc.nth(index).is_visible():
                visible += 1
        return visible
    except Exception:
        return 0
