from django.contrib import admin
from .models import CryptoRate, RateCache


@admin.register(CryptoRate)
class CryptoRateAdmin(admin.ModelAdmin):
    list_display = ('crypto_id', 'symbol', 'cedis_price', 'usd_price', 'price_change_percentage_24h', 'timestamp', 'is_active')
    list_filter = ('crypto_id', 'is_active', 'timestamp')
    search_fields = ('crypto_id', 'symbol')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)


@admin.register(RateCache)
class RateCacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'created_at', 'updated_at', 'expires_at', 'is_expired_display')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('cache_key',)
    readonly_fields = ('created_at', 'updated_at')
    
    def is_expired_display(self, obj):
        return obj.is_expired()
    is_expired_display.short_description = 'Expired'
    is_expired_display.boolean = True
