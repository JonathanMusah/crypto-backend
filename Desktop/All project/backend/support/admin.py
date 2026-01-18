from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import SupportTicket, SupportTicketResponse, ContactEnquiry, SpecialRequest, PayPalRequest, PayPalTransaction, PayPalPurchaseRequest, CashAppRequest, CashAppTransaction, CashAppPurchaseRequest, ZelleRequest, ZelleTransaction
from notifications.utils import create_notification


class SupportTicketResponseInline(admin.TabularInline):
    model = SupportTicketResponse
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'message', 'is_admin_response', 'created_at')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'user', 'category', 'status', 'priority', 'assigned_to', 'created_at', 'updated_at')
    list_filter = ('status', 'priority', 'category', 'created_at', 'assigned_to')
    search_fields = ('subject', 'message', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at', 'resolved_by')
    fieldsets = (
        ('Ticket Information', {
            'fields': ('user', 'subject', 'message', 'category', 'status', 'priority', 'assigned_to')
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolved_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [SupportTicketResponseInline]
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'resolved' and not obj.resolved_at:
                obj.resolved_at = timezone.now()
                obj.resolved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SupportTicketResponse)
class SupportTicketResponseAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'user', 'is_admin_response', 'created_at')
    list_filter = ('is_admin_response', 'created_at')
    search_fields = ('ticket__subject', 'message', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'phone_number', 'category', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'category', 'created_at', 'assigned_to')
    search_fields = ('subject', 'name', 'email', 'phone_number', 'message')
    readonly_fields = ('created_at', 'updated_at', 'responded_at')
    fieldsets = (
        ('Enquiry Information', {
            'fields': ('name', 'email', 'phone_number', 'subject', 'message', 'category', 'status', 'assigned_to', 'user')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'responded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'responded' and not obj.responded_at:
                obj.responded_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(SpecialRequest)
class SpecialRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'title', 'user', 'request_type', 'status', 'priority', 'estimated_amount', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'request_type', 'created_at', 'assigned_to')
    search_fields = ('reference', 'title', 'description', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'completed_at')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'request_type', 'title', 'description', 'status', 'priority')
        }),
        ('Financial Details', {
            'fields': ('estimated_amount', 'currency', 'quote_amount', 'quote_notes'),
            'classes': ('collapse',)
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'admin_notes', 'reviewed_by', 'reviewed_at', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status in ['approved', 'declined', 'quoted'] and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
            elif obj.status == 'completed' and not obj.completed_at:
                obj.completed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(PayPalRequest)
class PayPalRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'paypal_email', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'transaction_type', 'created_at', 'assigned_to')
    search_fields = ('reference', 'paypal_email', 'recipient_email', 'description', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'completed_at')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'status', 'priority')
        }),
        ('PayPal Details', {
            'fields': ('paypal_email', 'recipient_name', 'recipient_email', 'description')
        }),
        ('Financial Details', {
            'fields': ('quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes'),
            'classes': ('collapse',)
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'admin_notes', 'reviewed_by', 'reviewed_at', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status in ['approved', 'declined', 'quoted'] and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
            elif obj.status == 'completed' and not obj.completed_at:
                obj.completed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(PayPalTransaction)
class PayPalTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'amount_cedis_display', 'paypal_email', 'status', 'current_step', 'user_confirmed_balance_only', 'created_at')
    list_filter = ('status', 'transaction_type', 'current_step', 'user_confirmed_balance_only', 'created_at')
    search_fields = ('reference', 'paypal_email', 'payment_details', 'account_name', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at', 'verified_by', 'amount_cedis_display', 'exchange_rate_display', 'payment_proof_display')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'amount_cedis_display', 'exchange_rate_display', 'paypal_email', 'status', 'current_step')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_details', 'account_name', 'admin_paypal_email')
        }),
        ('Payment Proof', {
            'fields': ('payment_proof_display', 'payment_proof', 'payment_proof_notes', 'payment_sent_at'),
            'classes': ('collapse',)
        }),
        ('Financial Details', {
            'fields': ('exchange_rate', 'amount_cedis', 'service_fee'),
            'classes': ('collapse',)
        }),
        ('Security & Verification', {
            'fields': ('is_paypal_balance_only', 'user_confirmed_balance_only', 'payment_verified_at', 'verified_by'),
            'description': 'Important: Only PayPal balance is accepted. Bank transfers or third-party sources are not allowed.'
        }),
        ('Admin Management', {
            'fields': ('admin_notes', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_cedis_display(self, obj):
        """Display amount in cedis with currency symbol"""
        if obj.amount_cedis:
            return f"₵{obj.amount_cedis:,.2f}"
        return "-"
    amount_cedis_display.short_description = "Amount (GHS)"
    amount_cedis_display.admin_order_field = 'amount_cedis'
    
    def exchange_rate_display(self, obj):
        """Display exchange rate used"""
        if obj.exchange_rate:
            return f"₵{obj.exchange_rate:,.4f} per $1 USD"
        return "-"
    exchange_rate_display.short_description = "Exchange Rate"
    
    def payment_proof_display(self, obj):
        """Display payment proof image in admin"""
        if obj.payment_proof:
            # Check if it's an image file
            file_name = obj.payment_proof.name.lower()
            is_image = file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            
            if is_image:
                return format_html(
                    '<a href="{}" target="_blank" style="display: block; margin-bottom: 10px;"><img src="{}" style="max-width: 400px; max-height: 400px; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></a><a href="{}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 500;">🔗 Open in new tab</a>',
                    obj.payment_proof.url,
                    obj.payment_proof.url,
                    obj.payment_proof.url
                )
            else:
                # For PDFs or other files, show a download link
                return format_html(
                    '<a href="{}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">📄 View/Download Payment Proof</a>',
                    obj.payment_proof.url
                )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view)"

    def save_model(self, request, obj, form, change):
        """Save model and create notifications when status changes"""
        old_status = None
        if change:
            # Get the old status before saving
            try:
                old_obj = PayPalTransaction.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except PayPalTransaction.DoesNotExist:
                pass
            
            if 'status' in form.changed_data:
                if obj.status == 'payment_verified' and not obj.payment_verified_at:
                    obj.payment_verified_at = timezone.now()
                    obj.verified_by = request.user
                    obj.current_step = 'verified'
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_PAYMENT_VERIFIED',
                        title='Payment Verified',
                        message=f'Your payment for transaction {obj.reference} has been verified. Processing will begin shortly.',
                        related_object_type='paypal_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'completed' and not obj.completed_at:
                    obj.completed_at = timezone.now()
                    obj.current_step = 'completed'
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_TRANSACTION_COMPLETED',
                        title='Transaction Completed',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} has been completed.',
                        related_object_type='paypal_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'declined' and old_status != 'declined':
                    # Create notification for declined status
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_TRANSACTION_DECLINED',
                        title='Transaction Declined',
                        message=f'Your transaction {obj.reference} has been declined. {obj.admin_notes or "Please contact support for more information."}',
                        related_object_type='paypal_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'processing' and old_status not in ['processing', 'completed']:
                    # Create notification when transaction moves to processing
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_TRANSACTION_PROCESSING',
                        title='Transaction Processing',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} is now being processed.',
                        related_object_type='paypal_transaction',
                        related_object_id=obj.id,
                    )
        super().save_model(request, obj, form, change)


