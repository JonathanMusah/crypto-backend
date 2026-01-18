from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.utils import timezone
from .models import KYCVerification
from .serializers import KYCVerificationSerializer, KYCSubmissionSerializer
from notifications.utils import create_notification


class KYCVerificationViewSet(viewsets.ModelViewSet):
    serializer_class = KYCVerificationSerializer
    permission_classes = []

    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.request.user.is_staff:
                return KYCVerification.objects.all()
            return KYCVerification.objects.filter(user=self.request.user)
        return KYCVerification.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return KYCSubmissionSerializer
        return KYCVerificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = serializer.save(user=request.user, status='PENDING')
        return Response(KYCVerificationSerializer(verification).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        verification = self.get_object()
        verification.status = 'APPROVED'
        verification.reviewed_by = request.user
        verification.reviewed_at = timezone.now()
        verification.save()
        
        # Sync status to User model
        user = verification.user
        user.kyc_status = 'approved'
        user.save(update_fields=['kyc_status'])
        
        # Create notification using utility function (handles WebSocket)
        create_notification(
            user=verification.user,
            notification_type='KYC_APPROVED',
            title='KYC Approved',
            message='Your KYC verification has been approved. You now have full access to all platform features.',
            related_object_type='kyc_verification',
            related_object_id=verification.id,
        )
        return Response({'message': 'KYC approved'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        verification = self.get_object()
        rejection_reason = request.data.get('rejection_reason', '')
        verification.status = 'REJECTED'
        verification.rejection_reason = rejection_reason
        verification.reviewed_by = request.user
        verification.reviewed_at = timezone.now()
        verification.save()
        
        # Sync status to User model
        user = verification.user
        user.kyc_status = 'rejected'
        user.save(update_fields=['kyc_status'])
        
        # Create notification using utility function (handles WebSocket)
        rejection_message = f'Your KYC verification has been rejected. Reason: {rejection_reason}. Please review and resubmit your documents.' if rejection_reason else 'Your KYC verification has been rejected. Please review and resubmit your documents.'
        create_notification(
            user=verification.user,
            notification_type='KYC_REJECTED',
            title='KYC Rejected',
            message=rejection_message,
            related_object_type='kyc_verification',
            related_object_id=verification.id,
        )
        return Response({'message': 'KYC rejected'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def status(self, request):
        """Get the current user's KYC status"""
        try:
            # Since it's OneToOne, we can use get() directly
            verification = KYCVerification.objects.get(user=request.user)
            serializer = self.get_serializer(verification)
            # Convert status to lowercase to match frontend expectations
            data = serializer.data
            if 'status' in data:
                data['status'] = data['status'].lower()
            # Map field names to match frontend expectations
            if 'document_front' in data:
                data['document_front'] = data['document_front']
            if 'document_back' in data:
                data['document_back'] = data['document_back']
            return Response(data)
        except KYCVerification.DoesNotExist:
            return Response(
                {'detail': 'No KYC verification found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], permission_classes=[])
    def document_types(self, request):
        """Get list of supported document types"""
        return Response([
            {'value': 'PASSPORT', 'label': 'Passport'},
            {'value': 'DRIVER_LICENSE', 'label': 'Driver License'},
            {'value': 'NATIONAL_ID', 'label': 'National ID'},
        ])

