"""
Serializers for P2P service models (PayPal, CashApp, Zelle)
Binance-style: Sellers set their own rates and specify payment methods they accept
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .p2p_models import (
    P2PServiceListing,
    P2PServiceTransaction,
    P2PServiceDispute,
    P2PServiceTransactionRating,
    P2PServiceTransactionLog,
    P2PServiceDisputeLog,
    SellerApplication,
)


class P2PServiceListingSerializer(serializers.ModelSerializer):
    """Serializer for P2P service listings"""
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    seller_name = serializers.SerializerMethodField()
    seller_trust_score = serializers.SerializerMethodField()
    seller_rating_stats = serializers.SerializerMethodField()
    proof_image_url = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    service_identifier = serializers.SerializerMethodField()
    
    class Meta:
        model = P2PServiceListing
        fields = (
            'id', 'reference', 'listing_type', 'seller', 'seller_email', 'seller_name', 'seller_trust_score', 'seller_rating_stats',
            'service_type', 'paypal_email', 'cashapp_tag', 'zelle_email', 'service_identifier',
            'min_amount_usd', 'max_amount_usd', 'available_amount_usd', 'currency',
            'rate_cedis_per_usd', 'max_rate_cedis_per_usd', 'is_negotiable',
            'accepted_payment_methods', 'terms_notes',
            'proof_image', 'proof_image_url', 'proof_notes',
            'min_completed_trades', 'buyer_must_be_verified', 'buyer_must_be_kyc_verified', 'required_payment_providers',
            'status', 'views_count', 'expires_at',
            'admin_notes', 'reviewed_by', 'reviewed_at',
            'is_owner', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'reference', 'seller', 'seller_email', 'seller_name', 'seller_trust_score', 'seller_rating_stats',
            'status', 'views_count', 'reviewed_by', 'reviewed_at',
            'created_at', 'updated_at', 'is_owner', 'service_identifier'
        )
    
    def get_seller_name(self, obj):
        return obj.seller.get_full_name() or obj.seller.email
    
    def get_seller_trust_score(self, obj):
        return obj.seller.get_effective_trust_score()
    
    def get_seller_rating_stats(self, obj):
        """Get seller's rating statistics"""
        from .p2p_models import P2PServiceTransactionRating
        ratings = P2PServiceTransactionRating.objects.filter(rated_user=obj.seller)
        if ratings.exists():
            avg_rating = sum(r.rating for r in ratings) / ratings.count()
            return {
                'average_rating': round(avg_rating, 2),
                'total_ratings': ratings.count()
            }
        return {'average_rating': 0, 'total_ratings': 0}
    
    def get_proof_image_url(self, obj):
        if obj.proof_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.proof_image.url)
            return obj.proof_image.url
        return None
    
    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.seller == request.user
        return False
    
    def get_service_identifier(self, obj):
        """Get service-specific identifier"""
        return obj.get_service_identifier()