@admin.register(PayPalPurchaseRequest)
class PayPalPurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'item_name', 'user', 'amount_usd', 'amount_cedis_display', 'recipient_paypal_email', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'created_at', 'assigned_to')
    search_fields = ('reference', 'item_name', 'item_description', 'recipient_paypal_email', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'paid_at', 'purchased_at', 'completed_at', 'amount_cedis_display', 'exchange_rate_display', 'payment_proof_display')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'item_name', 'item_url', 'item_description', 'amount_usd', 'amount_cedis_display', 'exchange_rate_display', 'status', 'priority', 'urgency_reason')
        }),
        ('Recipient Details', {
            'fields': ('recipient_paypal_email', 'recipient_name', 'shipping_address')
        }),
        ('User Payment Details', {
            'fields': ('payment_method', 'payment_details', 'account_name')
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Purchase Tracking', {
            'fields': ('payment_proof_display', 'payment_proof', 'delivery_tracking', 'paid_at', 'purchased_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_cedis_display(self, obj):
        """Display amount in cedis with currency symbol"""
        if obj.quote_amount_cedis:
            return f"₵{obj.quote_amount_cedis:,.2f}"
        return "-"
    amount_cedis_display.short_description = "Quote Amount (GHS)"
    amount_cedis_display.admin_order_field = 'quote_amount_cedis'
    
    def exchange_rate_display(self, obj):
        """Display exchange rate used"""
        if obj.exchange_rate:
            return f"₵{obj.exchange_rate:,.4f} per $1 USD"
        return "-"
    exchange_rate_display.short_description = "Exchange Rate"
    
    def payment_proof_display(self, obj):
        """Display payment proof image in admin"""
        if obj.payment_proof:
            # Check if it's an image file
            file_name = obj.payment_proof.name.lower()
            is_image = file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            
            if is_image:
                return format_html(
                    '<a href="{}" target="_blank" style="display: block; margin-bottom: 10px;"><img src="{}" style="max-width: 400px; max-height: 400px; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></a><a href="{}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 500;">🔗 Open in new tab</a>',
                    obj.payment_proof.url,
                    obj.payment_proof.url,
                    obj.payment_proof.url
                )
            else:
                # For PDFs or other files, show a download link
                return format_html(
                    '<a href="{}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">📄 View/Download Payment Proof</a>',
                    obj.payment_proof.url
                )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view)"

    def save_model(self, request, obj, form, change):
        """Save model and create notifications when status changes"""
        old_status = None
        if change:
            # Get the old status before saving
            try:
                old_obj = PayPalPurchaseRequest.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except PayPalPurchaseRequest.DoesNotExist:
                pass
            
            if 'status' in form.changed_data:
                if obj.status == 'quoted' and not obj.reviewed_at:
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_PURCHASE_QUOTE_PROVIDED',
                        title='Purchase Request Quote Provided',
                        message=f'A quote has been provided for your purchase request "{obj.item_name}". Amount: ₵{obj.quote_amount_cedis or "TBD"}',
                        related_object_type='paypal_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'approved' and old_status != 'approved':
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_PURCHASE_APPROVED',
                        title='Purchase Request Approved',
                        message=f'Your purchase request for "{obj.item_name}" has been approved. Please proceed with payment.',
                        related_object_type='paypal_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'completed' and not obj.completed_at:
                    obj.completed_at = timezone.now()
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_PURCHASE_FULLY_COMPLETED',
                        title='Request Fully Completed',
                        message=f'Your purchase request for "{obj.item_name}" has been fully completed.',
                        related_object_type='paypal_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'declined' and old_status != 'declined':
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    # Create notification
                    create_notification(
                        user=obj.user,
                        notification_type='PAYPAL_PURCHASE_DECLINED',
                        title='Purchase Request Declined',
                        message=f'Your purchase request for "{obj.item_name}" has been declined. {obj.admin_notes or "Please contact support for more information."}',
                        related_object_type='paypal_purchase_request',
                        related_object_id=obj.id,
                    )
        super().save_model(request, obj, form, change)


# CashApp Admin Classes - Following the same pattern as PayPal
@admin.register(CashAppRequest)
class CashAppRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'cashapp_tag', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'transaction_type', 'priority', 'created_at', 'assigned_to')
    search_fields = ('reference', 'cashapp_tag', 'recipient_tag', 'description', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'completed_at')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'cashapp_tag', 'status', 'priority')
        }),
        ('Recipient Details (Send Only)', {
            'fields': ('recipient_name', 'recipient_tag'),
            'classes': ('collapse',)
        }),
        ('Transaction Details', {
            'fields': ('description',)
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved' and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
                create_notification(
                    user=obj.user,
                    notification_type='CASHAPP_REQUEST_APPROVED',
                    title='CashApp Request Approved',
                    message=f'Your CashApp request ({obj.get_transaction_type_display()}) for ${obj.amount_usd} has been approved.',
                    related_object_type='cashapp_request',
                    related_object_id=obj.id,
                )
            elif obj.status == 'declined' and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
                create_notification(
                    user=obj.user,
                    notification_type='CASHAPP_REQUEST_DECLINED',
                    title='CashApp Request Declined',
                    message=f'Your CashApp request ({obj.get_transaction_type_display()}) for ${obj.amount_usd} has been declined.',
                    related_object_type='cashapp_request',
                    related_object_id=obj.id,
                )
        super().save_model(request, obj, form, change)


@admin.register(CashAppTransaction)
class CashAppTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'amount_cedis_display', 'cashapp_tag', 'status', 'current_step', 'user_confirmed_balance_only', 'created_at')
    list_filter = ('status', 'transaction_type', 'current_step', 'user_confirmed_balance_only', 'created_at')
    search_fields = ('reference', 'cashapp_tag', 'payment_details', 'account_name', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at', 'verified_by', 'amount_cedis_display', 'exchange_rate_display', 'payment_proof_display')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'amount_cedis_display', 'exchange_rate_display', 'cashapp_tag', 'status', 'current_step')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_details', 'account_name', 'admin_cashapp_tag')
        }),
        ('Payment Proof', {
            'fields': ('payment_proof_display', 'payment_proof', 'payment_proof_notes', 'payment_sent_at'),
            'classes': ('collapse',)
        }),
        ('Financial Details', {
            'fields': ('exchange_rate', 'amount_cedis', 'service_fee'),
            'classes': ('collapse',)
        }),
        ('Security & Verification', {
            'fields': ('is_cashapp_balance_only', 'user_confirmed_balance_only', 'payment_verified_at', 'verified_by'),
            'description': 'Important: Only CashApp balance is accepted. Bank transfers or third-party sources are not allowed.'
        }),
        ('Admin Management', {
            'fields': ('admin_notes', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_cedis_display(self, obj):
        if obj.amount_cedis:
            return f"₵{obj.amount_cedis:,.2f}"
        return "-"
    amount_cedis_display.short_description = "Amount (GHS)"
    
    def exchange_rate_display(self, obj):
        if obj.exchange_rate:
            return f"₵{obj.exchange_rate:,.4f} per $1 USD"
        return "-"
    exchange_rate_display.short_description = "Exchange Rate"
    
    def payment_proof_display(self, obj):
        if obj.payment_proof:
            file_name = obj.payment_proof.name.lower()
            is_image = file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            
            if is_image:
                return format_html(
                    '<a href="{}" target="_blank" style="display: block; margin-bottom: 10px;"><img src="{}" style="max-width: 400px; max-height: 400px; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></a><a href="{}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 500;">🔗 Open in new tab</a>',
                    obj.payment_proof.url,
                    obj.payment_proof.url,
                    obj.payment_proof.url
                )
            else:
                return format_html(
                    '<a href="{}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">📄 View/Download Payment Proof</a>',
                    obj.payment_proof.url
                )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view)"

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            try:
                old_obj = CashAppTransaction.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except CashAppTransaction.DoesNotExist:
                pass
            
            if 'status' in form.changed_data:
                if obj.status == 'payment_verified' and not obj.payment_verified_at:
                    obj.payment_verified_at = timezone.now()
                    obj.verified_by = request.user
                    obj.current_step = 'verified'
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_PAYMENT_VERIFIED',
                        title='Payment Verified',
                        message=f'Your payment for transaction {obj.reference} has been verified. Processing will begin shortly.',
                        related_object_type='cashapp_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'completed' and not obj.completed_at:
                    obj.completed_at = timezone.now()
                    obj.current_step = 'completed'
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_TRANSACTION_COMPLETED',
                        title='Transaction Completed',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} has been completed.',
                        related_object_type='cashapp_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'declined' and old_status != 'declined':
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_TRANSACTION_DECLINED',
                        title='Transaction Declined',
                        message=f'Your transaction {obj.reference} has been declined. {obj.admin_notes or "Please contact support for more information."}',
                        related_object_type='cashapp_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'processing' and old_status not in ['processing', 'completed']:
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_TRANSACTION_PROCESSING',
                        title='Transaction Processing',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} is now being processed.',
                        related_object_type='cashapp_transaction',
                        related_object_id=obj.id,
                    )
        super().save_model(request, obj, form, change)


