from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import GiftCard, GiftCardOrder, Order, Trade, GiftCardListing, GiftCardTransaction, GiftCardDispute, GiftCardTransactionRating, GiftCardDisputeLog
from notifications.utils import create_notification

# Import P2P admin to register P2P models
from . import p2p_admin  # noqa


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'rate_buy', 'rate_sell', 'is_active', 'created_at')
    list_filter = ('brand', 'is_active', 'created_at')
    search_fields = ('name', 'brand')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GiftCardOrder)
class GiftCardOrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'order_type', 'amount', 'status', 'created_at')
    list_filter = ('status', 'order_type', 'created_at')
    search_fields = ('user__email', 'card__name', 'card__brand')
    readonly_fields = ('created_at', 'updated_at', 'calculated_amount')
    fieldsets = (
        ('Order Information', {
            'fields': ('user', 'card', 'order_type', 'amount', 'calculated_amount', 'status')
        }),
        ('Proof', {
            'fields': ('proof_image',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'order_type', 'currency_pair', 'amount', 'price', 'total', 'status', 'created_at')
    list_filter = ('order_type', 'status', 'currency_pair', 'created_at')
    search_fields = ('user__email', 'currency_pair')
    readonly_fields = ('total', 'created_at', 'updated_at', 'completed_at')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('order', 'buyer', 'seller', 'amount', 'price', 'total', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('buyer__email', 'seller__email')


@admin.register(GiftCardListing)
class GiftCardListingAdmin(admin.ModelAdmin):
    list_display = ('reference', 'seller', 'card', 'gift_card_value', 'currency', 'asking_price_cedis', 'status', 'views_count', 'created_at')
    list_filter = ('status', 'card__brand', 'is_negotiable', 'created_at')
    search_fields = ('reference', 'seller__email', 'card__name', 'card__brand')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'views_count', 'reviewed_by', 'reviewed_at', 'proof_image_display')
    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'reference', 'card', 'status', 'views_count')
        }),
        ('Gift Card Details', {
            'fields': ('gift_card_code', 'gift_card_pin', 'gift_card_value', 'currency')
        }),
        ('Pricing', {
            'fields': ('asking_price_cedis', 'is_negotiable')
        }),
        ('Proof & Verification', {
            'fields': ('proof_image_display', 'proof_image', 'proof_notes')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'expires_at')
        }),
    )
    
    def proof_image_display(self, obj):
        if obj.proof_image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 200px; max-height: 200px;" /></a>',
                obj.proof_image.url,
                obj.proof_image.url
            )
        return "No proof image"
    proof_image_display.short_description = "Proof Image"
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'active' and not obj.reviewed_at:
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
                create_notification(
                    user=obj.seller,
                    notification_type='GIFT_CARD_LISTING_APPROVED',
                    title='Gift Card Listing Approved',
                    message=f'Your gift card listing {obj.reference} has been approved and is now active.',
                    related_object_type='gift_card_listing',
                    related_object_id=obj.id,
                )
        super().save_model(request, obj, form, change)


