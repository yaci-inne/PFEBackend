from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from main.views import CustomTokenObtainPairView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('api/accessToken/', CustomTokenObtainPairView.as_view(), name='tokenAccess'),
    path('api/refreshToken/', TokenRefreshView.as_view(), name='tokenRefresh'),
]

# En local uniquement (Cloudinary gère les media en production)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)