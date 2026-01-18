"""
Messaging system models for secure marketplace communication
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import json


class Conversation(models.Model):
    """
    Conversation between two users, optionally linked to a listing
    """
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_user1'
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_user2'
    )
    listing = models.ForeignKey(
        'orders.GiftCardListing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    transaction = models.ForeignKey(
        'orders.GiftCardTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    is_locked = models.BooleanField(
        default=False,
        help_text="Lock conversation during disputes or admin intervention"
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_conversations',
        help_text="Admin who locked this conversation"
    )
    locked_reason = models.TextField(blank=True, help_text="Reason for locking")
    scam_score = models.IntegerField(
        default=0,
        help_text="Cumulative scam risk score (0-100)"
    )
    is_archived_user1 = models.BooleanField(default=False)
    is_archived_user2 = models.BooleanField(default=False)

    class Meta:
        db_table = 'conversations'
        ordering = ['-last_message_at']
        # Allow multiple conversations between same users for different listings/transactions
        # But prevent exact duplicates (same users, same listing, same transaction)
        unique_together = [['user1', 'user2', 'listing', 'transaction']]
        indexes = [
            models.Index(fields=['user1', 'last_message_at']),
            models.Index(fields=['user2', 'last_message_at']),
            models.Index(fields=['listing', 'created_at']),
        ]

    def __str__(self):
        listing_ref = f" - {self.listing.reference}" if self.listing else ""
        return f"{self.user1.email} ↔ {self.user2.email}{listing_ref}"

    def get_other_user(self, user):
        """Get the other participant in the conversation"""
        if not user:
            return None
        
        # Use ID comparison instead of object comparison for reliability
        user_id = user.id if hasattr(user, 'id') else None
        user1_id = self.user1.id if self.user1 else None
        user2_id = self.user2.id if self.user2 else None
        
        # Safety check: ensure user is part of conversation
        if user_id not in [user1_id, user2_id]:
            return None
        
        # Return the other user
        if user_id == user1_id:
            return self.user2
        elif user_id == user2_id:
            return self.user1
        
        return None

    def can_user_send_message(self, user):
        """Check if user can send messages in this conversation"""
        if self.is_locked and not user.is_staff:
            return False
        if user not in [self.user1, self.user2]:
            return False
        return True

    def update_scam_score(self, points):
        """Update scam score (clamped to 0-100)"""
        self.scam_score = max(0, min(100, self.scam_score + points))
        self.save(update_fields=['scam_score'])


class Message(models.Model):
    """
    Individual message in a conversation
    """
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('system', 'System Message'),
        ('warning', 'Warning Message'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_messages',
        help_text="Null for system messages"
    )
    content = models.TextField(help_text="Message content (may be filtered)")
    original_content = models.TextField(
        blank=True,
        help_text="Original content before filtering (admin only)"
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_edited = models.BooleanField(default=False, help_text="Whether this message has been edited")
    edited_at = models.DateTimeField(null=True, blank=True, help_text="When the message was last edited")
    flagged = models.BooleanField(
        default=False,
        help_text="Message flagged for review"
    )
    flagged_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for flagging"
    )
    scam_detected = models.BooleanField(
        default=False,
        help_text="Scam pattern detected in this message"
    )
    scam_patterns = models.JSONField(
        default=list,
        blank=True,
        help_text="List of detected scam patterns"
    )
    # File attachments
    attachment = models.FileField(
        upload_to='messages/attachments/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="File attachment (image, document, etc.)"
    )
    attachment_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Type of attachment: image, document, video, audio"
    )
    attachment_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Original filename"
    )
    attachment_size = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (system notes, etc.)"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag (users cannot delete, admin only)"
    )

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['flagged', 'created_at']),
            models.Index(fields=['scam_detected', 'created_at']),
        ]

    def __str__(self):
        sender_info = self.sender.email if self.sender else "System"
        return f"{sender_info}: {self.content[:50]}..."

    def mark_as_read(self, user):
        """Mark message as read by user"""
        if not self.read and self.sender and self.sender != user:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])


class MessageReaction(models.Model):
    """
    Emoji reactions to messages
    """
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reactions'
    )
    emoji = models.CharField(
        max_length=10,
        help_text="Emoji character (e.g., '👍', '❤️', '😂')"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_reactions'
        unique_together = ['message', 'user', 'emoji']  # One reaction per user per emoji per message
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['message', 'emoji']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} reacted {self.emoji} to message {self.message.id}"


class MessageReport(models.Model):
    """
    User reports of inappropriate messages
    """
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reports'
    )
    reason = models.TextField(help_text="Reason for reporting")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_message_reports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'message_reports'
        ordering = ['-created_at']
        unique_together = [['message', 'reported_by']]

    def __str__(self):
        return f"Report on message {self.message.id} by {self.reported_by.email}"

