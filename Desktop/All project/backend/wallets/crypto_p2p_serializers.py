"""
Serializers for Crypto P2P Trading
Handles validation and serialization of crypto listings and transactions
"""
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
import logging

from .crypto_p2p_models import (
    CryptoListing,
    CryptoP2PTransaction,
    CryptoTransactionAuditLog,
    CryptoTransactionDispute,
)

logger = logging.getLogger(__name__)


class CryptoListingSerializer(serializers.ModelSerializer):
    """Serializer for CryptoListing model"""
    
    seller_email = serializers.SerializerMethodField()
    crypto_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CryptoListing
        fields = [
            'id', 'reference', 'listing_type', 'seller', 'seller_email',
            'crypto_type', 'crypto_display', 'network',
            'min_amount_crypto', 'max_amount_crypto', 'available_amount_crypto',
            'rate_cedis_per_crypto', 'is_negotiable',
            'accepted_payment_methods',
            'min_completed_trades', 'buyer_must_be_verified', 'buyer_must_be_kyc_verified',
            'terms_notes', 'proof_image', 'status', 'status_display',
            'views_count', 'expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reference', 'seller', 'views_count', 'created_at', 'updated_at']
    
    def get_seller_email(self, obj):
        return obj.seller.email
    
    def get_crypto_display(self, obj):
        return obj.get_crypto_type_display()
    
    def validate_rate_cedis_per_crypto(self, value):
        if value <= 0:
            raise serializers.ValidationError("Rate must be greater than 0")
        return value
    
    def validate_available_amount_crypto(self, value):
        if value <= 0:
            raise serializers.ValidationError("Available amount must be greater than 0")
        return value


class CryptoListingDetailSerializer(CryptoListingSerializer):
    """Detailed serializer with additional information"""
    
    total_transactions = serializers.SerializerMethodField()
    successful_transactions = serializers.SerializerMethodField()
    seller_rating = serializers.SerializerMethodField()
    
    class Meta(CryptoListingSerializer.Meta):
        fields = CryptoListingSerializer.Meta.fields + [
            'total_transactions', 'successful_transactions', 'seller_rating'
        ]
    
    def get_total_transactions(self, obj):
        return obj.transactions.count()
    
    def get_successful_transactions(self, obj):
        return obj.transactions.filter(status='completed').count()
    
    def get_seller_rating(self, obj):
        # TODO: Implement rating system
        return None


