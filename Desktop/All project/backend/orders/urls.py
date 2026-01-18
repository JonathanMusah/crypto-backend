from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .views import (
    GiftCardViewSet, GiftCardOrderViewSet, OrderViewSet, TradeViewSet,
    GiftCardListingViewSet, GiftCardTransactionViewSet, GiftCardDisputeViewSet,
    GiftCardTransactionRatingViewSet
)
from .p2p_views import (
    P2PServiceListingViewSet, P2PServiceTransactionViewSet,
    P2PServiceDisputeViewSet, P2PServiceTransactionRatingViewSet,
    SellerApplicationViewSet
)
from .p2p_models import P2PServiceTransaction

# Create simple APIView classes that directly call the ViewSet action methods
# This is the most reliable way to expose @action methods as URL endpoints
class ReleaseEscrowAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        viewset = P2PServiceTransactionViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.action = 'release_escrow'
        viewset.kwargs = {'pk': pk}
        viewset.initial(request)
        # Override get_object to work properly
        def get_object():
            try:
                return P2PServiceTransaction.objects.get(pk=pk)
            except P2PServiceTransaction.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound("Transaction not found")
        viewset.get_object = get_object
        return viewset.release_escrow(request, pk)

class MarkPaymentCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        viewset = P2PServiceTransactionViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.action = 'mark_payment_complete'
        viewset.kwargs = {'pk': pk}
        viewset.initial(request)
        def get_object():
            try:
                return P2PServiceTransaction.objects.get(pk=pk)
            except P2PServiceTransaction.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound("Transaction not found")
        viewset.get_object = get_object
        return viewset.mark_payment_complete(request, pk)

class ConfirmPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        viewset = P2PServiceTransactionViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.action = 'confirm_payment'
        viewset.kwargs = {'pk': pk}
        viewset.initial(request)
        def get_object():
            try:
                return P2PServiceTransaction.objects.get(pk=pk)
            except P2PServiceTransaction.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound("Transaction not found")
        viewset.get_object = get_object
        return viewset.confirm_payment(request, pk)

router = DefaultRouter()
router.register(r'giftcards', GiftCardViewSet, basename='giftcard')
router.register(r'giftcard-orders', GiftCardOrderViewSet, basename='giftcard-order')
router.register(r'giftcard-listings', GiftCardListingViewSet, basename='giftcard-listing')
router.register(r'giftcard-transactions', GiftCardTransactionViewSet, basename='giftcard-transaction')
router.register(r'giftcard-disputes', GiftCardDisputeViewSet, basename='giftcard-dispute')
router.register(r'giftcard-ratings', GiftCardTransactionRatingViewSet, basename='giftcard-rating')
router.register(r'p2p-service-listings', P2PServiceListingViewSet, basename='p2p-service-listing')
router.register(r'p2p-service-transactions', P2PServiceTransactionViewSet, basename='p2p-service-transaction')
router.register(r'p2p-service-disputes', P2PServiceDisputeViewSet, basename='p2p-service-dispute')
router.register(r'p2p-service-ratings', P2PServiceTransactionRatingViewSet, basename='p2p-service-rating')
router.register(r'seller-applications', SellerApplicationViewSet, basename='seller-application')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'trades', TradeViewSet, basename='trade')

urlpatterns = [
    # Frontend API structure endpoints
    path('giftcards/list/', GiftCardViewSet.as_view({'get': 'list'}), name='giftcards-list'),
    path('giftcards/order/', GiftCardOrderViewSet.as_view({'post': 'order'}), name='giftcards-order'),
    path('giftcards/upload-proof/<int:pk>/', GiftCardOrderViewSet.as_view({'post': 'upload_proof'}), name='giftcards-upload-proof'),
    # Explicit routes for P2P transaction actions - MUST come BEFORE router to be matched first
    # Using APIView classes that directly call the ViewSet action methods
    # This is the most reliable way since ViewSet.as_view() doesn't work well with @action methods
    path('p2p-service-transactions/<int:pk>/release_escrow/', ReleaseEscrowAPIView.as_view(), name='p2p-service-transaction-release-escrow'),
    path('p2p-service-transactions/<int:pk>/mark_payment_complete/', MarkPaymentCompleteAPIView.as_view(), name='p2p-service-transaction-mark-payment-complete'),
    path('p2p-service-transactions/<int:pk>/confirm_payment/', ConfirmPaymentAPIView.as_view(), name='p2p-service-transaction-confirm-payment'),
    # Include router URLs for full CRUD - this should also auto-register the @action methods
    path('', include(router.urls)),
]

# Debug: Print URL patterns to verify they're being loaded
if __name__ == '__main__':
    print("URL patterns loaded:")
    for pattern in urlpatterns:
        print(f"  {pattern.pattern} -> {getattr(pattern, 'name', 'no name')}")

