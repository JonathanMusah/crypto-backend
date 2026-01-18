from rest_framework import serializers
from django.utils import timezone
from .models import SupportTicket, SupportTicketResponse, ContactEnquiry, SpecialRequest, PayPalRequest, PayPalTransaction, PayPalPurchaseRequest, CashAppRequest, CashAppTransaction, CashAppPurchaseRequest, ZelleRequest, ZelleTransaction


class SupportTicketResponseSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicketResponse
        fields = ['id', 'ticket', 'user', 'user_email', 'user_name', 'message', 'is_admin_response', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class SupportTicketSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    responses = SupportTicketResponseSerializer(many=True, read_only=True)
    response_count = serializers.IntegerField(source='responses.count', read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            'id', 'user', 'user_email', 'user_name', 'subject', 'message', 'category',
            'status', 'priority', 'assigned_to', 'assigned_to_email', 'created_at',
            'updated_at', 'resolved_at', 'resolved_by', 'responses', 'response_count'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'resolved_at', 'resolved_by']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'message', 'category', 'priority']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SupportTicketResponseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicketResponse
        fields = ['message']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['ticket'] = self.context['ticket']
        validated_data['is_admin_response'] = self.context['request'].user.is_staff
        return super().create(validated_data)


class ContactEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEnquiry
        fields = ['id', 'name', 'email', 'phone_number', 'subject', 'message', 'category', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']


class ContactEnquiryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEnquiry
        fields = ['name', 'email', 'phone_number', 'subject', 'message', 'category']
    
    def validate_email(self, value):
        # Basic email validation
        if not value or '@' not in value:
            raise serializers.ValidationError("Please provide a valid email address.")
        return value
    
    def validate_message(self, value):
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long.")
        return value


class SpecialRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = SpecialRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'request_type', 'title', 'description',
            'estimated_amount', 'currency', 'status', 'priority', 'assigned_to', 'assigned_to_email',
            'quote_amount', 'quote_notes', 'admin_notes', 'created_at', 'updated_at', 'reviewed_at',
            'reviewed_by', 'reviewed_by_email', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'assigned_to', 'admin_notes', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class SpecialRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialRequest
        fields = ['request_type', 'title', 'description', 'estimated_amount', 'currency', 'priority']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_title(self, value):
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value
    
    def validate_description(self, value):
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters long. Please provide more details about your request.")
        return value


class PayPalTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True, allow_null=True)
    payment_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = PayPalTransaction
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'paypal_email', 'payment_method', 'payment_details', 'account_name', 'admin_paypal_email',
            'payment_proof', 'payment_proof_url', 'payment_proof_notes', 'current_step', 'status',
            'admin_notes', 'exchange_rate', 'amount_cedis', 'service_fee', 'is_paypal_balance_only',
            'user_confirmed_balance_only', 'created_at', 'updated_at', 'payment_sent_at',
            'payment_verified_at', 'completed_at', 'verified_by', 'verified_by_email'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'admin_paypal_email', 'current_step', 'status', 'admin_notes',
            'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at',
            'verified_by', 'exchange_rate', 'amount_cedis', 'service_fee'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            return obj.payment_proof.url
        return None


class PayPalTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalTransaction
        fields = [
            'transaction_type', 'amount_usd', 'paypal_email', 'payment_method',
            'payment_details', 'account_name', 'user_confirmed_balance_only'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 5000:
            raise serializers.ValidationError("Maximum amount is $5,000.00 USD per transaction.")
        return value
    
    def validate_paypal_email(self, value):
        if not value or '@' not in value:
            raise serializers.ValidationError("Please provide a valid PayPal email address.")
        return value
    
    def validate_user_confirmed_balance_only(self, value):
        # Only require this confirmation for 'sell' transactions (where user sends PayPal)
        # For 'buy' transactions, user is sending MoMo, not PayPal, so this doesn't apply
        transaction_type = self.initial_data.get('transaction_type')
        if transaction_type == 'sell' and not value:
            raise serializers.ValidationError(
                "You must confirm that you are sending from PayPal balance only, not from bank or third-party sources. "
                "We only accept PayPal balance to prevent fraudulent transactions."
            )
        return value


class PayPalTransactionPaymentProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalTransaction
        fields = ['payment_proof', 'payment_proof_notes']
    
    def validate_payment_proof(self, value):
        if not value:
            raise serializers.ValidationError("Payment proof file is required.")
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 5MB.")
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("File must be an image (JPEG, PNG) or PDF.")
        return value


class PayPalRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = PayPalRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'paypal_email', 'recipient_name', 'recipient_email', 'description', 'status', 'priority',
            'assigned_to', 'assigned_to_email', 'quote_amount_cedis', 'exchange_rate', 'service_fee',
            'quote_notes', 'admin_notes', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'assigned_to', 'admin_notes', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class PayPalRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalRequest
        fields = [
            'transaction_type', 'amount_usd', 'paypal_email', 'recipient_name', 'recipient_email', 'description', 'priority'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 10000:
            raise serializers.ValidationError("Maximum amount is $10,000.00 USD per transaction.")
        return value
    
    def validate_paypal_email(self, value):
        if not value or '@' not in value:
            raise serializers.ValidationError("Please provide a valid PayPal email address.")
        return value
    
    def validate(self, data):
        # If sending, recipient email is required
        if data.get('transaction_type') == 'send':
            if not data.get('recipient_email'):
                raise serializers.ValidationError({
                    'recipient_email': 'Recipient PayPal email is required when sending funds.'
                })
        return data


class PayPalPurchaseRequestSerializer(serializers.ModelSerializer):
    """Serializer for PayPal Purchase Request"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)
    payment_proof_url = serializers.SerializerMethodField()
    amount_cedis_display = serializers.SerializerMethodField()

    class Meta:
        model = PayPalPurchaseRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'item_name', 'item_url',
            'item_description', 'amount_usd', 'recipient_paypal_email', 'recipient_name',
            'shipping_address', 'payment_method', 'payment_details', 'account_name',
            'priority', 'urgency_reason', 'status', 'assigned_to', 'assigned_to_email',
            'quote_amount_cedis', 'amount_cedis_display', 'exchange_rate', 'service_fee',
            'quote_notes', 'admin_notes', 'payment_proof', 'payment_proof_url',
            'delivery_tracking', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'paid_at', 'purchased_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'status', 'assigned_to', 'admin_notes',
            'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes',
            'payment_proof', 'delivery_tracking', 'created_at', 'updated_at',
            'reviewed_at', 'reviewed_by', 'paid_at', 'purchased_at', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_proof.url)
            return obj.payment_proof.url
        return None
    
    def get_amount_cedis_display(self, obj):
        if obj.quote_amount_cedis:
            return str(obj.quote_amount_cedis)
        return None


class PayPalPurchaseRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating PayPal Purchase Request"""
    
    class Meta:
        model = PayPalPurchaseRequest
        fields = [
            'item_name', 'item_url', 'item_description', 'amount_usd',
            'recipient_paypal_email', 'recipient_name', 'shipping_address',
            'payment_method', 'payment_details', 'account_name',
            'priority', 'urgency_reason'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 10000:
            raise serializers.ValidationError("Maximum amount is $10,000.00 USD per request.")
        return value
    
    def validate_recipient_paypal_email(self, value):
        if not value or '@' not in value:
            raise serializers.ValidationError("Please provide a valid PayPal email address for the seller/merchant.")
        return value
    
    def validate_item_name(self, value):
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Please provide a clear name/description of the item or service (at least 3 characters).")
        return value.strip()


# CashApp Serializers
class CashAppRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = CashAppRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'cashapp_tag', 'recipient_name', 'recipient_tag', 'description', 'status', 'priority',
            'assigned_to', 'assigned_to_email', 'quote_amount_cedis', 'exchange_rate', 'service_fee',
            'quote_notes', 'admin_notes', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'assigned_to', 'admin_notes', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class CashAppRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashAppRequest
        fields = [
            'transaction_type', 'amount_usd', 'cashapp_tag', 'recipient_name', 'recipient_tag', 'description', 'priority'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 10000:
            raise serializers.ValidationError("Maximum amount is $10,000.00 USD per transaction.")
        return value
    
    def validate_cashapp_tag(self, value):
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError("Please provide a valid CashApp $tag or email address.")
        return value.strip()
    
    def validate(self, data):
        # If sending, recipient tag is required
        if data.get('transaction_type') == 'send':
            if not data.get('recipient_tag'):
                raise serializers.ValidationError({
                    'recipient_tag': 'Recipient CashApp $tag is required when sending funds.'
                })
        return data


class CashAppTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True, allow_null=True)
    payment_proof_url = serializers.SerializerMethodField()

    class Meta:
        model = CashAppTransaction
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'cashapp_tag', 'payment_method', 'payment_details', 'account_name', 'admin_cashapp_tag',
            'payment_proof', 'payment_proof_url', 'payment_proof_notes', 'current_step', 'status',
            'admin_notes', 'exchange_rate', 'amount_cedis', 'service_fee', 'is_cashapp_balance_only',
            'user_confirmed_balance_only', 'created_at', 'updated_at', 'payment_sent_at',
            'payment_verified_at', 'completed_at', 'verified_by', 'verified_by_email'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'admin_cashapp_tag', 'current_step', 'status', 'admin_notes',
            'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at',
            'verified_by', 'exchange_rate', 'amount_cedis', 'service_fee'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            return obj.payment_proof.url
        return None


class CashAppTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashAppTransaction
        fields = [
            'transaction_type', 'amount_usd', 'cashapp_tag', 'payment_method',
            'payment_details', 'account_name', 'user_confirmed_balance_only'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 5000:
            raise serializers.ValidationError("Maximum amount is $5,000.00 USD per transaction.")
        return value
    
    def validate_cashapp_tag(self, value):
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError("Please provide a valid CashApp $tag or email address.")
        return value.strip()
    
    def validate(self, data):
        # Only require user_confirmed_balance_only for 'sell' transactions
        if data.get('transaction_type') == 'sell':
            if not data.get('user_confirmed_balance_only'):
                raise serializers.ValidationError(
                    "You must confirm that you are sending from CashApp balance only, not from bank or third-party sources. "
                    "We only accept CashApp balance to prevent fraudulent transactions."
                )
        return data


class CashAppTransactionPaymentProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashAppTransaction
        fields = ['payment_proof', 'payment_proof_notes']
    
    def validate_payment_proof(self, value):
        if not value:
            raise serializers.ValidationError("Payment proof file is required.")
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 5MB.")
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("File must be an image (JPEG, PNG) or PDF.")
        return value


class CashAppPurchaseRequestSerializer(serializers.ModelSerializer):
    """Serializer for CashApp Purchase Request"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)
    payment_proof_url = serializers.SerializerMethodField()
    amount_cedis_display = serializers.SerializerMethodField()

    class Meta:
        model = CashAppPurchaseRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'item_name', 'item_url',
            'item_description', 'amount_usd', 'recipient_cashapp_tag', 'recipient_name',
            'shipping_address', 'payment_method', 'payment_details', 'account_name',
            'priority', 'urgency_reason', 'status', 'assigned_to', 'assigned_to_email',
            'quote_amount_cedis', 'amount_cedis_display', 'exchange_rate', 'service_fee',
            'quote_notes', 'admin_notes', 'payment_proof', 'payment_proof_url',
            'delivery_tracking', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'paid_at', 'purchased_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'status', 'assigned_to', 'admin_notes',
            'quote_amount_cedis', 'exchange_rate', 'service_fee', 'quote_notes',
            'payment_proof', 'delivery_tracking', 'created_at', 'updated_at',
            'reviewed_at', 'reviewed_by', 'paid_at', 'purchased_at', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_proof.url)
            return obj.payment_proof.url
        return None
    
    def get_amount_cedis_display(self, obj):
        if obj.quote_amount_cedis:
            return str(obj.quote_amount_cedis)
        return None


class CashAppPurchaseRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating CashApp Purchase Request"""
    
    class Meta:
        model = CashAppPurchaseRequest
        fields = [
            'item_name', 'item_url', 'item_description', 'amount_usd',
            'recipient_cashapp_tag', 'recipient_name', 'shipping_address',
            'payment_method', 'payment_details', 'account_name',
            'priority', 'urgency_reason'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 10000:
            raise serializers.ValidationError("Maximum amount is $10,000.00 USD per request.")
        return value
    
    def validate_recipient_cashapp_tag(self, value):
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError("Please provide a valid CashApp $tag for the seller/merchant.")
        return value.strip()
    
    def validate_item_name(self, value):
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Please provide a clear name/description of the item or service (at least 3 characters).")
        return value.strip()


# Zelle Serializers
class ZelleRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, allow_null=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = ZelleRequest
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'zelle_email', 'recipient_name', 'recipient_email', 'description', 'status', 'priority',
            'assigned_to', 'assigned_to_email', 'quote_amount_cedis', 'exchange_rate', 'service_fee',
            'quote_notes', 'admin_notes', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
            'assigned_to', 'admin_notes', 'completed_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class ZelleRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZelleRequest
        fields = [
            'transaction_type', 'amount_usd', 'zelle_email', 'recipient_name', 'recipient_email', 'description', 'priority'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 10000:
            raise serializers.ValidationError("Maximum amount is $10,000.00 USD per request.")
        return value
    
    def validate_zelle_email(self, value):
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Please provide a valid Zelle email or phone number.")
        return value.strip()
    
    def validate(self, data):
        # If sending, recipient email is required
        if data.get('transaction_type') == 'send':
            if not data.get('recipient_email'):
                raise serializers.ValidationError({
                    'recipient_email': 'Recipient Zelle email or phone is required when sending funds.'
                })
        return data


class ZelleTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True, allow_null=True)
    payment_proof_url = serializers.SerializerMethodField()
    amount_cedis_display = serializers.SerializerMethodField()

    class Meta:
        model = ZelleTransaction
        fields = [
            'id', 'user', 'user_email', 'user_name', 'reference', 'transaction_type', 'amount_usd',
            'zelle_email', 'payment_method', 'payment_details', 'account_name', 'admin_zelle_email',
            'payment_proof', 'payment_proof_url', 'payment_proof_notes', 'current_step', 'status',
            'exchange_rate', 'amount_cedis', 'amount_cedis_display', 'service_fee',
            'is_zelle_balance_only', 'user_confirmed_balance_only', 'admin_notes',
            'created_at', 'updated_at', 'payment_sent_at', 'payment_verified_at', 'completed_at',
            'verified_by', 'verified_by_email'
        ]
        read_only_fields = [
            'id', 'user', 'reference', 'created_at', 'updated_at', 'payment_sent_at',
            'payment_verified_at', 'completed_at', 'verified_by', 'current_step',
            'admin_notes', 'exchange_rate', 'amount_cedis', 'service_fee', 'admin_zelle_email'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
    
    def get_payment_proof_url(self, obj):
        if obj.payment_proof:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_proof.url)
            return obj.payment_proof.url
        return None
    
    def get_amount_cedis_display(self, obj):
        if obj.amount_cedis:
            return str(obj.amount_cedis)
        return None


class ZelleTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZelleTransaction
        fields = [
            'transaction_type', 'amount_usd', 'zelle_email', 'payment_method',
            'payment_details', 'account_name', 'user_confirmed_balance_only'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < 1:
            raise serializers.ValidationError("Minimum amount is $1.00 USD.")
        if value > 5000:
            raise serializers.ValidationError("Maximum amount is $5,000.00 USD per transaction.")
        return value
    
    def validate_zelle_email(self, value):
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Please provide a valid Zelle email or phone number.")
        return value.strip()
    
    def validate_user_confirmed_balance_only(self, value):
        transaction_type = self.initial_data.get('transaction_type')
        if transaction_type == 'sell' and not value:
            raise serializers.ValidationError(
                "You must confirm that you are sending from Zelle balance only, not from bank or third-party sources. "
                "We only accept Zelle balance to prevent fraudulent transactions."
            )
        return value


class ZelleTransactionPaymentProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZelleTransaction
        fields = ['payment_proof', 'payment_proof_notes']
    
    def validate_payment_proof(self, value):
        if not value:
            raise serializers.ValidationError("Payment proof file is required.")
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 5MB.")
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("File must be an image (JPEG, PNG) or PDF.")
        return value

    def update(self, instance, validated_data):
        instance.payment_proof = validated_data.get('payment_proof', instance.payment_proof)
        instance.payment_proof_notes = validated_data.get('payment_proof_notes', instance.payment_proof_notes)
        instance.payment_sent_at = timezone.now()
        instance.current_step = 'payment_proof'
        instance.status = 'payment_sent'
        instance.save()
        return instance