class P2PServiceListingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating P2P service listings - Binance-style with seller rates or buy orders"""
    
    class Meta:
        model = P2PServiceListing
        fields = (
            'listing_type', 'service_type', 'paypal_email', 'cashapp_tag', 'zelle_email',
            'min_amount_usd', 'max_amount_usd', 'available_amount_usd', 'currency',
            'rate_cedis_per_usd', 'max_rate_cedis_per_usd', 'is_negotiable',
            'accepted_payment_methods', 'terms_notes',
            'proof_image', 'proof_notes',
            'min_completed_trades', 'buyer_must_be_verified', 'buyer_must_be_kyc_verified', 'required_payment_providers'
        )
    
    def create(self, validated_data):
        """Create listing with proper defaults"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("[SERIALIZER] Creating P2P listing...")
        logger.info(f"[SERIALIZER] Validated data keys: {list(validated_data.keys())}")
        
        # Ensure listing_type has a default
        if 'listing_type' not in validated_data or not validated_data['listing_type']:
            validated_data['listing_type'] = 'sell'
            logger.info("[SERIALIZER] Set default listing_type to 'sell'")
        
        try:
            logger.info("[SERIALIZER] Calling super().create()...")
            instance = super().create(validated_data)
            logger.info(f"[SERIALIZER] Listing created successfully! ID: {instance.id}")
            return instance
        except Exception as e:
            logger.error(f"[SERIALIZER] Error in create(): {str(e)}", exc_info=True)
            raise
    
    def validate_rate_cedis_per_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Rate must be greater than zero.")
        return value
    
    def validate_max_rate_cedis_per_usd(self, value):
        """For buy listings: Maximum rate buyer will pay"""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Maximum rate must be greater than zero.")
        return value
    
    def validate_min_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Minimum amount must be greater than zero.")
        return value
    
    def validate_max_amount_usd(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Maximum amount must be greater than zero.")
        return value
    
    def validate_available_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Available amount must be greater than zero.")
        
        # Check amount limit for new/low-trust sellers
        request = self.context.get('request')
        if request and request.user:
            seller = request.user
            max_value = seller.get_max_gift_card_value_cedis()  # Reuse gift card limit logic
            if max_value is not None:
                # Convert to USD (rough estimate, assuming rate around 12-15)
                max_usd = max_value / 12  # Conservative estimate
                if value > max_usd:
                    raise serializers.ValidationError(
                        f"New sellers (trust score < 3) cannot list services above ${max_usd:.2f} USD. "
                        f"Your current trust score is {seller.get_effective_trust_score()}. "
                        "Complete successful trades to increase your limit."
                    )
        
        return value
    
    def validate_accepted_payment_methods(self, value):
        """Validate payment methods structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Accepted payment methods must be a list.")
        
        if len(value) == 0:
            raise serializers.ValidationError("You must specify at least one payment method.")
        
        # For buy listings: Should be a single payment method
        # For sell listings: Can be multiple payment methods
        listing_type = self.initial_data.get('listing_type', 'sell')
        if listing_type == 'buy' and len(value) > 1:
            raise serializers.ValidationError("Buy listings can only specify one payment method (the method you will use to pay).")
        
        valid_methods = ['momo', 'bank', 'other']
        for method_data in value:
            if not isinstance(method_data, dict):
                raise serializers.ValidationError("Each payment method must be an object.")
            
            method = method_data.get('method')
            if method not in valid_methods:
                raise serializers.ValidationError(f"Invalid payment method: {method}. Must be one of {valid_methods}.")
            
            # Validate method-specific fields
            if method == 'momo':
                if not method_data.get('provider') or not method_data.get('number'):
                    raise serializers.ValidationError("MoMo payment method requires 'provider' and 'number'.")
            elif method == 'bank':
                if not method_data.get('bank_name') or not method_data.get('account_number'):
                    raise serializers.ValidationError("Bank payment method requires 'bank_name' and 'account_number'.")
        
        return value
    
    def validate(self, attrs):
        """Validate service-specific identifier and duplicates (Binance-style)"""
        listing_type = attrs.get('listing_type', 'sell')
        service_type = attrs.get('service_type')
        paypal_email = attrs.get('paypal_email', '').strip() if attrs.get('paypal_email') else ''
        cashapp_tag = attrs.get('cashapp_tag', '').strip() if attrs.get('cashapp_tag') else ''
        zelle_email = attrs.get('zelle_email', '').strip() if attrs.get('zelle_email') else ''
        proof_image = attrs.get('proof_image')
        max_rate = attrs.get('max_rate_cedis_per_usd')
        rate = attrs.get('rate_cedis_per_usd')
        
        # Get the user from context (seller/buyer)
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("You must be authenticated to create a listing.")
        
        user = request.user
        
        # Check seller verification for sell listings
        if listing_type == 'sell':
            # Refresh user from database to get latest seller status
            user.refresh_from_db()
            
            # Also check if user has an approved seller application (fallback check)
            # Use fully qualified import to avoid scoping issues
            from orders.p2p_models import SellerApplication
            has_approved_application = SellerApplication.objects.filter(
                user=user,
                status='approved'
            ).exists()
            
            # Allow if can_sell_p2p is True OR seller_status is 'approved' OR has approved application
            # (multiple checks handle cases where user fields haven't been updated yet)
            if not user.can_sell_p2p and user.seller_status != 'approved' and not has_approved_application:
                if user.seller_status == 'not_applied':
                    raise serializers.ValidationError({
                        'listing_type': 'You must apply to become a seller before creating sell listings. Please submit a seller application first.'
                    })
                elif user.seller_status == 'pending':
                    raise serializers.ValidationError({
                        'listing_type': 'Your seller application is pending review. You will be able to create listings once approved.'
                    })
                elif user.seller_status == 'rejected':
                    raise serializers.ValidationError({
                        'listing_type': 'Your seller application was rejected. Please contact support if you believe this is an error.'
                    })
                elif user.seller_status == 'revoked':
                    raise serializers.ValidationError({
                        'listing_type': 'Your seller privileges have been revoked. Please contact support for more information.'
                    })
                else:
                    raise serializers.ValidationError({
                        'listing_type': 'You are not authorized to create sell listings. Please apply to become a seller first.'
                    })
        
        # For buy listings: max_rate is required, service identifiers are NOT required
        if listing_type == 'buy':
            if not max_rate and not rate:
                raise serializers.ValidationError({
                    'max_rate_cedis_per_usd': 'Maximum rate is required for buy listings (highest rate you will pay).'
                })
            # Use rate_cedis_per_usd as max_rate if max_rate not provided
            if not max_rate and rate:
                attrs['max_rate_cedis_per_usd'] = rate
            identifier = None  # Buy listings don't have service identifiers
        else:
            # For sell listings: service identifier is required
            if service_type == 'paypal':
                if not paypal_email or '@' not in paypal_email:
                    raise serializers.ValidationError({'paypal_email': 'Valid PayPal email is required for PayPal listings.'})
                identifier = paypal_email.lower()
            elif service_type == 'cashapp':
                if not cashapp_tag or not cashapp_tag.startswith('$'):
                    raise serializers.ValidationError({'cashapp_tag': 'Valid CashApp tag (starting with $) is required for CashApp listings.'})
                identifier = cashapp_tag.lower()
            elif service_type == 'zelle':
                if not zelle_email or '@' not in zelle_email:
                    raise serializers.ValidationError({'zelle_email': 'Valid Zelle email is required for Zelle listings.'})
                identifier = zelle_email.lower()
            else:
                raise serializers.ValidationError({'service_type': 'Invalid service type.'})
        
        # Binance-style duplicate check: Allow multiple listings with same service identifier
        # but prevent exact duplicates and require meaningful differences
        if identifier and listing_type == 'sell':
            identifier_hash = P2PServiceListing.hash_service_identifier(identifier)
            
            # Get current listing values for comparison
            current_rate = rate
            current_min_amount = attrs.get('min_amount_usd')
            current_max_amount = attrs.get('max_amount_usd')
            current_available_amount = attrs.get('available_amount_usd')
            current_payment_methods = attrs.get('accepted_payment_methods', [])
            
            # Normalize payment methods for comparison (sort by method and provider/bank)
            def normalize_payment_methods(methods):
                """Normalize payment methods list for comparison"""
                if not isinstance(methods, list):
                    return []
                normalized = []
                for method in methods:
                    if isinstance(method, dict):
                        normalized.append({
                            'method': method.get('method', ''),
                            'provider': method.get('provider', ''),
                            'bank_name': method.get('bank_name', ''),
                        })
                # Sort for consistent comparison
                normalized.sort(key=lambda x: (x['method'], x.get('provider', ''), x.get('bank_name', '')))
                return normalized
            
            normalized_current_payment_methods = normalize_payment_methods(current_payment_methods)
            
            # Find existing active listings with same service identifier from same user
            existing_listings = P2PServiceListing.objects.filter(
                service_identifier_hash=identifier_hash,
                service_type=service_type,
                seller=user,
                status__in=['active', 'under_review']
            )
            
            if self.instance:
                existing_listings = existing_listings.exclude(id=self.instance.id)
            
            # Check for exact duplicates
            for existing in existing_listings:
                # Check if rate is the same (within 0.01 GHS tolerance)
                rate_diff = abs(float(existing.rate_cedis_per_usd) - float(current_rate))
                if rate_diff < Decimal('0.01'):
                    # Check if amounts are the same
                    if (existing.min_amount_usd == current_min_amount and 
                        existing.max_amount_usd == current_max_amount and
                        existing.available_amount_usd == current_available_amount):
                        # Check if payment methods are the same
                        existing_payment_methods = normalize_payment_methods(existing.accepted_payment_methods)
                        if normalized_current_payment_methods == existing_payment_methods:
                            # This is an exact duplicate!
                            raise serializers.ValidationError({
                                'rate_cedis_per_usd': f"You already have an active listing with the same rate (₵{existing.rate_cedis_per_usd}/USD), amount range (${existing.min_amount_usd}-${existing.max_amount_usd or 'unlimited'}), and payment methods. Please modify at least one of these to create a new listing."
                            })
            
            # Check for listings without meaningful differences
            # A listing must have at least ONE of these differences compared to existing listings:
            # 1. Rate difference >= 0.1 GHS
            # 2. Different amount ranges (min or max differs)
            # 3. Different payment methods
            if existing_listings.exists():
                similar_listings = []
                has_meaningful_difference = False
                
                for existing in existing_listings:
                    # Check rate difference
                    rate_diff = abs(float(existing.rate_cedis_per_usd) - float(current_rate))
                    if rate_diff >= 0.1:
                        has_meaningful_difference = True
                        break
                    
                    # Check amount differences
                    if (existing.min_amount_usd != current_min_amount or 
                        existing.max_amount_usd != current_max_amount or
                        existing.available_amount_usd != current_available_amount):
                        has_meaningful_difference = True
                        break
                    
                    # Check payment method differences
                    existing_payment_methods = normalize_payment_methods(existing.accepted_payment_methods)
                    if normalized_current_payment_methods != existing_payment_methods:
                        has_meaningful_difference = True
                        break
                    
                    # If we get here, this listing is too similar to this existing one
                    similar_listings.append(existing)
                
                # If we have similar listings but no meaningful difference, warn user
                if similar_listings and not has_meaningful_difference:
                    similar_count = len(similar_listings)
                    raise serializers.ValidationError({
                        'rate_cedis_per_usd': f"You have {similar_count} similar active listing(s) with the same service identifier. To create a new listing, please ensure it has at least one meaningful difference: (1) Rate difference of at least ₵0.10, (2) Different amount ranges, or (3) Different payment methods."
                    })
        
        # Check for duplicate proof image if provided (only for sell listings)
        if proof_image and listing_type == 'sell':
            try:
                from orders.image_utils import compute_image_hash, check_image_duplicate
                
                # Compute perceptual hash
                proof_image.seek(0)  # Reset file pointer
                image_hash = compute_image_hash(proof_image)
                
                if image_hash:
                    # Collect all existing hashes from listings and seller applications
                    existing_hashes = []
                    
                    # From P2P listings
                    existing_listings = P2PServiceListing.objects.filter(
                        proof_image_hash__isnull=False
                    ).exclude(id=self.instance.id if self.instance else -1)
                    existing_hashes.extend([l.proof_image_hash for l in existing_listings if l.proof_image_hash])
                    
                    # From seller applications
                    from orders.p2p_models import SellerApplication
                    existing_applications = SellerApplication.objects.filter(
                        proof_of_funds_hash__isnull=False
                    )
                    existing_hashes.extend([a.proof_of_funds_hash for a in existing_applications if a.proof_of_funds_hash])
                    
                    # Check for duplicates
                    proof_image.seek(0)
                    if check_image_duplicate(proof_image, existing_hashes, threshold=85):
                        raise serializers.ValidationError({
                            'proof_image': "This proof image has been used before. Please upload a different image."
                        })
                    
                    # Store hash for later
                    attrs['proof_image_hash'] = image_hash
                    
                    # Add watermark to image
                    from orders.image_utils import process_uploaded_image
                    proof_image.seek(0)
                    attrs['proof_image'] = process_uploaded_image(proof_image, add_watermark_flag=True)
            except Exception as e:
                # If image processing fails, log but don't block listing creation
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing proof image: {str(e)}")
        
        return attrs


class P2PServiceTransactionSerializer(serializers.ModelSerializer):
    """Serializer for P2P service transactions"""
    buyer_email = serializers.EmailField(source='buyer.email', read_only=True)
    buyer_name = serializers.SerializerMethodField()
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    seller_name = serializers.SerializerMethodField()
    listing_reference = serializers.CharField(source='listing.reference', read_only=True)
    service_type_display = serializers.CharField(source='listing.get_service_type_display', read_only=True)
    is_buyer = serializers.SerializerMethodField()
    is_seller = serializers.SerializerMethodField()
    service_proof_image_url = serializers.SerializerMethodField()
    payment_screenshot_url = serializers.SerializerMethodField()
    has_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = P2PServiceTransaction
        fields = (
            'id', 'reference', 'listing', 'listing_reference', 'buyer', 'buyer_email', 'buyer_name',
            'seller', 'seller_email', 'seller_name', 'service_type_display',
            'amount_usd', 'agreed_price_cedis', 'escrow_amount_cedis',
            'selected_payment_method', 'payment_method_details',
            'service_identifier', 'service_proof_image', 'service_proof_image_url', 'service_provided_at',
            'buyer_service_identifier',
            'buyer_verified', 'buyer_verification_notes', 'verified_at',
            'buyer_marked_paid', 'buyer_marked_paid_at', 'payment_screenshot', 'payment_screenshot_url', 'seller_confirmed_payment', 'seller_confirmed_payment_at',
            'status', 'has_dispute', 'dispute_reason', 'dispute_resolved', 'dispute_resolution',
            'payment_deadline', 'seller_response_deadline', 'buyer_verification_deadline', 'auto_release_at',
            'risk_score', 'risk_factors',
            'is_buyer', 'is_seller', 'has_rating',
            'created_at', 'updated_at', 'completed_at', 'cancelled_at'
        )
        read_only_fields = (
            'id', 'reference', 'buyer', 'seller', 'buyer_email', 'buyer_name',
            'seller_email', 'seller_name', 'listing_reference', 'service_type_display',
            'escrow_amount_cedis', 'status', 'has_dispute', 'dispute_resolved',
            'payment_deadline', 'seller_response_deadline', 'buyer_verification_deadline', 'auto_release_at',
            'risk_score', 'risk_factors',
            'is_buyer', 'is_seller', 'has_rating',
            'created_at', 'updated_at', 'completed_at', 'cancelled_at'
        )
    
    def get_buyer_name(self, obj):
        return obj.buyer.get_full_name() or obj.buyer.email
    
    def get_seller_name(self, obj):
        return obj.seller.get_full_name() or obj.seller.email
    
    def get_is_buyer(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.buyer == request.user
        return False
    
    def get_is_seller(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.seller == request.user
        return False
    
    def get_service_proof_image_url(self, obj):
        if obj.service_proof_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.service_proof_image.url)
            return obj.service_proof_image.url
        return None
    
    def get_payment_screenshot_url(self, obj):
        if obj.payment_screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.payment_screenshot.url)
            return obj.payment_screenshot.url
        return None
    
    def get_has_rating(self, obj):
        """Check if transaction has been rated"""
        return hasattr(obj, 'rating') and obj.rating is not None


class P2PServiceTransactionCreateSerializer(serializers.Serializer):
    """Serializer for creating P2P service transactions"""
    listing_id = serializers.IntegerField()
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    selected_payment_method = serializers.CharField(max_length=20)
    payment_method_details = serializers.JSONField(required=False, default=dict)
    buyer_service_identifier = serializers.CharField(max_length=255, required=False, allow_blank=True, help_text="Service identifier where buyer wants to receive service (required for BUY listings)")
    
    def validate_listing_id(self, value):
        try:
            listing = P2PServiceListing.objects.get(id=value)
            if listing.status != 'active':
                raise serializers.ValidationError("This listing is not available for purchase.")
            if listing.seller == self.context['request'].user:
                raise serializers.ValidationError("You cannot purchase your own listing.")
            return value
        except P2PServiceListing.DoesNotExist:
            raise serializers.ValidationError("Listing not found.")
    
    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
    
    def validate_selected_payment_method(self, value):
        valid_methods = ['momo', 'bank', 'other']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Invalid payment method. Must be one of {valid_methods}.")
        return value
    
    def validate(self, attrs):
        """Validate amount is within listing limits, payment method is accepted, and buyer service identifier for BUY listings"""
        listing_id = attrs.get('listing_id')
        amount_usd = attrs.get('amount_usd')
        selected_payment_method = attrs.get('selected_payment_method')
        
        try:
            listing = P2PServiceListing.objects.get(id=listing_id)
        except P2PServiceListing.DoesNotExist:
            raise serializers.ValidationError("Listing not found.")
        
        # For BUY listings, payment method validation is skipped (not needed - funds are in wallet)
        # For SELL listings, validate payment method
        if listing.listing_type == 'sell':
            # Check payment method is accepted
            accepted_methods = listing.accepted_payment_methods or []
            method_found = any(m.get('method') == selected_payment_method for m in accepted_methods)
            
            if not method_found:
                raise serializers.ValidationError({
                    'selected_payment_method': f"This seller does not accept {selected_payment_method} payments. Accepted methods: {', '.join([m.get('method') for m in accepted_methods])}."
                })
        
        # For BUY listings, buyer_service_identifier is required
        if listing.listing_type == 'buy':
            buyer_service_identifier = attrs.get('buyer_service_identifier', '').strip()
            if not buyer_service_identifier:
                raise serializers.ValidationError({
                    'buyer_service_identifier': 'Please provide where you want to receive the service (CashApp tag, PayPal email, or Zelle email).'
                })
            
            # Validate format based on service type
            import re
            if listing.service_type == 'paypal' or listing.service_type == 'zelle':
                # Must be a valid email
                if '@' not in buyer_service_identifier:
                    raise serializers.ValidationError({
                        'buyer_service_identifier': f'Valid email address is required for {listing.get_service_type_display()}.'
                    })
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, buyer_service_identifier):
                    raise serializers.ValidationError({
                        'buyer_service_identifier': 'Invalid email format.'
                    })
            elif listing.service_type == 'cashapp':
                # Must be a valid CashApp tag (starts with $)
                if not buyer_service_identifier.startswith('$'):
                    raise serializers.ValidationError({
                        'buyer_service_identifier': 'Valid CashApp tag (starting with $) is required. Example: $YourTag'
                    })
        
        # Check amount is within limits
        if amount_usd < listing.min_amount_usd:
            raise serializers.ValidationError({
                'amount_usd': f"Minimum transaction amount is ${listing.min_amount_usd} USD."
            })
        
        if listing.max_amount_usd and amount_usd > listing.max_amount_usd:
            raise serializers.ValidationError({
                'amount_usd': f"Maximum transaction amount is ${listing.max_amount_usd} USD."
            })
        
        if amount_usd > listing.available_amount_usd:
            raise serializers.ValidationError({
                'amount_usd': f"Available amount is only ${listing.available_amount_usd} USD."
            })
        
        # Check buyer qualification (Binance-style requirements)
        buyer = self.context['request'].user
        payment_method_details = attrs.get('payment_method_details', {})
        qualified, reason = listing.check_buyer_qualification(buyer, payment_method_details)
        
        if not qualified:
            raise serializers.ValidationError({
                'buyer_qualification': reason or "You do not meet the buyer requirements for this listing."
            })
        
        return attrs


class P2PServiceDisputeSerializer(serializers.ModelSerializer):
    """Serializer for P2P service disputes"""
    raised_by_email = serializers.EmailField(source='raised_by.email', read_only=True)
    transaction_reference = serializers.CharField(source='transaction.reference', read_only=True)
    dispute_type_display = serializers.CharField(source='get_dispute_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    resolution_display = serializers.CharField(source='get_resolution_display', read_only=True)
    
    class Meta:
        model = P2PServiceDispute
        fields = '__all__'
        read_only_fields = (
            'transaction', 'raised_by', 'created_at', 'updated_at',
            'assigned_to', 'assigned_at', 'resolved_at'
        )


class P2PServiceDisputeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating P2P service disputes"""
    evidence_images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True,
        help_text="List of evidence images"
    )
    
    class Meta:
        model = P2PServiceDispute
        fields = ('transaction', 'dispute_type', 'description', 'evidence_images', 'priority')
    
    def validate_transaction(self, value):
        request = self.context.get('request')
        if request and request.user:
            # Ensure user is part of the transaction
            if value.buyer != request.user and value.seller != request.user:
                raise serializers.ValidationError("You are not part of this transaction.")
            # Ensure transaction can be disputed
            if value.status not in ['service_provided', 'verifying', 'payment_received']:
                raise serializers.ValidationError("This transaction cannot be disputed in its current status.")
        return value


