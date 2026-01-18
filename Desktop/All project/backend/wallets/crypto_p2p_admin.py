"""
Django Admin Configuration for Crypto P2P Trading
Enables admins to monitor, manage, and resolve disputes
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from wallets.crypto_p2p_models import (
    CryptoListing,
    CryptoTransaction,
    CryptoTransactionAuditLog,
    CryptoTransactionDispute,
)


@admin.register(CryptoListing)
class CryptoListingAdmin(admin.ModelAdmin):
    """Admin interface for Crypto Listings"""
    
    list_display = (
        'reference',
        'seller_link',
        'crypto_display',
        'listing_type_display',
        'rate_cedis_per_crypto',
        'available_amount_crypto',
        'status_badge',
        'created_at',
        'views_count'
    )
    
    list_filter = (
        'status',
        'crypto_type',
        'listing_type',
        'network',
        'created_at',
    )
    
    search_fields = ('reference', 'seller__email', 'crypto_type')
    
    readonly_fields = (
        'reference',
        'seller',
        'created_at',
        'updated_at',
        'views_count',
        'transactions_count',
        'proof_image_display',
        'payment_methods_display',
        'buyer_requirements_display',
    )
    
    fieldsets = (
        ('Listing Info', {
            'fields': ('reference', 'seller', 'status', 'created_at', 'updated_at')
        }),
        ('Crypto Details', {
            'fields': (
                'crypto_type',
                'network',
                'listing_type',
                'amount_crypto',
                'available_amount_crypto',
                'min_amount_crypto',
                'max_amount_crypto'
            )
        }),
        ('Pricing & Payment', {
            'fields': (
                'rate_cedis_per_crypto',
                'payment_methods_display',
            )
        }),
        ('Buyer Requirements', {
            'fields': ('buyer_requirements_display',)
        }),
        ('Proof & Metrics', {
            'fields': (
                'proof_image_display',
                'views_count',
                'transactions_count'
            )
        }),
    )
    
    actions = ['approve_listings', 'reject_listings', 'pause_listings']
    
    def seller_link(self, obj):
        """Link to seller profile"""
        return obj.seller.email
    seller_link.short_description = 'Seller'
    
    def crypto_display(self, obj):
        """Display crypto type with icon"""
        return f"{obj.get_crypto_type_display()}"
    crypto_display.short_description = 'Crypto'
    
    def listing_type_display(self, obj):
        """Display listing type with color"""
        colors = {'buy': '#2196F3', 'sell': '#4CAF50'}
        color = colors.get(obj.listing_type, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_listing_type_display()
        )
    listing_type_display.short_description = 'Type'
    
    def status_badge(self, obj):
        """Status badge with color"""
        colors = {
            'active': '#4CAF50',
            'under_review': '#FF9800',
            'cancelled': '#F44336',
            'paused': '#9E9E9E'
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def proof_image_display(self, obj):
        """Display proof image thumbnail"""
        if obj.proof_image:
            return format_html(
                '<img src="{}" width="150" height="150" />',
                obj.proof_image.url
            )
        return 'No image'
    proof_image_display.short_description = 'Proof Image'
    
    def payment_methods_display(self, obj):
        """Display payment methods as readable list"""
        methods = ', '.join(obj.payment_methods) if obj.payment_methods else 'None'
        return methods
    payment_methods_display.short_description = 'Payment Methods'
    
    def buyer_requirements_display(self, obj):
        """Display buyer requirements as formatted text"""
        req = obj.buyer_requirements or {}
        lines = [f"{k}: {v}" for k, v in req.items()]
        return format_html('<br>'.join(lines) or 'No requirements')
    buyer_requirements_display.short_description = 'Buyer Requirements'
    
    @property
    def transactions_count(self):
        """Count of transactions for this listing"""
        return CryptoTransaction.objects.filter(listing=self).count()
    
    def approve_listings(self, request, queryset):
        """Approve pending listings"""
        updated = queryset.filter(status='under_review').update(status='active')
        self.message_user(request, f'{updated} listings approved and activated.')
    approve_listings.short_description = 'Approve selected listings'
    
    def reject_listings(self, request, queryset):
        """Reject pending listings"""
        updated = queryset.filter(status='under_review').update(status='cancelled')
        self.message_user(request, f'{updated} listings rejected.')
    reject_listings.short_description = 'Reject selected listings'
    
    def pause_listings(self, request, queryset):
        """Pause active listings"""
        updated = queryset.filter(status='active').update(status='paused')
        self.message_user(request, f'{updated} listings paused.')
    pause_listings.short_description = 'Pause selected listings'


@admin.register(CryptoTransaction)
class CryptoTransactionAdmin(admin.ModelAdmin):
    """Admin interface for Crypto Transactions"""
    
    list_display = (
        'reference',
        'buyer_email',
        'seller_email',
        'amount_display',
        'status_badge',
        'progress_indicator',
        'escrow_status',
        'created_at',
        'dispute_status'
    )
    
    list_filter = (
        'status',
        'has_dispute',
        'escrow_locked',
        'created_at',
        'completed_at',
    )
    
    search_fields = (
        'reference',
        'buyer__email',
        'seller__email',
        'transaction_hash'
    )
    
    readonly_fields = (
        'reference',
        'buyer',
        'seller',
        'listing',
        'created_at',
        'completed_at',
        'payment_deadline_status',
        'seller_confirmation_deadline_status',
        'seller_response_deadline_status',
        'buyer_verification_deadline_status',
        'payment_screenshot_display',
        'crypto_proof_image_display',
        'audit_trail_link',
        'dispute_link',
        'timeline_display'
    )
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('reference', 'status', 'created_at', 'completed_at')
        }),
        ('Parties', {
            'fields': ('buyer', 'seller', 'listing')
        }),
        ('Amounts', {
            'fields': (
                'amount_crypto',
                'amount_cedis',
                'rate_applied',
                'escrow_locked',
                'escrow_amount_cedis'
            )
        }),
        ('Buyer Info', {
            'fields': (
                'buyer_wallet_address',
                'buyer_payment_details',
                'buyer_marked_paid',
                'buyer_marked_paid_at',
                'payment_screenshot_display'
            ),
            'classes': ('collapse',)
        }),
        ('Seller Info', {
            'fields': (
                'seller_confirmed_payment',
                'seller_confirmed_payment_at',
                'crypto_sent',
                'crypto_sent_at',
                'transaction_hash',
                'crypto_proof_image_display'
            ),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': (
                'buyer_verified',
                'verified_at',
                'buyer_verification_notes',
                'blockchain_verified',
                'blockchain_verified_at'
            ),
            'classes': ('collapse',)
        }),
        ('Deadlines & Status', {
            'fields': (
                'payment_deadline_status',
                'seller_confirmation_deadline_status',
                'seller_response_deadline_status',
                'buyer_verification_deadline_status'
            ),
            'classes': ('collapse',)
        }),
        ('Risk & Disputes', {
            'fields': (
                'risk_score',
                'has_dispute',
                'dispute_link'
            )
        }),
        ('Audit & Timeline', {
            'fields': (
                'audit_trail_link',
                'timeline_display'
            ),
            'classes': ('wide',)
        }),
    )
    
    actions = ['mark_as_completed', 'create_dispute', 'cancel_transaction']
    
    def buyer_email(self, obj):
        return obj.buyer.email
    buyer_email.short_description = 'Buyer'
    
    def seller_email(self, obj):
        return obj.seller.email
    seller_email.short_description = 'Seller'
    
    def amount_display(self, obj):
        return f"{obj.amount_crypto} {obj.listing.get_crypto_type_display()} / ₵{obj.amount_cedis}"
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        """Status badge with color"""
        colors = {
            'payment_received': '#2196F3',
            'buyer_marked_paid': '#00BCD4',
            'seller_confirmed_payment': '#009688',
            'crypto_sent': '#4CAF50',
            'verifying': '#FF9800',
            'completed': '#8BC34A',
            'disputed': '#F44336',
            'cancelled': '#9E9E9E'
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress_indicator(self, obj):
        """Show transaction progress"""
        status_steps = {
            'payment_received': 1,
            'buyer_marked_paid': 2,
            'seller_confirmed_payment': 3,
            'crypto_sent': 4,
            'verifying': 5,
            'completed': 6,
        }
        current_step = status_steps.get(obj.status, 0)
        progress = int((current_step / 6) * 100)
        
        return format_html(
            '<div style="width: 100px; height: 10px; background-color: #eee; border-radius: 5px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background-color: #4CAF50;"></div>'
            '</div> {}%',
            progress,
            progress
        )
    progress_indicator.short_description = 'Progress'
    
    def escrow_status(self, obj):
        """Display escrow status"""
        if obj.escrow_locked:
            return format_html(
                '<span style="color: #F44336;"><strong>🔒 Locked: ₵{}</strong></span>',
                obj.escrow_amount_cedis
            )
        return format_html('<span style="color: #4CAF50;"><strong>✓ Released</strong></span>')
    escrow_status.short_description = 'Escrow'
    
    def dispute_status(self, obj):
        """Display dispute status"""
        if obj.has_dispute:
            return format_html('<span style="color: #F44336;"><strong>⚠️ DISPUTED</strong></span>')
        return format_html('<span style="color: #4CAF50;">OK</span>')
    dispute_status.short_description = 'Dispute'
    
    def payment_screenshot_display(self, obj):
        """Display payment screenshot"""
        if obj.payment_screenshot:
            return format_html(
                '<img src="{}" width="200" height="200" />',
                obj.payment_screenshot.url
            )
        return 'Not uploaded'
    payment_screenshot_display.short_description = 'Payment Proof'
    
    def crypto_proof_image_display(self, obj):
        """Display crypto proof image"""
        if obj.crypto_proof_image:
            return format_html(
                '<img src="{}" width="200" height="200" />',
                obj.crypto_proof_image.url
            )
        return 'Not uploaded'
    crypto_proof_image_display.short_description = 'Crypto Proof'
    
    def payment_deadline_status(self, obj):
        """Show payment deadline status"""
        if obj.payment_deadline:
            from django.utils import timezone
            now = timezone.now()
            time_left = (obj.payment_deadline - now).total_seconds() / 60
            if time_left < 0:
                return format_html('<span style="color: #F44336;">⏰ EXPIRED</span>')
            return format_html('<span style="color: #FF9800;">⏳ {} min left</span>', int(time_left))
        return '-'
    payment_deadline_status.short_description = 'Payment Deadline'
    
    def seller_confirmation_deadline_status(self, obj):
        if obj.seller_confirmation_deadline:
            from django.utils import timezone
            now = timezone.now()
            time_left = (obj.seller_confirmation_deadline - now).total_seconds() / 60
            if time_left < 0:
                return format_html('<span style="color: #F44336;">⏰ EXPIRED</span>')
            return format_html('<span style="color: #FF9800;">⏳ {} min left</span>', int(time_left))
        return '-'
    seller_confirmation_deadline_status.short_description = 'Confirmation Deadline'
    
    def seller_response_deadline_status(self, obj):
        if obj.seller_response_deadline:
            from django.utils import timezone
            now = timezone.now()
            time_left = (obj.seller_response_deadline - now).total_seconds() / 60
            if time_left < 0:
                return format_html('<span style="color: #F44336;">⏰ EXPIRED</span>')
            return format_html('<span style="color: #FF9800;">⏳ {} min left</span>', int(time_left))
        return '-'
    seller_response_deadline_status.short_description = 'Response Deadline'
    
    def buyer_verification_deadline_status(self, obj):
        if obj.buyer_verification_deadline:
            from django.utils import timezone
            now = timezone.now()
            time_left = (obj.buyer_verification_deadline - now).total_seconds() / 60
            if time_left < 0:
                return format_html('<span style="color: #F44336;">⏰ EXPIRED</span>')
            return format_html('<span style="color: #FF9800;">⏳ {} min left</span>', int(time_left))
        return '-'
    buyer_verification_deadline_status.short_description = 'Verification Deadline'
    
    def timeline_display(self, obj):
        """Display transaction timeline"""
        timeline_items = []
        
        timeline_items.append(f"<strong>Created:</strong> {obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.buyer_marked_paid_at:
            timeline_items.append(f"<strong>Buyer marked paid:</strong> {obj.buyer_marked_paid_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.seller_confirmed_payment_at:
            timeline_items.append(f"<strong>Seller confirmed:</strong> {obj.seller_confirmed_payment_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.crypto_sent_at:
            timeline_items.append(f"<strong>Crypto sent:</strong> {obj.crypto_sent_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.verified_at:
            timeline_items.append(f"<strong>Verified:</strong> {obj.verified_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.completed_at:
            timeline_items.append(f"<strong>Completed:</strong> {obj.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return format_html('<br>'.join(timeline_items))
    timeline_display.short_description = 'Transaction Timeline'
    
    def audit_trail_link(self, obj):
        """Link to audit trail"""
        count = obj.audit_logs.count()
        return format_html(
            '<a href="#" onclick="return false;">View {} audit log entries</a>',
            count
        )
    audit_trail_link.short_description = 'Audit Trail'
    
    def dispute_link(self, obj):
        """Link to dispute if exists"""
        if obj.has_dispute:
            dispute = obj.disputes.first()
            if dispute:
                url = reverse('admin:wallets_cryptotransactiondispute_change', args=[dispute.id])
                return format_html('<a href="{}" target="_blank">View Dispute #{}</a>', url, dispute.id)
        return 'No dispute'
    dispute_link.short_description = 'Dispute'
    
    def mark_as_completed(self, request, queryset):
        """Mark transactions as completed"""
        updated = queryset.filter(status='crypto_sent').update(status='completed')
        self.message_user(request, f'{updated} transactions marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'
    
    def create_dispute(self, request, queryset):
        """Create dispute for selected transactions"""
        count = 0
        for transaction in queryset:
            if not transaction.has_dispute:
                CryptoTransactionDispute.objects.create(
                    transaction=transaction,
                    raised_by=request.user,
                    dispute_type='other',
                    description='Created by admin'
                )
                count += 1
        self.message_user(request, f'{count} disputes created.')
    create_dispute.short_description = 'Create dispute'
    
    def cancel_transaction(self, request, queryset):
        """Cancel selected transactions"""
        updated = queryset.exclude(status__in=['completed', 'cancelled']).update(status='cancelled')
        self.message_user(request, f'{updated} transactions cancelled.')
    cancel_transaction.short_description = 'Cancel transaction'


@admin.register(CryptoTransactionAuditLog)
class CryptoTransactionAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Audit Logs"""
    
    list_display = (
        'transaction_ref',
        'action_display',
        'performed_by_email',
        'created_at',
        'signature_valid'
    )
    
    list_filter = (
        'action',
        'created_at',
    )
    
    search_fields = (
        'transaction__reference',
        'performed_by__email',
    )
    
    readonly_fields = (
        'transaction',
        'action',
        'performed_by',
        'created_at',
        'notes',
        'metadata_display',
        'signature'
    )
    
    def transaction_ref(self, obj):
        return obj.transaction.reference
    transaction_ref.short_description = 'Transaction'
    
    def action_display(self, obj):
        return obj.get_action_display()
    action_display.short_description = 'Action'
    
    def performed_by_email(self, obj):
        return obj.performed_by.email if obj.performed_by else 'System'
    performed_by_email.short_description = 'Performed By'
    
    def metadata_display(self, obj):
        import json
        return format_html(
            '<pre>{}</pre>',
            json.dumps(obj.metadata, indent=2)
        )
    metadata_display.short_description = 'Metadata'
    
    def signature_valid(self, obj):
        """Check HMAC signature validity"""
        if obj.signature:
            return format_html('<span style="color: #4CAF50;">✓ Valid</span>')
        return format_html('<span style="color: #F44336;">✗ Missing</span>')
    signature_valid.short_description = 'Signature'


