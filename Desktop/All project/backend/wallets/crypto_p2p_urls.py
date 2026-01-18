"""
Crypto P2P Trading URL Configuration
Routes for crypto listings and transactions
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from wallets.crypto_p2p_views import CryptoListingViewSet, CryptoTransactionViewSet

app_name = 'crypto_p2p'

router = DefaultRouter()
router.register(r'listings', CryptoListingViewSet, basename='crypto-listing')
router.register(r'transactions', CryptoTransactionViewSet, basename='crypto-transaction')

urlpatterns = [
    path('', include(router.urls)),
]
