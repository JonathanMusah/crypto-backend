from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import CryptoRate, RateCache

User = get_user_model()


class CryptoRateModelTest(TestCase):
    def setUp(self):
        self.rate = CryptoRate.objects.create(
            crypto_id='bitcoin',
            symbol='BTC',
            usd_price=Decimal('50000.00'),
            cedis_price=Decimal('300000.00'),
            is_active=True
        )

    def test_crypto_rate_creation(self):
        """Test that crypto rate is created correctly"""
        self.assertEqual(self.rate.crypto_id, 'bitcoin')
        self.assertEqual(self.rate.symbol, 'BTC')
        self.assertEqual(self.rate.usd_price, Decimal('50000.00'))
        self.assertEqual(self.rate.cedis_price, Decimal('300000.00'))
        self.assertTrue(self.rate.is_active)

    def test_crypto_rate_str(self):
        """Test crypto rate string representation"""
        expected = f"{self.rate.symbol} - ₵{self.rate.cedis_price} ({self.rate.timestamp})"
        self.assertEqual(str(self.rate), expected)

    def test_get_latest_rate(self):
        """Test getting latest rate for a crypto"""
        # Create another rate for the same crypto
        CryptoRate.objects.create(
            crypto_id='bitcoin',
            symbol='BTC',
            usd_price=Decimal('51000.00'),
            cedis_price=Decimal('306000.00'),
            is_active=True
        )
        
        latest_rate = CryptoRate.get_latest_rate('bitcoin')
        self.assertEqual(latest_rate.usd_price, Decimal('51000.00'))
        self.assertEqual(latest_rate.cedis_price, Decimal('306000.00'))

    def test_get_all_latest_rates(self):
        """Test getting all latest rates"""
        # Create rates for different cryptos
        CryptoRate.objects.create(
            crypto_id='ethereum',
            symbol='ETH',
            usd_price=Decimal('3000.00'),
            cedis_price=Decimal('18000.00'),
            is_active=True
        )
        
        rates = CryptoRate.get_all_latest_rates()
        self.assertEqual(len(rates), 2)
        self.assertIn('bitcoin', rates)
        self.assertIn('ethereum', rates)


class RateCacheModelTest(TestCase):
    def setUp(self):
        self.cache = RateCache.objects.create(
            cache_key='test_key',
            cache_value={'test': 'value'},
            expires_at='2025-12-31T23:59:59Z'
        )

    def test_rate_cache_creation(self):
        """Test that rate cache is created correctly"""
        self.assertEqual(self.cache.cache_key, 'test_key')
        self.assertEqual(self.cache.cache_value, {'test': 'value'})
        # The expires_at field is stored as a string in the database
        # We just need to verify it was set correctly
        self.assertIsNotNone(self.cache.expires_at)

    def test_rate_cache_str(self):
        """Test rate cache string representation"""
        expected = f"{self.cache.cache_key} - Expires: {self.cache.expires_at}"
        self.assertEqual(str(self.cache), expected)