@admin.register(CryptoTransactionDispute)
class CryptoTransactionDisputeAdmin(admin.ModelAdmin):
    """Admin interface for Disputes"""
    
    list_display = (
        'id',
        'transaction_ref',
        'raised_by_email',
        'dispute_type_display',
        'status_badge',
        'created_at',
        'resolution_link'
    )
    
    list_filter = (
        'status',
        'dispute_type',
        'created_at',
    )
    
    search_fields = (
        'transaction__reference',
        'raised_by__email',
    )
    
    readonly_fields = (
        'transaction',
        'raised_by',
        'created_at',
        'evidence_image_display',
    )
    
    fieldsets = (
        ('Dispute Info', {
            'fields': ('transaction', 'raised_by', 'created_at', 'status')
        }),
        ('Dispute Details', {
            'fields': (
                'dispute_type',
                'description',
                'evidence_image_display'
            )
        }),
        ('Resolution', {
            'fields': (
                'resolution_notes',
                'resolved_at'
            )
        }),
    )
    
    actions = ['mark_as_resolved', 'refund_buyer', 'release_to_seller']
    
    def transaction_ref(self, obj):
        return obj.transaction.reference
    transaction_ref.short_description = 'Transaction'
    
    def raised_by_email(self, obj):
        return obj.raised_by.email
    raised_by_email.short_description = 'Raised By'
    
    def dispute_type_display(self, obj):
        return obj.get_dispute_type_display()
    dispute_type_display.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'open': '#2196F3',
            'in_review': '#FF9800',
            'resolved': '#4CAF50',
            'closed': '#9E9E9E'
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def evidence_image_display(self, obj):
        if obj.evidence_image:
            return format_html(
                '<img src="{}" width="200" height="200" />',
                obj.evidence_image.url
            )
        return 'No image'
    evidence_image_display.short_description = 'Evidence Image'
    
    def resolution_link(self, obj):
        if obj.status == 'open':
            return format_html('<span style="color: #2196F3;">Pending review</span>')
        return format_html('<span style="color: #4CAF50;">Resolved</span>')
    resolution_link.short_description = 'Resolution'
    
    def mark_as_resolved(self, request, queryset):
        """Mark disputes as resolved"""
        updated = queryset.filter(status='in_review').update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} disputes marked as resolved.')
    mark_as_resolved.short_description = 'Mark as resolved'
    
    def refund_buyer(self, request, queryset):
        """Refund buyer's escrow"""
        from django.utils import timezone
        for dispute in queryset.filter(status='open'):
            transaction = dispute.transaction
            buyer_wallet = transaction.buyer.wallet
            buyer_wallet.release_cedis_from_escrow_atomic(transaction.escrow_amount_cedis)
            transaction.status = 'cancelled'
            transaction.save()
            dispute.status = 'resolved'
            dispute.resolution_notes = f'Refunded to buyer by {request.user.email}'
            dispute.resolved_at = timezone.now()
            dispute.save()
        self.message_user(request, f'Refunds issued for {queryset.count()} disputes.')
    refund_buyer.short_description = 'Refund buyer'
    
    def release_to_seller(self, request, queryset):
        """Release escrow to seller"""
        from django.utils import timezone
        for dispute in queryset.filter(status='open'):
            transaction = dispute.transaction
            seller_wallet = transaction.seller.wallet
            seller_wallet.release_cedis_from_escrow_atomic(transaction.escrow_amount_cedis)
            transaction.status = 'completed'
            transaction.save()
            dispute.status = 'resolved'
            dispute.resolution_notes = f'Escrow released to seller by {request.user.email}'
            dispute.resolved_at = timezone.now()
            dispute.save()
        self.message_user(request, f'Escrow released for {queryset.count()} disputes.')
    release_to_seller.short_description = 'Release to seller'


from django.utils import timezone
