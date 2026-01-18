from rest_framework import serializers
from .models import Wallet, WalletTransaction, CryptoTransaction, AdminCryptoAddress, AdminPaymentDetails, Deposit, Withdrawal, WalletLog
from decimal import Decimal


class WalletSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    total_balance = serializers.SerializerMethodField()
    available_cedis = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ('id', 'user', 'user_email', 'balance_cedis', 'balance_crypto', 'escrow_balance', 
                  'total_balance', 'available_cedis', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')

    def get_total_balance(self, obj):
        """Calculate total balance (cedis + escrow only - platform doesn't hold crypto)"""
        # Platform operates as fiat-only: all deposits (crypto or MoMo) are converted to cedis
        # Total balance is just available cedis + escrow balance
        return float(obj.balance_cedis + obj.escrow_balance)

    def get_available_cedis(self, obj):
        """Get available cedis (excluding escrow)"""
        return float(obj.balance_cedis)


class WalletTransactionSerializer(serializers.ModelSerializer):
    wallet_user = serializers.EmailField(source='wallet.user.email', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = ('id', 'wallet', 'wallet_user', 'transaction_type', 'amount', 'currency', 
                  'status', 'reference', 'description', 'balance_before', 'balance_after', 
                  'created_at', 'updated_at')
        read_only_fields = ('id', 'wallet', 'created_at', 'updated_at')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('1.00'))
    payment_method = serializers.ChoiceField(choices=['momo', 'bank'])
    payment_reference = serializers.CharField(max_length=255, required=False)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('1.00'))
    withdrawal_method = serializers.ChoiceField(choices=['momo', 'bank'])
    account_number = serializers.CharField(max_length=255)
    account_name = serializers.CharField(max_length=255, required=False)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class CryptoBuySerializer(serializers.Serializer):
    crypto_amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'))
    rate = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=['momo', 'bank', 'crypto'])
    crypto_id = serializers.CharField(max_length=50, required=True)
    network = serializers.CharField(max_length=20, required=True)
    user_address = serializers.CharField(max_length=255, required=True)

    def validate(self, attrs):
        # Calculate cedis amount
        cedis_amount = attrs['crypto_amount'] * attrs['rate']
        attrs['cedis_amount'] = cedis_amount
        return attrs


class CryptoSellSerializer(serializers.Serializer):
    crypto_amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'))
    rate = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('0.01'))
    crypto_id = serializers.CharField(max_length=50, required=True)
    network = serializers.CharField(max_length=20, required=True)
    momo_number = serializers.CharField(max_length=20, required=True)
    momo_name = serializers.CharField(max_length=255, required=True)
    transaction_id = serializers.CharField(max_length=255, required=True, help_text="Transaction ID/hash from crypto transfer")
    payment_proof = serializers.ImageField(required=True, help_text="Screenshot of crypto transfer transaction")

    def validate(self, attrs):
        # Calculate cedis amount
        cedis_amount = attrs['crypto_amount'] * attrs['rate']
        attrs['cedis_amount'] = cedis_amount
        return attrs


class CryptoTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    total_value = serializers.SerializerMethodField()
    payment_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = CryptoTransaction
        fields = ('id', 'user', 'user_email', 'type', 'crypto_id', 'network', 'cedis_amount', 
                  'crypto_amount', 'rate', 'status', 'payment_method', 'reference', 'escrow_locked', 
                  'admin_note', 'user_address', 'admin_address', 'momo_number', 'momo_name',
                  'transaction_id', 'payment_proof', 'payment_proof_url', 'total_value', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')

    def get_total_value(self, obj):
        """Calculate total value in cedis"""
        return float(obj.cedis_amount)

    def get_payment_proof_url(self, obj):
        """Get full URL for payment proof image"""
        if obj.payment_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_proof.url)
            return obj.payment_proof.url
        return None


class CryptoTransactionApprovalSerializer(serializers.Serializer):
    admin_note = serializers.CharField(required=False, allow_blank=True)
    action = serializers.ChoiceField(choices=['approve', 'decline'])


class AdminCryptoAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminCryptoAddress
        fields = ('id', 'crypto_id', 'network', 'address', 'is_active', 'notes', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class AdminPaymentDetailsSerializer(serializers.ModelSerializer):
    """Serializer for admin payment details (read-only for users)"""
    class Meta:
        model = AdminPaymentDetails
        fields = ('id', 'payment_type', 'momo_network', 'momo_number', 'momo_name', 
                  'bank_name', 'account_number', 'account_name', 'branch', 'swift_code',
                  'instructions', 'is_active')
        read_only_fields = ('id', 'payment_type', 'momo_network', 'momo_number', 'momo_name',
                           'bank_name', 'account_number', 'account_name', 'branch', 'swift_code',
                           'instructions', 'is_active')


class MomoDepositSerializer(serializers.Serializer):
    """Serializer for Mobile Money deposits - user only provides payment proof"""
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('1.00'))
    admin_payment_detail_id = serializers.IntegerField(required=True, help_text="ID of admin payment detail used for deposit")
    momo_network = serializers.ChoiceField(choices=['MTN', 'Vodafone', 'AirtelTigo'], required=True)
    momo_transaction_id = serializers.CharField(max_length=255, required=True, help_text="Transaction ID from MoMo transfer (payment proof)")
    momo_proof = serializers.ImageField(required=True, help_text="Screenshot of MoMo transaction (payment proof)")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value
    
    def validate_admin_payment_detail_id(self, value):
        """Verify admin payment detail exists and is active"""
        try:
            payment_detail = AdminPaymentDetails.objects.get(id=value, is_active=True, payment_type='momo')
            return value
        except AdminPaymentDetails.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive admin payment detail")


