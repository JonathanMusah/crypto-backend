from django.db import models
from django.conf import settings


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('TRANSACTION_CREATED', 'Transaction Created'),
        ('TRANSACTION_APPROVED', 'Transaction Approved'),
        ('TRANSACTION_REJECTED', 'Transaction Rejected'),
        ('GIFT_CARD_ORDER_CREATED', 'Gift Card Order Created'),
        ('GIFT_CARD_ORDER_APPROVED', 'Gift Card Order Approved'),
        ('GIFT_CARD_ORDER_DECLINED', 'Gift Card Order Declined'),
        ('GIFT_CARD_ORDER_COMPLETED', 'Gift Card Order Completed'),
        ('GIFT_CARD_PROOF_UPLOADED', 'Gift Card Proof Uploaded'),
        ('ORDER_COMPLETED', 'Order Completed'),
        ('ORDER_CANCELLED', 'Order Cancelled'),
        ('DEPOSIT_RECEIVED', 'Deposit Received'),
        ('DEPOSIT_APPROVED', 'Deposit Approved'),
        ('DEPOSIT_REJECTED', 'Deposit Rejected'),
        ('WITHDRAWAL_REQUESTED', 'Withdrawal Requested'),
        ('WITHDRAWAL_APPROVED', 'Withdrawal Approved'),
        ('WITHDRAWAL_REJECTED', 'Withdrawal Rejected'),
        ('WITHDRAWAL_COMPLETED', 'Withdrawal Completed'),
        ('KYC_APPROVED', 'KYC Approved'),
        ('KYC_REJECTED', 'KYC Rejected'),
        ('NEW_DEVICE_LOGIN', 'New Device Login'),
        ('ADMIN_NEW_DEVICE_ALERT', 'Admin New Device Alert'),
        ('SYSTEM', 'System Notification'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, blank=True)
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional fields for linking to related objects
    related_object_type = models.CharField(max_length=50, blank=True, null=True)  # e.g., 'transaction', 'gift_card_order'
    related_object_id = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.user.email}: {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.read = True
        self.save(update_fields=['read'])

    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user"""
        return cls.objects.filter(user=user, read=False).count()