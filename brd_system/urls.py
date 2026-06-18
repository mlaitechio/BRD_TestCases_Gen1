from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from apps.projects.views import ChatAPIView

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/projects/', include('apps.projects.urls')),
    
    # Explicit API endpoint BEFORE the catch-all
    path('api/', ChatAPIView.as_view(), name='chat_api'),

    # The catch-all route will automatically handle the React UI
    # We exclude 'assets/' and 'api/' so that if an API or asset fails, it returns a 404 instead of serving index.html
    re_path(r'^(?!api/|admin/|assets/).*$', TemplateView.as_view(template_name='index.html'), name='react-app'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
