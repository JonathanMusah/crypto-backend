from rest_framework import serializers
from .models import CryptoRate
from decimal import Decimal


class CryptoRateSerializer(serializers.ModelSerializer):
    """Serializer for crypto rates"""
    change_direction = serializers.SerializerMethodField()
    
    class Meta:
        model = CryptoRate
        fields = (
            'id', 'crypto_id', 'symbol', 'usd_price', 'cedis_price',
            'usd_to_cedis_rate', 'market_cap', 'volume_24h',
            'price_change_24h', 'price_change_percentage_24h',
            'change_direction', 'timestamp', 'is_active'
        )
        read_only_fields = ('id', 'timestamp')
    
    def get_change_direction(self, obj):
        """Get price change direction (up, down, neutral)"""
        if obj.price_change_percentage_24h is None:
            return 'neutral'
        if obj.price_change_percentage_24h > 0:
            return 'up'
        elif obj.price_change_percentage_24h < 0:
            return 'down'
        return 'neutral'


class ConvertCryptoSerializer(serializers.Serializer):
    """Serializer for crypto conversion requests"""
    crypto_id = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'))
    direction = serializers.ChoiceField(choices=['crypto_to_cedis', 'cedis_to_crypto'])
    
    def validate_crypto_id(self, value):
        """Validate that crypto_id is supported"""
        supported = [choice[0] for choice in CryptoRate.CRYPTO_CHOICES]
        if value not in supported:
            raise serializers.ValidationError(f"Unsupported crypto. Supported: {', '.join(supported)}")
        return value


class BuyCryptoSerializer(serializers.Serializer):
    """Serializer for buying crypto"""
    crypto_id = serializers.CharField(max_length=50)
    cedis_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('1.00'))
    
    def validate_crypto_id(self, value):
        """Validate that crypto_id is supported"""
        supported = [choice[0] for choice in CryptoRate.CRYPTO_CHOICES]
        if value not in supported:
            raise serializers.ValidationError(f"Unsupported crypto. Supported: {', '.join(supported)}")
        return value


class SellCryptoSerializer(serializers.Serializer):
    """Serializer for selling crypto"""
    crypto_id = serializers.CharField(max_length=50)
    crypto_amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'))
    
    def validate_crypto_id(self, value):
        """Validate that crypto_id is supported"""
        supported = [choice[0] for choice in CryptoRate.CRYPTO_CHOICES]
        if value not in supported:
            raise serializers.ValidationError(f"Unsupported crypto. Supported: {', '.join(supported)}")
        return value
