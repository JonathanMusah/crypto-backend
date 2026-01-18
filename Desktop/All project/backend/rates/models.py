from django.db import models
from django.utils import timezone
from decimal import Decimal


class CryptoRate(models.Model):
    """Store crypto rates with historical tracking"""
    CRYPTO_CHOICES = [
        ('bitcoin', 'Bitcoin (BTC)'),
        ('ethereum', 'Ethereum (ETH)'),
        ('binancecoin', 'Binance Coin (BNB)'),
        ('cardano', 'Cardano (ADA)'),
        ('solana', 'Solana (SOL)'),
        ('ripple', 'Ripple (XRP)'),
        ('polkadot', 'Polkadot (DOT)'),
        ('dogecoin', 'Dogecoin (DOGE)'),
        ('tether', 'Tether (USDT)'),
        ('usd-coin', 'USD Coin (USDC)'),
    ]

    crypto_id = models.CharField(max_length=50, choices=CRYPTO_CHOICES, db_index=True)
    symbol = models.CharField(max_length=10)
    usd_price = models.DecimalField(max_digits=20, decimal_places=8)
    cedis_price = models.DecimalField(max_digits=20, decimal_places=2)
    usd_to_cedis_rate = models.DecimalField(max_digits=10, decimal_places=4, default=12.50)
    
    # Market data
    market_cap = models.DecimalField(max_digits=30, decimal_places=2, null=True, blank=True)
    volume_24h = models.DecimalField(max_digits=30, decimal_places=2, null=True, blank=True)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_change_percentage_24h = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'crypto_rates'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['crypto_id', '-timestamp']),
            models.Index(fields=['is_active', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.symbol} - ₵{self.cedis_price} ({self.timestamp})"

    @classmethod
    def get_latest_rate(cls, crypto_id):
        """Get the most recent admin-set rate for a crypto"""
        return cls.objects.filter(
            crypto_id=crypto_id,
            is_active=True
        ).order_by('-timestamp').first()

    @classmethod
    def get_all_latest_rates(cls):
        """Get latest rates for all active cryptos"""
        latest_rates = {}
        for crypto_id, _ in cls.CRYPTO_CHOICES:
            rate = cls.get_latest_rate(crypto_id)
            if rate:
                latest_rates[crypto_id] = rate
        return latest_rates


class RateCache(models.Model):
    """Cache for rate data from external APIs"""
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    cache_value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'rate_cache'

    def __str__(self):
        return f"{self.cache_key} - Expires: {self.expires_at}"

    def is_expired(self):
        """Check if cache is expired"""
        return timezone.now() > self.expires_at

    @classmethod
    def get_cached(cls, key):
        """Get cached value if not expired"""
        try:
            cache = cls.objects.get(cache_key=key)
            if not cache.is_expired():
                return cache.cache_value
            cache.delete()
        except cls.DoesNotExist:
            pass
        return None

    @classmethod
    def set_cached(cls, key, value, ttl_seconds=15):
        """Set cache value with TTL"""
        expires_at = timezone.now() + timezone.timedelta(seconds=ttl_seconds)
        cache, created = cls.objects.update_or_create(
            cache_key=key,
            defaults={
                'cache_value': value,
                'expires_at': expires_at
            }
        )
        return cache
