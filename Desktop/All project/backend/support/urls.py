from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupportTicketViewSet, SupportTicketResponseViewSet, ContactEnquiryViewSet, SpecialRequestViewSet, PayPalRequestViewSet, PayPalTransactionViewSet, PayPalPurchaseRequestViewSet, CashAppRequestViewSet, CashAppTransactionViewSet, CashAppPurchaseRequestViewSet, ZelleRequestViewSet, ZelleTransactionViewSet

router = DefaultRouter()
router.register(r'tickets', SupportTicketViewSet, basename='support-ticket')
router.register(r'responses', SupportTicketResponseViewSet, basename='support-ticket-response')
router.register(r'enquiries', ContactEnquiryViewSet, basename='contact-enquiry')
router.register(r'special-requests', SpecialRequestViewSet, basename='special-request')
router.register(r'paypal-requests', PayPalRequestViewSet, basename='paypal-request')
router.register(r'paypal-transactions', PayPalTransactionViewSet, basename='paypal-transaction')
router.register(r'paypal-purchase-requests', PayPalPurchaseRequestViewSet, basename='paypal-purchase-request')
router.register(r'cashapp-requests', CashAppRequestViewSet, basename='cashapp-request')
router.register(r'cashapp-transactions', CashAppTransactionViewSet, basename='cashapp-transaction')
router.register(r'cashapp-purchase-requests', CashAppPurchaseRequestViewSet, basename='cashapp-purchase-request')
router.register(r'zelle-requests', ZelleRequestViewSet, basename='zelle-request')
router.register(r'zelle-transactions', ZelleTransactionViewSet, basename='zelle-transaction')

urlpatterns = [
    path('', include(router.urls)),
]

