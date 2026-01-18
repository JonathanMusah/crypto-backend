"""
Comprehensive Test Suite for Crypto P2P Trading System
Tests for models, serializers, views, and complete transaction flows
"""
import json
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from wallets.models import Wallet
from wallets.crypto_p2p_models import (
    CryptoListing,
    CryptoTransaction,
    CryptoTransactionAuditLog,
    CryptoTransactionDispute,
)

User = get_user_model()


class CryptoListingModelTest(TestCase):
    """Test CryptoListing model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='seller@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Seller'
        )
        self.wallet = Wallet.objects.create(user=self.user, cedis_balance=1000)
    
    def test_create_crypto_listing(self):
        """Test creating a crypto listing"""
        listing = CryptoListing.objects.create(
            seller=self.user,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            min_amount_crypto=Decimal('0.01'),
            max_amount_crypto=Decimal('2.0'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            payment_methods=['bank_transfer', 'momo'],
            buyer_requirements={'min_account_age_days': 1},
            status='active'
        )
        
        self.assertEqual(listing.seller, self.user)
        self.assertEqual(listing.listing_type, 'sell')
        self.assertEqual(listing.crypto_type, 'btc')
        self.assertEqual(listing.status, 'active')
        self.assertTrue(listing.reference)
    
    def test_listing_reference_generation(self):
        """Test unique reference generation"""
        listing1 = CryptoListing.objects.create(
            seller=self.user,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
        
        listing2 = CryptoListing.objects.create(
            seller=self.user,
            listing_type='buy',
            crypto_type='eth',
            network='ethereum',
            amount_crypto=Decimal('1.0'),
            available_amount_crypto=Decimal('1.0'),
            rate_cedis_per_crypto=Decimal('7500.00'),
            status='active'
        )
        
        self.assertNotEqual(listing1.reference, listing2.reference)
        self.assertTrue(listing1.reference.startswith('BTCSEL'))
        self.assertTrue(listing2.reference.startswith('ETHBUY'))


class CryptoTransactionModelTest(TransactionTestCase):
    """Test CryptoTransaction model with atomic operations"""
    
    def setUp(self):
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='testpass123'
        )
        
        self.seller_wallet = Wallet.objects.create(
            user=self.seller,
            cedis_balance=Decimal('1000.00')
        )
        self.buyer_wallet = Wallet.objects.create(
            user=self.buyer,
            cedis_balance=Decimal('500000.00')
        )
        
        self.listing = CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
    
    def test_create_crypto_transaction(self):
        """Test creating a crypto transaction with escrow"""
        transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={'momo': '+233502123456'},
            status='payment_received',
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15)
        )
        
        self.assertEqual(transaction.status, 'payment_received')
        self.assertTrue(transaction.escrow_locked)
        self.assertEqual(transaction.escrow_amount_cedis, Decimal('15000.00'))
        self.assertTrue(transaction.reference)
    
    def test_transaction_status_transitions(self):
        """Test transaction status flow"""
        transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={},
            status='payment_received',
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15)
        )
        
        # Step 1: Buyer marks paid
        transaction.mark_payment_sent(self.buyer)
        self.assertEqual(transaction.status, 'buyer_marked_paid')
        self.assertTrue(transaction.buyer_marked_paid)
        self.assertIsNotNone(transaction.seller_confirmation_deadline)
        
        # Step 2: Seller confirms payment
        transaction.confirm_payment(self.seller)
        self.assertEqual(transaction.status, 'seller_confirmed_payment')
        self.assertTrue(transaction.seller_confirmed_payment)
        self.assertIsNotNone(transaction.seller_response_deadline)
        
        # Step 3: Seller sends crypto
        transaction.send_crypto(
            self.seller,
            'abc123def456ghi789jkl012mno345pqr678stu901vwx234yz',
            None
        )
        self.assertEqual(transaction.status, 'crypto_sent')
        self.assertTrue(transaction.crypto_sent)
        self.assertIsNotNone(transaction.buyer_verification_deadline)
        
        # Step 4: Buyer verifies
        transaction.verify_crypto(self.buyer, True)
        self.assertEqual(transaction.status, 'completed')
        self.assertTrue(transaction.buyer_verified)
        self.assertIsNotNone(transaction.completed_at)


class CryptoListingAPITest(APITestCase):
    """Test Crypto Listing API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='testpass123'
        )
        
        self.seller_wallet = Wallet.objects.create(user=self.seller)
        self.buyer_wallet = Wallet.objects.create(user=self.buyer)
    
    def test_create_listing_authenticated(self):
        """Test creating a crypto listing as authenticated seller"""
        self.client.force_authenticate(user=self.seller)
        
        data = {
            'listing_type': 'sell',
            'crypto_type': 'btc',
            'network': 'bitcoin',
            'amount_crypto': '0.5',
            'available_amount_crypto': '0.5',
            'min_amount_crypto': '0.01',
            'max_amount_crypto': '2.0',
            'rate_cedis_per_crypto': '150000.00',
            'payment_methods': ['bank_transfer', 'momo']
        }
        
        response = self.client.post('/api/wallets/crypto/p2p/listings/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['listing_type'], 'sell')
        self.assertEqual(response.data['crypto_type'], 'btc')
    
    def test_list_active_listings(self):
        """Test listing active crypto listings"""
        self.client.force_authenticate(user=self.seller)
        
        CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
        
        response = self.client.get('/api/wallets/crypto/p2p/listings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_search_listings(self):
        """Test searching crypto listings"""
        self.client.force_authenticate(user=self.seller)
        
        CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
        
        response = self.client.post(
            '/api/wallets/crypto/p2p/listings/search/',
            {'crypto_type': 'btc'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CryptoTransactionAPITest(TransactionTestCase):
    """Test Crypto Transaction API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='testpass123'
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='testpass123'
        )
        
        self.seller_wallet = Wallet.objects.create(
            user=self.seller,
            cedis_balance=Decimal('1000.00')
        )
        self.buyer_wallet = Wallet.objects.create(
            user=self.buyer,
            cedis_balance=Decimal('500000.00')
        )
        
        self.listing = CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            min_amount_crypto=Decimal('0.01'),
            max_amount_crypto=Decimal('2.0'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
    
    def test_buyer_initiates_transaction(self):
        """Test buyer initiating a crypto transaction"""
        self.client.force_authenticate(user=self.buyer)
        
        data = {
            'listing_id': self.listing.id,
            'amount_crypto': '0.1',
            'buyer_wallet_address': '1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            'buyer_payment_details': {'momo': '+233502123456'}
        }
        
        response = self.client.post(
            '/api/wallets/crypto/p2p/transactions/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'payment_received')
        self.assertTrue(response.data['escrow_locked'])
        
        # Check escrow was locked in buyer's wallet
        self.buyer_wallet.refresh_from_db()
        self.assertEqual(self.buyer_wallet.cedis_in_escrow, Decimal('15000.00'))
    
    def test_buyer_marks_payment_sent(self):
        """Test buyer marking payment as sent"""
        self.client.force_authenticate(user=self.buyer)
        
        # Create transaction
        transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={},
            status='payment_received',
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15)
        )
        
        # Create fake image
        image = SimpleUploadedFile(
            "payment.jpg",
            b"fake_image_content",
            content_type="image/jpeg"
        )
        
        data = {
            'payment_screenshot': image,
            'notes': 'Sent payment via MoMo'
        }
        
        response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction.id}/mark_paid/',
            data,
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'buyer_marked_paid')
        self.assertTrue(response.data['buyer_marked_paid'])
    
    def test_seller_confirms_payment(self):
        """Test seller confirming payment"""
        self.client.force_authenticate(user=self.seller)
        
        transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={},
            status='buyer_marked_paid',
            buyer_marked_paid=True,
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15),
            seller_confirmation_deadline=timezone.now() + timedelta(minutes=15)
        )
        
        data = {'notes': 'Payment confirmed'}
        
        response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction.id}/confirm_payment/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'seller_confirmed_payment')
    
    def test_complete_transaction_flow(self):
        """Test complete happy path transaction flow"""
        # Create transaction
        self.client.force_authenticate(user=self.buyer)
        tx_data = {
            'listing_id': self.listing.id,
            'amount_crypto': '0.1',
            'buyer_wallet_address': '1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            'buyer_payment_details': {'momo': '+233502123456'}
        }
        
        tx_response = self.client.post(
            '/api/wallets/crypto/p2p/transactions/',
            tx_data,
            format='json'
        )
        self.assertEqual(tx_response.status_code, status.HTTP_201_CREATED)
        transaction_id = tx_response.data['id']
        
        # Buyer marks payment sent
        image = SimpleUploadedFile("payment.jpg", b"content", content_type="image/jpeg")
        mark_data = {'payment_screenshot': image, 'notes': 'Payment sent'}
        
        mark_response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction_id}/mark_paid/',
            mark_data,
            format='multipart'
        )
        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        
        # Seller confirms payment
        self.client.force_authenticate(user=self.seller)
        confirm_response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction_id}/confirm_payment/',
            {'notes': 'Confirmed'},
            format='json'
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        
        # Seller sends crypto
        send_data = {'transaction_hash': 'abc123def456ghi789jkl012mno345pqr678stu'}
        send_response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction_id}/send_crypto/',
            send_data,
            format='json'
        )
        self.assertEqual(send_response.status_code, status.HTTP_200_OK)
        
        # Buyer verifies
        self.client.force_authenticate(user=self.buyer)
        verify_data = {'verified': True, 'notes': 'Crypto received'}
        verify_response = self.client.post(
            f'/api/wallets/crypto/p2p/transactions/{transaction_id}/verify/',
            verify_data,
            format='json'
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_response.data['status'], 'completed')


class CryptoAuditLogTest(TestCase):
    """Test CryptoTransactionAuditLog"""
    
    def setUp(self):
        self.seller = User.objects.create_user(email='seller@test.com')
        self.buyer = User.objects.create_user(email='buyer@test.com')
        
        self.listing = CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
        
        self.transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={},
            status='payment_received',
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15)
        )
    
    def test_audit_log_creation(self):
        """Test creating audit log with HMAC signature"""
        audit = CryptoTransactionAuditLog.objects.create(
            transaction=self.transaction,
            action='created',
            performed_by=self.buyer,
            notes='Transaction initiated'
        )
        
        self.assertEqual(audit.action, 'created')
        self.assertEqual(audit.performed_by, self.buyer)
        self.assertIsNotNone(audit.signature)


class CryptoDisputeTest(TestCase):
    """Test CryptoTransactionDispute"""
    
    def setUp(self):
        self.seller = User.objects.create_user(email='seller@test.com')
        self.buyer = User.objects.create_user(email='buyer@test.com')
        
        self.listing = CryptoListing.objects.create(
            seller=self.seller,
            listing_type='sell',
            crypto_type='btc',
            network='bitcoin',
            amount_crypto=Decimal('0.5'),
            available_amount_crypto=Decimal('0.5'),
            rate_cedis_per_crypto=Decimal('150000.00'),
            status='active'
        )
        
        self.transaction = CryptoTransaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            amount_crypto=Decimal('0.1'),
            amount_cedis=Decimal('15000.00'),
            rate_applied=Decimal('150000.00'),
            buyer_wallet_address='1A1z7agoat3x4SksqM2F7JysSLaimHa6i',
            buyer_payment_details={},
            status='crypto_sent',
            escrow_locked=True,
            escrow_amount_cedis=Decimal('15000.00'),
            payment_deadline=timezone.now() + timedelta(minutes=15)
        )
    
    def test_create_dispute(self):
        """Test creating a dispute"""
        dispute = CryptoTransactionDispute.objects.create(
            transaction=self.transaction,
            raised_by=self.buyer,
            dispute_type='crypto_not_received',
            description='Crypto not received'
        )
        
        self.assertEqual(dispute.status, 'open')
        self.assertEqual(dispute.dispute_type, 'crypto_not_received')
        self.assertEqual(dispute.raised_by, self.buyer)
