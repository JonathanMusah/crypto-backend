from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserDevice, SecurityLog
from .serializers import UserDeviceSerializer, SecurityLogSerializer
from .views import get_client_ip, get_user_agent


class UserDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing user devices.
    Users can view and revoke their device sessions.
    """
    serializer_class = UserDeviceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return only devices for the current user"""
        return UserDevice.objects.filter(user=self.request.user, is_active=True)
    
    def get_serializer_context(self):
        """Add request to context for device comparison"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke a device session"""
        device = self.get_object()
        
        # Don't allow revoking the current device (security measure)
        current_ip = get_client_ip(request)
        current_ua = get_user_agent(request)
        current_fingerprint = UserDevice.generate_fingerprint(current_ip, current_ua)
        
        if device.device_fingerprint == current_fingerprint:
            return Response(
                {'error': 'You cannot revoke your current device session. Please log out instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Revoke the device
        device.is_active = False
        device.save(update_fields=['is_active'])
        
        # Log the revocation
        SecurityLog.objects.create(
            user=request.user,
            event_type='device_revoked',
            ip_address=current_ip,
            user_agent=current_ua,
            details={
                'revoked_device_id': device.id,
                'revoked_ip': device.ip_address,
                'message': f'Device session revoked by user'
            }
        )
        
        return Response({
            'message': 'Device session revoked successfully',
            'device_id': device.id
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def security_logs(self, request):
        """Get security logs for the current user"""
        logs = SecurityLog.objects.filter(user=request.user).order_by('-created_at')[:50]
        serializer = SecurityLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