class CryptoTransactionSerializer(serializers.ModelSerializer):
    """Serializer for CryptoTransaction model"""
    
    buyer_email = serializers.SerializerMethodField()
    seller_email = serializers.SerializerMethodField()
    listing_reference = serializers.CharField(source='listing.reference', read_only=True)
    crypto_type = serializers.CharField(source='listing.get_crypto_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CryptoP2PTransaction
        fields = [
            'id', 'reference', 'listing', 'listing_reference',
            'buyer', 'buyer_email', 'seller', 'seller_email',
            'amount_crypto', 'amount_cedis', 'rate_applied', 'crypto_type',
            'escrow_locked', 'escrow_amount_cedis',
            'buyer_payment_details', 'seller_payment_method',
            'buyer_wallet_address', 'seller_wallet_address',
            'transaction_hash',
            'buyer_marked_paid', 'buyer_marked_paid_at',
            'seller_confirmed_payment', 'seller_confirmed_payment_at',
            'crypto_sent', 'crypto_sent_at',
            'buyer_verified', 'blockchain_verified',
            'status', 'status_display',
            'payment_deadline', 'seller_confirmation_deadline',
            'seller_response_deadline', 'buyer_verification_deadline',
            'has_dispute', 'risk_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reference', 'buyer', 'seller', 'listing',
            'buyer_marked_paid', 'buyer_marked_paid_at',
            'seller_confirmed_payment', 'seller_confirmed_payment_at',
            'crypto_sent', 'crypto_sent_at',
            'buyer_verified', 'blockchain_verified',
            'created_at', 'updated_at'
        ]
    
    def get_buyer_email(self, obj):
        return obj.buyer.email
    
    def get_seller_email(self, obj):
        return obj.seller.email


class CreateCryptoTransactionSerializer(serializers.ModelSerializer):
    """Serializer for creating crypto transactions"""
    
    listing_id = serializers.IntegerField(write_only=True)
    amount_crypto = serializers.DecimalField(max_digits=18, decimal_places=8)
    buyer_wallet_address = serializers.CharField()
    buyer_payment_details = serializers.JSONField()
    
    class Meta:
        model = CryptoP2PTransaction
        fields = [
            'listing_id', 'amount_crypto',
            'buyer_wallet_address', 'buyer_payment_details'
        ]
    
    def validate_amount_crypto(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value
    
    def validate_buyer_wallet_address(self, value):
        if not value or len(value) < 20:
            raise serializers.ValidationError("Invalid wallet address")
        return value
    
    def validate(self, data):
        try:
            listing = CryptoListing.objects.get(id=data['listing_id'])
        except CryptoListing.DoesNotExist:
            raise serializers.ValidationError("Listing not found")
        
        # Validate amount
        if data['amount_crypto'] < listing.min_amount_crypto:
            raise serializers.ValidationError(
                f"Amount must be at least {listing.min_amount_crypto} {listing.get_crypto_type_display()}"
            )
        
        if listing.max_amount_crypto and data['amount_crypto'] > listing.max_amount_crypto:
            raise serializers.ValidationError(
                f"Amount cannot exceed {listing.max_amount_crypto} {listing.get_crypto_type_display()}"
            )
        
        if data['amount_crypto'] > listing.available_amount_crypto:
            raise serializers.ValidationError("Insufficient available amount")
        
        data['listing'] = listing
        return data


class MarkPaymentSentSerializer(serializers.Serializer):
    """Serializer for buyer marking payment as sent"""
    
    payment_screenshot = serializers.ImageField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_payment_screenshot(self, value):
        if value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("File size must be less than 5MB")
        
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Invalid image format. Use JPEG, PNG, or WebP.")
        
        return value


class ConfirmPaymentSerializer(serializers.Serializer):
    """Serializer for seller confirming payment received"""
    
    notes = serializers.CharField(required=False, allow_blank=True)


class SendCryptoSerializer(serializers.Serializer):
    """Serializer for seller sending crypto"""
    
    transaction_hash = serializers.CharField(required=True)
    proof_image = serializers.ImageField(required=False)
    
    def validate_transaction_hash(self, value):
        if not value or len(value) < 10:
            raise serializers.ValidationError("Invalid transaction hash")
        return value
    
    def validate_proof_image(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError("File size must be less than 5MB")
            
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError("Invalid image format. Use JPEG, PNG, or WebP.")
        
        return value


class VerifyCryptoSerializer(serializers.Serializer):
    """Serializer for buyer verifying crypto received"""
    
    verified = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class CryptoTransactionAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs"""
    
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    performed_by_email = serializers.SerializerMethodField()
    
    class Meta:
        model = CryptoTransactionAuditLog
        fields = [
            'id', 'transaction', 'action', 'action_display',
            'performed_by', 'performed_by_email', 'notes',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_performed_by_email(self, obj):
        return obj.performed_by.email if obj.performed_by else 'System'


class CryptoTransactionDisputeSerializer(serializers.ModelSerializer):
    """Serializer for transaction disputes"""
    
    raised_by_email = serializers.SerializerMethodField()
    dispute_type_display = serializers.CharField(source='get_dispute_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CryptoTransactionDispute
        fields = [
            'id', 'transaction', 'raised_by', 'raised_by_email',
            'dispute_type', 'dispute_type_display', 'description',
            'evidence_image', 'status', 'status_display',
            'resolution', 'resolved_by', 'resolved_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'transaction', 'raised_by', 'resolved_by',
            'resolved_at', 'created_at', 'updated_at'
        ]


class CryptoListingSearchSerializer(serializers.Serializer):
    """Serializer for searching crypto listings"""
    
    crypto_type = serializers.ChoiceField(
        choices=['bitcoin', 'ethereum', 'bnb', 'usdt', 'usdc'],
        required=False
    )
    listing_type = serializers.ChoiceField(
        choices=['buy', 'sell'],
        required=False
    )
    min_rate = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    max_rate = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    min_amount = serializers.DecimalField(max_digits=18, decimal_places=8, required=False)
    payment_method = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=['active', 'sold', 'cancelled', 'expired'],
        required=False
    )
    ordering = serializers.ChoiceField(
        choices=['rate_asc', 'rate_desc', 'newest', 'oldest'],
        default='newest'
    )
