"""
URL configuration for crypto platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/wallets/', include('wallets.urls')),
    # Re-enabling apps now that Pillow is installed
    path('api/orders/', include('orders.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/kyc/', include('kyc.urls')),
    path('api/tutorials/', include('tutorials.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('api/marketing/', include('marketing.urls')),
    path('api/support/', include('support.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/', include('rates.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

