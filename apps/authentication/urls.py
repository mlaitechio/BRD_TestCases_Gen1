"""
apps/authentication/urls.py

URL patterns for the CyberArk authentication app.

Include in brd_system/urls.py:
    path('auth/', include('apps.authentication.urls'))
    path('api/', include('apps.authentication.urls'))
"""

from django.urls import path

from .views import (
    CyberArkCallbackView,
    CyberArkLoginView,
    LogoutView,
    UserView,
    VerifyAuthView,
)

# Auth flow routes — mounted at /auth/ via brd_system/urls.py
auth_urlpatterns = [
    path("login", CyberArkLoginView.as_view(), name="cyberark-login"),
    path("callback", CyberArkCallbackView.as_view(), name="cyberark-callback"),
    path("logout", LogoutView.as_view(), name="cyberark-logout"),
]

# API routes — mounted at /api/ via brd_system/urls.py
api_urlpatterns = [
    path("verify_auth", VerifyAuthView.as_view(), name="verify-auth"),
    path("user", UserView.as_view(), name="current-user"),
]

# Combined — used when including this module directly
urlpatterns = auth_urlpatterns + api_urlpatterns
