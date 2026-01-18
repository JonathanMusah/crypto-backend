from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid
import hashlib
import io
import logging

logger = logging.getLogger(__name__)

# Import P2P models to ensure they're registered
from .p2p_models import (
    P2PServiceListing,
    P2PServiceTransaction,
    P2PServiceDispute,
    P2PServiceTransactionRating,
    P2PServiceTransactionLog,
    P2PServiceDisputeLog,
    SellerApplication,
)

__all__ = [
    'GiftCard', 'GiftCardOrder', 'Order', 'Trade',
    'GiftCardListing', 'GiftCardTransaction', 'GiftCardDispute',
    'GiftCardTransactionRating', 'GiftCardTransactionLog', 'GiftCardDisputeLog',
    'P2PServiceListing', 'P2PServiceTransaction', 'P2PServiceDispute',
    'P2PServiceTransactionRating', 'P2PServiceTransactionLog', 'P2PServiceDisputeLog',
    'SellerApplication',
]


class GiftCard(models.Model):
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100)
    rate_buy = models.DecimalField(max_digits=10, decimal_places=2)
    rate_sell = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='giftcards/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gift_cards'
        ordering = ['brand', 'name']

    def __str__(self):
        return f"{self.brand} - {self.name}"


class GiftCardOrder(models.Model):
    ORDER_TYPE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='giftcard_orders')
    card = models.ForeignKey(GiftCard, on_delete=models.PROTECT, related_name='orders')
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default='buy')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    proof_image = models.ImageField(upload_to='giftcard_proofs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def calculated_amount(self):
        """Calculate the amount based on the order type and rate"""
        if self.order_type == 'buy':
            # When buying, user pays amount * rate_buy
            return self.amount * self.card.rate_buy
        else:
            # When selling, user receives amount * rate_sell
            return self.amount * self.card.rate_sell

    class Meta:
        db_table = 'gift_card_orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.card.name} - {self.amount}"


class Order(models.Model):
    ORDER_TYPE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES)
    currency_pair = models.CharField(max_length=20)  # e.g., 'BTC/USDT'
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    total = models.DecimalField(max_digits=20, decimal_places=8)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_type} {self.currency_pair} - {self.amount} @ {self.price}"

    def save(self, *args, **kwargs):
        if not self.total:
            self.total = self.amount * self.price
        super().save(*args, **kwargs)


class Trade(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='trades')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buyer_trades')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_trades')
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    total = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trades'
        ordering = ['-created_at']

    def __str__(self):
        return f"Trade {self.amount} @ {self.price}"


