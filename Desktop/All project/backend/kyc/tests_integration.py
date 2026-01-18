from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from .models import KYCVerification

User = get_user_model()


class KYCApprovalWorkflowTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.kyc = KYCVerification.objects.create(
            user=self.user,
            status='PENDING',
            document_type='PASSPORT',
            document_number='P12345678',
            first_name='John',
            last_name='Doe',
            date_of_birth='1990-01-01',
            address='123 Test Street',
            document_front='kyc/documents/front.jpg',
            selfie='kyc/selfies/selfie.jpg'
        )

    def test_kyc_approval_workflow(self):
        """Test the complete KYC approval workflow"""
        # Initially KYC should be pending
        self.assertEqual(self.kyc.status, 'PENDING')
        
        # Admin approves KYC
        self.kyc.status = 'APPROVED'
        self.kyc.reviewed_by = self.admin_user
        self.kyc.reviewed_at = timezone.now()
        self.kyc.save()
        
        # Verify KYC is approved
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.status, 'APPROVED')
        self.assertEqual(self.kyc.reviewed_by, self.admin_user)
        self.assertIsNotNone(self.kyc.reviewed_at)

    def test_kyc_rejection_workflow(self):
        """Test the complete KYC rejection workflow"""
        # Initially KYC should be pending
        self.assertEqual(self.kyc.status, 'PENDING')
        
        # Admin rejects KYC with reason
        rejection_reason = 'Document not clear'
        self.kyc.status = 'REJECTED'
        self.kyc.reviewed_by = self.admin_user
        self.kyc.rejection_reason = rejection_reason
        self.kyc.reviewed_at = timezone.now()
        self.kyc.save()
        
        # Verify KYC is rejected
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.status, 'REJECTED')
        self.assertEqual(self.kyc.reviewed_by, self.admin_user)
        self.assertEqual(self.kyc.rejection_reason, rejection_reason)
        self.assertIsNotNone(self.kyc.reviewed_at)