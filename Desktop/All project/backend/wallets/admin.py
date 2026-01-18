from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db import transaction as db_transaction
from .models import Wallet, WalletTransaction, CryptoTransaction, AdminCryptoAddress, AdminPaymentDetails, Deposit, Withdrawal, WalletLog
from django import forms
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from notifications.utils import create_notification

# Import crypto P2P admin classes
try:
    from .crypto_p2p_admin import (
        CryptoListingAdmin,
        CryptoTransactionAdmin,
        CryptoTransactionAuditLogAdmin,
        CryptoTransactionDisputeAdmin
    )
except ImportError:
    pass  # Crypto P2P admin not yet available


class WithdrawalAdminForm(forms.ModelForm):
    """Custom form for Withdrawal admin to handle conditional field requirements"""
    
    class Meta:
        model = Withdrawal
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all conditional fields optional by default (only if they exist in the form)
        if 'momo_number' in self.fields:
            self.fields['momo_number'].required = False
        if 'momo_name' in self.fields:
            self.fields['momo_name'].required = False
        if 'momo_network' in self.fields:
            self.fields['momo_network'].required = False
        if 'crypto_id' in self.fields:
            self.fields['crypto_id'].required = False
        if 'crypto_amount' in self.fields:
            self.fields['crypto_amount'].required = False
        if 'network' in self.fields:
            self.fields['network'].required = False
        if 'crypto_address' in self.fields:
            self.fields['crypto_address'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        withdrawal_type = cleaned_data.get('withdrawal_type')
        
        if withdrawal_type == 'momo':
            if not cleaned_data.get('momo_number'):
                raise ValidationError({'momo_number': 'MoMo number is required for MoMo withdrawals.'})
            if not cleaned_data.get('momo_name'):
                raise ValidationError({'momo_name': 'MoMo name is required for MoMo withdrawals.'})
        elif withdrawal_type == 'crypto':
            if not cleaned_data.get('crypto_id'):
                raise ValidationError({'crypto_id': 'Crypto type is required for crypto withdrawals.'})
            if not cleaned_data.get('crypto_address'):
                raise ValidationError({'crypto_address': 'Crypto address is required for crypto withdrawals.'})
        
        return cleaned_data


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_cedis', 'balance_crypto', 'escrow_balance', 'created_at', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'currency', 'status', 'reference', 'created_at')
    list_filter = ('transaction_type', 'currency', 'status', 'created_at')
    search_fields = ('wallet__user__email', 'reference', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WalletLog)
class WalletLogAdmin(admin.ModelAdmin):
    """Admin interface for wallet activity logs"""
    list_display = ('user', 'log_type_display', 'amount_display', 'balance_after_display', 'transaction_id', 'timestamp')
    list_filter = ('log_type', 'timestamp')
    search_fields = ('user__email', 'transaction_id')
    readonly_fields = ('user', 'amount', 'log_type', 'transaction_id', 'balance_after', 'timestamp')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    list_per_page = 50
    
    fieldsets = (
        ('Activity Information', {
            'fields': ('user', 'log_type', 'amount', 'transaction_id', 'balance_after', 'timestamp')
        }),
    )
    
    def log_type_display(self, obj):
        """Display log type with color coding"""
        colors = {
            'deposit': '#28a745',
            'escrow_lock': '#ffc107',
            'escrow_release': '#17a2b8',
            'escrow_refund': '#dc3545',
            'withdrawal': '#6c757d',
            'admin_adjustment': '#6f42c1',
        }
        color = colors.get(obj.log_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color, obj.get_log_type_display().upper()
        )
    log_type_display.short_description = 'Type'
    log_type_display.admin_order_field = 'log_type'
    
    def amount_display(self, obj):
        """Display amount with color (green for positive, red for negative)"""
        color = '#28a745' if obj.log_type in ['deposit', 'escrow_release', 'escrow_refund'] else '#dc3545'
        sign = '+' if obj.log_type in ['deposit', 'escrow_release', 'escrow_refund'] else '-'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color, sign, f'₵{obj.amount:,.2f}'
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def balance_after_display(self, obj):
        """Display balance after"""
        return format_html(
            '<span style="font-weight: bold; color: #333;">₵{}</span>',
            f'{obj.balance_after:,.2f}'
        )
    balance_after_display.short_description = 'Balance After'
    balance_after_display.admin_order_field = 'balance_after'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user').order_by('-timestamp')


@admin.register(CryptoTransaction)
class CryptoTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'crypto_id', 'network', 'cedis_amount', 'crypto_amount', 'rate', 'status', 'escrow_locked', 'payment_method', 'reference', 'created_at')
    list_filter = ('type', 'status', 'payment_method', 'escrow_locked', 'crypto_id', 'network', 'created_at')
    search_fields = ('user__email', 'reference', 'admin_note', 'crypto_id', 'user_address', 'admin_address', 'momo_number', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at', 'payment_proof_display', 'transaction_id_display')
    fieldsets = (
        ('Transaction Info', {
            'fields': ('user', 'type', 'crypto_id', 'network', 'reference', 'payment_method', 'created_at', 'updated_at')
        }),
        ('Amounts', {
            'fields': ('cedis_amount', 'crypto_amount', 'rate')
        }),
        ('Addresses', {
            'fields': ('user_address', 'admin_address')
        }),
        ('MoMo Details (Sell)', {
            'fields': ('momo_number', 'momo_name')
        }),
        ('Sell Order Details', {
            'fields': ('transaction_id_display', 'transaction_id', 'payment_proof_display', 'payment_proof'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'escrow_locked', 'admin_note')
        }),
    )

    def payment_proof_display(self, obj):
        """Display payment proof image in admin"""
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" /></a>',
                obj.payment_proof.url,
                obj.payment_proof.url
            )
        return "No payment proof uploaded"
    payment_proof_display.short_description = "Payment Proof (Click to view full size)"

    def transaction_id_display(self, obj):
        """Display transaction ID in admin"""
        if obj.transaction_id:
            return format_html(
                '<code style="background: #f4f4f4; padding: 4px 8px; border-radius: 3px; font-family: monospace; display: block; word-break: break-all;">{}</code>',
                obj.transaction_id
            )
        return "No transaction ID"
    transaction_id_display.short_description = "Transaction ID/Hash"


