"""
Peer-to-Peer (P2P) service models for PayPal, CashApp, and Zelle
Following the same pattern as GiftCardListing/GiftCardTransaction
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)


class SellerApplication(models.Model):
    """
    Application model for users who want to become sellers
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),  # If seller privileges are later revoked
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_applications')
    
    # Application details
    reason = models.TextField(help_text="Why do you want to become a seller?")
    experience = models.TextField(blank=True, help_text="Any relevant experience with P2P trading?")
    service_types = models.JSONField(
        default=list,
        help_text="Which services do you plan to sell? ['paypal', 'cashapp', 'zelle']"
    )
    proof_of_funds_image = models.ImageField(
        upload_to='seller_applications/proof_of_funds/',
        blank=True,
        null=True,
        help_text="Proof of funds (required for new users without trade history)"
    )
    proof_of_funds_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Perceptual hash of proof of funds image for duplicate detection"
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_seller_applications',
        help_text="Admin who reviewed this application"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection (if rejected)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seller_applications'
        ordering = ['-created_at']
        verbose_name = 'Seller Application'
        verbose_name_plural = 'Seller Applications'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.status} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def approve(self, reviewer):
        """Approve the seller application"""
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()
        
        # Update user's seller status
        self.user.can_sell_p2p = True
        self.user.seller_status = 'approved'
        self.user.seller_approved_at = timezone.now()
        self.user.save(update_fields=['can_sell_p2p', 'seller_status', 'seller_approved_at'])
    
    def reject(self, reviewer, reason=''):
        """Reject the seller application"""
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Update user's seller status
        self.user.can_sell_p2p = False
        self.user.seller_status = 'rejected'
        self.user.save(update_fields=['can_sell_p2p', 'seller_status'])
    
    def revoke(self, reviewer, reason=''):
        """Revoke seller privileges"""
        self.status = 'revoked'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        # Update user's seller status
        self.user.can_sell_p2p = False
        self.user.seller_status = 'revoked'
        self.user.save(update_fields=['can_sell_p2p', 'seller_status'])


