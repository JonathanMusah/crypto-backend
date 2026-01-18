from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
from authentication.models import User, OTP, UserDevice, SecurityLog
from wallets.models import Wallet, CryptoTransaction
from orders.models import GiftCardOrder
from kyc.models import KYCVerification
from support.models import SupportTicket
from tutorials.models import Tutorial
from marketing.models import Testimonial


class CustomAdminSite(admin.AdminSite):
    site_header = "CryptoGhana Admin"
    site_title = "CryptoGhana Admin Portal"
    index_title = "Welcome to CryptoGhana Administration"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='admin_dashboard'),
        ]
        return custom_urls + urls

    def dashboard_view(self, request):
        # Calculate statistics with error handling
        now = timezone.now()
        last_24h = now - timedelta(days=1)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        # Helper function to safely get count
        def safe_count(queryset):
            try:
                return queryset.count()
            except:
                return 0

        def safe_aggregate(queryset, field):
            try:
                result = queryset.aggregate(total=Sum(field))['total']
                return result or 0
            except:
                return 0

        # User statistics
        try:
            total_users = User.objects.count()
            new_users_24h = User.objects.filter(date_joined__gte=last_24h).count()
            new_users_7d = User.objects.filter(date_joined__gte=last_7d).count()
            verified_users = User.objects.filter(kyc_status='approved').count()
        except:
            total_users = new_users_24h = new_users_7d = verified_users = 0

        try:
            pending_kyc = KYCVerification.objects.filter(status='PENDING').count()
        except:
            pending_kyc = 0

        # Transaction statistics
        try:
            total_transactions = CryptoTransaction.objects.count()
            pending_transactions = CryptoTransaction.objects.filter(status='pending').count()
            transactions_24h = CryptoTransaction.objects.filter(created_at__gte=last_24h).count()
            transactions_7d = CryptoTransaction.objects.filter(created_at__gte=last_7d).count()
            total_volume_cedis = safe_aggregate(CryptoTransaction.objects.all(), 'cedis_amount')
            volume_24h = safe_aggregate(
                CryptoTransaction.objects.filter(created_at__gte=last_24h, status='approved'),
                'cedis_amount'
            )
        except:
            total_transactions = pending_transactions = transactions_24h = transactions_7d = 0
            total_volume_cedis = volume_24h = 0

        # Wallet statistics
        try:
            total_wallets = Wallet.objects.count()
            total_balance_cedis = safe_aggregate(Wallet.objects.all(), 'balance_cedis')
            total_escrow = safe_aggregate(Wallet.objects.all(), 'escrow_balance')
        except:
            total_wallets = 0
            total_balance_cedis = total_escrow = 0

        # Support tickets
        try:
            open_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress']).count()
            urgent_tickets = SupportTicket.objects.filter(priority='urgent', status__in=['open', 'in_progress']).count()
            total_tickets = SupportTicket.objects.count()
            resolved_tickets_7d = SupportTicket.objects.filter(
                status='resolved',
                resolved_at__gte=last_7d
            ).count()
        except:
            open_tickets = urgent_tickets = total_tickets = resolved_tickets_7d = 0

        # Gift card orders
        try:
            pending_gift_orders = GiftCardOrder.objects.filter(status='pending').count()
            total_gift_orders = GiftCardOrder.objects.count()
        except:
            pending_gift_orders = total_gift_orders = 0

        # Tutorials
        try:
            published_tutorials = Tutorial.objects.filter(is_published=True).count()
            total_tutorials = Tutorial.objects.count()
        except:
            published_tutorials = total_tutorials = 0

        # Testimonials
        try:
            featured_testimonials = Testimonial.objects.filter(is_featured=True).count()
            total_testimonials = Testimonial.objects.count()
        except:
            featured_testimonials = total_testimonials = 0

        # Recent activity
        try:
            recent_transactions = CryptoTransaction.objects.select_related('user').order_by('-created_at')[:10]
        except:
            recent_transactions = []
        
        try:
            recent_tickets = SupportTicket.objects.select_related('user', 'assigned_to').order_by('-created_at')[:10]
        except:
            recent_tickets = []
        
        try:
            recent_kyc = KYCVerification.objects.select_related('user').order_by('-submitted_at')[:10]
        except:
            recent_kyc = []

        context = {
            **self.each_context(request),
            'title': 'Admin Dashboard',
            'total_users': total_users,
            'new_users_24h': new_users_24h,
            'new_users_7d': new_users_7d,
            'verified_users': verified_users,
            'pending_kyc': pending_kyc,
            'total_transactions': total_transactions,
            'pending_transactions': pending_transactions,
            'transactions_24h': transactions_24h,
            'transactions_7d': transactions_7d,
            'total_volume_cedis': total_volume_cedis,
            'volume_24h': volume_24h,
            'total_wallets': total_wallets,
            'total_balance_cedis': total_balance_cedis,
            'total_escrow': total_escrow,
            'open_tickets': open_tickets,
            'urgent_tickets': urgent_tickets,
            'total_tickets': total_tickets,
            'resolved_tickets_7d': resolved_tickets_7d,
            'pending_gift_orders': pending_gift_orders,
            'total_gift_orders': total_gift_orders,
            'published_tutorials': published_tutorials,
            'total_tutorials': total_tutorials,
            'featured_testimonials': featured_testimonials,
            'total_testimonials': total_testimonials,
            'recent_transactions': recent_transactions,
            'recent_tickets': recent_tickets,
            'recent_kyc': recent_kyc,
        }
        return render(request, 'admin/dashboard.html', context)


