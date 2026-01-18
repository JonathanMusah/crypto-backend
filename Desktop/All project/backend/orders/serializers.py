from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import GiftCard, GiftCardOrder, Order, Trade, GiftCardListing, GiftCardTransaction, GiftCardDispute, GiftCardTransactionRating, GiftCardDisputeLog


class GiftCardSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = GiftCard
        fields = ('id', 'name', 'brand', 'rate_buy', 'rate_sell', 'image', 'image_url', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class GiftCardOrderSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    card_name = serializers.CharField(source='card.name', read_only=True)
    card_brand = serializers.CharField(source='card.brand', read_only=True)
    proof_image_url = serializers.SerializerMethodField()
    calculated_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = GiftCardOrder
        fields = (
            'id', 'user', 'user_email', 'card', 'card_name', 'card_brand', 
            'order_type', 'amount', 'calculated_amount', 'status', 
            'proof_image', 'proof_image_url', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'created_at', 'updated_at', 'calculated_amount')

    def get_proof_image_url(self, obj):
        if obj.proof_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.proof_image.url)
            return obj.proof_image.url
        return None

    def validate(self, data):
        """Validate order data"""
        if 'card' in data:
            card = data['card']
            if not card.is_active:
                raise serializers.ValidationError("This gift card is not active.")
        return data


class GiftCardOrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating gift card orders without proof image"""
    class Meta:
        model = GiftCardOrder
        fields = ('card', 'order_type', 'amount')
    
    def validate(self, data):
        card = data.get('card')
        if card and not card.is_active:
            raise serializers.ValidationError("This gift card is not active.")
        
        amount = data.get('amount')
        if amount and amount <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        
        return data


class GiftCardRateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating gift card rates (admin only)"""
    class Meta:
        model = GiftCard
        fields = ('rate_buy', 'rate_sell')
    
    def validate_rate_buy(self, value):
        if value <= 0:
            raise serializers.ValidationError("Buy rate must be greater than zero.")
        return value
    
    def validate_rate_sell(self, value):
        if value <= 0:
            raise serializers.ValidationError("Sell rate must be greater than zero.")
        return value


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'user', 'order_type', 'currency_pair', 'amount', 'price', 'total', 'status', 'created_at', 'updated_at', 'completed_at')
        read_only_fields = ('id', 'user', 'total', 'created_at', 'updated_at', 'completed_at')


class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = ('id', 'order', 'buyer', 'seller', 'amount', 'price', 'total', 'created_at')
        read_only_fields = ('id', 'created_at')


# P2P Marketplace Serializers

class GiftCardListingSerializer(serializers.ModelSerializer):
    """Serializer for gift card listings"""
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    seller_name = serializers.SerializerMethodField()
    seller_trust_score = serializers.SerializerMethodField()
    seller_rating_stats = serializers.SerializerMethodField()  # Add this as SerializerMethodField
    card_name = serializers.CharField(source='card.name', read_only=True)
    card_brand = serializers.CharField(source='card.brand', read_only=True)
    card_image_url = serializers.SerializerMethodField()
    proof_image_url = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    
    class Meta:
        model = GiftCardListing
        fields = (
            'id', 'reference', 'seller', 'seller_email', 'seller_name', 'seller_trust_score', 'seller_rating_stats', 'card', 'card_name', 'card_brand', 'card_image_url',
            'gift_card_code', 'gift_card_pin', 'gift_card_value', 'currency',
            'asking_price_cedis', 'is_negotiable',
            'proof_image', 'proof_image_url', 'proof_notes',
            'status', 'views_count', 'expires_at',
            'admin_notes', 'reviewed_by', 'reviewed_at',
            'created_at', 'updated_at', 'is_owner'
        )
        read_only_fields = (
            'id', 'reference', 'seller', 'seller_email', 'seller_name', 'card_name', 'card_brand', 'card_image_url',
            'gift_card_code', 'gift_card_pin',  # Hidden until purchase
            'status', 'views_count', 'reviewed_by', 'reviewed_at',
            'created_at', 'updated_at', 'is_owner'
        )
    
    def get_seller_name(self, obj):
        if obj.seller.first_name or obj.seller.last_name:
            return f"{obj.seller.first_name} {obj.seller.last_name}".strip()
        return obj.seller.email.split('@')[0]
    
    def get_seller_trust_score(self, obj):
        """Get seller's effective trust score"""
        return obj.seller.get_effective_trust_score()
    
    def get_seller_rating_stats(self, obj):
        """Get seller's rating statistics"""
        from django.db.models import Avg
        ratings = GiftCardTransactionRating.objects.filter(
            rated_user=obj.seller,
            is_visible=True
        )
        total = ratings.count()
        if total == 0:
            return {
                'total_ratings': 0,
                'average_rating': 0
            }
        avg = ratings.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        return {
            'total_ratings': total,
            'average_rating': round(avg, 2)
        }
    
    def get_card_image_url(self, obj):
        if obj.card.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.card.image.url)
            return obj.card.image.url
        return None
    
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
    
    def validate_asking_price_cedis(self, value):
        if value <= 0:
            raise serializers.ValidationError("Asking price must be greater than zero.")
        return value
    
    def validate_gift_card_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Gift card value must be greater than zero.")
        return value


class GiftCardListingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating gift card listings"""
    gift_card_code = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text="Gift card code (optional during listing, but recommended for duplicate detection)")
    gift_card_pin = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text="Gift card PIN if applicable")
    
    class Meta:
        model = GiftCardListing
        fields = (
            'card', 'gift_card_value', 'currency', 'asking_price_cedis', 'is_negotiable',
            'proof_image', 'proof_notes', 'gift_card_code', 'gift_card_pin'
        )
    
    def validate_asking_price_cedis(self, value):
        if value <= 0:
            raise serializers.ValidationError("Asking price must be greater than zero.")
        return value
    
    def validate_gift_card_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Gift card value must be greater than zero.")
        
        # Check gift card value limit for new/low-trust sellers
        request = self.context.get('request')
        if request and request.user:
            seller = request.user
            max_value = seller.get_max_gift_card_value_cedis()
            if max_value is not None and value > max_value:
                raise serializers.ValidationError(
                    f"New sellers (trust score < 3) cannot list gift cards above {max_value} cedis. "
                    f"Your current trust score is {seller.get_effective_trust_score()}. "
                    "Complete successful trades to increase your limit."
                )
        
        return value
    
    def validate(self, attrs):
        """Validate duplicate gift card and image"""
        # Extract code and pin for hashing
        gift_card_code = attrs.get('gift_card_code', '').strip()
        gift_card_pin = attrs.get('gift_card_pin', '').strip()
        proof_image = attrs.get('proof_image')
        
        # Check for duplicate card if code is provided
        if gift_card_code:
            card_hash = GiftCardListing.compute_card_hash(gift_card_code, gift_card_pin)
            
            # Check if hash exists in active or disputed listings
            from orders.models import GiftCardListing, GiftCardTransaction
            # Exclude current instance if updating
            existing_listing = GiftCardListing.objects.filter(
                card_hash=card_hash,
                status__in=['active', 'under_review', 'sold']
            )
            
            if self.instance:
                existing_listing = existing_listing.exclude(id=self.instance.id)
            
            # Check if any existing listing has active transactions without disputes
            existing_listing = existing_listing.filter(
                transactions__has_dispute=False
            ) | existing_listing.exclude(
                transactions__isnull=False
            )
            
            existing = existing_listing.first()
            
            if existing:
                raise serializers.ValidationError({
                    'gift_card_code': "This gift card has already been listed. Duplicate or reused cards are not allowed. Please contact support if you believe this is an error."
                })
        
        # Check for duplicate proof image if provided
        if proof_image:
            try:
                # Compute perceptual hash
                proof_image.seek(0)  # Reset file pointer
                image_hash = GiftCardListing.compute_proof_image_hash(proof_image)
                
                if image_hash:
                    # Check for similar images
                    from orders.models import GiftCardListing
                    existing_listings = GiftCardListing.objects.filter(
                        proof_image_hash__isnull=False
                    ).exclude(id=self.instance.id if self.instance else -1)
                    
                    try:
                        import imagehash
                        current_hash = imagehash.hex_to_hash(image_hash)
                        
                        for listing in existing_listings:
                            if not listing.proof_image_hash:
                                continue
                            
                            try:
                                existing_hash = imagehash.hex_to_hash(listing.proof_image_hash)
                                distance = current_hash - existing_hash
                                similarity = ((64 - distance) / 64) * 100
                                
                                if similarity > 85:
                                    raise serializers.ValidationError({
                                        'proof_image': f"This proof image has been used before (similarity: {similarity:.1f}%). Reused photos are not allowed. Please upload a unique image of your gift card."
                                    })
                            except (ValueError, TypeError):
                                continue
                    except ImportError:
                        # Fallback: exact match if imagehash not available
                        exact_match = existing_listings.filter(
                            proof_image_hash=image_hash
                        ).first()
                        if exact_match:
                            raise serializers.ValidationError({
                                'proof_image': "This proof image has been used before. Reused photos are not allowed. Please upload a unique image of your gift card."
                            })
                
                # Store image hash for future comparisons
                proof_image.seek(0)  # Reset again for saving
                attrs['proof_image_hash'] = image_hash
                
                # Add watermark to image (users will see this in listings)
                try:
                    from orders.image_utils import process_uploaded_image
                    proof_image.seek(0)
                    attrs['proof_image'] = process_uploaded_image(proof_image, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                except Exception as e:
                    logger.warning(f"Failed to watermark gift card listing proof image: {str(e)}")
                    # Continue with original image if watermarking fails
                    proof_image.seek(0)
            except Exception as e:
                # Don't block listing creation if image hash computation fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error computing image hash during listing validation: {str(e)}")
        
        return attrs
    
    def create(self, validated_data):
        seller = self.context['request'].user
        
        # Extract code and pin for hashing (if provided and not already processed in validate)
        gift_card_code = validated_data.pop('gift_card_code', '').strip() if 'gift_card_code' in validated_data else ''
        gift_card_pin = validated_data.pop('gift_card_pin', '').strip() if 'gift_card_pin' in validated_data else ''
        
        # Compute and store card hash if code is provided
        if gift_card_code and 'card_hash' not in validated_data:
            validated_data['card_hash'] = GiftCardListing.compute_card_hash(gift_card_code, gift_card_pin)
            # Store code and pin (hidden from buyers until purchase)
            validated_data['gift_card_code'] = gift_card_code
            validated_data['gift_card_pin'] = gift_card_pin
        
        # Check trust score limits
        if not seller.can_create_listing():
            max_allowed = seller.get_max_listings_allowed()
            if max_allowed == 0:
                raise serializers.ValidationError(
                    "You cannot create listings. Your trust score is too low. "
                    "Please complete some successful trades to increase your trust score."
                )
            else:
                from orders.models import GiftCardListing
                active_count = GiftCardListing.objects.filter(
                    seller=seller,
                    status='active'
                ).count()
                raise serializers.ValidationError(
                    f"You have reached your listing limit ({active_count}/{max_allowed} active listings). "
                    f"Your current trust score ({seller.get_effective_trust_score()}) allows a maximum of {max_allowed} active listings. "
                    "Complete more successful trades to increase your limit."
                )
        
        # Proof image hash is already computed in validate method
        # Card hash is already computed above (lines 326-335)
        validated_data['seller'] = seller
        return super().create(validated_data)


class GiftCardTransactionSerializer(serializers.ModelSerializer):
    """Serializer for gift card transactions"""
    buyer_email = serializers.EmailField(source='buyer.email', read_only=True)
    buyer_name = serializers.SerializerMethodField()
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    seller_name = serializers.SerializerMethodField()
    listing_reference = serializers.CharField(source='listing.reference', read_only=True)
    card_name = serializers.CharField(source='listing.card.name', read_only=True)
    card_brand = serializers.CharField(source='listing.card.brand', read_only=True)
    is_buyer = serializers.SerializerMethodField()
    is_seller = serializers.SerializerMethodField()
    
    class Meta:
        model = GiftCardTransaction
        fields = (
            'id', 'reference', 'listing', 'listing_reference', 'buyer', 'buyer_email', 'buyer_name',
            'seller', 'seller_email', 'seller_name', 'card_name', 'card_brand',
            'agreed_price_cedis', 'escrow_amount_cedis',
            'gift_card_code', 'gift_card_pin', 'card_provided_at',
            'buyer_verified', 'buyer_verification_notes', 'verified_at',
            'status', 'has_dispute', 'dispute_reason', 'dispute_resolved', 'dispute_resolution',
            'admin_notes', 'created_at', 'updated_at', 'completed_at', 'cancelled_at',
            'is_buyer', 'is_seller'
        )
        read_only_fields = (
            'id', 'reference', 'buyer', 'buyer_email', 'buyer_name', 'seller', 'seller_email', 'seller_name',
            'listing_reference', 'card_name', 'card_brand',
            'gift_card_code', 'gift_card_pin',  # Hidden until seller provides
            'escrow_amount_cedis', 'card_provided_at', 'buyer_verified', 'verified_at',
            'status', 'has_dispute', 'dispute_resolved', 'dispute_resolution',
            'created_at', 'updated_at', 'completed_at', 'cancelled_at',
            'is_buyer', 'is_seller'
        )
    
    def get_buyer_name(self, obj):
        if obj.buyer.first_name or obj.buyer.last_name:
            return f"{obj.buyer.first_name} {obj.buyer.last_name}".strip()
        return obj.buyer.email.split('@')[0]
    
    def get_seller_name(self, obj):
        if obj.seller.first_name or obj.seller.last_name:
            return f"{obj.seller.first_name} {obj.seller.last_name}".strip()
        return obj.seller.email.split('@')[0]
    
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
    
    def to_representation(self, instance):
        """Hide gift card code/pin unless user is buyer or seller"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if request and request.user.is_authenticated:
            # Show code/pin only to buyer or seller
            if instance.buyer != request.user and instance.seller != request.user:
                data['gift_card_code'] = None
                data['gift_card_pin'] = None
        
        return data


class GiftCardTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a transaction (buying a listing)"""
    class Meta:
        model = GiftCardTransaction
        fields = ('listing',)
    
    def validate_listing(self, value):
        if value.status != 'active':
            raise serializers.ValidationError("This listing is not available for purchase.")
        if value.seller == self.context['request'].user:
            raise serializers.ValidationError("You cannot buy your own listing.")
        return value
    
    def create(self, validated_data):
        listing = validated_data['listing']
        buyer = self.context['request'].user
        
        # Create transaction
        transaction = GiftCardTransaction.objects.create(
            listing=listing,
            buyer=buyer,
            seller=listing.seller,
            agreed_price_cedis=listing.asking_price_cedis,
            escrow_amount_cedis=listing.asking_price_cedis,
            status='pending_payment'
        )
        
        return transaction


class GiftCardDisputeSerializer(serializers.ModelSerializer):
    """Serializer for gift card disputes"""
    raised_by_email = serializers.EmailField(source='raised_by.email', read_only=True)
    transaction_reference = serializers.CharField(source='transaction.reference', read_only=True)
    
    class Meta:
        model = GiftCardDispute
        fields = (
            'id', 'transaction', 'transaction_reference', 'raised_by', 'raised_by_email',
            'dispute_type', 'description', 'evidence_images',
            'status', 'resolution', 'resolution_notes',
            'assigned_to', 'resolved_by', 'resolved_at',
            'priority', 'fraud_indicators', 'verification_attempts',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'transaction_reference', 'raised_by', 'raised_by_email',
            'status', 'resolution', 'resolution_notes',
            'assigned_to', 'resolved_by', 'resolved_at',
            'priority', 'fraud_indicators', 'verification_attempts',
            'created_at', 'updated_at', 'evidence_images'
        )
    
    def validate_description(self, value):
        """Require detailed description"""
        if not value or len(value.strip()) < 50:
            raise serializers.ValidationError(
                "Please provide a detailed description (at least 50 characters). "
                "Include: what went wrong, when you discovered it, and steps you've taken."
            )
        return value
    
    
    def validate_transaction(self, value):
        """Ensure transaction can be disputed with security checks"""
        request = self.context.get('request')
        if not request:
            return value
            
        user = request.user
        
        # Check if transaction can be disputed
        if value.status in ['completed', 'cancelled', 'refunded']:
            raise serializers.ValidationError("This transaction cannot be disputed.")
        if value.has_dispute:
            raise serializers.ValidationError("A dispute already exists for this transaction.")
        
        # Security: Only buyer or seller can dispute
        if value.buyer != user and value.seller != user:
            raise serializers.ValidationError("You can only dispute transactions you are involved in.")
        
        # Security: Check dispute rate limiting (max 3 disputes per user per day)
        from django.utils import timezone
        from datetime import timedelta
        recent_disputes = GiftCardDispute.objects.filter(
            raised_by=user,
            created_at__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        if recent_disputes >= 3:
            raise serializers.ValidationError(
                "You have reached the daily limit for raising disputes (3 per day). "
                "Please contact support if you need to raise more disputes."
            )
        
        return value
    
    def create(self, validated_data):
        request = self.context['request']
        validated_data['raised_by'] = request.user
        
        # Handle evidence file uploads
        uploaded_urls = []
        files = request.FILES.getlist('evidence_images')
        if files:
            
            for file in files:
                # Validate file type
                if not file.content_type.startswith('image/'):
                    raise serializers.ValidationError(
                        {'evidence_images': f'File {file.name} must be an image'}
                    )
                
                # Validate file size (max 5MB per image)
                if file.size > 5 * 1024 * 1024:
                    raise serializers.ValidationError(
                        {'evidence_images': f'File {file.name} must be less than 5MB'}
                    )
                
                # Watermark the image before saving (users will see this in disputes)
                try:
                    from orders.image_utils import process_uploaded_image
                    file.seek(0)
                    file = process_uploaded_image(file, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to watermark dispute evidence image: {str(e)}")
                    # Continue with original image if watermarking fails
                    file.seek(0)
                
                # Save file
                from django.core.files.storage import default_storage
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'dispute_evidence/{validated_data["transaction"].id}/{timestamp}_{file.name}'
                saved_path = default_storage.save(filename, file)
                file_url = default_storage.url(saved_path)
                uploaded_urls.append(file_url)
        
        # Check if evidence is required for this dispute type
        dispute_type = validated_data.get('dispute_type')
        requires_evidence = dispute_type in ['invalid_code', 'wrong_amount', 'expired_card', 'already_used']
        
        if requires_evidence and len(uploaded_urls) == 0:
            raise serializers.ValidationError(
                {'evidence_images': 'Evidence is required for this dispute type. Please upload screenshots showing the issue (e.g., error messages, invalid code attempts, expiration date, etc.).'}
            )
        
        validated_data['evidence_images'] = uploaded_urls
        
        # Calculate fraud indicators
        transaction = validated_data['transaction']
        fraud_indicators = {
            'user_dispute_count_30d': GiftCardDispute.objects.filter(
                raised_by=request.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'transaction_age_hours': (timezone.now() - transaction.created_at).total_seconds() / 3600,
            'has_evidence': len(uploaded_urls) > 0,
            'description_length': len(validated_data.get('description', '')),
        }
        validated_data['fraud_indicators'] = fraud_indicators
        
        # Set priority based on fraud indicators
        if fraud_indicators['user_dispute_count_30d'] > 5:
            validated_data['priority'] = 'high'
        elif fraud_indicators['user_dispute_count_30d'] > 2:
            validated_data['priority'] = 'medium'
        else:
            validated_data['priority'] = 'low'
        
        dispute = super().create(validated_data)
        
        # Mark transaction as disputed
        dispute.transaction.has_dispute = True
        dispute.transaction.status = 'disputed'
        dispute.transaction.save()
        
        # Log dispute creation (will be done in views.py create method)
        
        return dispute


class GiftCardTransactionRatingSerializer(serializers.ModelSerializer):
    """Serializer for transaction ratings"""
    rater_email = serializers.EmailField(source='rater.email', read_only=True)
    rater_name = serializers.SerializerMethodField()
    rated_user_email = serializers.EmailField(source='rated_user.email', read_only=True)
    rated_user_name = serializers.SerializerMethodField()
    transaction_reference = serializers.CharField(source='transaction.reference', read_only=True)
    
    class Meta:
        model = GiftCardTransactionRating
        fields = (
            'id', 'transaction', 'transaction_reference',
            'rater', 'rater_email', 'rater_name',
            'rated_user', 'rated_user_email', 'rated_user_name',
            'rating', 'comment', 'is_visible',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'rater', 'rater_email', 'rater_name',
            'rated_user', 'rated_user_email', 'rated_user_name',
            'transaction_reference', 'created_at', 'updated_at'
        )
    
    def get_rater_name(self, obj):
        if obj.rater.first_name or obj.rater.last_name:
            return f"{obj.rater.first_name} {obj.rater.last_name}".strip()
        return obj.rater.email.split('@')[0]
    
    def get_rated_user_name(self, obj):
        if obj.rated_user.first_name or obj.rated_user.last_name:
            return f"{obj.rated_user.first_name} {obj.rated_user.last_name}".strip()
        return obj.rated_user.email.split('@')[0]
    
    def validate_transaction(self, value):
        """Validate that transaction can be rated"""
        request = self.context.get('request')
        if not request:
            return value
        
        # Check if transaction is completed
        if value.status != 'completed':
            raise serializers.ValidationError("You can only rate completed transactions.")
        
        # Check if user is the buyer
        if value.buyer != request.user:
            raise serializers.ValidationError("Only the buyer can rate this transaction.")
        
        # Check if rating already exists
        if GiftCardTransactionRating.objects.filter(transaction=value).exists():
            raise serializers.ValidationError("You have already rated this transaction.")
        
        return value
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def create(self, validated_data):
        request = self.context['request']
        transaction = validated_data['transaction']
        
        # Set rater (buyer) and rated_user (seller)
        validated_data['rater'] = request.user
        validated_data['rated_user'] = transaction.seller
        
        rating = super().create(validated_data)
        
        # Update seller's trust score after rating is created
        transaction.seller.update_trust_score()
        
        return rating