class GiftCardListing(models.Model):
    """
    Peer-to-peer gift card listings - users can list their gift cards for sale
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('sold', 'Sold'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('under_review', 'Under Review'),
    ]

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='giftcard_listings')
    card = models.ForeignKey(GiftCard, on_delete=models.PROTECT, related_name='listings')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this listing")
    
    # Gift card details
    gift_card_code = models.CharField(max_length=255, blank=True, help_text="Gift card code (hidden until purchase)")
    gift_card_pin = models.CharField(max_length=50, blank=True, help_text="Gift card PIN if applicable")
    gift_card_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Value of the gift card in original currency")
    currency = models.CharField(max_length=10, default='USD', help_text="Original currency (USD, EUR, etc.)")
    
    # Pricing
    asking_price_cedis = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price seller wants in GHS")
    is_negotiable = models.BooleanField(default=False, help_text="Whether price is negotiable")
    
    # Proof and verification
    proof_image = models.ImageField(upload_to='giftcard_listing_proofs/', blank=True, null=True, help_text="Proof of gift card ownership")
    proof_notes = models.TextField(blank=True, help_text="Additional notes about the gift card")
    
    # Duplicate protection - hashing
    card_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text="SHA256 hash of gift card code + PIN for duplicate detection")
    proof_image_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text="Perceptual hash (pHash) of proof image for duplicate detection")
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='under_review')
    views_count = models.IntegerField(default=0, help_text="Number of times listing was viewed")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When listing expires (optional)")
    
    # Admin fields
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_giftcard_listings'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Card Listing'
        verbose_name_plural = 'Gift Card Listings'
        db_table = 'gift_card_listings'

    def __str__(self):
        return f"{self.reference} - {self.card.brand} {self.gift_card_value} {self.currency} by {self.seller.email}"

    @classmethod
    def generate_reference(cls, prefix='GCL'):
        """Generate unique listing reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class GiftCardTransaction(models.Model):
    """
    Transactions between users for gift card purchases with escrow system
    """
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('payment_received', 'Payment Received (Escrow)'),
        ('card_provided', 'Card Provided by Seller'),
        ('verifying', 'Buyer Verifying'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
        ('auto_cancelled', 'Auto-Cancelled (Seller Timeout)'),  # ✅ FIX #4: New status
        ('refunded', 'Refunded'),
    ]

    listing = models.ForeignKey(GiftCardListing, on_delete=models.PROTECT, related_name='transactions')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='giftcard_purchases')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='giftcard_sales')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this transaction")
    
    # Transaction details
    agreed_price_cedis = models.DecimalField(max_digits=10, decimal_places=2, help_text="Agreed price in GHS")
    escrow_amount_cedis = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount held in escrow")
    
    # Gift card delivery
    gift_card_code = models.CharField(max_length=255, blank=True, help_text="Gift card code provided by seller")
    gift_card_pin = models.CharField(max_length=50, blank=True, help_text="Gift card PIN if applicable")
    card_proof_image = models.ImageField(upload_to='giftcard_transaction_proofs/', blank=True, null=True, help_text="Proof image of gift card provided by seller")
    card_provided_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-action timers
    seller_response_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for seller to provide card details")
    buyer_verification_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for buyer to verify card")
    auto_release_at = models.DateTimeField(null=True, blank=True, help_text="When to auto-release funds (1 hour after verification)")
    
    # ✅ FIX #4: Timeout tracking fields for automatic actions
    auto_cancelled = models.BooleanField(default=False, help_text="Was this transaction auto-cancelled due to timeout?")
    cancellation_reason = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('seller_response_timeout', 'Seller did not respond within 24 hours'),
            ('buyer_verification_timeout', 'Buyer did not verify within deadline'),
            ('admin_timeout', 'Admin did not process within deadline'),
            ('manual', 'Manually cancelled by user'),
        ],
        help_text="Reason for cancellation if auto-cancelled"
    )
    escrow_released = models.BooleanField(default=False, help_text="Have the escrowed funds been released?")
    escrow_released_at = models.DateTimeField(null=True, blank=True, help_text="When were escrow funds released?")
    seller_reminder_sent = models.BooleanField(default=False, help_text="Has reminder notification been sent to seller?")
    
    # Verification
    buyer_verified = models.BooleanField(default=False, help_text="Buyer has verified the gift card works")
    buyer_verification_notes = models.TextField(blank=True, help_text="Buyer's verification notes")
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    
    # Dispute handling
    has_dispute = models.BooleanField(default=False)
    dispute_reason = models.TextField(blank=True, help_text="Reason for dispute")
    dispute_resolved = models.BooleanField(default=False)
    dispute_resolution = models.TextField(blank=True, help_text="Admin resolution of dispute")
    dispute_resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_giftcard_transaction_disputes'
    )
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Admin fields
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Security & Risk Assessment
    risk_score = models.IntegerField(null=True, blank=True, help_text="Risk score calculated at transaction creation (0-100, higher = more risk)")
    risk_factors = models.JSONField(default=dict, blank=True, help_text="Factors contributing to risk score")
    device_fingerprint = models.CharField(max_length=64, blank=True, null=True, help_text="Device fingerprint for fraud detection")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Card Transaction'
        verbose_name_plural = 'Gift Card Transactions'
        db_table = 'gift_card_transactions'
        # ✅ FIX #4: Database indexes for timeout queries
        indexes = [
            models.Index(fields=['status', 'seller_response_deadline'], name='idx_status_seller_deadline'),
            models.Index(fields=['status', 'auto_release_at'], name='idx_status_auto_release'),
            models.Index(fields=['auto_cancelled'], name='idx_auto_cancelled'),
            models.Index(fields=['escrow_released'], name='idx_escrow_released'),
        ]


    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Card Transaction'
        verbose_name_plural = 'Gift Card Transactions'
        db_table = 'gift_card_transactions'

    def __str__(self):
        return f"{self.reference} - {self.buyer.email} buys from {self.seller.email}"

    @classmethod
    def generate_reference(cls, prefix='GCT'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class GiftCardDispute(models.Model):
    """
    Dispute system for gift card transactions
    """
    DISPUTE_TYPE_CHOICES = [
        ('invalid_code', 'Invalid/Non-working Gift Card'),
        ('wrong_amount', 'Wrong Gift Card Amount'),
        ('expired_card', 'Expired Gift Card'),
        ('already_used', 'Gift Card Already Used'),
        ('seller_not_responding', 'Seller Not Responding'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    RESOLUTION_CHOICES = [
        ('refund_buyer', 'Refund Buyer'),
        ('release_to_seller', 'Release to Seller'),
        ('partial_refund', 'Partial Refund'),
        ('no_action', 'No Action Required'),
    ]

    transaction = models.OneToOneField(GiftCardTransaction, on_delete=models.CASCADE, related_name='dispute')
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='giftcard_disputes_raised')
    dispute_type = models.CharField(max_length=50, choices=DISPUTE_TYPE_CHOICES)
    description = models.TextField(help_text="Detailed description of the dispute - REQUIRED: Explain what went wrong, when you discovered the issue, and any steps you've taken")
    evidence_images = models.JSONField(default=list, blank=True, help_text="List of image URLs as evidence - REQUIRED: Screenshots showing the issue (e.g., error messages, invalid code attempts)")
    evidence_required = models.BooleanField(default=True, help_text="Evidence is required for dispute resolution")
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium',
        help_text="Dispute priority level"
    )
    fraud_indicators = models.JSONField(default=dict, blank=True, help_text="Automated fraud detection indicators")
    verification_attempts = models.IntegerField(default=0, help_text="Number of verification attempts made")
    
    # Status and resolution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.CharField(max_length=30, choices=RESOLUTION_CHOICES, blank=True)
    resolution_notes = models.TextField(blank=True, help_text="Admin notes on resolution")
    
    # Admin handling
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_giftcard_disputes'
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_giftcard_disputes'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Card Dispute'
        verbose_name_plural = 'Gift Card Disputes'
        db_table = 'gift_card_disputes'

    def __str__(self):
        return f"Dispute {self.transaction.reference} - {self.get_dispute_type_display()}"


class GiftCardTransactionRating(models.Model):
    """
    Rating/Review system for gift card transactions
    Buyers can rate sellers after transaction completion
    """
    RATING_CHOICES = [
        (1, '1 Star - Very Poor'),
        (2, '2 Stars - Poor'),
        (3, '3 Stars - Average'),
        (4, '4 Stars - Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    transaction = models.OneToOneField(
        GiftCardTransaction,
        on_delete=models.CASCADE,
        related_name='rating',
        help_text="Transaction this rating is for"
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_given',
        help_text="User who gave the rating (buyer)"
    )
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_received',
        help_text="User being rated (seller)"
    )
    rating = models.IntegerField(choices=RATING_CHOICES, help_text="Rating from 1 to 5 stars")
    comment = models.TextField(blank=True, help_text="Optional comment about the transaction")
    is_visible = models.BooleanField(default=True, help_text="Whether this rating is visible to others")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'gift_card_transaction_ratings'
        ordering = ['-created_at']
        verbose_name = 'Transaction Rating'
        verbose_name_plural = 'Transaction Ratings'
        indexes = [
            models.Index(fields=['rated_user', 'rating']),
            models.Index(fields=['transaction']),
        ]
    
    def __str__(self):
        return f"{self.rater.email} rated {self.rated_user.email} - {self.rating} stars"
    
    def save(self, *args, **kwargs):
        # Ensure rater and rated_user are set correctly
        if not self.rated_user_id and self.transaction_id:
            # Buyer rates seller
            self.rated_user = self.transaction.seller
        if not self.rater_id and self.transaction_id:
            # Rater is the buyer
            self.rater = self.transaction.buyer
        super().save(*args, **kwargs)


class GiftCardTransactionLog(models.Model):
    """
    Log all actions and state changes for gift card transactions
    Used for dispute resolution and audit trail
    """
    ACTION_CHOICES = [
        ('created', 'Transaction Created'),
        ('payment_locked', 'Payment Locked in Escrow'),
        ('card_provided', 'Card Details Provided'),
        ('card_verified', 'Card Verified by Buyer'),
        ('card_rejected', 'Card Rejected by Buyer'),
        ('dispute_created', 'Dispute Created'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('cancelled', 'Transaction Cancelled'),
        ('completed', 'Transaction Completed'),
        ('auto_cancelled', 'Auto-Cancelled (Seller Timeout)'),
        ('auto_disputed', 'Auto-Disputed (Buyer Timeout)'),
        ('auto_released', 'Auto-Released (Buyer Verified)'),
    ]
    
    transaction = models.ForeignKey(GiftCardTransaction, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='giftcard_transaction_logs',
        help_text="User who performed this action (null for system actions)"
    )
    notes = models.TextField(blank=True, help_text="Additional notes about this action")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata (e.g., amounts, status changes)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gift Card Transaction Log'
        verbose_name_plural = 'Gift Card Transaction Logs'
        db_table = 'gift_card_transaction_logs'
        indexes = [
            models.Index(fields=['transaction', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        user_str = self.performed_by.email if self.performed_by else 'System'
        return f"{self.transaction.reference} - {self.action} by {user_str} at {self.created_at}"


class GiftCardDisputeLog(models.Model):
    """
    Immutable audit log for all dispute actions
    Logs cannot be modified after creation for audit-proof tracking
    """
    ACTION_CHOICES = [
        ('dispute_created', 'Dispute Created'),
        ('evidence_uploaded', 'Evidence Uploaded'),
        ('status_changed', 'Status Changed'),
        ('assigned', 'Assigned to Admin'),
        ('unassigned', 'Unassigned from Admin'),
        ('priority_changed', 'Priority Changed'),
        ('comment_added', 'Comment Added'),
        ('evidence_added', 'Evidence Added'),
        ('evidence_removed', 'Evidence Removed'),
        ('resolution_proposed', 'Resolution Proposed'),
        ('resolution_finalized', 'Resolution Finalized'),
        ('dispute_closed', 'Dispute Closed'),
        ('reopened', 'Dispute Reopened'),
    ]
    
    dispute = models.ForeignKey(GiftCardDispute, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='giftcard_dispute_logs',
        help_text="User who performed this action (null for system actions)"
    )
    comment = models.TextField(blank=True, help_text="Comment or notes about this action")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata (e.g., old_status, new_status, file_names)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['created_at']  # Chronological order for timeline
        verbose_name = 'Gift Card Dispute Log'
        verbose_name_plural = 'Gift Card Dispute Logs'
        db_table = 'gift_card_dispute_logs'
        indexes = [
            models.Index(fields=['dispute', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['performed_by', 'created_at']),
        ]
        # Prevent updates/deletes for audit-proof logging
        permissions = [
            ('can_delete_dispute_log', 'Can delete dispute log'),
            ('can_modify_dispute_log', 'Can modify dispute log'),
        ]
    
    def __str__(self):
        user_str = self.performed_by.email if self.performed_by else 'System'
        return f"Dispute {self.dispute.id} - {self.action} by {user_str} at {self.created_at}"
    
    def save(self, *args, **kwargs):
        # Prevent modifications to existing logs (audit-proof)
        if self.pk:
            raise ValueError("Dispute logs cannot be modified after creation for audit purposes")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion of logs (audit-proof)
        raise ValueError("Dispute logs cannot be deleted for audit purposes")


# ✅ FIX #6: Audit logging model for transaction tracking
class TransactionAuditLog(models.Model):
    """
    Comprehensive audit log for all transaction actions
    Tracks who did what, when, and why for complete transaction history and dispute resolution
    """
    TRANSACTION_TYPE_CHOICES = [
        ('gift_card', 'Gift Card Transaction'),
        ('p2p_service', 'P2P Service Transaction'),
        ('crypto_buy', 'Crypto Buy'),
        ('crypto_sell', 'Crypto Sell'),
        ('escrow', 'Escrow Operation'),
    ]
    
    ACTION_CHOICES = [
        ('created', 'Transaction Created'),
        ('payment_verified', 'Payment Verified'),
        ('payment_locked', 'Payment Locked in Escrow'),
        ('card_provided', 'Gift Card Provided'),
        ('buyer_verified', 'Buyer Verified Item'),
        ('funds_released', 'Funds Released to Seller'),
        ('auto_cancelled', 'Auto-Cancelled by System'),
        ('auto_released', 'Auto-Released by System'),
        ('dispute_opened', 'Dispute Opened'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('cancelled', 'Transaction Cancelled'),
        ('refund_issued', 'Refund Issued'),
        ('approved_by_admin', 'Approved by Admin'),
        ('rejected_by_admin', 'Rejected by Admin'),
    ]

    # Core fields
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    transaction_id = models.PositiveIntegerField()  # Not a ForeignKey to allow flexibility
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    
    # User information
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transaction_audit_logs',
        help_text="User who performed action (null for system actions)"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of requester")
    user_agent = models.TextField(blank=True, help_text="User agent of requester")
    
    # State tracking
    previous_state = models.JSONField(default=dict, blank=True, help_text="Previous transaction state")
    new_state = models.JSONField(default=dict, blank=True, help_text="New transaction state after action")
    
    # Details
    notes = models.TextField(blank=True, help_text="Detailed notes about this action")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional context (amounts, reasons, etc)")
    
    # Security
    signature = models.CharField(max_length=256, blank=True, help_text="HMAC signature for log integrity")
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Transaction Audit Log'
        verbose_name_plural = 'Transaction Audit Logs'
        db_table = 'transaction_audit_logs'
        indexes = [
            models.Index(fields=['transaction_type', 'transaction_id'], name='idx_txn_type_id'),
            models.Index(fields=['action', 'timestamp'], name='idx_action_timestamp'),
            models.Index(fields=['performed_by', 'timestamp'], name='idx_user_timestamp'),
        ]
    
    def __str__(self):
        user_str = self.performed_by.email if self.performed_by else 'SYSTEM'
        return f"{self.transaction_type}#{self.transaction_id} - {self.action} by {user_str}"
    
    def save(self, *args, **kwargs):
        """Generate HMAC signature for audit integrity"""
        import hmac
        import hashlib
        if not self.signature:
            # Create HMAC signature of key fields for integrity checking
            signature_data = f"{self.transaction_type}{self.transaction_id}{self.action}{self.timestamp}"
            self.signature = hmac.new(
                key=settings.SECRET_KEY.encode(),
                msg=signature_data.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()
        super().save(*args, **kwargs)
    
    @staticmethod
    def create_audit_log(transaction_type, transaction_id, action, performed_by=None, 
                        previous_state=None, new_state=None, notes="", metadata=None,
                        ip_address=None, user_agent=None):
        """
        Helper function to create audit logs with proper error handling
        """
        return TransactionAuditLog.objects.create(
            transaction_type=transaction_type,
            transaction_id=transaction_id,
            action=action,
            performed_by=performed_by,
            previous_state=previous_state or {},
            new_state=new_state or {},
            notes=notes,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