class CryptoDepositSerializer(serializers.Serializer):
    """Serializer for Crypto deposits - user only provides payment proof"""
    crypto_id = serializers.CharField(max_length=50, required=True)
    crypto_amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'), required=True)
    network = serializers.CharField(max_length=20, required=True)
    admin_crypto_address_id = serializers.IntegerField(required=False, help_text="ID of admin crypto address used (optional, for tracking)")
    transaction_id = serializers.CharField(max_length=255, required=True, help_text="Transaction ID/hash from crypto transfer (payment proof)")
    crypto_proof = serializers.ImageField(required=True, help_text="Screenshot of crypto transaction (payment proof)")

    def validate_crypto_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Crypto amount must be greater than zero")
        return value
    
    def validate_admin_crypto_address_id(self, value):
        """Verify admin crypto address exists if provided"""
        if value:
            try:
                AdminCryptoAddress.objects.get(id=value, is_active=True)
                return value
            except AdminCryptoAddress.DoesNotExist:
                raise serializers.ValidationError("Invalid or inactive admin crypto address")
        return value


class DepositSerializer(serializers.ModelSerializer):
    """Serializer for Deposit model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    momo_proof_url = serializers.SerializerMethodField()
    crypto_proof_url = serializers.SerializerMethodField()
    admin_payment_detail_info = serializers.SerializerMethodField()

    class Meta:
        model = Deposit
        fields = (
            'id', 'user', 'user_email', 'deposit_type', 'amount', 'crypto_amount', 'status', 'reference',
            'admin_payment_detail', 'admin_payment_detail_info',
            'momo_network', 'momo_transaction_id', 'momo_proof', 'momo_proof_url',
            'crypto_id', 'network', 'transaction_id', 'crypto_proof', 'crypto_proof_url',
            'admin_note', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'status', 'reference', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at')
    
    def get_admin_payment_detail_info(self, obj):
        """Get admin payment detail info if available"""
        if obj.admin_payment_detail:
            return AdminPaymentDetailsSerializer(obj.admin_payment_detail, context=self.context).data
        return None

    def get_momo_proof_url(self, obj):
        """Get full URL for MoMo proof image"""
        if obj.momo_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.momo_proof.url)
            return obj.momo_proof.url
        return None

    def get_crypto_proof_url(self, obj):
        """Get full URL for crypto proof image"""
        if obj.crypto_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.crypto_proof.url)
            return obj.crypto_proof.url
        return None


class MomoWithdrawalSerializer(serializers.Serializer):
    """Serializer for Mobile Money withdrawals"""
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('1.00'))
    momo_number = serializers.CharField(max_length=20, required=True)
    momo_name = serializers.CharField(max_length=255, required=True)
    momo_network = serializers.ChoiceField(choices=['MTN', 'Vodafone', 'AirtelTigo'], required=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value


class CryptoWithdrawalSerializer(serializers.Serializer):
    """Serializer for Crypto withdrawals"""
    crypto_id = serializers.CharField(max_length=50, required=True)
    crypto_amount = serializers.DecimalField(max_digits=20, decimal_places=8, min_value=Decimal('0.00000001'), required=True)
    network = serializers.CharField(max_length=20, required=True)
    crypto_address = serializers.CharField(max_length=255, required=True)

    def validate_crypto_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Crypto amount must be greater than zero")
        return value


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for Withdrawal model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Withdrawal
        fields = (
            'id', 'user', 'user_email', 'withdrawal_type', 'amount', 'fee', 'total_amount', 'crypto_amount', 'status', 'reference',
            'momo_number', 'momo_name', 'momo_network',
            'crypto_id', 'network', 'crypto_address',
            'admin_note', 'transaction_id', 'reviewed_by', 'reviewed_at', 'completed_at',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'status', 'reference', 'fee', 'total_amount', 'reviewed_by', 'reviewed_at', 'completed_at', 'created_at', 'updated_at')


class WalletLogSerializer(serializers.ModelSerializer):
    """Serializer for wallet activity logs"""
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = WalletLog
        fields = (
            'id', 'user', 'user_email', 'amount', 'log_type', 'log_type_display',
            'transaction_id', 'balance_after', 'timestamp'
        )
        read_only_fields = '__all__'

