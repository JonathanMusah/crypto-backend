from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CryptoRateViewSet, CryptoTradingViewSet

router = DefaultRouter()
router.register(r'rates', CryptoRateViewSet, basename='crypto-rate')
router.register(r'crypto', CryptoTradingViewSet, basename='crypto-trading')

urlpatterns = [
    path('', include(router.urls)),
]
