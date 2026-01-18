from rest_framework import serializers
from .models import Settings, AnalyticsEvent, UserMetric


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = (
            'id', 'live_rate_source', 'escrow_percent', 'support_contacts', 
            'gift_cards_enabled', 'special_requests_enabled', 'paypal_enabled', 'cashapp_enabled', 'zelle_enabled',
            'paypal_sell_rate', 'paypal_buy_rate', 'admin_paypal_email', 'admin_momo_details',
            'paypal_transaction_fee_percent', 'paypal_transaction_fixed_fee_usd', 'paypal_transaction_min_fee_usd', 'paypal_transaction_max_fee_usd',
            'cashapp_sell_rate', 'cashapp_buy_rate', 'admin_cashapp_tag',
            'cashapp_transaction_fee_percent', 'cashapp_transaction_fixed_fee_usd', 'cashapp_transaction_min_fee_usd', 'cashapp_transaction_max_fee_usd',
            'zelle_sell_rate', 'zelle_buy_rate', 'admin_zelle_email',
            'zelle_transaction_fee_percent', 'zelle_transaction_fixed_fee_usd', 'zelle_transaction_min_fee_usd', 'zelle_transaction_max_fee_usd',
            'momo_withdrawal_fee_percent', 'momo_withdrawal_fee_fixed_usd', 'momo_withdrawal_min_fee_usd', 'momo_withdrawal_max_fee_usd',
            'crypto_withdrawal_fee_percent', 'crypto_withdrawal_fee_fixed_usd', 'crypto_withdrawal_min_fee_usd', 'crypto_withdrawal_max_fee_usd',
            'usd_to_cedis_rate', 'updated_at'
        )
        read_only_fields = ('id', 'updated_at')


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = ('id', 'user', 'event_type', 'event_name', 'properties', 'session_id', 'created_at')
        read_only_fields = ('id', 'user', 'created_at')


class UserMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMetric
        fields = ('id', 'user', 'total_trades', 'total_volume', 'total_profit', 'last_trade_at', 'updated_at')
        read_only_fields = ('id', 'user', 'updated_at')