# Create custom admin site instance
admin_site = CustomAdminSite(name='custom_admin')

# Import all models first
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from wallets.models import Wallet, WalletTransaction, CryptoTransaction, AdminCryptoAddress, AdminPaymentDetails, Deposit, Withdrawal
from orders.models import GiftCard, GiftCardOrder, Order, Trade, GiftCardListing, GiftCardTransaction, GiftCardDispute
from orders.p2p_models import (
    P2PServiceListing, P2PServiceTransaction, P2PServiceDispute,
    P2PServiceTransactionRating, P2PServiceTransactionLog, P2PServiceDisputeLog,
    SellerApplication
)
from kyc.models import KYCVerification
from support.models import SupportTicket, SupportTicketResponse, ContactEnquiry, SpecialRequest, PayPalRequest, PayPalTransaction, PayPalPurchaseRequest, CashAppRequest, CashAppTransaction, CashAppPurchaseRequest, ZelleRequest, ZelleTransaction
from tutorials.models import Tutorial, TutorialProgress
from marketing.models import FeatureBlock, SecurityHighlight, SupportedAsset, Testimonial, PolicyPage, UserReview
from analytics.models import Settings, AnalyticsEvent
from rates.models import CryptoRate, RateCache
from notifications.models import Notification

# Import admin classes
from authentication.admin import UserAdmin, OTPAdmin, UserDeviceAdmin, SecurityLogAdmin
from wallets.admin import WalletAdmin, WalletTransactionAdmin, CryptoTransactionAdmin, AdminCryptoAddressAdmin, AdminPaymentDetailsAdmin, DepositAdmin, WithdrawalAdmin
from orders.admin import GiftCardAdmin, GiftCardOrderAdmin, OrderAdmin, TradeAdmin, GiftCardListingAdmin, GiftCardTransactionAdmin, GiftCardDisputeAdmin
from orders.p2p_admin import (
    P2PServiceListingAdmin, P2PServiceTransactionAdmin, P2PServiceDisputeAdmin,
    P2PServiceTransactionRatingAdmin, P2PServiceTransactionLogAdmin, P2PServiceDisputeLogAdmin,
    SellerApplicationAdmin
)
from kyc.admin import KYCVerificationAdmin
from support.admin import SupportTicketAdmin, SupportTicketResponseAdmin, ContactEnquiryAdmin, SpecialRequestAdmin, PayPalRequestAdmin, PayPalTransactionAdmin, PayPalPurchaseRequestAdmin, CashAppRequestAdmin, CashAppTransactionAdmin, CashAppPurchaseRequestAdmin, ZelleRequestAdmin, ZelleTransactionAdmin
from tutorials.admin import TutorialAdmin, TutorialProgressAdmin
from marketing.admin import FeatureBlockAdmin, SecurityHighlightAdmin, SupportedAssetAdmin, TestimonialAdmin, PolicyPageAdmin, UserReviewAdmin
from analytics.admin import SettingsAdmin, AnalyticsEventAdmin
from rates.admin import CryptoRateAdmin, RateCacheAdmin
from notifications.admin import NotificationAdmin