class AdminCryptoAddressAdmin(admin.ModelAdmin):
    list_display = ('crypto_display', 'network_display', 'address_short', 'is_active', 'created_at', 'updated_at')
    list_filter = ('crypto_id', 'network', 'is_active', 'created_at')
    search_fields = ('crypto_id', 'network', 'address', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Address Information', {
            'fields': ('crypto_id', 'network', 'address', 'is_active'),
            'description': 'Select the crypto type and network from the dropdowns, then enter the address. Only active addresses are shown to users for deposits.'
        }),
        ('Notes', {
            'fields': ('notes',),
            'description': 'Optional internal notes about this address (not visible to users)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def crypto_display(self, obj):
        """Display crypto with icon"""
        return dict(AdminCryptoAddress.CRYPTO_CHOICES).get(obj.crypto_id, obj.crypto_id)
    crypto_display.short_description = "Crypto"
    
    def network_display(self, obj):
        """Display network name"""
        return dict(AdminCryptoAddress.NETWORK_CHOICES).get(obj.network, obj.network)
    network_display.short_description = "Network"
    
    def address_short(self, obj):
        """Display shortened address"""
        if len(obj.address) > 30:
            return f"{obj.address[:15]}...{obj.address[-10:]}"
        return obj.address
    address_short.short_description = "Address"


class AdminPaymentDetailsAdmin(admin.ModelAdmin):
    list_display = ('payment_type', 'momo_network', 'momo_number', 'momo_name', 'bank_name', 'account_number', 'is_active', 'created_at')
    list_filter = ('payment_type', 'momo_network', 'is_active', 'created_at')
    search_fields = ('momo_number', 'momo_name', 'bank_name', 'account_number', 'account_name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Payment Type', {
            'fields': ('payment_type', 'is_active')
        }),
        ('Mobile Money Details', {
            'fields': ('momo_network', 'momo_number', 'momo_name'),
            'description': 'Fill these fields if payment_type is Mobile Money'
        }),
        ('Bank Account Details', {
            'fields': ('bank_name', 'account_number', 'account_name', 'branch', 'swift_code'),
            'description': 'Fill these fields if payment_type is Bank Account'
        }),
        ('Instructions', {
            'fields': ('instructions',),
            'description': 'Additional instructions for users (e.g., "Include your email in the reference")'
        }),
        ('Internal Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('payment_type', 'momo_network', '-is_active')


class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'deposit_type', 'amount', 'crypto_amount', 'status', 'reference', 'momo_proof_display', 'crypto_proof_display', 'created_at')
    list_filter = ('deposit_type', 'status', 'momo_network', 'crypto_id', 'network', 'created_at')
    search_fields = ('user__email', 'reference', 'momo_transaction_id', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'reviewed_by', 'momo_proof_display', 'crypto_proof_display')
    actions = ['approve_deposits', 'reject_deposits']
    list_per_page = 100  # Show 100 deposits per page
    list_max_show_all = 500  # Allow showing up to 500 at once
    date_hierarchy = 'created_at'  # Add date hierarchy for easy navigation
    ordering = ('-created_at',)  # Order by newest first
    
    def get_queryset(self, request):
        """Ensure we get all deposits with optimized queries"""
        qs = super().get_queryset(request)
        # Use select_related to optimize user queries
        return qs.select_related('user', 'reviewed_by', 'admin_payment_detail').order_by('-created_at')
    fieldsets = (
        ('Deposit Info', {
            'fields': ('user', 'deposit_type', 'amount', 'status', 'reference', 'created_at', 'updated_at')
        }),
        ('MoMo Deposit Details', {
            'fields': ('admin_payment_detail', 'momo_network', 'momo_transaction_id', 'momo_proof', 'momo_proof_display'),
            'description': 'Admin payment details are stored in AdminPaymentDetails. User submitted transaction ID and proof.',
            'classes': ('collapse',)
        }),
        ('Crypto Deposit Details', {
            'fields': ('crypto_id', 'crypto_amount', 'network', 'transaction_id', 'crypto_proof', 'crypto_proof_display'),
            'classes': ('collapse',)
        }),
        ('Admin Review', {
            'fields': ('admin_note', 'reviewed_by', 'reviewed_at')
        }),
    )

    def approve_deposits(self, request, queryset):
        """Approve selected deposits"""
        from decimal import Decimal
        from rates.models import CryptoRate
        
        approved_count = 0
        for deposit in queryset:
            if deposit.status != 'awaiting_admin':
                continue
            
            try:
                with db_transaction.atomic():
                    wallet, created = Wallet.objects.get_or_create(user=deposit.user)
                    balance_before = wallet.balance_cedis

                    if deposit.deposit_type == 'momo':
                        amount = deposit.amount
                        wallet.add_cedis(amount)
                        wallet.refresh_from_db()  # Ensure we have the latest balance
                        balance_after = wallet.balance_cedis
                    else:  # crypto deposit
                        # Auto-calculate from crypto amount using current rate
                        crypto_rate = CryptoRate.get_latest_rate(deposit.crypto_id)
                        if crypto_rate:
                            amount = Decimal(str(deposit.crypto_amount)) * crypto_rate.cedis_price
                        else:
                            self.message_user(request, f'Deposit {deposit.reference}: Unable to get rate for {deposit.crypto_id}. Please approve manually.', level='error')
                            continue
                        deposit.amount = amount
                        wallet.add_cedis(amount)
                        balance_after = wallet.balance_cedis

                    # Create wallet transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='deposit',
                        amount=amount,
                        currency='cedis',
                        status='completed',
                        reference=deposit.reference,
                        description=f"Deposit via {deposit.deposit_type}. Ref: {deposit.reference}." + 
                                  (f" Crypto {deposit.crypto_amount} {deposit.crypto_id} converted to {amount} cedis" if deposit.deposit_type == 'crypto' else ""),
                        balance_before=balance_before,
                        balance_after=balance_after
                    )

                    # Update deposit
                    deposit.status = 'approved'
                    deposit.reviewed_by = request.user
                    deposit.reviewed_at = timezone.now()
                    deposit.save()

                    # Create notification
                    deposit_message = (
                        f'Your {deposit.deposit_type} deposit of ₵{amount} has been approved and credited to your wallet.'
                        if deposit.deposit_type == 'momo'
                        else f'Your crypto deposit of {deposit.crypto_amount} {deposit.crypto_id} has been converted to ₵{amount} and credited to your wallet.'
                    )
                    create_notification(
                        user=deposit.user,
                        notification_type='DEPOSIT_APPROVED',
                        title='Deposit Approved',
                        message=deposit_message,
                        related_object_type='deposit',
                        related_object_id=deposit.id,
                    )
                    
                    approved_count += 1
            except Exception as e:
                self.message_user(request, f'Error approving deposit {deposit.reference}: {str(e)}', level='error')
        
        self.message_user(request, f'Successfully approved {approved_count} deposit(s).')
    approve_deposits.short_description = "Approve selected deposits"

    def reject_deposits(self, request, queryset):
        """Reject selected deposits - requires admin note"""
        rejected_count = 0
        for deposit in queryset:
            if deposit.status != 'awaiting_admin':
                continue
            
            try:
                with db_transaction.atomic():
                    deposit.status = 'rejected'
                    deposit.reviewed_by = request.user
                    deposit.reviewed_at = timezone.now()
                    if not deposit.admin_note:
                        deposit.admin_note = 'Rejected via admin panel'
                    deposit.save()

                    # Create notification
                    create_notification(
                        user=deposit.user,
                        notification_type='DEPOSIT_REJECTED',
                        title='Deposit Rejected',
                        message=f'Your {deposit.deposit_type} deposit has been rejected. Reason: {deposit.admin_note}',
                        related_object_type='deposit',
                        related_object_id=deposit.id,
                    )
                    
                    rejected_count += 1
            except Exception as e:
                self.message_user(request, f'Error rejecting deposit {deposit.reference}: {str(e)}', level='error')
        
        self.message_user(request, f'Successfully rejected {rejected_count} deposit(s).')
    reject_deposits.short_description = "Reject selected deposits"

    def momo_proof_display(self, obj):
        """Display MoMo proof image in admin"""
        if obj.momo_proof:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" /></a>',
                obj.momo_proof.url,
                obj.momo_proof.url
            )
        return "No proof uploaded"
    momo_proof_display.short_description = "MoMo Proof (Click to view full size)"

    def crypto_proof_display(self, obj):
        """Display crypto proof image in admin"""
        if obj.crypto_proof:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 300px; border: 1px solid #ddd; border-radius: 4px;" /></a>',
                obj.crypto_proof.url,
                obj.crypto_proof.url
            )
        return "No proof uploaded"
    crypto_proof_display.short_description = "Crypto Proof (Click to view full size)"