@admin.register(GiftCardTransaction)
class GiftCardTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'buyer', 'seller', 'listing', 'agreed_price_cedis', 'status', 'has_dispute', 'created_at')
    list_filter = ('status', 'has_dispute', 'buyer_verified', 'created_at')
    search_fields = ('reference', 'buyer__email', 'seller__email', 'listing__reference')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'completed_at', 'cancelled_at', 'card_provided_at', 'verified_at')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('reference', 'listing', 'buyer', 'seller', 'status', 'has_dispute')
        }),
        ('Financial Details', {
            'fields': ('agreed_price_cedis', 'escrow_amount_cedis')
        }),
        ('Gift Card Delivery', {
            'fields': ('gift_card_code', 'gift_card_pin', 'card_provided_at')
        }),
        ('Verification', {
            'fields': ('buyer_verified', 'buyer_verification_notes', 'verified_at')
        }),
        ('Dispute', {
            'fields': ('dispute_reason', 'dispute_resolved', 'dispute_resolution', 'dispute_resolved_by', 'dispute_resolved_at'),
            'classes': ('collapse',)
        }),
        ('Admin', {
            'fields': ('admin_notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GiftCardTransactionRating)
class GiftCardTransactionRatingAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_link', 'rater', 'rated_user', 'rating_display', 'is_visible', 'created_at')
    list_filter = ('rating', 'is_visible', 'created_at')
    search_fields = ('transaction__reference', 'rater__email', 'rated_user__email', 'comment')
    readonly_fields = ('created_at', 'updated_at', 'transaction_reference_display')
    list_per_page = 25
    
    fieldsets = (
        ('Rating Information', {
            'fields': ('transaction', 'transaction_reference_display', 'rater', 'rated_user', 'rating', 'comment', 'is_visible')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def transaction_link(self, obj):
        """Make transaction reference clickable"""
        if obj.transaction:
            url = f'/admin/orders/giftcardtransaction/{obj.transaction.id}/change/'
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.transaction.reference)
        return '-'
    transaction_link.short_description = 'Transaction'
    
    def transaction_reference_display(self, obj):
        """Display transaction reference"""
        if obj.transaction:
            return obj.transaction.reference
        return '-'
    transaction_reference_display.short_description = 'Transaction Reference'
    
    def rating_display(self, obj):
        """Display rating with stars"""
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        colors = {
            5: 'green',
            4: 'blue',
            3: 'orange',
            2: 'red',
            1: 'darkred'
        }
        color = colors.get(obj.rating, 'gray')
        return format_html(
            '<span style="color: {}; font-size: 16px; font-weight: bold;">{} ({})</span>',
            color, stars, obj.rating
        )
    rating_display.short_description = 'Rating'
    rating_display.admin_order_field = 'rating'


@admin.register(GiftCardDispute)
class GiftCardDisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_link', 'raised_by', 'dispute_type', 'status_badge', 'resolution_display', 'created_at', 'action_buttons')
    list_filter = ('status', 'dispute_type', 'resolution', 'created_at', 'resolved_at')
    search_fields = ('transaction__reference', 'raised_by__email', 'raised_by__first_name', 'raised_by__last_name', 'description', 'resolution_notes')
    readonly_fields = ('created_at', 'updated_at', 'resolved_by', 'resolved_at', 'transaction_details', 'transaction_summary', 'priority', 'fraud_indicators', 'verification_attempts', 'evidence_required', 'evidence_images_display', 'dispute_timeline_display')
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Dispute Information', {
            'fields': ('transaction', 'transaction_summary', 'transaction_details', 'raised_by', 'dispute_type', 'status', 'priority', 'assigned_to', 'fraud_indicators', 'verification_attempts')
        }),
        ('Dispute Details', {
            'fields': ('description', 'evidence_images_display'),
            'classes': ('wide',)
        }),
        ('Resolution', {
            'fields': ('resolution', 'resolution_notes', 'resolved_by', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def transaction_link(self, obj):
        """Make transaction reference clickable"""
        if obj.transaction:
            url = f'/admin/orders/giftcardtransaction/{obj.transaction.id}/change/'
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.transaction.reference)
        return '-'
    transaction_link.short_description = 'Transaction'
    transaction_link.admin_order_field = 'transaction__reference'
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'open': 'red',
            'under_review': 'orange',
            'resolved': 'green',
            'closed': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def resolution_display(self, obj):
        """Display resolution in a readable format"""
        if obj.resolution:
            return format_html(
                '<strong>{}</strong>',
                obj.get_resolution_display()
            )
        return format_html('<span style="color: #999;">-</span>')
    resolution_display.short_description = 'Resolution'
    resolution_display.admin_order_field = 'resolution'
    
    def transaction_summary(self, obj):
        """Show transaction summary information"""
        if obj.transaction:
            tx = obj.transaction
            return format_html(
                '<div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">'
                '<strong>Buyer:</strong> {}<br>'
                '<strong>Seller:</strong> {}<br>'
                '<strong>Amount:</strong> ₵{}<br>'
                '<strong>Status:</strong> {}'
                '</div>',
                tx.buyer.email if tx.buyer else '-',
                tx.seller.email if tx.seller else '-',
                tx.escrow_amount_cedis,
                tx.get_status_display()
            )
        return '-'
    transaction_summary.short_description = 'Transaction Summary'
    
    def transaction_details(self, obj):
        """Show detailed transaction information"""
        if obj.transaction:
            tx = obj.transaction
            gift_card_info = ''
            if tx.gift_card_code:
                gift_card_info = format_html(
                    '<br><strong>Gift Card Code:</strong> {}<br>'
                    '<strong>PIN:</strong> {}',
                    tx.gift_card_code,
                    tx.gift_card_pin if tx.gift_card_pin else 'N/A'
                )
            return format_html(
                '<div style="padding: 10px; background: #f0f9ff; border-radius: 5px; margin-top: 10px;">'
                '<strong>Reference:</strong> {}<br>'
                '<strong>Card:</strong> {} {}<br>'
                '<strong>Escrow Amount:</strong> ₵{}<br>'
                '<strong>Transaction Status:</strong> {}'
                '{}'
                '</div>',
                tx.reference,
                tx.listing.card.brand if tx.listing and tx.listing.card else '-',
                tx.listing.gift_card_value if tx.listing else '-',
                tx.escrow_amount_cedis,
                tx.get_status_display(),
                gift_card_info
            )
        return '-'
    transaction_details.short_description = 'Transaction Details'
    
    def evidence_images_display(self, obj):
        """Display evidence images as clickable thumbnails"""
        if not obj.evidence_images:
            return format_html('<span style="color: #999;">No evidence images uploaded</span>')
        
        images_html = []
        if isinstance(obj.evidence_images, list):
            for idx, img_url in enumerate(obj.evidence_images, 1):
                # Handle URL formatting - ensure it's a proper URL
                # URLs from database are like: "/media/dispute_evidence/3/..."
                if img_url.startswith('/media/'):
                    # Already correct format, use as-is
                    full_url = img_url
                elif img_url.startswith('http'):
                    # Full URL
                    full_url = img_url
                else:
                    # Prepend /media/ if not present
                    full_url = f"/media/{img_url.lstrip('/')}" if not img_url.startswith('/') else f"/media{img_url}"
                
                # Create thumbnail preview with clickable link
                images_html.append(
                    format_html(
                        '<div style="display: inline-block; margin: 10px; text-align: center; vertical-align: top; width: 220px;">'
                        '<a href="{}" target="_blank" style="display: block; text-decoration: none;">'
                        '<img src="{}" alt="Evidence {}" style="max-width: 200px; max-height: 200px; '
                        'width: auto; height: auto; border: 2px solid #ddd; border-radius: 5px; padding: 5px; '
                        'background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); '
                        'cursor: pointer; transition: transform 0.2s; object-fit: contain;" '
                        'onmouseover="this.style.transform=\'scale(1.05)\'; this.style.borderColor=\'#0066cc\'" '
                        'onmouseout="this.style.transform=\'scale(1)\'; this.style.borderColor=\'#ddd\'">'
                        '</a>'
                        '<p style="margin: 5px 0 2px 0; font-size: 11px; color: #666; font-weight: bold;">Evidence {}</p>'
                        '<a href="{}" target="_blank" style="font-size: 11px; color: #0066cc; text-decoration: underline;">View Full Size →</a>'
                        '</div>',
                        full_url, full_url, idx, idx, full_url
                    )
                )
        
        if images_html:
            return format_html(
                '<div style="padding: 10px; background: #f9f9f9; border-radius: 5px; margin-top: 10px;">'
                '<strong style="display: block; margin-bottom: 10px;">Evidence Images ({}):</strong>'
                '{}'
                '</div>',
                len(obj.evidence_images) if isinstance(obj.evidence_images, list) else 0,
                format_html(''.join(images_html))
            )
        return format_html('<span style="color: #999;">No evidence images uploaded</span>')
    evidence_images_display.short_description = 'Evidence Images'
    
    def dispute_timeline_display(self, obj):
        """Display dispute timeline/logs in admin"""
        logs = obj.logs.all().select_related('performed_by').order_by('created_at')
        
        if not logs.exists():
            return format_html('<span style="color: #999;">No logs available</span>')
        
        timeline_html = []
        for log in logs:
            user_str = log.performed_by.email if log.performed_by else 'System'
            user_name = log.performed_by.first_name + ' ' + log.performed_by.last_name if log.performed_by and (log.performed_by.first_name or log.performed_by.last_name) else user_str.split('@')[0] if log.performed_by else 'System'
            
            # Color code by action type
            action_colors = {
                'dispute_created': '#dc3545',
                'evidence_uploaded': '#17a2b8',
                'status_changed': '#ffc107',
                'assigned': '#6c757d',
                'comment_added': '#28a745',
                'resolution_finalized': '#007bff',
                'dispute_closed': '#6c757d',
            }
            color = action_colors.get(log.action, '#6c757d')
            
            # Format timestamp
            from django.utils import timezone
            time_str = timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M:%S')
            
            metadata_str = ''
            if log.metadata:
                metadata_items = []
                for key, value in log.metadata.items():
                    if key not in ['text_evidence']:  # Skip large text fields
                        metadata_items.append(f"{key}: {value}")
                if metadata_items:
                    metadata_str = format_html(
                        '<div style="font-size: 11px; color: #666; margin-top: 5px; padding-left: 20px;">{}</div>',
                        ' | '.join(metadata_items[:5])  # Limit to 5 items
                    )
            
            timeline_html.append(
                format_html(
                    '<div style="border-left: 3px solid {}; padding: 10px; margin: 10px 0; background: #f9f9f9; border-radius: 5px;">'
                    '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">'
                    '<strong style="color: {};">{}</strong>'
                    '<span style="font-size: 11px; color: #666;">{}</span>'
                    '</div>'
                    '<div style="font-size: 12px; color: #333; margin: 5px 0;">'
                    '<strong>By:</strong> {}'
                    '</div>'
                    '{}'
                    '{}'
                    '</div>',
                    color,
                    color,
                    log.get_action_display(),
                    time_str,
                    user_name,
                    format_html('<div style="margin-top: 5px; padding: 5px; background: white; border-radius: 3px; font-size: 12px;">{}</div>', log.comment) if log.comment else '',
                    metadata_str
                )
            )
        
        return format_html(
            '<div style="max-height: 600px; overflow-y: auto; padding: 10px; background: #f5f5f5; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Dispute Timeline ({} entries)</h3>'
            '{}'
            '</div>',
            logs.count(),
            format_html(''.join([str(h) for h in timeline_html]))
        )
    dispute_timeline_display.short_description = 'Dispute Timeline (Audit Log)'
    
    def action_buttons(self, obj):
        """Add action buttons for resolving disputes"""
        if obj.status in ['open', 'under_review']:
            return format_html(
                '<a href="/admin/orders/giftcarddispute/{}/change/" class="button" style="background: #28a745; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; font-size: 12px;">View & Resolve</a>',
                obj.id
            )
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">✓ Resolved</span>'
        )
    action_buttons.short_description = 'Actions'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'transaction', 
            'transaction__buyer', 
            'transaction__seller',
            'transaction__listing',
            'transaction__listing__card',
            'raised_by',
            'assigned_to',
            'resolved_by'
        ).prefetch_related('transaction__listing__card')
    
    def get_readonly_fields(self, request, obj=None):
        """Make more fields readonly when viewing resolved disputes"""
        readonly = list(self.readonly_fields)
        if obj and obj.status in ['resolved', 'closed']:
            readonly.extend(['status', 'resolution', 'resolution_notes', 'assigned_to', 'transaction', 'raised_by', 'dispute_type', 'description'])
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on dispute status"""
        fieldsets = list(self.fieldsets)
        if obj and obj.status in ['open', 'under_review']:
            # Add resolution section prominently for open disputes
            fieldsets = (
                ('Dispute Information', {
                    'fields': ('transaction', 'transaction_summary', 'transaction_details', 'raised_by', 'dispute_type', 'status', 'assigned_to')
                }),
                ('Dispute Details', {
                    'fields': ('description', 'evidence_images_display'),
                    'classes': ('wide',)
                }),
                ('⚠️ RESOLUTION (Required for Open/Under Review Disputes)', {
                    'fields': ('resolution', 'resolution_notes'),
                    'description': 'Select a resolution type and provide detailed notes. This will automatically process the escrow funds.'
                }),
                ('Resolution Tracking', {
                    'fields': ('resolved_by', 'resolved_at'),
                    'classes': ('collapse',)
                }),
                ('Timestamps', {
                    'fields': ('created_at', 'updated_at'),
                    'classes': ('collapse',)
                }),
            )
        return fieldsets
    
    def save_model(self, request, obj, form, change):
        """Handle dispute resolution when saving"""
        if change and obj.status in ['open', 'under_review']:
            # If resolution is set and dispute is being resolved
            if obj.resolution and not obj.resolved_by:
                from orders.views import resolve_dispute_helper
                
                try:
                    success, error_message = resolve_dispute_helper(
                        dispute=obj,
                        resolution=obj.resolution,
                        resolution_notes=obj.resolution_notes or 'Resolved via Django Admin',
                        resolved_by=request.user,
                        buyer_refund_amount=None,  # Can be added to admin form if needed
                        seller_amount=None  # Can be added to admin form if needed
                    )
                    
                    if success:
                        # Refresh from DB to get updated fields
                        obj.refresh_from_db()
                        self.message_user(request, f'Dispute {obj.id} resolved successfully! Funds processed.', level='SUCCESS')
                    else:
                        self.message_user(request, f'Error resolving dispute: {error_message}', level='ERROR')
                        # Don't save if resolution failed
                        return
                except Exception as e:
                    self.message_user(request, f'Error resolving dispute: {str(e)}', level='ERROR')
                    # Don't save if resolution failed
                    return
        
        super().save_model(request, obj, form, change)
    
    actions = ['mark_under_review', 'mark_resolved', 'assign_to_me']
    
    def mark_under_review(self, request, queryset):
        """Mark selected disputes as under review"""
        count = queryset.update(status='under_review', assigned_to=request.user)
        self.message_user(request, f'{count} dispute(s) marked as under review and assigned to you.')
    mark_under_review.short_description = 'Mark as Under Review & Assign to Me'
    
    def assign_to_me(self, request, queryset):
        """Assign selected disputes to current admin"""
        count = queryset.update(assigned_to=request.user, status='under_review')
        self.message_user(request, f'{count} dispute(s) assigned to you and marked as under review.')
    assign_to_me.short_description = 'Assign to Me & Mark Under Review'
    
    def mark_resolved(self, request, queryset):
        """Mark selected disputes as resolved (requires resolution)"""
        unresolved = queryset.filter(resolution='')
        if unresolved.exists():
            self.message_user(request, 'Cannot mark disputes as resolved without a resolution. Please set resolution first.', level='ERROR')
            return
        count = queryset.update(status='resolved', resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f'{count} dispute(s) marked as resolved.')
    mark_resolved.short_description = 'Mark selected disputes as Resolved'

