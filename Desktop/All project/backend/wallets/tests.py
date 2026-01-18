from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Wallet, WalletTransaction, CryptoTransaction

User = get_user_model()


class WalletModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance_cedis=Decimal('1000.00'),
            balance_crypto=Decimal('0.50000000'),
            escrow_balance=Decimal('100.00')
        )

    def test_wallet_creation(self):
        """Test that wallet is created correctly"""
        self.assertEqual(self.wallet.user, self.user)
        self.assertEqual(self.wallet.balance_cedis, Decimal('1000.00'))
        self.assertEqual(self.wallet.balance_crypto, Decimal('0.50000000'))
        self.assertEqual(self.wallet.escrow_balance, Decimal('100.00'))

    def test_has_sufficient_cedis(self):
        """Test cedis balance checking"""
        self.assertTrue(self.wallet.has_sufficient_cedis(Decimal('500.00')))
        self.assertFalse(self.wallet.has_sufficient_cedis(Decimal('2000.00')))

    def test_has_sufficient_crypto(self):
        """Test crypto balance checking"""
        self.assertTrue(self.wallet.has_sufficient_crypto(Decimal('0.25000000')))
        self.assertFalse(self.wallet.has_sufficient_crypto(Decimal('1.00000000')))

    def test_add_cedis(self):
        """Test adding cedis to wallet"""
        initial_balance = self.wallet.balance_cedis
        self.wallet.add_cedis(Decimal('250.00'))
        self.assertEqual(self.wallet.balance_cedis, initial_balance + Decimal('250.00'))

    def test_deduct_crypto(self):
        """Test deducting crypto from wallet"""
        initial_balance = self.wallet.balance_crypto
        self.wallet.deduct_crypto(Decimal('0.10000000'))
        self.assertEqual(self.wallet.balance_crypto, initial_balance - Decimal('0.10000000'))

    def test_lock_cedis_to_escrow(self):
        """Test locking cedis to escrow"""
        initial_balance = self.wallet.balance_cedis
        initial_escrow = self.wallet.escrow_balance
        self.wallet.lock_cedis_to_escrow(Decimal('200.00'))
        self.assertEqual(self.wallet.balance_cedis, initial_balance - Decimal('200.00'))
        self.assertEqual(self.wallet.escrow_balance, initial_escrow + Decimal('200.00'))

    def test_deduct_from_escrow(self):
        """Test deducting from escrow"""
        initial_escrow = self.wallet.escrow_balance
        self.wallet.deduct_from_escrow(Decimal('50.00'))
        self.assertEqual(self.wallet.escrow_balance, initial_escrow - Decimal('50.00'))

    def test_release_cedis_from_escrow(self):
        """Test releasing cedis from escrow back to balance"""
        initial_balance = self.wallet.balance_cedis
        initial_escrow = self.wallet.escrow_balance
        self.wallet.release_cedis_from_escrow(Decimal('50.00'))
        self.assertEqual(self.wallet.balance_cedis, initial_balance + Decimal('50.00'))
        self.assertEqual(self.wallet.escrow_balance, initial_escrow - Decimal('50.00'))


class WalletTransactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.wallet = Wallet.objects.create(user=self.user)
        self.transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type='deposit',
            amount=Decimal('100.00'),
            currency='cedis',
            status='completed',
            reference='DEP-001',
            description='Test deposit',
            balance_before=Decimal('0.00'),
            balance_after=Decimal('100.00')
        )

    def test_transaction_creation(self):
        """Test that transaction is created correctly"""
        self.assertEqual(self.transaction.wallet, self.wallet)
        self.assertEqual(self.transaction.amount, Decimal('100.00'))
        self.assertEqual(self.transaction.currency, 'cedis')
        self.assertEqual(self.transaction.status, 'completed')
        self.assertEqual(self.transaction.reference, 'DEP-001')

    def test_generate_reference(self):
        """Test reference generation"""
        ref1 = WalletTransaction.generate_reference('DEP')
        ref2 = WalletTransaction.generate_reference('WTH')
        self.assertTrue(ref1.startswith('DEP-'))
        self.assertTrue(ref2.startswith('WTH-'))
        self.assertNotEqual(ref1, ref2)


class CryptoTransactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.crypto_transaction = CryptoTransaction.objects.create(
            user=self.user,
            type='buy',
            cedis_amount=Decimal('1000.00'),
            crypto_amount=Decimal('0.02500000'),
            rate=Decimal('40000.00'),
            status='pending',
            payment_method='momo',
            reference='BUY-001'
        )

    def test_crypto_transaction_creation(self):
        """Test that crypto transaction is created correctly"""
        self.assertEqual(self.crypto_transaction.user, self.user)
        self.assertEqual(self.crypto_transaction.type, 'buy')
        self.assertEqual(self.crypto_transaction.cedis_amount, Decimal('1000.00'))
        self.assertEqual(self.crypto_transaction.crypto_amount, Decimal('0.02500000'))
        self.assertEqual(self.crypto_transaction.rate, Decimal('40000.00'))
        self.assertEqual(self.crypto_transaction.status, 'pending')
        self.assertEqual(self.crypto_transaction.payment_method, 'momo')
        self.assertEqual(self.crypto_transaction.reference, 'BUY-001')

    def test_generate_reference(self):
        """Test reference generation"""
        ref1 = CryptoTransaction.generate_reference('BUY')
        ref2 = CryptoTransaction.generate_reference('SELL')
        self.assertTrue(ref1.startswith('BUY-'))
        self.assertTrue(ref2.startswith('SELL-'))
        self.assertNotEqual(ref1, ref2)