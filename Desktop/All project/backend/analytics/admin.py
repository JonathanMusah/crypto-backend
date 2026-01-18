from django.contrib import admin
from .models import Settings, AnalyticsEvent, UserMetric
from .forms import SettingsAdminForm


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    form = SettingsAdminForm
    list_display = ('live_rate_source', 'escrow_percent', 'momo_withdrawal_fee_percent', 'crypto_withdrawal_fee_percent', 'updated_at')
    readonly_fields = ('updated_at',)
    
    def has_add_permission(self, request):
        """Prevent adding new Settings records - only allow editing existing one"""
        if not Settings.objects.exists():
            return True  # Allow creating if none exists
        return False  # Prevent adding if one already exists
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting Settings record"""
        return False
    
    def save_model(self, request, obj, form, change):
        """Ensure support_contacts has a default dict if empty and enforce singleton"""
        if not obj.support_contacts:
            obj.support_contacts = {}
        
        # Always enforce singleton pattern - use pk=1
        existing = Settings.objects.filter(pk=1).first()
        
        if not change and existing:
            # Trying to create new but one exists - update existing instead
            for field in obj._meta.fields:
                if field.name not in ['id', 'created_at', 'updated_at']:
                    setattr(existing, field.name, getattr(obj, field.name))
            existing.save()
            return
        
        # Clean up any duplicates before saving
        if change:
            # Delete any other Settings records (duplicates)
            Settings.objects.exclude(pk=obj.pk).delete()
            # Ensure we're using pk=1
            if obj.pk != 1:
                obj.pk = 1
                obj.save()
                return
        
        # New record - set pk to 1 and delete any existing
        Settings.objects.exclude(pk=1).delete()
        obj.pk = 1
        super().save_model(request, obj, form, change)
    
    fieldsets = (
        ('General Settings', {
            'fields': ('live_rate_source', 'escrow_percent', 'support_contacts')
        }),
            ('Feature Flags', {
                'fields': ('gift_cards_enabled', 'special_requests_enabled', 'paypal_enabled', 'cashapp_enabled', 'zelle_enabled'),
                'description': 'Enable or disable features for users. When disabled, users will see a message explaining the feature is unavailable.'
            }),
            ('PayPal Exchange Rates', {
                'fields': ('paypal_sell_rate', 'paypal_buy_rate'),
                'description': 'PayPal exchange rates (USD to GHS). Sell rate: What we pay users when they sell PayPal. Buy rate: What users pay us when they buy PayPal.'
            }),
            ('PayPal Admin Details', {
                'fields': ('admin_paypal_email', 'admin_momo_details'),
                'description': 'Admin payment details for PayPal transactions. PayPal email for Sell transactions (where users send PayPal). MoMo details for Buy transactions (where users send MoMo payment).'
            }),
            ('PayPal Transaction Fees (USD)', {
                'fields': ('paypal_transaction_fee_percent', 'paypal_transaction_fixed_fee_usd', 'paypal_transaction_min_fee_usd', 'paypal_transaction_max_fee_usd'),
                'description': 'Fees for PayPal Buy/Sell transactions.'
            }),
            ('CashApp Exchange Rates', {
                'fields': ('cashapp_sell_rate', 'cashapp_buy_rate'),
                'description': 'CashApp exchange rates (USD to GHS). Sell rate: What we pay users when they sell CashApp. Buy rate: What users pay us when they buy CashApp.'
            }),
            ('CashApp Admin Details', {
                'fields': ('admin_cashapp_tag',),
                'description': 'Admin CashApp $tag for Sell transactions (where users send CashApp). MoMo details for Buy transactions are shared with PayPal (admin_momo_details).'
            }),
            ('CashApp Transaction Fees (USD)', {
                'fields': ('cashapp_transaction_fee_percent', 'cashapp_transaction_fixed_fee_usd', 'cashapp_transaction_min_fee_usd', 'cashapp_transaction_max_fee_usd'),
                'description': 'Fees for CashApp Buy/Sell transactions.'
            }),
            ('Zelle Exchange Rates', {
                'fields': ('zelle_sell_rate', 'zelle_buy_rate'),
                'description': 'Zelle exchange rates (USD to GHS). Sell rate: What we pay users when they sell Zelle. Buy rate: What users pay us when they buy Zelle.'
            }),
            ('Zelle Admin Details', {
                'fields': ('admin_zelle_email',),
                'description': 'Admin Zelle email/phone for Sell transactions (where users send Zelle). MoMo details for Buy transactions are shared with PayPal (admin_momo_details).'
            }),
            ('Zelle Transaction Fees (USD)', {
                'fields': ('zelle_transaction_fee_percent', 'zelle_transaction_fixed_fee_usd', 'zelle_transaction_min_fee_usd', 'zelle_transaction_max_fee_usd'),
                'description': 'Fees for Zelle Buy/Sell transactions.'
            }),
        ('MoMo Withdrawal Fees (USD)', {
            'fields': (
                'momo_withdrawal_fee_percent',
                'momo_withdrawal_fee_fixed_usd',
                'momo_withdrawal_min_fee_usd',
                'momo_withdrawal_max_fee_usd',
            ),
            'description': 'MoMo withdrawal fees are stored in USD and calculated as: (amount_usd × percentage) + fixed_fee_usd, then clamped between min_usd and max_usd, then converted to cedis using current exchange rate.'
        }),
        ('Crypto Withdrawal Fees (USD)', {
            'fields': (
                'crypto_withdrawal_fee_percent',
                'crypto_withdrawal_fee_fixed_usd',
                'crypto_withdrawal_min_fee_usd',
                'crypto_withdrawal_max_fee_usd',
            ),
            'description': 'Crypto withdrawal fees are stored in USD and calculated on the cedis equivalent amount: (cedis_amount_usd × percentage) + fixed_fee_usd, then clamped between min_usd and max_usd, then converted to cedis using current exchange rate.'
        }),
    )


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'event_name', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('event_name', 'user__email')
    readonly_fields = ('created_at',)


@admin.register(UserMetric)
class UserMetricAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_trades', 'total_volume', 'total_profit', 'last_trade_at')
    search_fields = ('user__email',)
    readonly_fields = ('updated_at',)

