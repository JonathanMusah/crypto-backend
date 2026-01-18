from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet
from .views_device import UserDeviceViewSet

router = DefaultRouter()
# Register devices first to avoid conflicts with AuthViewSet actions
router.register(r'devices', UserDeviceViewSet, basename='device')
router.register(r'', AuthViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
]

