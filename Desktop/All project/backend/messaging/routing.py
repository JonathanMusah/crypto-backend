"""
WebSocket URL routing for messaging.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/messages/(?P<conversation_id>\d+)/$', consumers.MessageConsumer.as_asgi()),
]

