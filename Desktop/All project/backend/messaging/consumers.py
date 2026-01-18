"""
Django Channels consumers for real-time messaging.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time messaging.
    Users join conversation rooms to receive real-time message updates.
    """
    
    async def connect(self):
        """User connects to a conversation room"""
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Get conversation ID from URL
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'messages_{self.conversation_id}'
        
        # Join conversation room
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Update user's last_seen when they connect (must be after accept)
        await self.update_user_presence(True)
        
        # Broadcast user online status to conversation
        await self.broadcast_presence(True)
    
    async def disconnect(self, close_code):
        """Leave conversation room"""
        # Mark user as offline when they disconnect WebSocket
        if self.user and self.user.is_authenticated:
            await self.mark_user_offline()
        
        # Broadcast user offline status
        if hasattr(self, 'room_group_name'):
            await self.broadcast_presence(False)
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'typing':
                # Broadcast typing indicator to other users in conversation
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': self.user.id,
                        'user_name': await self.get_user_name(),
                        'is_typing': data.get('is_typing', False)
                    }
                )
        except json.JSONDecodeError:
            pass
    
    async def new_message(self, event):
        """Send new message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
    
    async def message_updated(self, event):
        """Send message update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_updated',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    @database_sync_to_async
    def get_user_name(self):
        """Get user's display name"""
        if self.user:
            return self.user.get_full_name() or self.user.email
        return 'Unknown'
    
    @database_sync_to_async
    def update_user_presence(self, is_online):
        """Update user's online status"""
        if self.user and self.user.is_authenticated:
            from django.utils import timezone
            from django.core.cache import cache
            
            # Refresh user from database to get latest last_seen value
            self.user.refresh_from_db(fields=['last_seen'])
            
            # If last_seen is None, user has explicitly logged out - don't update
            # This ensures logged-out users stay offline
            if self.user.last_seen is None:
                return
            
            # Update last_seen in database
            self.user.last_seen = timezone.now()
            self.user.save(update_fields=['last_seen'])
            
            # Also update cache to ensure immediate consistency
            cache_key = f'last_seen_update_{self.user.id}'
            cache.set(cache_key, timezone.now(), 15)
    
    async def broadcast_presence(self, is_online):
        """Broadcast user's online/offline status to conversation"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_presence',
                    'user_id': self.user.id,
                    'user_name': await self.get_user_name(),
                    'is_online': is_online
                }
            )
    
    @database_sync_to_async
    def mark_user_offline(self):
        """Mark user as offline by clearing cache - keep last_seen for "last seen" display"""
        if self.user and self.user.is_authenticated:
            from django.core.cache import cache
            
            # Only clear cache - don't set last_seen to None
            # This way we can still show "Last seen X minutes ago" after browser close
            # Setting last_seen to None is reserved for explicit logout only
            cache_key = f'last_seen_update_{self.user.id}'
            cache.delete(cache_key)
    
    async def user_presence(self, event):
        """Send user presence update to WebSocket"""
        # Don't send presence to the user themselves
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'presence',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_online': event['is_online']
            }))

