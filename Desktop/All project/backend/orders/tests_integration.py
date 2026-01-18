from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import GiftCard, GiftCardOrder
from wallets.models import Wallet

User = get_user_model()


class GiftCardPurchaseWorkflowTest(TestCase):
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

    def test_gift_card_purchase_workflow(self):
        """Test the complete gift card purchase workflow"""
        # User wants to buy a $100 gift card
        amount = Decimal('100.00')
        calculated_amount = amount * self.gift_card.rate_buy  # 95 GHS
        
        # Create gift card order
        order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='buy',
            amount=amount,
            status='pending'
        )
        
        # Verify order details
        self.assertEqual(order.calculated_amount, calculated_amount)
        self.assertEqual(order.status, 'pending')
        
        # Admin approves the order
        order.status = 'approved'
        order.save()
        
        # Verify order is approved
        order.refresh_from_db()
        self.assertEqual(order.status, 'approved')

    def test_gift_card_sell_workflow(self):
        """Test the complete gift card sell workflow"""
        # User wants to sell a $100 gift card
        amount = Decimal('100.00')
        calculated_amount = amount * self.gift_card.rate_sell  # 90 GHS
        
        # Create gift card order
        order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='sell',
            amount=amount,
            status='pending'
        )
        
        # Verify order details
        self.assertEqual(order.calculated_amount, calculated_amount)
        self.assertEqual(order.status, 'pending')
        
        # Admin approves the order
        order.status = 'approved'
        order.save()
        
        # Verify order is approved
        order.refresh_from_db()
        self.assertEqual(order.status, 'approved')