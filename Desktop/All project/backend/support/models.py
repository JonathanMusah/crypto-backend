from django.db import models
from django.conf import settings
import uuid


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    CATEGORY_CHOICES = [
        ('technical', 'Technical Issue'),
        ('billing', 'Billing'),
        ('kyc', 'KYC Verification'),
        ('transaction', 'Transaction Issue'),
        ('account', 'Account Issue'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_tickets'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'

    def __str__(self):
        return f"{self.subject} - {self.user.email} ({self.status})"


class SupportTicketResponse(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_admin_response = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Ticket Response'
        verbose_name_plural = 'Ticket Responses'

    def __str__(self):
        return f"Response to {self.ticket.subject} by {self.user.email}"


class ContactEnquiry(models.Model):
    """
    Public contact/enquiry form for non-authenticated users
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('responded', 'Responded'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'General Inquiry'),
        ('technical', 'Technical Question'),
        ('billing', 'Billing Question'),
        ('partnership', 'Partnership'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_enquiries'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_enquiries',
        help_text='User account if they register later'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Enquiry'
        verbose_name_plural = 'Contact Enquiries'

    def __str__(self):
        return f"{self.subject} - {self.name} ({self.email})"


class SpecialRequest(models.Model):
    """
    Special requests for services not currently offered
    e.g., receiving money from abroad, custom payment methods, etc.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('money_transfer', 'Money Transfer (International)'),
        ('custom_payment', 'Custom Payment Method'),
        ('bulk_transaction', 'Bulk Transaction'),
        ('escrow_service', 'Escrow Service'),
        ('crypto_service', 'Custom Crypto Service'),
        ('other', 'Other Service'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='special_requests')
    reference = models.CharField(max_length=255, unique=True, help_text="Unique reference for this request")
    
    # Request details
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES, default='other')
    title = models.CharField(max_length=255, help_text="Brief title of the request")
    description = models.TextField(help_text="Detailed description of what you need")
    
    # Optional financial details
    estimated_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Estimated amount involved (if applicable)")
    currency = models.CharField(max_length=10, default='GHS', help_text="Currency (GHS, USD, etc.)")
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Admin fields
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_special_requests'
    )
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes (not visible to user)")
    quote_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Quote provided to user")
    quote_notes = models.TextField(blank=True, help_text="Quote details/terms (visible to user)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_special_requests'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Special Request'
        verbose_name_plural = 'Special Requests'
        db_table = 'special_requests'

    def __str__(self):
        return f"{self.reference} - {self.title} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='SPR'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class PayPalRequest(models.Model):
    """
    PayPal service requests - for receiving and sending PayPal funds
    Since PayPal doesn't work directly in Ghana, users can request third-party services
    """
    TRANSACTION_TYPE_CHOICES = [
        ('receive', 'Receive PayPal Funds'),
        ('send', 'Send PayPal Funds'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_requests')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this request")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Receive or send PayPal funds")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    paypal_email = models.EmailField(help_text="PayPal email address")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Recipient name (if sending)")
    recipient_email = models.EmailField(blank=True, help_text="Recipient PayPal email (if sending)")
    description = models.TextField(help_text="Transaction description/purpose")
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Admin fields
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_paypal_requests'
    )
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes (not visible to user)")
    quote_amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Quote in GHS")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    quote_notes = models.TextField(blank=True, help_text="Quote details/terms (visible to user)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_paypal_requests'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'PayPal Request'
        verbose_name_plural = 'PayPal Requests'
        db_table = 'paypal_requests'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='PPR'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class PayPalTransaction(models.Model):
    """
    Buy/Sell PayPal transactions - for freelancers to exchange PayPal balance
    Users can sell their PayPal balance (we pay them in cedis) or buy PayPal balance (they pay us in cedis)
    """
    TRANSACTION_TYPE_CHOICES = [
        ('sell', 'Sell PayPal Balance'),
        ('buy', 'Buy PayPal Balance'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('payment_sent', 'Payment Sent (Awaiting Verification)'),
        ('payment_verified', 'Payment Verified'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    STEP_CHOICES = [
        ('details', 'Details Submitted'),
        ('payment_proof', 'Payment Proof Uploaded'),
        ('verified', 'Payment Verified'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_transactions')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this transaction")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Buy or sell PayPal balance")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    paypal_email = models.EmailField(help_text="User's PayPal email address")
    
    # For SELL: Where to send payment to user
    # For BUY: Where user wants to receive PayPal
    payment_method = models.CharField(max_length=50, help_text="MoMo, Bank, etc.")
    payment_details = models.TextField(help_text="Account number, MoMo number, bank details, etc.")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    
    # Admin PayPal email (where user sends PayPal funds for SELL, or where we send for BUY)
    admin_paypal_email = models.EmailField(blank=True, help_text="Admin PayPal email for transaction")
    
    # Payment proof
    payment_proof = models.FileField(upload_to='paypal_payment_proofs/', null=True, blank=True, help_text="Screenshot or proof of payment")
    payment_proof_notes = models.TextField(blank=True, help_text="Additional notes about payment proof")
    
    # Current step in the process
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='details')
    
    # Status and admin fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Financial details
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Amount in GHS")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    
    # Important: Only PayPal balance accepted
    is_paypal_balance_only = models.BooleanField(default=True, help_text="Transaction must be from PayPal balance only, not bank/third party")
    user_confirmed_balance_only = models.BooleanField(default=False, help_text="User confirmed they are sending from PayPal balance only")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_sent_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_paypal_transactions'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'PayPal Transaction'
        verbose_name_plural = 'PayPal Transactions'
        db_table = 'paypal_transactions'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='PPT'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class PayPalPurchaseRequest(models.Model):
    """
    PayPal Purchase Request Service
    Users can request admin to pay for something online using PayPal on their behalf
    User pays admin in cedis, admin pays seller via PayPal
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('payment_pending', 'Awaiting User Payment'),
        ('processing', 'Processing Purchase'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_purchase_requests')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this request")
    
    # Item/Service details
    item_name = models.CharField(max_length=500, help_text="Name/description of the item or service")
    item_url = models.URLField(blank=True, help_text="URL to the item or service (if available)")
    item_description = models.TextField(help_text="Detailed description of what you want to purchase")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount needed in USD")
    
    # Recipient details (where to send PayPal payment)
    recipient_paypal_email = models.EmailField(help_text="PayPal email of the seller/merchant")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Name of the recipient (optional)")
    shipping_address = models.TextField(blank=True, help_text="Shipping address if physical item (optional)")
    
    # User payment details (how user will pay admin)
    payment_method = models.CharField(max_length=50, default='momo', help_text="MoMo, Bank, etc.")
    payment_details = models.TextField(blank=True, help_text="MoMo number, account details, etc. (if known)")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    
    # Priority and urgency
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', help_text="Request priority")
    urgency_reason = models.TextField(blank=True, help_text="Why this is urgent (if applicable)")
    
    # Admin fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_paypal_purchase_requests',
        help_text="Admin assigned to handle this request"
    )
    
    # Admin quote/response
    quote_amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Amount user needs to pay in cedis")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="Exchange rate used")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in cedis")
    quote_notes = models.TextField(blank=True, help_text="Notes about the quote or process")
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Tracking
    payment_proof = models.FileField(upload_to='paypal_purchase_proofs/', null=True, blank=True, help_text="Proof of PayPal payment made by admin")
    delivery_tracking = models.CharField(max_length=500, blank=True, help_text="Tracking number or delivery info (if applicable)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_paypal_purchase_requests'
    )
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When user paid admin")
    purchased_at = models.DateTimeField(null=True, blank=True, help_text="When admin made the PayPal payment")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'PayPal Purchase Request'
        verbose_name_plural = 'PayPal Purchase Requests'
        db_table = 'paypal_purchase_requests'

    def __str__(self):
        return f"{self.reference} - {self.item_name} (${self.amount_usd}) - {self.user.email}"

    @classmethod
    def generate_reference(cls, prefix='PPP'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)
    
    def get_transaction_type_display(self):
        """Helper method for consistent naming"""
        return "PayPal Purchase Request"


class CashAppRequest(models.Model):
    """
    CashApp service requests - for receiving and sending CashApp funds
    Since CashApp doesn't work directly in Ghana, users can request third-party services
    """
    TRANSACTION_TYPE_CHOICES = [
        ('receive', 'Receive CashApp Funds'),
        ('send', 'Send CashApp Funds'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cashapp_requests')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this request")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Receive or send CashApp funds")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    cashapp_tag = models.CharField(max_length=100, help_text="CashApp $tag or email address")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Recipient name (if sending)")
    recipient_tag = models.CharField(max_length=100, blank=True, help_text="Recipient CashApp $tag (if sending)")
    description = models.TextField(help_text="Transaction description/purpose")
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Admin fields
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cashapp_requests'
    )
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes (not visible to user)")
    quote_amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Quote in GHS")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    quote_notes = models.TextField(blank=True, help_text="Quote details/terms (visible to user)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_cashapp_requests'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CashApp Request'
        verbose_name_plural = 'CashApp Requests'
        db_table = 'cashapp_requests'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='CAR'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class CashAppTransaction(models.Model):
    """
    Buy/Sell CashApp transactions - for freelancers to exchange CashApp balance
    Users can sell their CashApp balance (we pay them in cedis) or buy CashApp balance (they pay us in cedis)
    """
    TRANSACTION_TYPE_CHOICES = [
        ('sell', 'Sell CashApp Balance'),
        ('buy', 'Buy CashApp Balance'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('payment_sent', 'Payment Sent (Awaiting Verification)'),
        ('payment_verified', 'Payment Verified'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    STEP_CHOICES = [
        ('details', 'Details Submitted'),
        ('payment_proof', 'Payment Proof Uploaded'),
        ('verified', 'Payment Verified'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cashapp_transactions')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this transaction")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Buy or sell CashApp balance")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    cashapp_tag = models.CharField(max_length=100, help_text="User's CashApp $tag or email")
    
    # For SELL: Where to send payment to user
    # For BUY: Where user wants to receive CashApp
    payment_method = models.CharField(max_length=50, help_text="MoMo, Bank, etc.")
    payment_details = models.TextField(help_text="Account number, MoMo number, bank details, etc.")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    
    # Admin CashApp tag (where user sends CashApp funds for SELL, or where we send for BUY)
    admin_cashapp_tag = models.CharField(max_length=100, blank=True, help_text="Admin CashApp $tag for transaction")
    
    # Payment proof
    payment_proof = models.FileField(upload_to='cashapp_payment_proofs/', null=True, blank=True, help_text="Screenshot or proof of payment")
    payment_proof_notes = models.TextField(blank=True, help_text="Additional notes about payment proof")
    
    # Current step in the process
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='details')
    
    # Status and admin fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Financial details
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Amount in GHS")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    
    # Important: Only CashApp balance accepted
    is_cashapp_balance_only = models.BooleanField(default=True, help_text="Transaction must be from CashApp balance only, not bank/third party")
    user_confirmed_balance_only = models.BooleanField(default=False, help_text="User confirmed they are sending from CashApp balance only")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_sent_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_cashapp_transactions'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CashApp Transaction'
        verbose_name_plural = 'CashApp Transactions'
        db_table = 'cashapp_transactions'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='CAT'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class CashAppPurchaseRequest(models.Model):
    """
    CashApp Purchase Request Service
    Users can request admin to pay for something online using CashApp on their behalf
    User pays admin in cedis, admin pays seller via CashApp
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('payment_pending', 'Awaiting User Payment'),
        ('processing', 'Processing Purchase'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cashapp_purchase_requests')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this request")
    
    # Item/Service details
    item_name = models.CharField(max_length=500, help_text="Name/description of the item or service")
    item_url = models.URLField(blank=True, help_text="URL to the item or service (if available)")
    item_description = models.TextField(help_text="Detailed description of what you want to purchase")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount needed in USD")
    
    # Recipient details (where to send CashApp payment)
    recipient_cashapp_tag = models.CharField(max_length=100, help_text="CashApp $tag of the seller/merchant")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Name of the recipient (optional)")
    shipping_address = models.TextField(blank=True, help_text="Shipping address if physical item (optional)")
    
    # User payment details (how user will pay admin)
    payment_method = models.CharField(max_length=50, default='momo', help_text="MoMo, Bank, etc.")
    payment_details = models.TextField(blank=True, help_text="MoMo number, account details, etc. (if known)")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    
    # Priority and urgency
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', help_text="Request priority")
    urgency_reason = models.TextField(blank=True, help_text="Why this is urgent (if applicable)")
    
    # Admin fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cashapp_purchase_requests',
        help_text="Admin assigned to handle this request"
    )
    
    # Admin quote/response
    quote_amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Amount user needs to pay in cedis")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="Exchange rate used")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in cedis")
    quote_notes = models.TextField(blank=True, help_text="Notes about the quote or process")
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Tracking
    payment_proof = models.FileField(upload_to='cashapp_purchase_proofs/', null=True, blank=True, help_text="Proof of CashApp payment made by admin")
    delivery_tracking = models.CharField(max_length=500, blank=True, help_text="Tracking number or delivery info (if applicable)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_cashapp_purchase_requests'
    )
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When user paid admin")
    purchased_at = models.DateTimeField(null=True, blank=True, help_text="When admin made the CashApp payment")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CashApp Purchase Request'
        verbose_name_plural = 'CashApp Purchase Requests'
        db_table = 'cashapp_purchase_requests'

    def __str__(self):
        return f"{self.reference} - {self.item_name} (${self.amount_usd}) - {self.user.email}"

    @classmethod
    def generate_reference(cls, prefix='CAP'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)
    
    def get_transaction_type_display(self):
        """Helper method for consistent naming"""
        return "CashApp Purchase Request"


class ZelleRequest(models.Model):
    """
    Zelle service requests - for receiving and sending Zelle funds
    Since Zelle doesn't work directly in Ghana, users can request third-party services
    """
    TRANSACTION_TYPE_CHOICES = [
        ('receive', 'Receive Zelle Funds'),
        ('send', 'Send Zelle Funds'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('quoted', 'Quote Provided'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zelle_requests')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this request")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Receive or send Zelle funds")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    zelle_email = models.EmailField(help_text="Zelle email or phone number")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Recipient name (if sending)")
    recipient_email = models.EmailField(blank=True, help_text="Recipient Zelle email or phone (if sending)")
    description = models.TextField(help_text="Transaction description/purpose")
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Admin fields
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_zelle_requests'
    )
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes (not visible to user)")
    quote_amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Quote in GHS")
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    quote_notes = models.TextField(blank=True, help_text="Quote details/terms (visible to user)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_zelle_requests'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Zelle Request'
        verbose_name_plural = 'Zelle Requests'
        db_table = 'zelle_requests'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='ZER'):
        """Generate unique request reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class ZelleTransaction(models.Model):
    """
    Buy/Sell Zelle transactions - for freelancers to exchange Zelle balance
    Users can sell their Zelle balance (we pay them in cedis) or buy Zelle balance (they pay us in cedis)
    """
    TRANSACTION_TYPE_CHOICES = [
        ('sell', 'Sell Zelle Balance'),
        ('buy', 'Buy Zelle Balance'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('payment_sent', 'Payment Sent (Awaiting Verification)'),
        ('payment_verified', 'Payment Verified'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]
    
    STEP_CHOICES = [
        ('details', 'Details Submitted'),
        ('payment_proof', 'Payment Proof Uploaded'),
        ('verified', 'Payment Verified'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zelle_transactions')
    reference = models.CharField(max_length=255, unique=True, blank=True, help_text="Unique reference for this transaction")
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Buy or sell Zelle balance")
    amount_usd = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount in USD")
    zelle_email = models.EmailField(help_text="User's Zelle email or phone number")
    
    # For SELL: Where to send payment to user
    # For BUY: Where user wants to receive Zelle
    payment_method = models.CharField(max_length=50, help_text="MoMo, Bank, etc.")
    payment_details = models.TextField(help_text="Account number, MoMo number, bank details, etc.")
    account_name = models.CharField(max_length=255, blank=True, help_text="Account holder name")
    
    # Admin Zelle email (where user sends Zelle funds for SELL, or where we send for BUY)
    admin_zelle_email = models.EmailField(blank=True, help_text="Admin Zelle email or phone for transaction")
    
    # Payment proof
    payment_proof = models.FileField(upload_to='zelle_payment_proofs/', null=True, blank=True, help_text="Screenshot or proof of payment")
    payment_proof_notes = models.TextField(blank=True, help_text="Additional notes about payment proof")
    
    # Current step in the process
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='details')
    
    # Status and admin fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    # Financial details
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text="USD to GHS rate used")
    amount_cedis = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Amount in GHS")
    service_fee = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Service fee in GHS")
    
    # Important: Only Zelle balance accepted
    is_zelle_balance_only = models.BooleanField(default=True, help_text="Transaction must be from Zelle balance only, not bank/third party")
    user_confirmed_balance_only = models.BooleanField(default=False, help_text="User confirmed they are sending from Zelle balance only")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_sent_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_zelle_transactions'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Zelle Transaction'
        verbose_name_plural = 'Zelle Transactions'
        db_table = 'zelle_transactions'

    def __str__(self):
        return f"{self.reference} - {self.get_transaction_type_display()} ${self.amount_usd} ({self.user.email})"

    @classmethod
    def generate_reference(cls, prefix='ZET'):
        """Generate unique transaction reference"""
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)
