"""
Utility functions for notifications including real-time WebSocket support.
"""

import json
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification


def create_notification(user, notification_type, title, message, related_object_type=None, related_object_id=None, sender_user=None):
    """
    Create a notification and send it via WebSocket if Channels is enabled.
    
    Args:
        user: User to send notification to
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        related_object_type: Optional related object type
        related_object_id: Optional related object ID
        sender_user: Optional sender user (for NEW_MESSAGE notifications, prevents notifying sender)
    """
    # CRITICAL SAFETY CHECK: For NEW_MESSAGE notifications, NEVER notify the sender
    if notification_type == 'NEW_MESSAGE':
        import logging
        logger = logging.getLogger(__name__)
        
        print(f"[NOTIFICATION UTILS] ========== create_notification called ==========")
        print(f"[NOTIFICATION UTILS] User (recipient): {user.id if user else None} ({user.email if user else 'None'})")
        print(f"[NOTIFICATION UTILS] Sender: {sender_user.id if sender_user else None} ({sender_user.email if sender_user else 'None'})")
        print(f"[NOTIFICATION UTILS] Notification type: {notification_type}")
        
        # Check if sender_user is provided and matches the recipient
        if sender_user:
            user_id = user.id if user else None
            sender_id = sender_user.id if sender_user else None
            
            print(f"[NOTIFICATION UTILS] Safety check - User ID: {user_id}, Sender ID: {sender_id}, Match: {user_id == sender_id}")
            logger.info(f"[NOTIFICATION] Safety check - User ID: {user_id}, Sender ID: {sender_id}, Match: {user_id == sender_id}")
            
            if user_id is not None and sender_id is not None and user_id == sender_id:
                print(f"[NOTIFICATION UTILS] BLOCKED: Attempted to notify sender!")
                print(f"[NOTIFICATION UTILS] User ID: {user_id}, Sender ID: {sender_id}")
                print(f"[NOTIFICATION UTILS] User email: {user.email if user else 'None'}")
                print(f"[NOTIFICATION UTILS] Sender email: {sender_user.email if sender_user else 'None'}")
                logger.error(f"[NOTIFICATION] BLOCKED: Attempted to create NEW_MESSAGE notification for sender! User: {user_id} ({user.email if user else 'None'}), Sender: {sender_id} ({sender_user.email if sender_user else 'None'})")
                return None  # Don't create the notification
            else:
                print(f"[NOTIFICATION UTILS] OK: Safety check passed - User and Sender are different")
        else:
            print(f"[NOTIFICATION UTILS] ⚠ WARNING: sender_user is None - cannot perform safety check!")
            logger.warning(f"[NOTIFICATION] sender_user is None - safety check skipped")
    
    # Create the notification in database
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    
    # Send real-time notification via WebSocket if enabled
    if 'channels' in settings.INSTALLED_APPS:
        send_realtime_notification(user.id, {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'created_at': notification.created_at.isoformat(),
            'read': notification.read,
        })
    
    return notification


def send_realtime_notification(user_id, notification_data):
    """
    Send real-time notification via WebSocket.
    
    Args:
        user_id: ID of user to send notification to
        notification_data: Dictionary containing notification data
    """
    try:
        channel_layer = get_channel_layer()
        # Only send if channel layer is properly configured
        if channel_layer is not None:
            group_name = f"notifications_{user_id}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification.message',
                    'notification': notification_data
                }
            )
    except Exception as e:
        # Log error but don't fail the notification creation
        # This is expected if Channels is not fully configured
        pass