class P2PServiceListing(models.Model):
    """
    Peer-to-peer service listings - users can list their services (PayPal, CashApp, Zelle) for sale OR buy
    Binance-style: Sellers set their own rates and specify which payment methods they accept
    For buy listings: Buyers specify max rate they'll pay and payment method they'll use
    """
    LISTING_TYPE_CHOICES = [
        ('sell', 'Sell - I have service to sell'),
        ('buy', 'Buy - I want to buy service'),
    ]
    
    SERVICE_TYPE_CHOICES = [
        ('paypal', 'PayPal'),
        ('cashapp', 'CashApp'),
        ('zelle', 'Zelle'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('sold', 'Sold'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('under_review', 'Under Review'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('momo', 'Mobile Money (MoMo)'),
        ('bank', 'Bank Transfer'),
        ('other', 'Other'),
    ]

    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default='sell', help_text="Whether this is a sell listing (seller has service) or buy listing (buyer wants service)")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='p2p_service_listings', help_text="For sell listings: seller. For buy listings: buyer (person who wants to buy)")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, help_text="Type of service (PayPal, CashApp, Zelle)")
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this listing")
    
    # Service-specific identifiers (different for each service type)
    paypal_email = models.EmailField(blank=True, null=True, help_text="PayPal email address (for PayPal listings)")
    cashapp_tag = models.CharField(max_length=100, blank=True, null=True, help_text="CashApp tag starting with $ (for CashApp listings)")
    zelle_email = models.EmailField(blank=True, null=True, help_text="Zelle email address (for Zelle listings)")
    
    # Service details
    min_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, help_text="Minimum transaction amount in USD")
    max_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Maximum transaction amount in USD (null = unlimited)")
    available_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, help_text="Total amount available in USD")
    currency = models.CharField(max_length=10, default='USD', help_text="Original currency (USD)")
    
    # Rate fields - different meaning for sell vs buy
    # For SELL listings: Seller's rate (1 USD = rate_cedis_per_usd GHS)
    # For BUY listings: Buyer's max rate (highest rate buyer will pay, 1 USD = max_rate_cedis_per_usd GHS)
    rate_cedis_per_usd = models.DecimalField(max_digits=10, decimal_places=4, default=12.00, help_text="For sell: Seller's rate (1 USD = X GHS). For buy: Buyer's max rate (highest rate buyer will pay)")
    max_rate_cedis_per_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="For buy listings: Maximum rate buyer will pay (1 USD = X GHS). For sell listings: Not used.")
    is_negotiable = models.BooleanField(default=False, help_text="Whether rate is negotiable")
    
    # Payment methods - different meaning for sell vs buy
    # For SELL listings: Payment methods seller accepts (multiple methods)
    # For BUY listings: Payment method buyer will use (single method)
    accepted_payment_methods = models.JSONField(
        default=list,
        help_text="For sell: List of payment methods seller accepts. For buy: Single payment method buyer will use. Format: [{'method': 'momo', 'provider': 'MTN', 'number': '0244123456', 'name': 'John Doe'}, ...]"
    )
    
    # Buyer requirements (Binance-style)
    min_completed_trades = models.IntegerField(default=0, help_text="Minimum number of completed P2P trades required from buyers (0 = no requirement)")
    buyer_must_be_verified = models.BooleanField(default=False, help_text="Buyer must have verified email")
    buyer_must_be_kyc_verified = models.BooleanField(default=False, help_text="Buyer must have KYC approved")
    required_payment_providers = models.JSONField(
        default=list,
        blank=True,
        help_text="Required payment providers buyer must use (filters accepted payment methods). Empty list = accept all. Format: ['MTN', 'Vodafone', 'AirtelTigo', 'Bank']. Only relevant for MoMo/bank methods."
    )
    
    # Terms and conditions
    terms_notes = models.TextField(blank=True, help_text="Seller's terms, notes, or special instructions")
    
    # Proof and verification
    proof_image = models.ImageField(upload_to='p2p_service_listing_proofs/', blank=True, null=True, help_text="Proof of service ownership (screenshot of balance, etc.)")
    proof_notes = models.TextField(blank=True, help_text="Additional notes about the service")
    
    # Duplicate protection - hashing
    service_identifier_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text="SHA256 hash of service identifier (email/tag) for duplicate detection")
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
        related_name='reviewed_p2p_service_listings'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'P2P Service Listing'
        verbose_name_plural = 'P2P Service Listings'
        db_table = 'p2p_service_listings'
        indexes = [
            models.Index(fields=['service_type', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['service_identifier_hash']),
        ]

    def __str__(self):
        if self.listing_type == 'buy':
            return f"{self.reference} - {self.get_service_type_display()} BUY - Max Rate: ₵{self.max_rate_cedis_per_usd or self.rate_cedis_per_usd}/USD by {self.seller.email}"
        else:
            identifier = self.get_service_identifier()
            return f"{self.reference} - {self.get_service_type_display()} SELL ({identifier}) - Rate: ₵{self.rate_cedis_per_usd}/USD by {self.seller.email}"

    def get_service_identifier(self):
        """Get the service-specific identifier based on service type"""
        if self.service_type == 'paypal':
            return self.paypal_email or 'N/A'
        elif self.service_type == 'cashapp':
            return self.cashapp_tag or 'N/A'
        elif self.service_type == 'zelle':
            return self.zelle_email or 'N/A'
        return 'N/A'

    @classmethod
    def generate_reference(cls, service_type='paypal', listing_type='sell'):
        """Generate unique listing reference"""
        prefix_map = {
            'paypal': 'PPL',
            'cashapp': 'CAP',
            'zelle': 'ZEL',
        }
        prefix = prefix_map.get(service_type, 'P2P')
        type_suffix = 'B' if listing_type == 'buy' else 'S'  # B for Buy, S for Sell
        return f"{prefix}{type_suffix}-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def hash_service_identifier(identifier):
        """Hash service identifier (email or tag) for duplicate detection"""
        if not identifier:
            return ''
        return hashlib.sha256(identifier.lower().strip().encode('utf-8')).hexdigest()
    
    def calculate_price_cedis(self, amount_usd, seller_rate=None):
        """
        Calculate price in GHS based on rate
        For sell listings: Uses listing's rate_cedis_per_usd
        For buy listings: Uses seller_rate (rate seller offers, must be <= buyer's max_rate)
        """
        if self.listing_type == 'buy':
            # For buy listings, use the seller's rate (passed as parameter)
            # This rate must be <= buyer's max_rate_cedis_per_usd
            rate = seller_rate or self.max_rate_cedis_per_usd or self.rate_cedis_per_usd
        else:
            # For sell listings, use the listing's rate
            rate = self.rate_cedis_per_usd
        return amount_usd * rate
    
    def check_buyer_qualification(self, buyer, selected_payment_method_details=None):
        """
        Check if a buyer qualifies to purchase from this listing based on Binance-style requirements.
        Returns (qualified: bool, reason: str or None)
        """
        # Only check requirements for sell listings
        if self.listing_type != 'sell':
            return True, None
        
        # Check minimum completed trades
        if self.min_completed_trades > 0:
            completed_trades = self._get_buyer_completed_trades_count(buyer)
            if completed_trades < self.min_completed_trades:
                return False, f"Buyer must have at least {self.min_completed_trades} completed P2P trades. You have {completed_trades}."
        
        # Check verification requirements
        if self.buyer_must_be_verified:
            if not buyer.email_verified:
                return False, "Buyer must have verified email address"
        
        if self.buyer_must_be_kyc_verified:
            if buyer.kyc_status != 'approved':
                return False, "Buyer must have KYC approval"
        
        # Check payment provider requirements
        if self.required_payment_providers and len(self.required_payment_providers) > 0:
            if not selected_payment_method_details:
                return False, f"Buyer must use one of the required payment providers: {', '.join(self.required_payment_providers)}"
            
            payment_method = selected_payment_method_details.get('method', '')
            provider = selected_payment_method_details.get('provider', '')
            
            # For MoMo, check provider
            if payment_method == 'momo':
                if provider not in self.required_payment_providers:
                    return False, f"Buyer must use one of these MoMo providers: {', '.join(self.required_payment_providers)}"
            # For bank, check if 'Bank' is in required providers
            elif payment_method == 'bank':
                if 'Bank' not in self.required_payment_providers:
                    return False, f"Buyer must use one of these payment providers: {', '.join(self.required_payment_providers)}"
            # For other methods, check if 'Other' is in required providers
            else:
                if 'Other' not in self.required_payment_providers:
                    return False, f"Buyer must use one of these payment providers: {', '.join(self.required_payment_providers)}"
        
        return True, None
    
    def _get_buyer_completed_trades_count(self, buyer):
        """Get count of completed P2P service transactions for a buyer"""
        return P2PServiceTransaction.objects.filter(
            buyer=buyer,
            status='completed'
        ).count()

    @staticmethod
    def compute_proof_image_hash(image_file):
        """Compute perceptual hash for proof image"""
        try:
            import imagehash
            from PIL import Image
            
            image_file.seek(0)
            img = Image.open(image_file)
            hash_value = imagehash.phash(img)
            return str(hash_value)
        except Exception as e:
            logger.error(f"Error computing image hash: {str(e)}")
            return None

    def save(self, *args, **kwargs):
        logger.info(f"[MODEL SAVE] Starting save for P2PServiceListing")
        logger.info(f"[MODEL SAVE] listing_type: {self.listing_type}, service_type: {self.service_type}")
        logger.info(f"[MODEL SAVE] pk: {self.pk}, is_new: {not hasattr(self, '_state') or self._state.adding}")
        
        # Ensure listing_type has a default value
        if not self.listing_type:
            self.listing_type = 'sell'
            logger.info("[MODEL SAVE] Set default listing_type to 'sell'")
        
        # Ensure service_type is set (should always be set, but safety check)
        if not self.service_type:
            error_msg = "service_type is required for P2PServiceListing"
            logger.error(f"[MODEL SAVE] {error_msg}")
            raise ValueError(error_msg)
        
        if not self.reference:
            self.reference = self.generate_reference(self.service_type, self.listing_type)
            logger.info(f"[MODEL SAVE] Generated reference: {self.reference}")
        
        # For sell listings: Hash service identifier for duplicate detection
        # For buy listings: No service identifier to hash (buyer doesn't have service yet)
        if self.listing_type == 'sell':
            identifier = self.get_service_identifier()
            if identifier and identifier != 'N/A':
                self.service_identifier_hash = self.hash_service_identifier(identifier)
        else:
            # Buy listings don't have service identifiers - leave hash empty/blank
            if not self.service_identifier_hash:
                self.service_identifier_hash = ''
        
        # Hash proof image if provided (only for sell listings typically)
        # Skip image hashing during initial save - it will be hashed on update after image is stored
        # This prevents errors when the image file hasn't been saved to disk yet
        # Only attempt to hash if the object already exists in the database
        if self.proof_image and self.pk and hasattr(self, '_state') and not self._state.adding:
            try:
                # For saved ImageFieldFile, access the underlying file
                if hasattr(self.proof_image, 'file'):
                    try:
                        file_obj = self.proof_image.file
                        file_obj.seek(0)
                        image_hash = self.compute_proof_image_hash(file_obj)
                        if image_hash:
                            self.proof_image_hash = image_hash
                    except (AttributeError, IOError, ValueError, OSError) as e:
                        logger.warning(f"Could not hash proof image (may be new upload): {str(e)}")
            except Exception as e:
                logger.error(f"Error hashing proof image: {str(e)}")
        
        # For buy listings, set max_rate if not set (use rate_cedis_per_usd as default)
        if self.listing_type == 'buy' and not self.max_rate_cedis_per_usd:
            self.max_rate_cedis_per_usd = self.rate_cedis_per_usd
        
        try:
            logger.info("[MODEL SAVE] Calling super().save()...")
            super().save(*args, **kwargs)
            logger.info(f"[MODEL SAVE] Successfully saved! ID: {self.pk}")
        except Exception as e:
            logger.error("=" * 80)
            logger.error("[MODEL SAVE] ERROR SAVING P2PServiceListing")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"listing_type: {self.listing_type}")
            logger.error(f"service_type: {self.service_type}")
            logger.error(f"reference: {self.reference}")
            logger.error("Full traceback:", exc_info=True)
            logger.error("=" * 80)
            raise


