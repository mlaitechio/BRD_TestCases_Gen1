"""
apps/authentication/middleware.py

Two middleware classes:

1. SecurityHeadersMiddleware
   Adds comprehensive HTTP security headers to every response
   (ports the Flask `after_request` hook from the reference app).

2. JWTAuthMiddleware
   Reads the `auth_token` cookie and attaches the decoded payload
   to `request.auth_payload` on every request — lightweight, no DB hit.
   Views that need protection should use the `require_auth` decorator
   (see decorators.py) which checks this attribute.
"""

import logging

from django.conf import settings

from .utils import Security

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Attach security response headers to every HTTP response.

    Activated by adding to settings.MIDDLEWARE:
        'apps.authentication.middleware.SecurityHeadersMiddleware'
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.is_prod = getattr(settings, "APP_ENV", "dev").lower() == "prod"

    def __call__(self, request):
        response = self.get_response(request)
        self._add_headers(response)
        return response

    def _add_headers(self, response):
        # ── Clickjacking protection ──────────────────────────────────────────
        response["X-Frame-Options"] = "SAMEORIGIN"

        # ── HTTPS enforcement (prod only) ────────────────────────────────────
        if self.is_prod:
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            response["Expect-CT"] = "max-age=86400, enforce"

        # ── Content Security Policy ──────────────────────────────────────────
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response["Content-Security-Policy"] = csp
        response["X-Content-Security-Policy"] = csp  # legacy IE

        # ── MIME-type sniffing prevention ────────────────────────────────────
        response["X-Content-Type-Options"] = "nosniff"

        # ── XSS protection (older browsers) ─────────────────────────────────
        response["X-XSS-Protection"] = "1; mode=block"

        # ── Referrer policy ──────────────────────────────────────────────────
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ── Permissions policy ───────────────────────────────────────────────
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # ── Cache control ────────────────────────────────────────────────────
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        # ── Cross-origin isolation headers ───────────────────────────────────
        response["Cross-Origin-Embedder-Policy"] = "require-corp"
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response["Cross-Origin-Resource-Policy"] = "same-origin"

        # ── Miscellaneous legacy headers ─────────────────────────────────────
        response["X-Download-Options"] = "noopen"
        response["X-DNS-Prefetch-Control"] = "off"
        response["X-Permitted-Cross-Domain-Policies"] = "none"


class JWTAuthMiddleware:
    """
    Lightweight middleware that reads the `auth_token` cookie and attaches
    the decoded JWT payload to ``request.auth_payload``.

    - If the cookie is missing or invalid, ``request.auth_payload`` is ``None``.
    - Views that require authentication should use the ``@require_auth``
      decorator, which inspects this attribute and returns 401 when absent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request.COOKIES.get("auth_token")
        if token:
            payload = Security.verify_jwt_token(token)
            request.auth_payload = payload  # may be None if invalid/expired
        else:
            request.auth_payload = None

        return self.get_response(request)
