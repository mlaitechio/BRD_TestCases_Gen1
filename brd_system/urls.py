from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/projects/', include('apps.projects.urls')),
    # Catch-all route to serve the React frontend index.html for any non-API/Admin URLs
re_path(r'^(?!api/|admin/|chatgpt/chat/|chatgpt/assets/).*$', TemplateView.as_view(template_name='index.html'), name='react-app'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)