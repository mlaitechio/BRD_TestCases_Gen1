from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from apps.projects.views import ChatAPIView
from apps.authentication.views import (
    CyberArkLoginView,
    CyberArkCallbackView,
    LogoutView,
    VerifyAuthView,
    UserView,
    GetUserRoleView,
    TestAdminAccessView,
    TestUserAccessView,
    TestLoginView,
)

main_patterns = [
    path('admin/', admin.site.urls),

    # ── CyberArk Authentication ────────────────────────────────────────────
    path('auth/login',    CyberArkLoginView.as_view(),    name='cyberark-login'),
    path('auth/callback', CyberArkCallbackView.as_view(), name='cyberark-callback'),
    path('auth/logout',   LogoutView.as_view(),           name='cyberark-logout'),

    # ── Auth API ──────────────────────────────────────────────────────
    path('api/verify_auth', VerifyAuthView.as_view(), name='verify-auth'),
    path('api/user',        UserView.as_view(),        name='current-user'),
    path('api/user/role',   GetUserRoleView.as_view(), name='user-role'),
    path('api/test/login',  TestLoginView.as_view(),   name='test-login'),
    path('api/test/admin-access', TestAdminAccessView.as_view(), name='test-admin'),
    path('api/test/user-access',  TestUserAccessView.as_view(),  name='test-user'),

    # ── BRD Project APIs ───────────────────────────────────────────────
    path('api/projects/', include('apps.projects.urls')),

    # ── RAG Knowledge Base APIs ────────────────────────────────────────
    path('api/rag/', include('apps.rag.urls')),

    # ── AI Chat & Search APIs ──────────────────────────────────────────
    path('api/chat/', include('apps.ai_chat.urls')),

    # Explicit API endpoint BEFORE the catch-all
    path('api/', ChatAPIView.as_view(), name='chat_api'),

    # The catch-all route will automatically handle the React UI
    # We exclude 'assets/' and 'api/' so that if an API or asset fails, it returns a 404 instead of serving index.html
    re_path(r'^(?!api/|admin/|assets/|auth/).*$', TemplateView.as_view(template_name='index.html'), name='react-app'),
]

urlpatterns = [
    path(settings.URL_PREFIX, include(main_patterns)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
