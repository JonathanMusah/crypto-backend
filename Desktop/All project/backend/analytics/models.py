from django.db import models
from django.conf import settings
from decimal import Decimal


class Settings(models.Model):
    live_rate_source = models.CharField(max_length=255, default='coinmarketcap')
    escrow_percent = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    support_contacts = models.JSONField(default=dict, blank=True)
    
    # Withdrawal fees (stored in USD, converted to cedis when calculating)
    # MoMo withdrawal fees
    momo_withdrawal_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Percentage fee for MoMo withdrawals (e.g., 1.0 = 1%)")
    momo_withdrawal_fee_fixed_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fixed fee in USD for MoMo withdrawals (applied in addition to percentage)")
    momo_withdrawal_min_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.08, help_text="Minimum fee in USD for MoMo withdrawals")
    momo_withdrawal_max_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=4.00, help_text="Maximum fee in USD for MoMo withdrawals")
    
    # Crypto withdrawal fees
    crypto_withdrawal_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.5, help_text="Percentage fee for crypto withdrawals (e.g., 0.5 = 0.5%)")
    crypto_withdrawal_fee_fixed_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fixed fee in USD for crypto withdrawals (applied in addition to percentage)")
    crypto_withdrawal_min_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.16, help_text="Minimum fee in USD for crypto withdrawals")
    crypto_withdrawal_max_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=8.00, help_text="Maximum fee in USD for crypto withdrawals")
    
    # Feature flags
    gift_cards_enabled = models.BooleanField(default=True, help_text="Enable/disable gift card feature for users")
    special_requests_enabled = models.BooleanField(default=True, help_text="Enable/disable special requests feature for users")
    paypal_enabled = models.BooleanField(default=True, help_text="Enable/disable PayPal service feature for users")
    cashapp_enabled = models.BooleanField(default=True, help_text="Enable/disable CashApp service feature for users")
    zelle_enabled = models.BooleanField(default=True, help_text="Enable/disable Zelle service feature for users")
    
    # PayPal Exchange Rates (USD to GHS)
    paypal_sell_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('14.50'), 
        help_text="Rate for selling PayPal balance (1 USD = X GHS). What we pay users when they sell PayPal."
    )
    paypal_buy_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('15.00'), 
        help_text="Rate for buying PayPal balance (1 USD = X GHS). What users pay us when they buy PayPal."
    )
    
    # Admin PayPal Details (for Sell transactions - where users send PayPal to)
    admin_paypal_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Admin PayPal email/username where users should send PayPal funds when selling"
    )
    
    # Admin MoMo Details (for Buy transactions - where users send MoMo payment to)
    admin_momo_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Admin MoMo details for Buy PayPal transactions (MTN, Vodafone, etc.)"
    )
    
    # PayPal Transaction Fees (USD) and Rates
    paypal_transaction_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Percentage fee for PayPal Buy/Sell transactions (e.g., 1.0 = 1%)")
    paypal_transaction_fixed_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fixed fee in USD for PayPal Buy/Sell transactions")
    paypal_transaction_min_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.08, help_text="Minimum fee in USD for PayPal Buy/Sell transactions")
    paypal_transaction_max_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=4.00, help_text="Maximum fee in USD for PayPal Buy/Sell transactions")
    
    # CashApp Exchange Rates (USD to GHS)
    cashapp_sell_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('14.50'), 
        help_text="Rate for selling CashApp balance (1 USD = X GHS). What we pay users when they sell CashApp."
    )
    cashapp_buy_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('15.00'), 
        help_text="Rate for buying CashApp balance (1 USD = X GHS). What users pay us when they buy CashApp."
    )
    
    # Admin CashApp Details (for Sell transactions - where users send CashApp to)
    admin_cashapp_tag = models.CharField(
        max_length=100,
        blank=True, 
        null=True,
        help_text="Admin CashApp $tag where users should send CashApp funds when selling"
    )
    
    # CashApp Transaction Fees (USD) and Rates
    cashapp_transaction_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Percentage fee for CashApp Buy/Sell transactions (e.g., 1.0 = 1%)")
    cashapp_transaction_fixed_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fixed fee in USD for CashApp Buy/Sell transactions")
    cashapp_transaction_min_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.08, help_text="Minimum fee in USD for CashApp Buy/Sell transactions")
    cashapp_transaction_max_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=4.00, help_text="Maximum fee in USD for CashApp Buy/Sell transactions")
    
    # Zelle Exchange Rates (USD to GHS)
    zelle_sell_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('14.50'), 
        help_text="Rate for selling Zelle balance (1 USD = X GHS). What we pay users when they sell Zelle."
    )
    zelle_buy_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=Decimal('15.00'), 
        help_text="Rate for buying Zelle balance (1 USD = X GHS). What users pay us when they buy Zelle."
    )
    
    # Admin Zelle Details (for Sell transactions - where users send Zelle to)
    admin_zelle_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Admin Zelle email/phone where users should send Zelle funds when selling"
    )
    
    # Zelle Transaction Fees (USD) and Rates
    zelle_transaction_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Percentage fee for Zelle Buy/Sell transactions (e.g., 1.0 = 1%)")
    zelle_transaction_fixed_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fixed fee in USD for Zelle Buy/Sell transactions")
    zelle_transaction_min_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.08, help_text="Minimum fee in USD for Zelle Buy/Sell transactions")
    zelle_transaction_max_fee_usd = models.DecimalField(max_digits=10, decimal_places=2, default=4.00, help_text="Maximum fee in USD for Zelle Buy/Sell transactions")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'settings'
        verbose_name_plural = 'Settings'
    
    def __str__(self):
        return f"Platform Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    def get_usd_to_cedis_rate(self):
        """Get current USD to Cedis exchange rate"""
        from rates.models import CryptoRate
        # Use a stable coin or get from settings
        # For now, use a default rate or get from latest crypto rate
        try:
            # Try to get rate from tether or usd-coin
            rate = CryptoRate.get_latest_rate('tether') or CryptoRate.get_latest_rate('usd-coin')
            if rate and rate.usd_to_cedis_rate:
                return rate.usd_to_cedis_rate
        except:
            pass
        # Default fallback rate
        return Decimal('12.50')
    
    def calculate_momo_withdrawal_fee(self, amount):
        """Calculate MoMo withdrawal fee in cedis (fees stored in USD)"""
        from decimal import Decimal
        from rates.models import CryptoRate
        
        amount = Decimal(str(amount))
        usd_to_cedis = self.get_usd_to_cedis_rate()
        
        # Convert amount to USD for fee calculation
        amount_usd = amount / usd_to_cedis
        
        # Calculate percentage fee in USD
        percent_fee_usd = amount_usd * (self.momo_withdrawal_fee_percent / Decimal('100'))
        
        # Add fixed fee in USD
        total_fee_usd = percent_fee_usd + self.momo_withdrawal_fee_fixed_usd
        
        # Apply min/max limits in USD
        if total_fee_usd < self.momo_withdrawal_min_fee_usd:
            total_fee_usd = self.momo_withdrawal_min_fee_usd
        elif total_fee_usd > self.momo_withdrawal_max_fee_usd:
            total_fee_usd = self.momo_withdrawal_max_fee_usd
        
        # Convert back to cedis
        total_fee_cedis = total_fee_usd * usd_to_cedis
        
        return total_fee_cedis
    
    def calculate_crypto_withdrawal_fee(self, cedis_amount):
        """Calculate crypto withdrawal fee in cedis (fees stored in USD)"""
        from decimal import Decimal
        from rates.models import CryptoRate
        
        cedis_amount = Decimal(str(cedis_amount))
        usd_to_cedis = self.get_usd_to_cedis_rate()
        
        # Convert amount to USD for fee calculation
        amount_usd = cedis_amount / usd_to_cedis
        
        # Calculate percentage fee in USD
        percent_fee_usd = amount_usd * (self.crypto_withdrawal_fee_percent / Decimal('100'))
        
        # Add fixed fee in USD
        total_fee_usd = percent_fee_usd + self.crypto_withdrawal_fee_fixed_usd
        
        # Apply min/max limits in USD
        if total_fee_usd < self.crypto_withdrawal_min_fee_usd:
            total_fee_usd = self.crypto_withdrawal_min_fee_usd
        elif total_fee_usd > self.crypto_withdrawal_max_fee_usd:
            total_fee_usd = self.crypto_withdrawal_max_fee_usd
        
        # Convert back to cedis
        total_fee_cedis = total_fee_usd * usd_to_cedis
        
        return total_fee_cedis


class AnalyticsEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('PAGE_VIEW', 'Page View'),
        ('BUTTON_CLICK', 'Button Click'),
        ('FORM_SUBMIT', 'Form Submit'),
        ('TRADE_EXECUTED', 'Trade Executed'),
        ('WALLET_CREATED', 'Wallet Created'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    event_name = models.CharField(max_length=255)
    properties = models.JSONField(default=dict, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.event_name}"


class UserMetric(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='metrics')
    total_trades = models.IntegerField(default=0)
    total_volume = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_profit = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    last_trade_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_metrics'

    def __str__(self):
        return f"{self.user.email} - Metrics"

