"""
URL configuration for store project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from main.views import CustomTokenObtainPairView
from django.conf import settings
from django.conf.urls.static import static
from .health_views import health_check, test_sparql  # 👈 AJOUTEZ CETTE LIGNE

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('api/accessToken/', CustomTokenObtainPairView.as_view(), name='tokenAccess'),
    path('api/refreshToken/', TokenRefreshView.as_view(), name='tokenRefresh'),
    path('api/health/', health_check, name='health_check'),
    path('api/sparql/test/', test_sparql, name='test_sparql'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)