class P2PServiceTransaction(models.Model):
    """
    Transactions between users for P2P service purchases with escrow system
    Similar to GiftCardTransaction but for digital payment services
    """
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('payment_received', 'Payment Received (Escrow)'),
        ('buyer_marked_paid', 'Buyer Marked as Paid'),
        ('seller_confirmed_payment', 'Seller Confirmed Payment'),
        ('service_provided', 'Service Details Provided by Seller'),
        ('verifying', 'Buyer Verifying'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    listing = models.ForeignKey(P2PServiceListing, on_delete=models.PROTECT, related_name='transactions')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='p2p_service_purchases')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='p2p_service_sales')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this transaction")
    
    # Transaction details
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Transaction amount in USD")
    agreed_price_cedis = models.DecimalField(max_digits=10, decimal_places=2, help_text="Agreed price in GHS (calculated from amount_usd * listing.rate_cedis_per_usd)")
    escrow_amount_cedis = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount held in escrow")
    escrow_released = models.BooleanField(default=False, help_text="Whether escrow has been released to seller")
    escrow_released_at = models.DateTimeField(null=True, blank=True, help_text="When escrow was released")
    
    # Payment method selected by buyer
    selected_payment_method = models.CharField(max_length=20, blank=True, help_text="Payment method buyer selected (momo, bank, other)")
    payment_method_details = models.JSONField(default=dict, blank=True, help_text="Details for selected payment method (provider, number, account, etc.)")
    
    # Binance-style: Payment confirmation flow
    buyer_marked_paid = models.BooleanField(default=False, help_text="Buyer has marked payment as complete")
    buyer_marked_paid_at = models.DateTimeField(null=True, blank=True, help_text="When buyer marked payment as complete")
    payment_screenshot = models.ImageField(upload_to='p2p_payment_screenshots/', blank=True, null=True, help_text="Screenshot of payment proof uploaded by buyer")
    seller_confirmed_payment = models.BooleanField(default=False, help_text="Seller has confirmed payment receipt")
    seller_confirmed_payment_at = models.DateTimeField(null=True, blank=True, help_text="When seller confirmed payment")
    
    # Service delivery
    service_identifier = models.CharField(max_length=255, blank=True, help_text="Service identifier provided by seller (email or tag based on service type)")
    service_proof_image = models.ImageField(upload_to='p2p_service_transaction_proofs/', blank=True, null=True, help_text="Proof image of service provided by seller")
    service_provided_at = models.DateTimeField(null=True, blank=True)
    
    # Buyer's service identifier (for BUY listings - where buyer wants to receive service)
    buyer_service_identifier = models.CharField(max_length=255, blank=True, help_text="Service identifier provided by buyer (where they want to receive service - for BUY listings)")
    
    # Auto-action timers (Binance-style: 15 minutes for each step)
    payment_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for buyer to complete payment (15 minutes)")
    seller_confirmation_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for seller to confirm payment receipt (15 minutes after buyer marks payment)")
    seller_response_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for seller to provide service details (15 minutes)")
    buyer_verification_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for buyer to verify service (15 minutes)")
    auto_release_at = models.DateTimeField(null=True, blank=True, help_text="When to auto-release funds (15 minutes after verification)")
    
    # Verification
    buyer_verified = models.BooleanField(default=False, help_text="Buyer has verified the service works")
    buyer_verification_notes = models.TextField(blank=True, help_text="Buyer's verification notes")
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_payment')
    
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
        related_name='resolved_p2p_service_transaction_disputes'
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
        verbose_name = 'P2P Service Transaction'
        verbose_name_plural = 'P2P Service Transactions'
        db_table = 'p2p_service_transactions'
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['listing', 'status']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.buyer.email} buys {self.listing.get_service_type_display()} from {self.seller.email}"

    @classmethod
    def generate_reference(cls, service_type='paypal'):
        """Generate unique transaction reference"""
        prefix_map = {
            'paypal': 'PPT',
            'cashapp': 'CAT',
            'zelle': 'ZET',
        }
        prefix = prefix_map.get(service_type, 'P2P')
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference(self.listing.service_type)
        
        # Track if status is changing to completed
        if self.pk:
            try:
                old_instance = P2PServiceTransaction.objects.get(pk=self.pk)
                old_status = old_instance.status
            except P2PServiceTransaction.DoesNotExist:
                old_status = None
        else:
            old_status = None
        
        super().save(*args, **kwargs)
        
        # If status changed to completed and escrow hasn't been released, trigger release
        if self.status == 'completed' and not self.escrow_released and self.escrow_amount_cedis > 0:
            if old_status != 'completed':  # Only trigger on status change
                # Use a signal or async task to release escrow
                # This will be handled by the signal handler
                pass


