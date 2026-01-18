"""
Crypto P2P Trading Models - True Peer-to-Peer Crypto Trading
Follows the same Binance-style pattern as P2P Services but for crypto assets
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)


class CryptoListing(models.Model):
    """
    Crypto P2P Listings - Users can buy/sell crypto (Bitcoin, Ethereum, BNB) at their own rates
    Follows the same Binance-style pattern as P2PServiceListing
    """
    
    LISTING_TYPE_CHOICES = [
        ('sell', 'Sell - I have crypto to sell'),
        ('buy', 'Buy - I want to buy crypto'),
    ]
    
    CRYPTO_TYPE_CHOICES = [
        ('bitcoin', 'Bitcoin (BTC)'),
        ('ethereum', 'Ethereum (ETH)'),
        ('bnb', 'Binance Coin (BNB)'),
        ('usdt', 'Tether USDT'),
        ('usdc', 'USD Coin (USDC)'),
    ]
    
    NETWORK_CHOICES = [
        ('mainnet', 'Mainnet'),
        ('testnet', 'Testnet'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('sold', 'Sold Out'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('under_review', 'Under Review'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('momo', 'Mobile Money (MoMo)'),
        ('bank', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('cashapp', 'CashApp'),
    ]

    # Basic Info
    listing_type = models.CharField(
        max_length=10,
        choices=LISTING_TYPE_CHOICES,
        default='sell',
        help_text="Whether this is a sell listing (seller has crypto) or buy listing (buyer wants crypto)"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='crypto_listings',
        help_text="For sell listings: seller (who has crypto). For buy listings: buyer (who wants crypto)"
    )
    reference = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="Unique reference for this listing"
    )
    
    # Crypto Details
    crypto_type = models.CharField(
        max_length=20,
        choices=CRYPTO_TYPE_CHOICES,
        default='bitcoin',
        help_text="Type of cryptocurrency"
    )
    network = models.CharField(
        max_length=20,
        choices=NETWORK_CHOICES,
        default='mainnet',
        help_text="Blockchain network (mainnet or testnet)"
    )
    
    # Amount and Rate
    min_amount_crypto = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default='0.001',
        help_text="Minimum crypto amount (e.g., 0.001 BTC)"
    )
    max_amount_crypto = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Maximum crypto amount (null = unlimited)"
    )
    available_amount_crypto = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        help_text="Current available crypto amount"
    )
    
    # Rate fields - different meaning for sell vs buy
    # For SELL listings: Seller's rate (rate_cedis_per_crypto)
    # For BUY listings: Buyer's max rate (highest rate buyer will pay)
    rate_cedis_per_crypto = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="For sell: Seller's rate (1 crypto = X GHS). For buy: Buyer's max rate"
    )
    is_negotiable = models.BooleanField(
        default=False,
        help_text="Whether rate is negotiable"
    )
    
    # Payment methods seller accepts (or buyer will use)
    accepted_payment_methods = models.JSONField(
        default=list,
        help_text="Payment methods accepted/to be used: Format: [{'method': 'momo', 'provider': 'MTN', 'number': '0244123456', 'name': 'John Doe'}, ...]"
    )
    
    # Buyer requirements (Binance-style)
    min_completed_trades = models.IntegerField(
        default=0,
        help_text="Minimum completed P2P trades required from buyers"
    )
    buyer_must_be_verified = models.BooleanField(
        default=False,
        help_text="Buyer must have verified email"
    )
    buyer_must_be_kyc_verified = models.BooleanField(
        default=False,
        help_text="Buyer must have KYC approval"
    )
    
    # Terms
    terms_notes = models.TextField(
        blank=True,
        help_text="Seller's terms and special instructions"
    )
    
    # Proof and verification
    proof_image = models.ImageField(
        upload_to='crypto_listing_proofs/',
        blank=True,
        null=True,
        help_text="Proof of wallet ownership or funds"
    )
    proof_image_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Hash of proof image for duplicate detection"
    )
    
    # Status and metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='under_review'
    )
    views_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Admin fields
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_crypto_listings'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Crypto Listing'
        verbose_name_plural = 'Crypto Listings'
        db_table = 'crypto_listings'
        indexes = [
            models.Index(fields=['crypto_type', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['listing_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.reference} - {self.get_crypto_type_display()} {self.get_listing_type_display()} - Rate: ₵{self.rate_cedis_per_crypto}/{self.get_crypto_type_display()}"
    
    @classmethod
    def generate_reference(cls, crypto_type='bitcoin', listing_type='sell'):
        """Generate unique listing reference"""
        prefix_map = {
            'bitcoin': 'BTC',
            'ethereum': 'ETH',
            'bnb': 'BNB',
            'usdt': 'USDT',
            'usdc': 'USDC',
        }
        prefix = prefix_map.get(crypto_type, 'CRYPTO')
        type_suffix = 'B' if listing_type == 'buy' else 'S'
        return f"{prefix}{type_suffix}-{uuid.uuid4().hex[:12].upper()}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference(self.crypto_type, self.listing_type)
        super().save(*args, **kwargs)


class CryptoP2PTransaction(models.Model):
    """
    Crypto P2P Transactions - True peer-to-peer trading with atomic operations
    Upgraded from simple buy/sell to full Binance-style 6-step transaction flow
    
    Flow:
    1. Buyer initiates transaction → status='payment_received', escrow locked
    2. Buyer marks payment sent → status='buyer_marked_paid'
    3. Seller confirms payment → status='seller_confirmed_payment'
    4. Seller sends crypto → status='crypto_sent'
    5. Buyer confirms receipt → status='verifying'
    6. Transaction complete → status='completed'
    """
    
    STATUS_CHOICES = [
        ('payment_received', 'Payment Received (awaiting payment marking)'),
        ('buyer_marked_paid', 'Buyer Marked Paid (awaiting seller confirmation)'),
        ('seller_confirmed_payment', 'Seller Confirmed Payment (awaiting crypto send)'),
        ('crypto_sent', 'Crypto Sent (awaiting buyer verification)'),
        ('verifying', 'Verifying (final step)'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Listing and Parties
    listing = models.ForeignKey(
        CryptoListing,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='crypto_purchases'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='crypto_sales'
    )
    
    # Basic Info
    reference = models.CharField(max_length=255, unique=True, blank=True)
    
    # Amounts
    amount_crypto = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        help_text="Amount of crypto to trade"
    )
    amount_cedis = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Amount in Cedis (GHS)"
    )
    rate_applied = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Rate applied for this transaction"
    )
    
    # Escrow Fields
    escrow_locked = models.BooleanField(default=False)
    escrow_amount_cedis = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0')
    )
    
    # Payment Details
    buyer_payment_details = models.JSONField(
        default=dict,
        help_text="Buyer's payment method (MoMo number, bank account, etc.)"
    )
    seller_payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="How seller will receive payment (MoMo number, bank account, etc.)"
    )
    
    # Crypto Delivery Details
    buyer_wallet_address = models.CharField(
        max_length=255,
        help_text="Buyer's wallet address to receive crypto"
    )
    seller_wallet_address = models.CharField(
        max_length=255,
        blank=True,
        help_text="Seller's wallet address (used to verify blockchain transaction)"
    )
    transaction_hash = models.CharField(
        max_length=255,
        blank=True,
        help_text="Blockchain transaction hash"
    )
    
    # Payment Tracking
    buyer_marked_paid = models.BooleanField(default=False)
    buyer_marked_paid_at = models.DateTimeField(null=True, blank=True)
    payment_screenshot = models.ImageField(
        upload_to='crypto_payment_screenshots/',
        null=True,
        blank=True,
        help_text="Buyer's proof of payment"
    )
    
    seller_confirmed_payment = models.BooleanField(default=False)
    seller_confirmed_payment_at = models.DateTimeField(null=True, blank=True)
    
    # Crypto Delivery Tracking
    crypto_sent = models.BooleanField(default=False)
    crypto_sent_at = models.DateTimeField(null=True, blank=True)
    crypto_proof_image = models.ImageField(
        upload_to='crypto_proofs/',
        null=True,
        blank=True,
        help_text="Seller's proof of crypto transfer"
    )
    
    buyer_verified = models.BooleanField(default=False)
    buyer_verification_notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Blockchain Verification (Optional)
    blockchain_verified = models.BooleanField(default=False)
    blockchain_verified_at = models.DateTimeField(null=True, blank=True)
    blockchain_verification_notes = models.TextField(blank=True)
    
    # Status and Timeouts - Binance-style timeouts
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='payment_received'
    )
    payment_deadline = models.DateTimeField(help_text="Buyer has until this time to mark payment sent")
    seller_confirmation_deadline = models.DateTimeField(null=True, blank=True, help_text="Seller has until this time to confirm payment")
    seller_response_deadline = models.DateTimeField(null=True, blank=True, help_text="Seller has until this time to send crypto")
    buyer_verification_deadline = models.DateTimeField(null=True, blank=True, help_text="Buyer has until this time to verify crypto received")
    auto_release_at = models.DateTimeField(null=True, blank=True, help_text="Auto-complete transaction at this time if no issues")
    
    # Dispute Fields
    has_dispute = models.BooleanField(default=False)
    dispute_reason = models.TextField(blank=True)
    
    # Risk Assessment
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Risk score (0-100, higher = riskier)"
    )
    
    # Audit Trail
    cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.CharField(max_length=50, blank=True)  # 'buyer', 'seller', 'system', 'admin'
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Crypto Transaction'
        verbose_name_plural = 'Crypto Transactions'
        db_table = 'crypto_transactions'
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_deadline']),
        ]
    
    def __str__(self):
        return f"{self.reference} - {self.amount_crypto} {self.listing.get_crypto_type_display()} - {self.get_status_display()}"
    
    @classmethod
    def generate_reference(cls):
        """Generate unique transaction reference"""
        return f"CRY-{uuid.uuid4().hex[:12].upper()}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        if not self.payment_deadline:
            # Default: 15 minutes from now (Binance-style)
            self.payment_deadline = timezone.now() + timezone.timedelta(minutes=15)
        super().save(*args, **kwargs)
    
    def mark_payment_sent(self, buyer):
        """Buyer marks payment as sent"""
        if buyer != self.buyer:
            raise ValidationError("Only the buyer can mark payment as sent")
        if self.status != 'payment_received':
            raise ValidationError(f"Cannot mark payment sent for transaction with status: {self.status}")
        
        self.buyer_marked_paid = True
        self.buyer_marked_paid_at = timezone.now()
        self.status = 'buyer_marked_paid'
        # Seller has 15 minutes to confirm
        self.seller_confirmation_deadline = timezone.now() + timezone.timedelta(minutes=15)
        self.save()
    
    def confirm_payment(self, seller):
        """Seller confirms payment received"""
        if seller != self.seller:
            raise ValidationError("Only the seller can confirm payment")
        if self.status != 'buyer_marked_paid':
            raise ValidationError(f"Cannot confirm payment for transaction with status: {self.status}")
        
        self.seller_confirmed_payment = True
        self.seller_confirmed_payment_at = timezone.now()
        self.status = 'seller_confirmed_payment'
        # Seller has 15 minutes to send crypto
        self.seller_response_deadline = timezone.now() + timezone.timedelta(minutes=15)
        self.save()
    
    def send_crypto(self, seller, transaction_hash=None, proof_image=None):
        """Seller sends crypto to buyer"""
        if seller != self.seller:
            raise ValidationError("Only the seller can send crypto")
        if self.status != 'seller_confirmed_payment':
            raise ValidationError(f"Cannot send crypto for transaction with status: {self.status}")
        
        self.crypto_sent = True
        self.crypto_sent_at = timezone.now()
        if transaction_hash:
            self.transaction_hash = transaction_hash
        if proof_image:
            self.crypto_proof_image = proof_image
        self.status = 'crypto_sent'
        # Buyer has 15 minutes to verify
        self.buyer_verification_deadline = timezone.now() + timezone.timedelta(minutes=15)
        self.save()
    
    def verify_crypto(self, buyer, verified=True, notes=''):
        """Buyer verifies crypto received"""
        if buyer != self.buyer:
            raise ValidationError("Only the buyer can verify crypto")
        if self.status != 'crypto_sent':
            raise ValidationError(f"Cannot verify crypto for transaction with status: {self.status}")
        
        self.buyer_verified = verified
        self.buyer_verification_notes = notes
        self.verified_at = timezone.now()
        
        if verified:
            self.status = 'completed'
            self.completed_at = timezone.now()
        else:
            self.status = 'disputed'
            self.has_dispute = True
        
        self.save()


class CryptoTransactionAuditLog(models.Model):
    """
    Audit trail for crypto transactions - HMAC-signed for integrity
    Follows the same pattern as gift card audit logs
    """
    
    ACTION_CHOICES = [
        ('created', 'Transaction Created'),
        ('marked_paid', 'Payment Marked Sent'),
        ('payment_confirmed', 'Payment Confirmed'),
        ('crypto_sent', 'Crypto Sent'),
        ('verified', 'Crypto Verified'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        CryptoP2PTransaction,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # HMAC signature for integrity
    signature = models.CharField(max_length=256, blank=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Crypto Transaction Audit Log'
        verbose_name_plural = 'Crypto Transaction Audit Logs'
        db_table = 'crypto_transaction_audit_logs'
        indexes = [
            models.Index(fields=['transaction', 'created_at']),
            models.Index(fields=['performed_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction.reference} - {self.get_action_display()}"


class CryptoTransactionDispute(models.Model):
    """
    Disputes for crypto transactions - when buyer or seller raises an issue
    """
    
    DISPUTE_TYPE_CHOICES = [
        ('crypto_not_received', 'Crypto Not Received'),
        ('wrong_amount', 'Wrong Amount Received'),
        ('payment_not_received', 'Payment Not Received'),
        ('other', 'Other Issue'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        CryptoP2PTransaction,
        on_delete=models.CASCADE,
        related_name='disputes'
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    dispute_type = models.CharField(max_length=30, choices=DISPUTE_TYPE_CHOICES)
    description = models.TextField()
    
    evidence_image = models.ImageField(
        upload_to='crypto_dispute_evidence/',
        null=True,
        blank=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_crypto_disputes'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Crypto Transaction Dispute'
        verbose_name_plural = 'Crypto Transaction Disputes'
        db_table = 'crypto_transaction_disputes'
    
    def __str__(self):
        return f"{self.transaction.reference} - {self.get_dispute_type_display()}"
