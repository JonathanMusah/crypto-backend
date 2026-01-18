from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WalletViewSet, CryptoTransactionViewSet, AdminCryptoAddressViewSet, DepositViewSet, WithdrawalViewSet
from .crypto_p2p_urls import router as crypto_p2p_router

router = DefaultRouter()
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'admin-addresses', AdminCryptoAddressViewSet, basename='admin-address')
router.register(r'deposits', DepositViewSet, basename='deposit')
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')

# Use regular paths instead of router for custom actions
urlpatterns = [
    path('balance/', WalletViewSet.as_view({'get': 'balance'}), name='wallet-balance'),
    path('deposit/', WalletViewSet.as_view({'post': 'deposit'}), name='wallet-deposit'),
    path('withdraw/', WalletViewSet.as_view({'post': 'withdraw'}), name='wallet-withdraw'),
    path('buy-crypto/', WalletViewSet.as_view({'post': 'buy_crypto'}), name='wallet-buy-crypto'),
    path('sell-crypto/', WalletViewSet.as_view({'post': 'sell_crypto'}), name='wallet-sell-crypto'),
    path('transactions/', WalletViewSet.as_view({'get': 'transactions'}), name='wallet-transactions'),
    path('escrow-status/', WalletViewSet.as_view({'get': 'escrow_status'}), name='wallet-escrow-status'),
    path('crypto-transactions/', CryptoTransactionViewSet.as_view({'get': 'list', 'post': 'create'}), name='crypto-transaction-list'),
    path('crypto-transactions/<int:pk>/', CryptoTransactionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='crypto-transaction-detail'),
    path('crypto-transactions/<int:pk>/approve/', CryptoTransactionViewSet.as_view({'post': 'approve'}), name='crypto-transaction-approve'),
    path('crypto-transactions/<int:pk>/decline/', CryptoTransactionViewSet.as_view({'post': 'decline'}), name='crypto-transaction-decline'),
    # Note: admin-addresses/get_address/ is automatically created by the router from the @action decorator
    path('deposits/payment-details/', DepositViewSet.as_view({'get': 'payment_details'}), name='deposit-payment-details'),
    path('deposits/momo/', DepositViewSet.as_view({'post': 'momo_deposit'}), name='deposit-momo'),
    path('deposits/crypto/', DepositViewSet.as_view({'post': 'crypto_deposit'}), name='deposit-crypto'),
    path('deposits/<int:pk>/approve/', DepositViewSet.as_view({'post': 'approve'}), name='deposit-approve'),
    path('deposits/<int:pk>/reject/', DepositViewSet.as_view({'post': 'reject'}), name='deposit-reject'),
    path('withdrawals/momo/', WithdrawalViewSet.as_view({'post': 'momo_withdrawal'}), name='withdrawal-momo'),
    path('withdrawals/crypto/', WithdrawalViewSet.as_view({'post': 'crypto_withdrawal'}), name='withdrawal-crypto'),
    path('withdrawals/<int:pk>/approve/', WithdrawalViewSet.as_view({'post': 'approve'}), name='withdrawal-approve'),
    path('withdrawals/<int:pk>/reject/', WithdrawalViewSet.as_view({'post': 'reject'}), name='withdrawal-reject'),
    path('withdrawals/<int:pk>/complete/', WithdrawalViewSet.as_view({'post': 'complete'}), name='withdrawal-complete'),
    # Crypto P2P routes
    path('crypto/p2p/', include(crypto_p2p_router.urls)),
    path('', include(router.urls)),
]