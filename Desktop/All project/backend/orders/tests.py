from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import GiftCard, GiftCardOrder

User = get_user_model()


class GiftCardModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.gift_card = GiftCard.objects.create(
            name='Amazon $50 Gift Card',
            brand='Amazon',
            rate_buy=Decimal('0.95'),
            rate_sell=Decimal('0.90'),
            is_active=True
        )

    def test_gift_card_creation(self):
        """Test that gift card is created correctly"""
        self.assertEqual(self.gift_card.name, 'Amazon $50 Gift Card')
        self.assertEqual(self.gift_card.brand, 'Amazon')
        self.assertEqual(self.gift_card.rate_buy, Decimal('0.95'))
        self.assertEqual(self.gift_card.rate_sell, Decimal('0.90'))
        self.assertTrue(self.gift_card.is_active)

    def test_gift_card_str(self):
        """Test gift card string representation"""
        self.assertEqual(str(self.gift_card), 'Amazon - Amazon $50 Gift Card')


class GiftCardOrderModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.gift_card = GiftCard.objects.create(
            name='Amazon $50 Gift Card',
            brand='Amazon',
            rate_buy=Decimal('0.95'),
            rate_sell=Decimal('0.90'),
            is_active=True
        )
        self.order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='buy',
            amount=Decimal('100.00'),
            status='pending'
        )

    def test_gift_card_order_creation(self):
        """Test that gift card order is created correctly"""
        self.assertEqual(self.order.user, self.user)
        self.assertEqual(self.order.card, self.gift_card)
        self.assertEqual(self.order.order_type, 'buy')
        self.assertEqual(self.order.amount, Decimal('100.00'))
        self.assertEqual(self.order.status, 'pending')

    def test_gift_card_order_str(self):
        """Test gift card order string representation"""
        expected = f"{self.user.email} - {self.gift_card.name} - {self.order.amount}"
        self.assertEqual(str(self.order), expected)

    def test_calculated_amount(self):
        """Test calculated amount based on order type and rates"""
        # For buy order, calculated amount = amount * rate_buy
        buy_order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='buy',
            amount=Decimal('100.00'),
            status='pending'
        )
        self.assertEqual(buy_order.calculated_amount, Decimal('95.00'))  # 100 * 0.95

        # For sell order, calculated amount = amount * rate_sell
        sell_order = GiftCardOrder.objects.create(
            user=self.user,
            card=self.gift_card,
            order_type='sell',
            amount=Decimal('100.00'),
            status='pending'
        )
        self.assertEqual(sell_order.calculated_amount, Decimal('90.00'))  # 100 * 0.90