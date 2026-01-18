"""
Admin interfaces for P2P Service models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .p2p_models import (
    P2PServiceListing,
    P2PServiceTransaction,
    P2PServiceDispute,
    P2PServiceTransactionRating,
    P2PServiceTransactionLog,
    P2PServiceDisputeLog,
    SellerApplication,
)
from notifications.utils import create_notification

# Note: These models are registered with the custom admin site in config/admin.py
# Using @admin.register() would register with default admin, so we don't use it here


class P2PServiceListingAdmin(admin.ModelAdmin):
    list_display = ('reference', 'service_type', 'seller', 'service_identifier_display', 'available_amount_usd', 'rate_cedis_per_usd', 'status', 'views_count', 'created_at')
    list_filter = ('status', 'service_type', 'is_negotiable', 'created_at')
    search_fields = ('reference', 'seller__email', 'paypal_email', 'cashapp_tag', 'zelle_email', 'service_identifier_hash')
    readonly_fields = ('reference', 'service_identifier_hash', 'proof_image_hash', 'views_count', 'created_at', 'updated_at', 'reviewed_at')
    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'service_type', 'reference', 'status')
        }),
        ('Service Details', {
            'fields': ('paypal_email', 'cashapp_tag', 'zelle_email', 'service_identifier_hash', 'min_amount_usd', 'max_amount_usd', 'available_amount_usd', 'currency')
        }),
        ('Pricing (Binance-style)', {
            'fields': ('rate_cedis_per_usd', 'is_negotiable', 'accepted_payment_methods', 'terms_notes')
        }),
        ('Proof & Verification', {
            'fields': ('proof_image', 'proof_image_hash', 'proof_notes')
        }),
        ('Metadata', {
            'fields': ('views_count', 'expires_at')
        }),
        ('Admin Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def service_identifier_display(self, obj):
        """Display service identifier based on service type"""
        return obj.get_service_identifier()
    service_identifier_display.short_description = 'Service Identifier'
    
    actions = ['approve_listings', 'reject_listings']
    
    def approve_listings(self, request, queryset):
        """Approve selected listings"""
        count = 0
        for listing in queryset.filter(status='under_review'):
            listing.status = 'active'
            listing.reviewed_by = request.user
            listing.reviewed_at = timezone.now()
            listing.save()
            
            create_notification(
                user=listing.seller,
                notification_type='P2P_SERVICE_LISTING_APPROVED',
                title='P2P Service Listing Approved',
                message=f'Your {listing.get_service_type_display()} listing {listing.reference} has been approved.',
                related_object_type='p2p_service_listing',
                related_object_id=listing.id,
            )
            count += 1
        self.message_user(request, f'{count} listing(s) approved.')
    approve_listings.short_description = 'Approve selected listings'
    
    def reject_listings(self, request, queryset):
        """Reject selected listings"""
        count = 0
        for listing in queryset.filter(status='under_review'):
            listing.status = 'cancelled'
            listing.reviewed_by = request.user
            listing.reviewed_at = timezone.now()
            listing.save()
            
            create_notification(
                user=listing.seller,
                notification_type='P2P_SERVICE_LISTING_REJECTED',
                title='P2P Service Listing Rejected',
                message=f'Your {listing.get_service_type_display()} listing {listing.reference} has been rejected.',
                related_object_type='p2p_service_listing',
                related_object_id=listing.id,
            )
            count += 1
        self.message_user(request, f'{count} listing(s) rejected.')
    reject_listings.short_description = 'Reject selected listings'


class P2PServiceTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'listing', 'buyer', 'seller', 'amount_usd', 'agreed_price_cedis', 'status', 'risk_score', 'created_at')
    list_filter = ('status', 'has_dispute', 'listing__service_type', 'created_at')
    search_fields = ('reference', 'buyer__email', 'seller__email', 'listing__reference')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'completed_at', 'cancelled_at', 'risk_score', 'risk_factors', 'device_fingerprint')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('reference', 'listing', 'buyer', 'seller', 'status')
        }),
        ('Financial Details', {
            'fields': ('amount_usd', 'agreed_price_cedis', 'escrow_amount_cedis', 'selected_payment_method', 'payment_method_details')
        }),
        ('Service Delivery', {
            'fields': ('service_identifier', 'service_proof_image', 'service_provided_at')
        }),
        ('Verification', {
            'fields': ('buyer_verified', 'buyer_verification_notes', 'verified_at')
        }),
        ('Deadlines', {
            'fields': ('seller_response_deadline', 'buyer_verification_deadline', 'auto_release_at')
        }),
        ('Dispute Information', {
            'fields': ('has_dispute', 'dispute_reason', 'dispute_resolved', 'dispute_resolution', 'dispute_resolved_by', 'dispute_resolved_at')
        }),
        ('Security & Risk', {
            'fields': ('risk_score', 'risk_factors', 'device_fingerprint')
        }),
        ('Admin Notes', {
            'fields': ('admin_notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'cancelled_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('buyer', 'seller', 'listing')


class P2PServiceDisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_reference', 'raised_by', 'dispute_type', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'dispute_type', 'priority', 'created_at')
    search_fields = ('transaction__reference', 'raised_by__email', 'description')
    readonly_fields = ('transaction', 'raised_by', 'created_at', 'updated_at', 'resolved_at', 'assigned_at')
    fieldsets = (
        ('Dispute Information', {
            'fields': ('transaction', 'raised_by', 'dispute_type', 'status', 'priority')
        }),
        ('Details', {
            'fields': ('description', 'evidence_images', 'evidence_required')
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolution_notes', 'resolved_at')
        }),
        ('Admin Assignment', {
            'fields': ('assigned_to', 'assigned_at')
        }),
        ('Fraud Detection', {
            'fields': ('fraud_indicators', 'verification_attempts')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def transaction_reference(self, obj):
        return obj.transaction.reference
    transaction_reference.short_description = 'Transaction Reference'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('transaction', 'raised_by', 'assigned_to')


class P2PServiceTransactionRatingAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_reference', 'rater', 'rated_user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('transaction__reference', 'rater__email', 'rated_user__email', 'comment')
    readonly_fields = ('transaction', 'rater', 'rated_user', 'created_at', 'updated_at')
    
    def transaction_reference(self, obj):
        return obj.transaction.reference
    transaction_reference.short_description = 'Transaction Reference'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('transaction', 'rater', 'rated_user')


class P2PServiceTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_reference', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('transaction__reference', 'performed_by__email', 'notes')
    readonly_fields = ('transaction', 'action', 'performed_by', 'notes', 'timestamp')
    
    def transaction_reference(self, obj):
        return obj.transaction.reference
    transaction_reference.short_description = 'Transaction Reference'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class P2PServiceDisputeLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'dispute_id', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('dispute__transaction__reference', 'performed_by__email', 'notes')
    readonly_fields = ('dispute', 'action', 'performed_by', 'notes', 'timestamp')
    
    def dispute_id(self, obj):
        return obj.dispute.id
    dispute_id.short_description = 'Dispute ID'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class SellerApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'user_name', 'status', 'service_types_display', 'reviewed_by', 'created_at', 'reviewed_at')
    list_filter = ('status', 'created_at', 'reviewed_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'reason', 'experience')
    readonly_fields = ('id', 'user', 'created_at', 'updated_at', 'reviewed_at', 'proof_of_funds_hash')
    fieldsets = (
        ('Application Information', {
            'fields': ('user', 'status', 'id')
        }),
        ('Application Details', {
            'fields': ('reason', 'experience', 'service_types')
        }),
        ('Proof of Funds', {
            'fields': ('proof_of_funds_image', 'proof_of_funds_hash')
        }),
        ('Review Information', {
            'fields': ('reviewed_by', 'reviewed_at', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    user_name.short_description = 'User Name'
    
    def service_types_display(self, obj):
        if isinstance(obj.service_types, list):
            return ', '.join([st.upper() for st in obj.service_types])
        return str(obj.service_types)
    service_types_display.short_description = 'Service Types'
    
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        """Approve selected applications"""
        count = 0
        for application in queryset.filter(status='pending'):
            application.approve(reviewer=request.user)
            
            create_notification(
                user=application.user,
                notification_type='SELLER_APPLICATION_APPROVED',
                title='Seller Application Approved',
                message='Your seller application has been approved! You can now create P2P service listings.',
                related_object_type='seller_application',
                related_object_id=str(application.id),
            )
            count += 1
        self.message_user(request, f'{count} application(s) approved.')
    approve_applications.short_description = 'Approve selected applications'
    
    def reject_applications(self, request, queryset):
        """Reject selected applications"""
        count = 0
        for application in queryset.filter(status='pending'):
            application.reject(reviewer=request.user, reason='Rejected via admin panel')
            
            create_notification(
                user=application.user,
                notification_type='SELLER_APPLICATION_REJECTED',
                title='Seller Application Rejected',
                message='Your seller application has been rejected. Please review the requirements and try again.',
                related_object_type='seller_application',
                related_object_id=str(application.id),
            )
            count += 1
        self.message_user(request, f'{count} application(s) rejected.')
    reject_applications.short_description = 'Reject selected applications'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'reviewed_by')