@admin.register(CashAppPurchaseRequest)
class CashAppPurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'item_name', 'user', 'amount_usd', 'amount_cedis_display', 'recipient_cashapp_tag', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'created_at', 'assigned_to')
    search_fields = ('reference', 'item_name', 'item_description', 'recipient_cashapp_tag', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'paid_at', 'purchased_at', 'completed_at', 'amount_cedis_display', 'exchange_rate_display', 'payment_proof_display')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'item_name', 'item_url', 'item_description', 'amount_usd', 'amount_cedis_display', 'exchange_rate_display', 'status', 'priority', 'urgency_reason')
        }),
        ('Recipient Details', {
            'fields': ('recipient_cashapp_tag', 'recipient_name', 'shipping_address')
        }),
        ('User Payment Details', {
            'fields': ('payment_method', 'payment_details', 'account_name')
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Purchase Tracking', {
            'fields': ('payment_proof_display', 'payment_proof', 'delivery_tracking', 'paid_at', 'purchased_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_cedis_display(self, obj):
        if obj.quote_amount_cedis:
            return f"₵{obj.quote_amount_cedis:,.2f}"
        return "-"
    amount_cedis_display.short_description = "Quote Amount (GHS)"
    
    def exchange_rate_display(self, obj):
        if obj.exchange_rate:
            return f"₵{obj.exchange_rate:,.4f} per $1 USD"
        return "-"
    exchange_rate_display.short_description = "Exchange Rate"
    
    def payment_proof_display(self, obj):
        if obj.payment_proof:
            file_name = obj.payment_proof.name.lower()
            is_image = file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            
            if is_image:
                return format_html(
                    '<a href="{}" target="_blank" style="display: block; margin-bottom: 10px;"><img src="{}" style="max-width: 400px; max-height: 400px; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></a><a href="{}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 500;">🔗 Open in new tab</a>',
                    obj.payment_proof.url,
                    obj.payment_proof.url,
                    obj.payment_proof.url
                )
            else:
                return format_html(
                    '<a href="{}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">📄 View/Download Payment Proof</a>',
                    obj.payment_proof.url
                )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view)"

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            try:
                old_obj = CashAppPurchaseRequest.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except CashAppPurchaseRequest.DoesNotExist:
                pass
            
            if 'status' in form.changed_data:
                if obj.status == 'quoted' and not obj.reviewed_at:
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_PURCHASE_QUOTE_PROVIDED',
                        title='Purchase Request Quote Provided',
                        message=f'A quote has been provided for your purchase request "{obj.item_name}". Amount: ₵{obj.quote_amount_cedis or "TBD"}',
                        related_object_type='cashapp_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'approved' and old_status != 'approved':
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_PURCHASE_APPROVED',
                        title='Purchase Request Approved',
                        message=f'Your purchase request for "{obj.item_name}" has been approved. Please proceed with payment.',
                        related_object_type='cashapp_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'completed' and not obj.completed_at:
                    obj.completed_at = timezone.now()
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_PURCHASE_FULLY_COMPLETED',
                        title='Request Fully Completed',
                        message=f'Your purchase request for "{obj.item_name}" has been fully completed.',
                        related_object_type='cashapp_purchase_request',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'declined' and old_status != 'declined':
                    obj.reviewed_at = timezone.now()
                    obj.reviewed_by = request.user
                    create_notification(
                        user=obj.user,
                        notification_type='CASHAPP_PURCHASE_DECLINED',
                        title='Purchase Request Declined',
                        message=f'Your purchase request for "{obj.item_name}" has been declined. {obj.admin_notes or "Please contact support for more information."}',
                        related_object_type='cashapp_purchase_request',
                        related_object_id=obj.id,
                    )
        super().save_model(request, obj, form, change)


# Zelle Admin Classes - Following the same pattern as PayPal and CashApp
@admin.register(ZelleRequest)
class ZelleRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'zelle_email', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'transaction_type', 'priority', 'created_at', 'assigned_to')
    search_fields = ('reference', 'zelle_email', 'recipient_email', 'description', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'completed_at')
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'zelle_email', 'status', 'priority')
        }),
        ('Recipient Details (Send Only)', {
            'fields': ('recipient_name', 'recipient_email'),
            'classes': ('collapse',)
        }),
        ('Transaction Details', {
            'fields': ('description',)
        }),
        ('Admin Management', {
            'fields': ('assigned_to', 'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved' and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
                create_notification(
                    user=obj.user,
                    notification_type='ZELLE_REQUEST_APPROVED',
                    title='Zelle Request Approved',
                    message=f'Your Zelle request ({obj.get_transaction_type_display()}) for ${obj.amount_usd} has been approved.',
                    related_object_type='zelle_request',
                    related_object_id=obj.id,
                )
            elif obj.status == 'declined' and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewed_by = request.user
                create_notification(
                    user=obj.user,
                    notification_type='ZELLE_REQUEST_DECLINED',
                    title='Zelle Request Declined',
                    message=f'Your Zelle request ({obj.get_transaction_type_display()}) for ${obj.amount_usd} has been declined.',
                    related_object_type='zelle_request',
                    related_object_id=obj.id,
                )
        super().save_model(request, obj, form, change)


@admin.register(ZelleTransaction)
class ZelleTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'user', 'amount_usd', 'amount_cedis_display', 'zelle_email', 'status', 'current_step', 'user_confirmed_balance_only', 'created_at')
    list_filter = ('status', 'transaction_type', 'current_step', 'user_confirmed_balance_only', 'created_at')
    search_fields = ('reference', 'zelle_email', 'payment_details', 'account_name', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at', 'verified_by', 'amount_cedis_display', 'exchange_rate_display', 'payment_proof_display')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('user', 'reference', 'transaction_type', 'amount_usd', 'amount_cedis_display', 'exchange_rate_display', 'zelle_email', 'status', 'current_step')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_details', 'account_name', 'admin_zelle_email')
        }),
        ('Payment Proof', {
            'fields': ('payment_proof_display', 'payment_proof', 'payment_proof_notes', 'payment_sent_at'),
            'classes': ('collapse',)
        }),
        ('Financial Details', {
            'fields': ('exchange_rate', 'amount_cedis', 'service_fee'),
            'classes': ('collapse',)
        }),
        ('Security & Verification', {
            'fields': ('is_zelle_balance_only', 'user_confirmed_balance_only', 'payment_verified_at', 'verified_by'),
            'description': 'Important: Only Zelle balance is accepted. Bank transfers or third-party sources are not allowed.'
        }),
        ('Admin Management', {
            'fields': ('admin_notes', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_cedis_display(self, obj):
        if obj.amount_cedis:
            return f"₵{obj.amount_cedis:,.2f}"
        return "-"
    amount_cedis_display.short_description = "Amount (GHS)"
    amount_cedis_display.admin_order_field = 'amount_cedis'
    
    def exchange_rate_display(self, obj):
        if obj.exchange_rate:
            return f"₵{obj.exchange_rate:,.4f} per $1 USD"
        return "-"
    exchange_rate_display.short_description = "Exchange Rate"
    
    def payment_proof_display(self, obj):
        if obj.payment_proof:
            file_name = obj.payment_proof.name.lower()
            is_image = file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            
            if is_image:
                return format_html(
                    '<a href="{}" target="_blank" style="display: block; margin-bottom: 10px;"><img src="{}" style="max-width: 400px; max-height: 400px; border: 2px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" /></a><a href="{}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 500;">🔗 Open in new tab</a>',
                    obj.payment_proof.url,
                    obj.payment_proof.url,
                    obj.payment_proof.url
                )
            else:
                return format_html(
                    '<a href="{}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #0066cc; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">📄 View/Download Payment Proof</a>',
                    obj.payment_proof.url
                )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view)"

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            try:
                old_obj = ZelleTransaction.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except ZelleTransaction.DoesNotExist:
                pass
            
            if 'status' in form.changed_data:
                if obj.status == 'payment_verified' and not obj.payment_verified_at:
                    obj.payment_verified_at = timezone.now()
                    obj.verified_by = request.user
                    obj.current_step = 'verified'
                    create_notification(
                        user=obj.user,
                        notification_type='ZELLE_PAYMENT_VERIFIED',
                        title='Payment Verified',
                        message=f'Your payment for transaction {obj.reference} has been verified. Processing will begin shortly.',
                        related_object_type='zelle_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'completed' and not obj.completed_at:
                    obj.completed_at = timezone.now()
                    obj.current_step = 'completed'
                    create_notification(
                        user=obj.user,
                        notification_type='ZELLE_TRANSACTION_COMPLETED',
                        title='Transaction Completed',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} has been completed.',
                        related_object_type='zelle_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'declined' and old_status != 'declined':
                    create_notification(
                        user=obj.user,
                        notification_type='ZELLE_TRANSACTION_DECLINED',
                        title='Transaction Declined',
                        message=f'Your transaction {obj.reference} has been declined. {obj.admin_notes or "Please contact support for more information."}',
                        related_object_type='zelle_transaction',
                        related_object_id=obj.id,
                    )
                elif obj.status == 'processing' and old_status not in ['processing', 'completed']:
                    create_notification(
                        user=obj.user,
                        notification_type='ZELLE_TRANSACTION_PROCESSING',
                        title='Transaction Processing',
                        message=f'Your {obj.get_transaction_type_display()} transaction {obj.reference} is now being processed.',
                        related_object_type='zelle_transaction',
                        related_object_id=obj.id,
                    )
        super().save_model(request, obj, form, change)