class WithdrawalAdmin(admin.ModelAdmin):
    form = WithdrawalAdminForm
    list_display = ('user', 'withdrawal_type', 'amount', 'fee', 'total_amount', 'crypto_amount', 'status', 'reference', 'created_at')
    list_filter = ('withdrawal_type', 'status', 'momo_network', 'crypto_id', 'network', 'created_at')
    search_fields = ('user__email', 'reference', 'momo_number', 'crypto_address', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at', 'completed_at', 'reviewed_by', 'fee', 'total_amount')
    actions = ['approve_withdrawals', 'reject_withdrawals', 'complete_withdrawals']
    def get_fieldsets(self, request, obj=None):
        """Dynamically show fields based on withdrawal type"""
        fieldsets = (
            ('Withdrawal Info', {
                'fields': ('user', 'withdrawal_type', 'amount', 'fee', 'total_amount', 'status', 'reference', 'created_at', 'updated_at')
            }),
            ('Admin Review', {
                'fields': ('admin_note', 'transaction_id', 'reviewed_by', 'reviewed_at', 'completed_at')
            }),
        )
        
        # Add MoMo fields only if it's a MoMo withdrawal
        if obj and obj.withdrawal_type == 'momo':
            fieldsets = fieldsets + (
                ('MoMo Withdrawal Details', {
                    'fields': ('momo_number', 'momo_name', 'momo_network'),
                }),
            )
        elif not obj:  # For new objects, show both but make them optional
            fieldsets = fieldsets + (
                ('MoMo Withdrawal Details (Only for MoMo withdrawals)', {
                    'fields': ('momo_number', 'momo_name', 'momo_network'),
                    'classes': ('collapse',)
                }),
            )
        
        # Add Crypto fields only if it's a crypto withdrawal
        if obj and obj.withdrawal_type == 'crypto':
            fieldsets = fieldsets + (
                ('Crypto Withdrawal Details', {
                    'fields': ('crypto_id', 'crypto_amount', 'network', 'crypto_address'),
                }),
            )
        elif not obj:  # For new objects, show both but make them optional
            fieldsets = fieldsets + (
                ('Crypto Withdrawal Details (Only for Crypto withdrawals)', {
                    'fields': ('crypto_id', 'crypto_amount', 'network', 'crypto_address'),
                    'classes': ('collapse',)
                }),
            )
        
        return fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        """Make fee and total_amount readonly"""
        readonly = list(super().get_readonly_fields(request, obj))
        readonly.extend(['fee', 'total_amount'])
        return readonly
    
    def save_model(self, request, obj, form, change):
        """Override save to handle status changes from admin form"""
        if change and obj.pk:
            # Get the old status before saving
            old_obj = Withdrawal.objects.get(pk=obj.pk)
            old_status = old_obj.status
            new_status = obj.status
            
            # If status changed to 'rejected' from admin form (not through action)
            if old_status != 'rejected' and new_status == 'rejected':
                # Ensure required fields are set
                if not obj.admin_note:
                    obj.admin_note = 'Rejected via admin form'
                if not obj.reviewed_by:
                    obj.reviewed_by = request.user
                if not obj.reviewed_at:
                    from django.utils import timezone
                    obj.reviewed_at = timezone.now()
                
                # Manually trigger escrow release if signal doesn't fire
                # (Signal should handle it, but this is a safety net)
                try:
                    wallet, _ = Wallet.objects.get_or_create(user=obj.user)
                    # Use total_amount if available, otherwise use amount (for old withdrawals)
                    release_amount = obj.total_amount if obj.total_amount > 0 else obj.amount
                    
                    if release_amount > 0 and wallet.escrow_balance >= release_amount:
                        # Check if already released
                        existing_release = WalletTransaction.objects.filter(
                            reference__startswith=obj.reference,
                            transaction_type='escrow_release',
                            status='completed'
                        ).first()
                        
                        if not existing_release:
                            balance_before = wallet.balance_cedis
                            escrow_before = wallet.escrow_balance
                            wallet.release_cedis_from_escrow(release_amount)
                            wallet.refresh_from_db()
                            
                            import uuid
                            unique_ref = f"{obj.reference}-ADMIN-{uuid.uuid4().hex[:8]}"
                            WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type='escrow_release',
                                amount=release_amount,
                                currency='cedis',
                                status='completed',
                                reference=unique_ref,
                                description=f"Withdrawal rejected via admin form: {obj.amount:.2f} + {obj.fee:.2f} fee = {release_amount:.2f} cedis. Ref: {obj.reference}",
                                balance_before=balance_before,
                                balance_after=wallet.balance_cedis
                            )
                except Exception as e:
                    # Log error but don't prevent save
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error releasing escrow in save_model for {obj.reference}: {str(e)}")
        
        super().save_model(request, obj, form, change)

    def approve_withdrawals(self, request, queryset):
        """Approve selected withdrawals"""
        approved_count = 0
        for withdrawal in queryset:
            if withdrawal.status != 'awaiting_admin':
                continue
            
            try:
                with db_transaction.atomic():
                    wallet, created = Wallet.objects.get_or_create(user=withdrawal.user)

                    if withdrawal.withdrawal_type == 'momo':
                        # Deduct total amount from escrow (amount + fee were already locked)
                        balance_before = wallet.escrow_balance
                        wallet.deduct_from_escrow(withdrawal.total_amount)  # Deduct total (amount + fee)
                        balance_after = wallet.escrow_balance

                        # Create wallet transaction record
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='withdraw',
                            amount=withdrawal.total_amount,  # Total amount deducted (amount + fee)
                            currency='cedis',
                            status='completed',
                            reference=withdrawal.reference,
                            description=f"Withdrawal via MoMo to {withdrawal.momo_number}: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}",
                            balance_before=wallet.balance_cedis + balance_before,
                            balance_after=wallet.balance_cedis + balance_after
                        )
                    else:  # crypto
                        # Deduct total amount from escrow (cedis_amount + fee were locked when withdrawal was created)
                        # Platform is fiat-only: we convert cedis to crypto at current rate
                        escrow_before = wallet.escrow_balance
                        wallet.deduct_from_escrow(withdrawal.total_amount)  # Deduct total (cedis_amount + fee)
                        wallet.refresh_from_db()
                        escrow_after = wallet.escrow_balance

                        # Create wallet transaction record for withdrawal
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='withdraw',
                            amount=withdrawal.total_amount,  # Total amount deducted (cedis_amount + fee)
                            currency='cedis',
                            status='completed',
                            reference=withdrawal.reference,
                            description=f"Crypto withdrawal approved: {withdrawal.crypto_amount} {withdrawal.crypto_id.upper()} sent (₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f} deducted). Ref: {withdrawal.reference}. Admin: {request.user.email}",
                            balance_before=wallet.balance_cedis + escrow_before,
                            balance_after=wallet.balance_cedis + escrow_after
                        )

                    # Update withdrawal
                    withdrawal.status = 'approved'
                    withdrawal.reviewed_by = request.user
                    withdrawal.reviewed_at = timezone.now()
                    withdrawal.save()

                    # Create notification
                    create_notification(
                        user=withdrawal.user,
                        notification_type='WITHDRAWAL_APPROVED',
                        title='Withdrawal Approved',
                        message=f'Your {withdrawal.withdrawal_type} withdrawal of {withdrawal.amount if withdrawal.withdrawal_type == "momo" else withdrawal.crypto_amount} has been approved and will be processed shortly.',
                        related_object_type='withdrawal',
                        related_object_id=withdrawal.id,
                    )
                    
                    approved_count += 1
            except Exception as e:
                self.message_user(request, f'Error approving withdrawal {withdrawal.reference}: {str(e)}', level='error')
        
        self.message_user(request, f'Successfully approved {approved_count} withdrawal(s).')
    approve_withdrawals.short_description = "Approve selected withdrawals"

    def reject_withdrawals(self, request, queryset):
        """Reject selected withdrawals and return funds"""
        rejected_count = 0
        for withdrawal in queryset:
            if withdrawal.status != 'awaiting_admin':
                continue
            
            try:
                with db_transaction.atomic():
                    wallet, created = Wallet.objects.get_or_create(user=withdrawal.user)

                    if withdrawal.withdrawal_type == 'momo':
                        # Release total amount from escrow back to balance (amount + fee)
                        wallet.release_cedis_from_escrow(withdrawal.total_amount)

                        # Create wallet transaction record
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='escrow_release',
                            amount=withdrawal.total_amount,  # Release total (amount + fee)
                            currency='cedis',
                            status='completed',
                            reference=withdrawal.reference,
                            description=f"Withdrawal rejected, funds released from escrow: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}",
                            balance_before=wallet.balance_cedis - withdrawal.total_amount,
                            balance_after=wallet.balance_cedis
                        )
                    else:  # crypto
                        # Release total amount from escrow back to balance (cedis_amount + fee)
                        balance_before = wallet.balance_cedis
                        escrow_before = wallet.escrow_balance
                        wallet.release_cedis_from_escrow(withdrawal.total_amount)  # Release total (cedis_amount + fee)
                        wallet.refresh_from_db()
                        balance_after = wallet.balance_cedis
                        escrow_after = wallet.escrow_balance

                        # Create escrow release transaction
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type='escrow_release',
                            amount=withdrawal.total_amount,  # Release total (cedis_amount + fee)
                            currency='cedis',
                            status='completed',
                            reference=withdrawal.reference,
                            description=f"Crypto withdrawal rejected, funds released from escrow: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}. Reason: {withdrawal.admin_note or 'Rejected via admin panel'}",
                            balance_before=balance_before,
                            balance_after=balance_after
                        )

                    # Update withdrawal
                    withdrawal.status = 'rejected'
                    withdrawal.reviewed_by = request.user
                    withdrawal.reviewed_at = timezone.now()
                    if not withdrawal.admin_note:
                        withdrawal.admin_note = 'Rejected via admin panel'
                    withdrawal.save()

                    # Create notification
                    create_notification(
                        user=withdrawal.user,
                        notification_type='WITHDRAWAL_REJECTED',
                        title='Withdrawal Rejected',
                        message=f'Your {withdrawal.withdrawal_type} withdrawal has been rejected. Reason: {withdrawal.admin_note}. Funds have been returned to your wallet.',
                        related_object_type='withdrawal',
                        related_object_id=withdrawal.id,
                    )
                    
                    rejected_count += 1
            except Exception as e:
                self.message_user(request, f'Error rejecting withdrawal {withdrawal.reference}: {str(e)}', level='error')
        
        self.message_user(request, f'Successfully rejected {rejected_count} withdrawal(s).')
    reject_withdrawals.short_description = "Reject selected withdrawals"

    def complete_withdrawals(self, request, queryset):
        """Mark selected withdrawals as completed (after transfer is confirmed)"""
        completed_count = 0
        for withdrawal in queryset:
            if withdrawal.status != 'approved':
                continue
            
            try:
                withdrawal.status = 'completed'
                withdrawal.completed_at = timezone.now()
                withdrawal.save()

                # Create notification
                create_notification(
                    user=withdrawal.user,
                    notification_type='WITHDRAWAL_COMPLETED',
                    title='Withdrawal Completed',
                    message=f'Your {withdrawal.withdrawal_type} withdrawal has been completed. Transaction ID: {withdrawal.transaction_id or "N/A"}',
                    related_object_type='withdrawal',
                    related_object_id=withdrawal.id,
                )
                
                completed_count += 1
            except Exception as e:
                self.message_user(request, f'Error completing withdrawal {withdrawal.reference}: {str(e)}', level='error')
        
        self.message_user(request, f'Successfully marked {completed_count} withdrawal(s) as completed.')
    complete_withdrawals.short_description = "Mark as completed"

