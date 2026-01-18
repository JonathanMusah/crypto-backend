from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import KYCVerification

User = get_user_model()


class KYCVerificationModelTest(TestCase):
    def setUp(self):
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

    def test_kyc_verification_creation(self):
        """Test that KYC verification is created correctly"""
        self.assertEqual(self.kyc.user, self.user)
        self.assertEqual(self.kyc.status, 'PENDING')
        self.assertEqual(self.kyc.document_type, 'PASSPORT')
        self.assertEqual(self.kyc.document_number, 'P12345678')
        self.assertEqual(self.kyc.first_name, 'John')
        self.assertEqual(self.kyc.last_name, 'Doe')
        self.assertEqual(str(self.kyc.date_of_birth), '1990-01-01')
        self.assertEqual(self.kyc.address, '123 Test Street')
        self.assertEqual(self.kyc.document_front, 'kyc/documents/front.jpg')
        self.assertEqual(self.kyc.selfie, 'kyc/selfies/selfie.jpg')

    def test_kyc_verification_str(self):
        """Test KYC verification string representation"""
        expected = f"{self.user.email} - {self.kyc.status}"
        self.assertEqual(str(self.kyc), expected)

    def test_kyc_verification_status_choices(self):
        """Test that KYC verification status choices work correctly"""
        # Test changing status to approved
        self.kyc.status = 'APPROVED'
        self.kyc.save()
        self.assertEqual(self.kyc.status, 'APPROVED')
        
        # Test changing status to rejected
        self.kyc.status = 'REJECTED'
        self.kyc.save()
        self.assertEqual(self.kyc.status, 'REJECTED')
        
        # Test rejection reason field
        self.kyc.rejection_reason = 'Document not clear'
        self.kyc.save()
        self.assertEqual(self.kyc.rejection_reason, 'Document not clear')