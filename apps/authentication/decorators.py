"""
apps/authentication/decorators.py

`require_auth` — a view decorator that enforces JWT cookie authentication.

Usage on a function-based view:
    from apps.authentication.decorators import require_auth

    @require_auth
    def my_view(request):
        user = request.auth_payload   # always populated here
        ...

Usage on a DRF class-based view:
    from rest_framework.views import APIView
    from apps.authentication.decorators import CyberArkIsAuthenticated

    class MyView(APIView):
        permission_classes = [CyberArkIsAuthenticated]
        ...
"""

import logging
from functools import wraps

from django.http import JsonResponse
from rest_framework.permissions import BasePermission

from .utils import Security

logger = logging.getLogger(__name__)


def require_auth(f):
    """
    Decorator that enforces JWT-cookie authentication on any Django view.

    Relies on JWTAuthMiddleware having already set ``request.auth_payload``.
    Falls back to re-verifying the cookie itself if the middleware is not
    installed (so the decorator is safe to use standalone).
    """

    @wraps(f)
    def decorated(request, *args, **kwargs):
        # Prefer the value already set by JWTAuthMiddleware
        payload = getattr(request, "auth_payload", _SENTINEL)

        if payload is _SENTINEL:
            # Middleware not installed — verify inline
            token = request.COOKIES.get("auth_token")
            if not token:
                logger.warning("require_auth: no auth_token cookie")
                return JsonResponse({"error": "Not authenticated"}, status=401)
            payload = Security.verify_jwt_token(token)

        if not payload:
            logger.warning("require_auth: invalid or expired token")
            return JsonResponse({"error": "Invalid or expired token"}, status=401)

        # Bind payload to request so views can access it
        request.auth_payload = payload
        return f(request, *args, **kwargs)

    return decorated


# Sentinel to detect "attribute not set" vs "attribute set to None"
_SENTINEL = object()


# ──────────────────────────────────────────────────────────────────────────────
# DRF permission class (for APIView / ViewSet)
# ──────────────────────────────────────────────────────────────────────────────

class CyberArkIsAuthenticated(BasePermission):
    """
    DRF permission class that validates the JWT cookie.

    Add to any APIView / ViewSet:
        permission_classes = [CyberArkIsAuthenticated]
    """

    message = "Authentication required. Please log in via CyberArk."

    def has_permission(self, request, view):
        payload = getattr(request, "auth_payload", None)
        if payload is None:
            # JWTAuthMiddleware may not be installed — try inline
            token = request.COOKIES.get("auth_token")
            if not token:
                return False
            payload = Security.verify_jwt_token(token)
            if payload:
                request.auth_payload = payload

        return payload is not None


# ──────────────────────────────────────────────────────────────────────────────
# Role-Based Access Control Decorators
# ──────────────────────────────────────────────────────────────────────────────

def require_admin(view_func):
    """Decorator to require admin role"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)

        try:
            profile = request.user.profile
            if profile.role == 'admin' and profile.is_active:
                return view_func(request, *args, **kwargs)
            else:
                return JsonResponse({'error': 'Admin access required'}, status=403)
        except AttributeError:
            return JsonResponse({'error': 'User profile not found'}, status=400)

    return wrapper


def require_user(view_func):
    """Decorator to require authenticated user (any role)"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)

        try:
            profile = request.user.profile
            if profile.is_active:
                return view_func(request, *args, **kwargs)
            else:
                return JsonResponse({'error': 'User account is inactive'}, status=403)
        except AttributeError:
            return JsonResponse({'error': 'User profile not found'}, status=400)

    return wrapper


def check_role(required_role='user'):
    """
    Flexible decorator to check specific role.
    Usage: @check_role('admin') or @check_role('user')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Not authenticated'}, status=401)

            try:
                profile = request.user.profile
                if profile.role == required_role and profile.is_active:
                    return view_func(request, *args, **kwargs)
                else:
                    return JsonResponse({
                        'error': f'{required_role.capitalize()} access required',
                        'required_role': required_role,
                        'user_role': profile.role
                    }, status=403)
            except AttributeError:
                return JsonResponse({'error': 'User profile not found'}, status=400)

        return wrapper
    return decorator
