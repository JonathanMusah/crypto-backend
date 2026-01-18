from django.db import models, transaction as db_transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F
from decimal import Decimal
import uuid


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance_cedis = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    balance_crypto = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    escrow_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    version = models.IntegerField(default=0)  # ✅ Optimistic locking for concurrent updates
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'

    def __str__(self):
        return f"{self.user.email} - Wallet"

    def has_sufficient_cedis(self, amount):
        """Check if wallet has sufficient cedis balance"""
        return self.balance_cedis >= Decimal(str(amount))

    def has_sufficient_crypto(self, amount):
        """Check if wallet has sufficient crypto balance"""
        return self.balance_crypto >= Decimal(str(amount))

    @db_transaction.atomic
    def lock_cedis_to_escrow_atomic(self, amount):
        """✅ ATOMIC: Lock cedis to escrow using database-level operations"""
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        
        # Database-level atomic update with conditional check
        updated_rows = Wallet.objects.filter(
            user=self.user,
            version=self.version,
            balance_cedis__gte=amount  # Check balance at DB level
        ).update(
            balance_cedis=F('balance_cedis') - amount,
            escrow_balance=F('escrow_balance') + amount,
            version=F('version') + 1  # Increment for optimistic locking
        )
        
        if updated_rows == 0:
            self.refresh_from_db()
            if self.balance_cedis < amount:
                raise ValidationError(f"Insufficient cedis balance. Have: {self.balance_cedis}, Need: {amount}")
            else:
                raise ValidationError("Transaction conflict. Please retry.")
        
        self.refresh_from_db()

    @db_transaction.atomic
    def release_cedis_from_escrow_atomic(self, amount):
        """✅ ATOMIC: Release cedis from escrow to balance"""
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        
        updated_rows = Wallet.objects.filter(
            user=self.user,
            version=self.version,
            escrow_balance__gte=amount
        ).update(
            escrow_balance=F('escrow_balance') - amount,
            balance_cedis=F('balance_cedis') + amount,
            version=F('version') + 1
        )
        
        if updated_rows == 0:
            self.refresh_from_db()
            if self.escrow_balance < amount:
                raise ValidationError(f"Insufficient escrow balance. Have: {self.escrow_balance}, Need: {amount}")
            else:
                raise ValidationError("Transaction conflict. Please retry.")
        
        self.refresh_from_db()

    @db_transaction.atomic
    def deduct_from_escrow_atomic(self, amount):
        """✅ ATOMIC: Deduct amount from escrow"""
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        
        updated_rows = Wallet.objects.filter(
            user=self.user,
            version=self.version,
            escrow_balance__gte=amount
        ).update(
            escrow_balance=F('escrow_balance') - amount,
            version=F('version') + 1
        )
        
        if updated_rows == 0:
            self.refresh_from_db()
            raise ValidationError("Insufficient escrow balance or transaction conflict")
        
        self.refresh_from_db()

    @db_transaction.atomic
    def add_cedis_atomic(self, amount):
        """✅ ATOMIC: Add cedis to wallet"""
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        
        Wallet.objects.filter(user=self.user).update(
            balance_cedis=F('balance_cedis') + amount,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        self.refresh_from_db()

    @db_transaction.atomic
    def deduct_cedis_atomic(self, amount):
        """✅ ATOMIC: Deduct cedis from wallet"""
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        
        updated_rows = Wallet.objects.filter(
            user=self.user,
            version=self.version,
            balance_cedis__gte=amount
        ).update(
            balance_cedis=F('balance_cedis') - amount,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        
        if updated_rows == 0:
            self.refresh_from_db()
            raise ValidationError("Insufficient balance or transaction conflict")
        
        self.refresh_from_db()

    # Keep old methods for backward compatibility (deprecated)
    def lock_cedis_to_escrow(self, amount):
        """Deprecated: Use lock_cedis_to_escrow_atomic instead"""
        return self.lock_cedis_to_escrow_atomic(amount)

    def release_cedis_from_escrow(self, amount):
        """Deprecated: Use release_cedis_from_escrow_atomic instead"""
        return self.release_cedis_from_escrow_atomic(amount)

    def deduct_from_escrow(self, amount):
        """Deprecated: Use deduct_from_escrow_atomic instead"""
        return self.deduct_from_escrow_atomic(amount)

    def add_crypto(self, amount):
        """Add crypto to wallet"""
        self.balance_crypto += Decimal(str(amount))
        self.save()

    def deduct_crypto(self, amount):
        """Deduct crypto from wallet"""
        amount = Decimal(str(amount))
        if not self.has_sufficient_crypto(amount):
            raise ValidationError("Insufficient crypto balance")
        self.balance_crypto -= amount
        self.save()

    def add_cedis(self, amount):
        """Deprecated: Use add_cedis_atomic instead"""
        return self.add_cedis_atomic(amount)


class WalletLog(models.Model):
    """
    Comprehensive wallet activity log for audit and user tracking
    """
    LOG_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('escrow_lock', 'Escrow Lock'),
        ('escrow_release', 'Escrow Release'),
        ('escrow_refund', 'Escrow Refund'),
        ('withdrawal', 'Withdrawal'),
        ('admin_adjustment', 'Admin Adjustment'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_logs', db_index=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount involved in this activity")
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, db_index=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True, help_text="Optional reference to related transaction")
    balance_after = models.DecimalField(max_digits=20, decimal_places=2, help_text="Wallet balance after this activity")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'wallet_logs'
        ordering = ['-timestamp']
        verbose_name = 'Wallet Activity Log'
        verbose_name_plural = 'Wallet Activity Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['log_type', '-timestamp']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_log_type_display()} - ₵{self.amount} at {self.timestamp}"


class WalletTransaction(models.Model):
    """Track all wallet balance changes"""
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('escrow_lock', 'Escrow Lock'),
        ('escrow_release', 'Escrow Release'),
        ('crypto_buy', 'Crypto Buy'),
        ('crypto_sell', 'Crypto Sell'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default='cedis')  # cedis or crypto
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    balance_before = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.wallet.user.email} - {self.transaction_type} - {self.reference}"

    @classmethod
    def generate_reference(cls, prefix='TXN'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class Deposit(models.Model):
    """Internal wallet deposits - MoMo and Crypto"""
    DEPOSIT_TYPE_CHOICES = [
        ('momo', 'Mobile Money'),
        ('crypto', 'Crypto'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_admin', 'Awaiting Admin Confirmation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    MOMO_NETWORK_CHOICES = [
        ('MTN', 'MTN Mobile Money'),
        ('Vodafone', 'Vodafone Cash'),
        ('AirtelTigo', 'AirtelTigo Money'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposits')
    deposit_type = models.CharField(max_length=10, choices=DEPOSIT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=255, unique=True)
    
    # Reference to admin payment detail used (optional, for tracking)
    admin_payment_detail = models.ForeignKey('AdminPaymentDetails', on_delete=models.SET_NULL, null=True, blank=True, related_name='deposits', help_text="Admin payment detail used for this deposit")
    
    # MoMo deposit fields - Admin's payment details are in AdminPaymentDetails model
    # These fields store which admin payment was used and user's transaction proof
    momo_network = models.CharField(max_length=20, choices=MOMO_NETWORK_CHOICES, blank=True, help_text="Mobile Money network used (from admin payment details)")
    momo_transaction_id = models.CharField(max_length=255, blank=True, help_text="Transaction ID from MoMo transfer (user's payment proof)")
    momo_proof = models.ImageField(upload_to='deposits/momo_proofs/', blank=True, null=True, help_text="Screenshot of MoMo transaction (user's payment proof)")
    
    # Crypto deposit fields
    crypto_id = models.CharField(max_length=50, blank=True, help_text="Crypto type (e.g., bitcoin, ethereum)")
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Amount in crypto")
    network = models.CharField(max_length=20, blank=True, help_text="Network (e.g., TRC20, ERC20, BEP20)")
    transaction_id = models.CharField(max_length=255, blank=True, help_text="Transaction ID/hash from crypto transfer")
    crypto_proof = models.ImageField(upload_to='deposits/crypto_proofs/', blank=True, null=True, help_text="Screenshot of crypto transaction")
    
    # Admin fields
    admin_note = models.TextField(blank=True, help_text="Admin notes about this deposit")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_deposits')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'deposits'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.deposit_type} - {self.reference}"

    @classmethod
    def generate_reference(cls, prefix='DEP'):
        """Generate unique deposit reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class CryptoTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_admin', 'Awaiting Admin Confirmation'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('momo', 'Mobile Money'),
        ('bank', 'Bank Transfer'),
        ('crypto', 'Crypto'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crypto_transactions')
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    crypto_id = models.CharField(max_length=50, blank=True)  # e.g., 'bitcoin', 'ethereum'
    network = models.CharField(max_length=20, blank=True)  # e.g., 'TRC20', 'ERC20', 'BEP20'
    cedis_amount = models.DecimalField(max_digits=20, decimal_places=2)
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8)
    rate = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=255, unique=True)
    escrow_locked = models.BooleanField(default=False)
    admin_note = models.TextField(blank=True)
    # For BUY orders: user's crypto address where they want to receive
    user_address = models.CharField(max_length=255, blank=True)
    # For SELL orders: admin's receiving address + user's MoMo details
    admin_address = models.CharField(max_length=255, blank=True)
    momo_number = models.CharField(max_length=20, blank=True)
    momo_name = models.CharField(max_length=255, blank=True)
    # For SELL orders: transaction ID/hash from crypto transfer
    transaction_id = models.CharField(max_length=255, blank=True, help_text="Transaction ID/hash from crypto transfer")
    # For SELL orders: payment proof image
    payment_proof = models.ImageField(upload_to='crypto_payment_proofs/', blank=True, null=True, help_text="Screenshot of crypto transfer transaction")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crypto_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.type} - {self.reference}"

    @classmethod
    def generate_reference(cls, prefix='CRYPTO'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class Withdrawal(models.Model):
    """Internal wallet withdrawals - MoMo and Crypto"""
    WITHDRAWAL_TYPE_CHOICES = [
        ('momo', 'Mobile Money'),
        ('crypto', 'Crypto'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_admin', 'Awaiting Admin Confirmation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    MOMO_NETWORK_CHOICES = [
        ('MTN', 'MTN Mobile Money'),
        ('Vodafone', 'Vodafone Cash'),
        ('AirtelTigo', 'AirtelTigo Money'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawals')
    withdrawal_type = models.CharField(max_length=10, choices=WITHDRAWAL_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount requested by user (before fees)")
    fee = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'), help_text="Withdrawal fee charged")
    total_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'), help_text="Total amount deducted (amount + fee)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=255, unique=True)
    
    # MoMo withdrawal fields (only required for MoMo withdrawals)
    momo_number = models.CharField(max_length=20, blank=True, help_text="Mobile Money number to receive withdrawal")
    momo_name = models.CharField(max_length=255, blank=True, help_text="Name on Mobile Money account")
    momo_network = models.CharField(max_length=20, choices=MOMO_NETWORK_CHOICES, blank=True, help_text="Mobile Money network")
    
    # Crypto withdrawal fields
    crypto_id = models.CharField(max_length=50, blank=True, help_text="Crypto type (e.g., bitcoin, ethereum)")
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0, help_text="Amount in crypto")
    network = models.CharField(max_length=20, blank=True, help_text="Network (e.g., TRC20, ERC20, BEP20)")
    crypto_address = models.CharField(max_length=255, blank=True, help_text="Crypto address to receive withdrawal")
    
    # Admin fields
    admin_note = models.TextField(blank=True, help_text="Admin notes about this withdrawal")
    transaction_id = models.CharField(max_length=255, blank=True, help_text="Transaction ID from admin's transfer")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_withdrawals')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'withdrawals'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.withdrawal_type} - {self.reference}"

    @classmethod
    def generate_reference(cls, prefix='WTH'):
        """Generate unique withdrawal reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class AdminCryptoAddress(models.Model):
    """Admin's receiving addresses for different crypto and networks"""
    
    CRYPTO_CHOICES = [
        ('bitcoin', 'Bitcoin (BTC)'),
        ('ethereum', 'Ethereum (ETH)'),
        ('tether', 'Tether (USDT)'),
        ('usd-coin', 'USD Coin (USDC)'),
        ('binancecoin', 'Binance Coin (BNB)'),
        ('cardano', 'Cardano (ADA)'),
        ('solana', 'Solana (SOL)'),
        ('ripple', 'Ripple (XRP)'),
        ('polkadot', 'Polkadot (DOT)'),
        ('dogecoin', 'Dogecoin (DOGE)'),
        ('litecoin', 'Litecoin (LTC)'),
        ('chainlink', 'Chainlink (LINK)'),
        ('polygon', 'Polygon (MATIC)'),
        ('avalanche', 'Avalanche (AVAX)'),
    ]
    
    NETWORK_CHOICES = [
        ('BTC', 'Bitcoin Network (BTC)'),
        ('ERC20', 'Ethereum Network (ERC20)'),
        ('TRC20', 'Tron Network (TRC20)'),
        ('BEP20', 'Binance Smart Chain (BEP20)'),
        ('SOL', 'Solana Network (SOL)'),
        ('MATIC', 'Polygon Network (MATIC)'),
        ('AVAX', 'Avalanche Network (AVAX)'),
        ('ARBITRUM', 'Arbitrum One'),
        ('OPTIMISM', 'Optimism'),
        ('BASE', 'Base'),
    ]
    
    crypto_id = models.CharField(max_length=50, choices=CRYPTO_CHOICES, help_text="Select the cryptocurrency type")
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES, help_text="Select the blockchain network")
    address = models.CharField(max_length=255, help_text="Enter the crypto address for receiving deposits")
    is_active = models.BooleanField(default=True, help_text="Only active addresses are shown to users")
    notes = models.TextField(blank=True, help_text="Internal notes about this address")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_crypto_addresses'
        unique_together = [['crypto_id', 'network']]
        ordering = ['crypto_id', 'network']
        verbose_name = "Admin Crypto Address"
        verbose_name_plural = "Admin Crypto Addresses"

    def __str__(self):
        crypto_display = dict(self.CRYPTO_CHOICES).get(self.crypto_id, self.crypto_id)
        network_display = dict(self.NETWORK_CHOICES).get(self.network, self.network)
        return f"{crypto_display} ({network_display}): {self.address[:20]}..."


class AdminPaymentDetails(models.Model):
    """Admin's payment details for deposits (MoMo numbers, bank accounts)"""
    PAYMENT_TYPE_CHOICES = [
        ('momo', 'Mobile Money'),
        ('bank', 'Bank Account'),
    ]

    MOMO_NETWORK_CHOICES = [
        ('MTN', 'MTN Mobile Money'),
        ('Vodafone', 'Vodafone Cash'),
        ('AirtelTigo', 'AirtelTigo Money'),
    ]

    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES)
    
    # MoMo fields
    momo_network = models.CharField(max_length=20, choices=MOMO_NETWORK_CHOICES, blank=True, help_text="Mobile Money network")
    momo_number = models.CharField(max_length=20, blank=True, help_text="Admin's Mobile Money number")
    momo_name = models.CharField(max_length=255, blank=True, help_text="Name on Mobile Money account")
    
    # Bank account fields
    bank_name = models.CharField(max_length=255, blank=True, help_text="Bank name")
    account_number = models.CharField(max_length=50, blank=True, help_text="Bank account number")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    branch = models.CharField(max_length=255, blank=True, help_text="Bank branch")
    swift_code = models.CharField(max_length=20, blank=True, help_text="SWIFT code (for international)")
    
    is_active = models.BooleanField(default=True, help_text="Active payment details for deposits")
    instructions = models.TextField(blank=True, help_text="Additional instructions for users (e.g., include reference number)")
    notes = models.TextField(blank=True, help_text="Internal admin notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_payment_details'
        ordering = ['payment_type', 'momo_network', '-is_active']
        verbose_name = "Admin Payment Detail"
        verbose_name_plural = "Admin Payment Details"

    def __str__(self):
        if self.payment_type == 'momo':
            return f"{self.get_momo_network_display()} - {self.momo_number} ({self.momo_name})"
        else:
            return f"{self.bank_name} - {self.account_number} ({self.account_name})"