class P2PServiceTransactionRatingSerializer(serializers.ModelSerializer):
    """Serializer for P2P service transaction ratings"""
    rater_email = serializers.EmailField(source='rater.email', read_only=True)
    rated_user_email = serializers.EmailField(source='rated_user.email', read_only=True)
    transaction_reference = serializers.CharField(source='transaction.reference', read_only=True)
    
    class Meta:
        model = P2PServiceTransactionRating
        fields = '__all__'
        read_only_fields = ('transaction', 'rater', 'rated_user', 'created_at', 'updated_at')


class P2PServiceTransactionRatingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating P2P service transaction ratings"""
    
    class Meta:
        model = P2PServiceTransactionRating
        fields = ('transaction', 'rating', 'comment')
    
    def validate_transaction(self, value):
        request = self.context.get('request')
        if request and request.user:
            # Ensure user is the buyer
            if value.buyer != request.user:
                raise serializers.ValidationError("Only the buyer can rate this transaction.")
            # Ensure transaction is completed
            if value.status != 'completed':
                raise serializers.ValidationError("You can only rate completed transactions.")
            # Ensure transaction hasn't been rated
            # Check if rating already exists (OneToOneField means hasattr always returns True, so check if it's not None)
            if hasattr(value, 'rating') and value.rating is not None:
                raise serializers.ValidationError("This transaction has already been rated.")
        return value
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class P2PServiceTransactionLogSerializer(serializers.ModelSerializer):
    """Serializer for P2P service transaction logs"""
    
    class Meta:
        model = P2PServiceTransactionLog
        fields = '__all__'
        read_only_fields = ('transaction', 'action_by', 'created_at')


class P2PServiceDisputeLogSerializer(serializers.ModelSerializer):
    """Serializer for P2P service dispute logs"""
    
    class Meta:
        model = P2PServiceDisputeLog
        fields = '__all__'
        read_only_fields = ('dispute', 'action_by', 'created_at')


class SellerApplicationSerializer(serializers.ModelSerializer):
    """Serializer for seller applications"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    reviewer_email = serializers.EmailField(source='reviewed_by.email', read_only=True)
    reviewer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SellerApplication
        fields = (
            'id', 'user', 'user_email', 'user_name',
            'reason', 'experience', 'service_types',
            'status', 'reviewed_by', 'reviewer_email', 'reviewer_name',
            'reviewed_at', 'rejection_reason',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'user', 'user_email', 'user_name',
            'status', 'reviewed_by', 'reviewer_email', 'reviewer_name',
            'reviewed_at', 'rejection_reason',
            'created_at', 'updated_at'
        )
    
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email
    
    def get_reviewer_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None


class SellerApplicationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating seller applications"""
    
    class Meta:
        model = SellerApplication
        fields = ('reason', 'experience', 'service_types', 'proof_of_funds_image')
    
    def to_internal_value(self, data):
        """Parse service_types from JSON string if needed (for FormData)"""
        # Handle service_types if it comes as a JSON string from FormData
        if 'service_types' in data and isinstance(data.get('service_types'), str):
            try:
                import json
                data = data.copy()  # Make a mutable copy
                data['service_types'] = json.loads(data['service_types'])
            except (json.JSONDecodeError, TypeError):
                pass  # Let the validation handle the error
        return super().to_internal_value(data)
    
    def validate_service_types(self, value):
        """Validate service types"""
        valid_types = ['paypal', 'cashapp', 'zelle']
        if not isinstance(value, list):
            raise serializers.ValidationError("Service types must be a list.")
        if not value:
            raise serializers.ValidationError("You must select at least one service type.")
        for service_type in value:
            if service_type not in valid_types:
                raise serializers.ValidationError(f"Invalid service type: {service_type}. Must be one of {valid_types}.")
        return value
    
    def validate_reason(self, value):
        """Validate reason field"""
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError("Please provide a detailed reason (at least 20 characters).")
        return value.strip()
    
    def create(self, validated_data):
        """Create seller application"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("You must be authenticated to apply.")
        
        user = request.user
        
        # Check if user already has a pending application
        existing = SellerApplication.objects.filter(
            user=user,
            status__in=['pending', 'approved']
        ).first()
        
        if existing:
            if existing.status == 'pending':
                raise serializers.ValidationError("You already have a pending seller application. Please wait for review.")
            elif existing.status == 'approved':
                raise serializers.ValidationError("You are already an approved seller.")
        
        # Check requirements - allow proof of funds for new users without trade history
        requirements_errors = []
        proof_of_funds_image = validated_data.get('proof_of_funds_image')
        proof_of_funds_provided = proof_of_funds_image is not None
        
        # Calculate current trust score
        current_trust_score = user.get_effective_trust_score()
        
        # Check for duplicate images if proof of funds is provided
        if proof_of_funds_image:
            try:
                from PIL import Image
                import imagehash
                
                # Compute hash
                proof_of_funds_image.seek(0)
                img = Image.open(proof_of_funds_image)
                image_hash = str(imagehash.phash(img))
                
                # Check against all existing proof of funds images
                existing_applications = SellerApplication.objects.filter(
                    proof_of_funds_hash__isnull=False
                ).exclude(user=user)
                
                for existing in existing_applications:
                    if existing.proof_of_funds_hash:
                        try:
                            existing_hash = imagehash.hex_to_hash(existing.proof_of_funds_hash)
                            current_hash = imagehash.hex_to_hash(image_hash)
                            distance = current_hash - existing_hash
                            similarity = ((64 - distance) / 64) * 100
                            
                            if similarity > 85:
                                raise serializers.ValidationError({
                                    'proof_of_funds_image': "This image has been used before. Please upload a different proof of funds image."
                                })
                        except Exception:
                            continue
                
                # Also check against P2P listing proof images
                from orders.p2p_models import P2PServiceListing
                existing_listings = P2PServiceListing.objects.filter(
                    proof_image_hash__isnull=False
                )
                
                for listing in existing_listings:
                    if listing.proof_image_hash:
                        try:
                            existing_hash = imagehash.hex_to_hash(listing.proof_image_hash)
                            current_hash = imagehash.hex_to_hash(image_hash)
                            distance = current_hash - existing_hash
                            similarity = ((64 - distance) / 64) * 100
                            
                            if similarity > 85:
                                raise serializers.ValidationError({
                                    'proof_of_funds_image': "This image has been used in a listing before. Please upload a different proof of funds image."
                                })
                        except Exception:
                            continue
                
                # Store hash for later use
                validated_data['proof_of_funds_hash'] = image_hash
            except ImportError:
                # imagehash not available, skip duplicate check
                pass
            except Exception as e:
                # Log but don't block if image processing fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error checking proof of funds image: {str(e)}")
        
        if not user.email_verified:
            requirements_errors.append("Email verification is required.")
        
        if user.kyc_status != 'approved':
            requirements_errors.append("KYC approval is required.")
        
        # For new users (0 trades): allow proof of funds to bypass trust score requirement
        # For existing users: require trust score >= 5 OR proof of funds
        if user.successful_trades == 0:
            # New user must provide proof of funds (trust score requirement waived)
            if not proof_of_funds_provided:
                requirements_errors.append("Since you have no completed trades, you must provide proof of funds (e.g., screenshot of PayPal balance, bank statement, etc.).")
        else:
            # Existing users: need either trust score >= 5 OR proof of funds
            if current_trust_score < 5 and not proof_of_funds_provided:
                requirements_errors.append(
                    f"Minimum trust score of 5 is required (your current score: {current_trust_score}). "
                    "You can either:\n"
                    "1. Complete more trades to increase your trust score, OR\n"
                    "2. Provide proof of funds to bypass this requirement.\n\n"
                    "Trust score increases by:\n"
                    "- +1 point for each completed trade\n"
                    "- +1 point for verified email\n"
                    "- +2 points for each 5-star rating\n"
                    "- +1 point for each 4-star rating"
                )
            if user.successful_trades < 3 and not proof_of_funds_provided:
                requirements_errors.append(
                    "At least 3 completed trades are required, OR you can provide proof of funds to bypass this requirement."
                )
        
        if requirements_errors:
            raise serializers.ValidationError({
                'requirements': requirements_errors  # Return as list, not single string
            })
        
        validated_data['user'] = user
        
        # Save the application
        application = super().create(validated_data)
        
        # If proof of funds hash was computed, save it
        if 'proof_of_funds_hash' in validated_data:
            application.proof_of_funds_hash = validated_data['proof_of_funds_hash']
            application.save(update_fields=['proof_of_funds_hash'])
        
        return application
