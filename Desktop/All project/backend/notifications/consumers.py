"""
Django Channels consumers for real-time notifications.
This file prepares the system for real-time integration using Django Channels.

To enable real-time notifications:
1. Install channels and channels-redis: pip install channels channels-redis
2. Configure ASGI application in config/asgi.py
3. Add channels to INSTALLED_APPS
4. Configure channel layers in settings.py
5. Run daphne or uvicorn instead of runserver

Example usage:
- When a notification is created, send it via WebSocket to the user
- Frontend connects to WebSocket and receives real-time updates
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Each user connects to their own notification channel.
    """
    
    async def connect(self):
        """User connects to their notification channel"""
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.room_group_name = f"notifications_{self.user.id}"
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        """Leave room group"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Receive message from WebSocket"""
        text_data_json = json.loads(text_data)
        message = text_data_json.get('message')
        
        # Handle different message types
        if message == 'mark_read':
            notification_id = text_data_json.get('notification_id')
            await self.mark_notification_read(notification_id)
    
    async def notification_message(self, event):
        """Send notification to WebSocket"""
        notification = event['notification']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': notification
        }))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

