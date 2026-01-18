"""
URL configuration for messaging app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, MessageViewSet, MessageReportViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'reports', MessageReportViewSet, basename='message-report')

urlpatterns = [
    path('', include(router.urls)),
]

