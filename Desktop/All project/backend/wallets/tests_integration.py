from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Wallet, CryptoTransaction
from orders.models import GiftCard, GiftCardOrder

User = get_user_model()


class BuyCryptoWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance_cedis=Decimal('1000.00'),
            balance_crypto=Decimal('0.00000000'),
            escrow_balance=Decimal('0.00')
        )

    def test_buy_crypto_workflow(self):
        """Test the complete buy crypto workflow"""
        # User has 1000 GHS in wallet
        self.assertEqual(self.wallet.balance_cedis, Decimal('1000.00'))
        
        # User wants to buy crypto worth 500 GHS at rate 40000 GHS/BTC
        crypto_amount = Decimal('0.01250000')  # 500 / 40000
        cedis_amount = Decimal('500.00')
        rate = Decimal('40000.00')
        
        # Create crypto transaction (simulating the buy_crypto view)
        crypto_txn = CryptoTransaction.objects.create(
            user=self.user,
            type='buy',
            cedis_amount=cedis_amount,
            crypto_amount=crypto_amount,
            rate=rate,
            status='pending',
            payment_method='momo',
            reference=CryptoTransaction.generate_reference('BUY'),
            escrow_locked=True
        )
        
        # Lock cedis to escrow (simulating the wallet.lock_cedis_to_escrow)
        self.wallet.lock_cedis_to_escrow(cedis_amount)
        
        # Verify escrow balance increased
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.escrow_balance, cedis_amount)
        self.assertEqual(self.wallet.balance_cedis, Decimal('500.00'))
        
        # Admin approves the transaction
        crypto_txn.status = 'approved'
        crypto_txn.escrow_locked = False
        crypto_txn.save()
        
        # Deduct from escrow and add crypto (simulating the approve view)
        self.wallet.deduct_from_escrow(cedis_amount)
        self.wallet.add_crypto(crypto_amount)
        
        # Verify final state
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.escrow_balance, Decimal('0.00'))
        self.assertEqual(self.wallet.balance_cedis, Decimal('500.00'))
        self.assertEqual(self.wallet.balance_crypto, crypto_amount)


class SellCryptoWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance_cedis=Decimal('0.00'),
            balance_crypto=Decimal('0.10000000'),
            escrow_balance=Decimal('0.00')
        )

    def test_sell_crypto_workflow(self):
        """Test the complete sell crypto workflow"""
        # User has 0.1 BTC in wallet
        self.assertEqual(self.wallet.balance_crypto, Decimal('0.10000000'))
        
        # User wants to sell 0.05 BTC at rate 40000 GHS/BTC
        crypto_amount = Decimal('0.05000000')
        cedis_amount = Decimal('2000.00')  # 0.05 * 40000
        rate = Decimal('40000.00')
        
        # Create crypto transaction (simulating the sell_crypto view)
        crypto_txn = CryptoTransaction.objects.create(
            user=self.user,
            type='sell',
            cedis_amount=cedis_amount,
            crypto_amount=crypto_amount,
            rate=rate,
            status='pending',
            payment_method='crypto',
            reference=CryptoTransaction.generate_reference('SELL'),
            escrow_locked=True
        )
        
        # Deduct crypto from wallet (simulating the wallet.deduct_crypto)
        self.wallet.deduct_crypto(crypto_amount)
        
        # Verify crypto balance decreased
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_crypto, Decimal('0.05000000'))
        
        # Admin approves the transaction
        crypto_txn.status = 'approved'
        crypto_txn.escrow_locked = False
        crypto_txn.save()
        
        # Add cedis to wallet (simulating the approve view)
        self.wallet.add_cedis(cedis_amount)
        
        # Verify final state
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_crypto, Decimal('0.05000000'))
        self.assertEqual(self.wallet.balance_cedis, cedis_amount)


class GiftCardWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance_cedis=Decimal('1000.00'),
            balance_crypto=Decimal('0.00000000'),
            escrow_balance=Decimal('0.00')
        )
        self.gift_card = GiftCard.objects.create(
            name='Amazon $100 Gift Card',
            brand='Amazon',
            rate_buy=Decimal('0.95'),  # 95 GHS for $100
            rate_sell=Decimal('0.90'),  # 90 GHS for $100
            is_active=True
        )

    def test_buy_gift_card_workflow(self):
        """Test buying a gift card"""
        # User wants to buy a $100 gift card
        amount = Decimal('100.00')
        
        # Create gift card order
        order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='buy',
            amount=amount,
            status='pending'
        )
        
        # Calculated amount should be 95 GHS (100 * 0.95)
        self.assertEqual(order.calculated_amount, Decimal('95.00'))
        
        # User uploads proof and admin approves
        order.status = 'approved'
        order.save()
        
        # In a real scenario, the user would receive the gift card
        # This is just a test to verify the workflow

    def test_sell_gift_card_workflow(self):
        """Test selling a gift card"""
        # User wants to sell a $100 gift card
        amount = Decimal('100.00')
        
        # Create gift card order
        order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='sell',
            amount=amount,
            status='pending'
        )
        
        # Calculated amount should be 90 GHS (100 * 0.90)
        self.assertEqual(order.calculated_amount, Decimal('90.00'))
        
        # User uploads proof and admin approves
        order.status = 'approved'
        order.save()
        
        # In a real scenario, the user would receive 90 GHS in their wallet
        # This is just a test to verify the workflow