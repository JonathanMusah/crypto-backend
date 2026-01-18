
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