User = get_user_model()

# Register all models with the custom admin site
admin_site.register(User, UserAdmin)
admin_site.register(OTP, OTPAdmin)
admin_site.register(UserDevice, UserDeviceAdmin)
admin_site.register(SecurityLog, SecurityLogAdmin)
admin_site.register(Group)
admin_site.register(Wallet, WalletAdmin)
admin_site.register(WalletTransaction, WalletTransactionAdmin)
admin_site.register(CryptoTransaction, CryptoTransactionAdmin)
admin_site.register(AdminCryptoAddress, AdminCryptoAddressAdmin)
admin_site.register(AdminPaymentDetails, AdminPaymentDetailsAdmin)
admin_site.register(Deposit, DepositAdmin)
admin_site.register(Withdrawal, WithdrawalAdmin)
admin_site.register(GiftCard, GiftCardAdmin)
admin_site.register(GiftCardOrder, GiftCardOrderAdmin)
admin_site.register(GiftCardListing, GiftCardListingAdmin)
admin_site.register(GiftCardTransaction, GiftCardTransactionAdmin)
admin_site.register(GiftCardDispute, GiftCardDisputeAdmin)
admin_site.register(Order, OrderAdmin)
admin_site.register(Trade, TradeAdmin)
# P2P Service Marketplace
admin_site.register(P2PServiceListing, P2PServiceListingAdmin)
admin_site.register(P2PServiceTransaction, P2PServiceTransactionAdmin)
admin_site.register(P2PServiceDispute, P2PServiceDisputeAdmin)
admin_site.register(P2PServiceTransactionRating, P2PServiceTransactionRatingAdmin)
admin_site.register(P2PServiceTransactionLog, P2PServiceTransactionLogAdmin)
admin_site.register(P2PServiceDisputeLog, P2PServiceDisputeLogAdmin)
admin_site.register(SellerApplication, SellerApplicationAdmin)
admin_site.register(KYCVerification, KYCVerificationAdmin)
admin_site.register(SupportTicket, SupportTicketAdmin)
admin_site.register(SupportTicketResponse, SupportTicketResponseAdmin)
admin_site.register(ContactEnquiry, ContactEnquiryAdmin)
admin_site.register(SpecialRequest, SpecialRequestAdmin)
admin_site.register(PayPalRequest, PayPalRequestAdmin)
admin_site.register(PayPalTransaction, PayPalTransactionAdmin)
admin_site.register(PayPalPurchaseRequest, PayPalPurchaseRequestAdmin)
admin_site.register(CashAppRequest, CashAppRequestAdmin)
admin_site.register(CashAppTransaction, CashAppTransactionAdmin)
admin_site.register(CashAppPurchaseRequest, CashAppPurchaseRequestAdmin)
admin_site.register(ZelleRequest, ZelleRequestAdmin)
admin_site.register(ZelleTransaction, ZelleTransactionAdmin)
admin_site.register(Tutorial, TutorialAdmin)
admin_site.register(TutorialProgress, TutorialProgressAdmin)
admin_site.register(FeatureBlock, FeatureBlockAdmin)
admin_site.register(SecurityHighlight, SecurityHighlightAdmin)
admin_site.register(SupportedAsset, SupportedAssetAdmin)
admin_site.register(Testimonial, TestimonialAdmin)
admin_site.register(UserReview, UserReviewAdmin)
admin_site.register(PolicyPage, PolicyPageAdmin)
admin_site.register(Settings, SettingsAdmin)
admin_site.register(AnalyticsEvent, AnalyticsEventAdmin)
admin_site.register(CryptoRate, CryptoRateAdmin)
admin_site.register(RateCache, RateCacheAdmin)
admin_site.register(Notification, NotificationAdmin)

