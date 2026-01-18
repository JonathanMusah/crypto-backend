from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from authentication.permissions import IsAdminUser
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notifications.
    - List: User's own notifications (or all for admins)
    - Retrieve: Get single notification
    - Create: Admin only - Create new notification
    - Mark as read: Update notification status
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'read']
    ordering_fields = ['created_at']

    def get_permissions(self):
        """Allow create only for admin users"""
        if self.action == 'create':
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Users see their own notifications only"""
        # Always filter by current user - even admins should only see their own notifications
        # If admins need to see all notifications, create a separate admin-only endpoint
        return Notification.objects.filter(user=self.request.user).select_related('user')

    def create(self, request, *args, **kwargs):
        """Create notification - admin only"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # If user is specified, use it; otherwise create for all users (if needed)
        notification = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark a single notification as read.
        Endpoint: /api/notifications/notifications/{id}/mark_read/
        """
        notification = self.get_object()
        notification.mark_as_read()
        return Response({
            'message': 'Notification marked as read',
            'notification': NotificationSerializer(notification).data
        })

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read for the current user.
        Endpoint: /api/notifications/notifications/mark_all_read/
        """
        updated_count = Notification.objects.filter(
            user=request.user, 
            read=False
        ).update(read=True)
        return Response({
            'message': f'{updated_count} notifications marked as read',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Get count of unread notifications.
        Endpoint: /api/notifications/notifications/unread_count/
        """
        count = Notification.objects.filter(user=request.user, read=False).count()
        return Response({'unread_count': count})