class P2PServiceDispute(models.Model):
    """
    Dispute system for P2P service transactions
    Similar to GiftCardDispute
    """
    DISPUTE_TYPE_CHOICES = [
        ('invalid_email', 'Invalid/Non-working Service Email'),
        ('wrong_amount', 'Wrong Service Amount'),
        ('service_not_received', 'Service Not Received'),
        ('seller_not_responding', 'Seller Not Responding'),
        ('fraud', 'Suspected Fraud'),
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

    transaction = models.OneToOneField(P2PServiceTransaction, on_delete=models.CASCADE, related_name='dispute')
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='p2p_service_disputes_raised')
    dispute_type = models.CharField(max_length=50, choices=DISPUTE_TYPE_CHOICES)
    description = models.TextField(help_text="Detailed description of the dispute")
    evidence_images = models.JSONField(default=list, blank=True, help_text="List of image URLs as evidence")
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
        related_name='assigned_p2p_service_disputes'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'P2P Service Dispute'
        verbose_name_plural = 'P2P Service Disputes'
        db_table = 'p2p_service_disputes'

    def __str__(self):
        return f"Dispute for {self.transaction.reference} - {self.get_dispute_type_display()}"


class P2PServiceTransactionRating(models.Model):
    """
    Rating/Review system for P2P service transactions
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
        P2PServiceTransaction,
        on_delete=models.CASCADE,
        related_name='rating',
        help_text="Transaction this rating is for"
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='p2p_service_ratings_given',
        help_text="User who gave the rating (buyer)"
    )
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='p2p_service_ratings_received',
        help_text="User being rated (seller)"
    )
    rating = models.IntegerField(choices=RATING_CHOICES, help_text="Rating from 1 to 5 stars")
    comment = models.TextField(blank=True, help_text="Optional comment about the transaction")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'P2P Service Transaction Rating'
        verbose_name_plural = 'P2P Service Transaction Ratings'
        db_table = 'p2p_service_transaction_ratings'
        unique_together = [['transaction', 'rater']]

    def __str__(self):
        return f"{self.rater.email} rated {self.rated_user.email} {self.rating} stars"


class P2PServiceTransactionLog(models.Model):
    """
    Log all actions and state changes for P2P service transactions
    Used for dispute resolution and audit trail
    """
    ACTION_CHOICES = [
        ('created', 'Transaction Created'),
        ('payment_locked', 'Payment Locked in Escrow'),
        ('service_provided', 'Service Details Provided'),
        ('service_verified', 'Service Verified by Buyer'),
        ('service_rejected', 'Service Rejected by Buyer'),
        ('dispute_created', 'Dispute Created'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('cancelled', 'Transaction Cancelled'),
        ('completed', 'Transaction Completed'),
        ('auto_cancelled', 'Auto-Cancelled (Seller Timeout)'),
        ('auto_disputed', 'Auto-Disputed (Buyer Timeout)'),
        ('auto_released', 'Auto-Released (Buyer Verified)'),
    ]
    
    transaction = models.ForeignKey(P2PServiceTransaction, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='p2p_service_transaction_logs',
        help_text="User who performed this action (null for system actions)"
    )
    notes = models.TextField(blank=True, help_text="Additional notes about this action")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'P2P Service Transaction Log'
        verbose_name_plural = 'P2P Service Transaction Logs'
        db_table = 'p2p_service_transaction_logs'

    def __str__(self):
        return f"{self.transaction.reference} - {self.get_action_display()} at {self.timestamp}"


class P2PServiceDisputeLog(models.Model):
    """
    Immutable audit log for all dispute actions
    """
    ACTION_CHOICES = [
        ('dispute_created', 'Dispute Created'),
        ('evidence_uploaded', 'Evidence Uploaded'),
        ('assigned_to_admin', 'Assigned to Admin'),
        ('admin_review_started', 'Admin Review Started'),
        ('admin_decision', 'Admin Decision Made'),
        ('resolution_applied', 'Resolution Applied'),
        ('dispute_closed', 'Dispute Closed'),
    ]
    
    dispute = models.ForeignKey(P2PServiceDispute, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='p2p_service_dispute_logs',
        help_text="User who performed this action (null for system actions)"
    )
    notes = models.TextField(blank=True, help_text="Additional notes about this action")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'P2P Service Dispute Log'
        verbose_name_plural = 'P2P Service Dispute Logs'
        db_table = 'p2p_service_dispute_logs'

    def __str__(self):
        return f"Dispute {self.dispute.id} - {self.get_action_display()} at {self.timestamp}"

