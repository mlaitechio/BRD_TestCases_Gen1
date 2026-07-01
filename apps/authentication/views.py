"""
apps/authentication/views.py

CyberArk OAuth2 / OIDC authentication views.

Routes (defined in urls.py):
    GET  /auth/login         → CyberArkLoginView     — redirect to CyberArk authorize
    GET  /auth/callback      → CyberArkCallbackView  — exchange code, set JWT cookie
    GET  /auth/logout        → LogoutView            — clear session + cookie
    GET  /api/verify_auth    → VerifyAuthView        — verify JWT, return user info
    GET  /api/user           → UserView              — @require_auth, return payload
"""

import logging
import secrets
from urllib.parse import urlencode

import pytz
import requests
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .decorators import require_auth
from .utils import Security, log_db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _set_auth_cookie(response, jwt_token: str):
    """Attach the signed JWT as an HttpOnly cookie to *response*."""
    response.set_cookie(
        "auth_token",
        jwt_token,
        httponly=settings.AUTH_COOKIE_HTTPONLY,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.AUTH_COOKIE_MAX_AGE,
    )


def _clear_auth_cookie(response):
    """Delete the auth_token cookie."""
    response.delete_cookie(
        "auth_token",
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def _get_proxies():
    """Return proxy dict for requests if configured, else None."""
    return getattr(settings, "AUTH_PROXIES", None)


# ──────────────────────────────────────────────────────────────────────────────
# Auth Views
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class CyberArkLoginView(View):
    """
    GET /auth/login

    Generates an anti-CSRF ``state`` token, stores it in the session,
    and redirects the user to the CyberArk authorization endpoint.
    """

    def get(self, request):
        try:
            state = secrets.token_urlsafe(32)
            request.session["oauth_state"] = state

            params = {
                "response_type": "code",
                "client_id": settings.AUTH_CLIENT_ID,
                "redirect_uri": settings.AUTH_REDIRECT_URI,
                "scope": "openid",
                "state": state,
            }
            auth_url = f"{settings.AUTH_URL}?{urlencode(params)}"
            logger.info("Initiating CyberArk OAuth login")
            return redirect(auth_url)

        except Exception as exc:
            logger.error("Error in CyberArkLoginView: %s", exc)
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class CyberArkCallbackView(View):
    """
    GET /auth/callback

    Handles the CyberArk authorization code callback:
    1. Validates the ``state`` parameter (CSRF protection).
    2. Exchanges the authorization code for an access token.
    3. Fetches user info from the CyberArk userinfo endpoint.
    4. Creates a signed JWT and sets it as an HttpOnly cookie.
    5. Redirects to the frontend root (/).
    """

    def get(self, request):
        try:
            code = request.GET.get("code")
            state = request.GET.get("state")

            # ── CSRF state validation ────────────────────────────────────────
            if not state or state != request.session.get("oauth_state"):
                logger.warning("OAuth state mismatch — possible CSRF attack")
                return JsonResponse({"error": "Invalid state parameter"}, status=400)

            # Clear used state to prevent replay attacks
            request.session.pop("oauth_state", None)

            if not code:
                logger.warning("No authorization code received in callback")
                return JsonResponse({"error": "No authorization code"}, status=400)

            # ── Exchange code for token ──────────────────────────────────────
            token_payload = {
                "redirect_uri": settings.AUTH_REDIRECT_URI,
                "code": str(code).strip(),
                "grant_type": "authorization_code",
                "client_id": str(settings.AUTH_CLIENT_ID).strip(),
                "client_secret": str(settings.AUTH_CLIENT_SECRET).strip(),
                "scope": "openid",
            }
            token_response = requests.post(
                settings.AUTH_TOKEN_URL,
                data=token_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                proxies=_get_proxies(),
                timeout=settings.AUTH_REQUEST_TIMEOUT,
            )

            if not token_response.ok:
                logger.error(
                    "Token exchange failed: %s — %s",
                    token_response.status_code,
                    token_response.text,
                )
                return JsonResponse(
                    {
                        "error": "Token exchange failed",
                        "status": token_response.status_code,
                        "details": token_response.text,
                    },
                    status=token_response.status_code,
                )

            access_token = token_response.json().get("access_token")
            if not access_token:
                logger.error("No access_token in CyberArk token response")
                return JsonResponse({"error": "Failed to obtain access token"}, status=500)

            # ── Fetch user info ──────────────────────────────────────────────
            user_response = requests.get(
                settings.AUTH_USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                proxies=_get_proxies(),
                timeout=settings.AUTH_REQUEST_TIMEOUT,
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            logger.debug("CyberArk userinfo: %s", user_data)

            # Validate that we got a usable identity
            if not user_data.get("Mail") and not user_data.get("sub"):
                logger.error("Invalid user data from CyberArk userinfo")
                return JsonResponse({"error": "Invalid user data"}, status=500)

            # ── Issue JWT and create session ─────────────────────────────────
            jwt_token = Security.create_jwt_token(user_data)
            request.session["user"] = user_data

            response = redirect("/")
            _set_auth_cookie(response, jwt_token)

            logger.info("Successful CyberArk login for: %s", user_data.get("Mail"))
            return response

        except requests.Timeout:
            logger.error("Timeout during CyberArk OAuth callback")
            return JsonResponse({"error": "Request timeout"}, status=408)
        except requests.RequestException as exc:
            logger.error("Request error during CyberArk callback: %s", exc)
            return JsonResponse({"error": "Error communicating with CyberArk"}, status=502)
        except Exception as exc:
            logger.error("Unexpected error during CyberArk callback: %s", exc)
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(View):
    """
    GET /auth/logout

    Clears the server-side session and the auth_token cookie,
    then redirects to the login page.
    """

    def get(self, request):
        try:
            user_email = request.session.get("user", {}).get("Mail", "Unknown")
            request.session.flush()  # destroy session data + regenerate key

            response = redirect("/auth/login")
            _clear_auth_cookie(response)

            logger.info("User logged out: %s", user_email)
            return response

        except Exception as exc:
            logger.error("Error during logout: %s", exc)
            return JsonResponse({"error": "Error during logout"}, status=500)


# ──────────────────────────────────────────────────────────────────────────────
# API Views
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class VerifyAuthView(View):
    """
    GET /api/verify_auth

    Verifies the JWT cookie and returns current authentication status.
    On success, also logs the visit to ``app_logs.log``.

    Response (unauthenticated):
        {"authenticated": false}

    Response (authenticated):
        {
            "authenticated": true,
            "email": "...",
            "accountname": "...",
            "company": "..."
        }
    """

    def get(self, request):
        token = request.COOKIES.get("auth_token")
        if not token:
            return JsonResponse({"authenticated": False})

        payload = Security.verify_jwt_token(token)
        if not payload:
            return JsonResponse({"authenticated": False})

        # Log the visit (mirrors the Flask reference)
        indian_tz = pytz.timezone("Asia/Kolkata")
        indian_now = datetime.now(indian_tz).strftime("%Y-%m-%d %H:%M:%S.%f")
        email = payload.get("email", "")
        accountname = payload.get("accountname", "")
        log_db("VERIFY_AUTH", "auth_visit", f"email={email}, name={accountname}, ts={indian_now}")

        return JsonResponse(
            {
                "authenticated": True,
                "email": email,
                "accountname": accountname,
                "company": payload.get("company", ""),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class UserView(View):
    """
    GET /api/user

    Returns the authenticated user's info from the JWT payload.
    Requires a valid auth_token cookie (protected by @require_auth).
    """

    @method_decorator(require_auth)
    def get(self, request):
        try:
            payload = request.auth_payload
            return JsonResponse(
                {
                    "email": payload.get("email"),
                    "accountname": payload.get("accountname", ""),
                    "company": payload.get("company", ""),
                },
                status=200,
            )
        except Exception as exc:
            logger.error("Error in UserView: %s", exc)
            return JsonResponse({"error": "Internal server error"}, status=500)
