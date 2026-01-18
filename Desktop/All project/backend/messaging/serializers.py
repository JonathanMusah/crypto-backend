"""
Serializers for messaging system
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Conversation, Message, MessageReport
from orders.models import GiftCardListing, GiftCardTransaction

# Try to import P2P service transaction (may not exist in all environments)
try:
    from orders.p2p_models import P2PServiceTransaction
except ImportError:
    P2PServiceTransaction = None

User = get_user_model()


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model"""
    user1_email = serializers.EmailField(source='user1.email', read_only=True)
    user2_email = serializers.EmailField(source='user2.email', read_only=True)
    user1_name = serializers.SerializerMethodField()
    user2_name = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()
    listing_title = serializers.SerializerMethodField()
    listing_reference = serializers.SerializerMethodField()
    transaction_detail = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'user1', 'user1_email', 'user1_name',
            'user2', 'user2_email', 'user2_name',
            'other_user', 'listing', 'listing_title', 'listing_reference',
            'transaction', 'transaction_detail', 'created_at', 'last_message_at',
            'is_locked', 'locked_by', 'locked_reason',
            'scam_score', 'unread_count', 'last_message_preview',
            'is_archived_user1', 'is_archived_user2', 'is_archived'
        ]
        read_only_fields = [
            'created_at', 'last_message_at', 'scam_score',
            'locked_by', 'locked_reason'
        ]

    def get_user1_name(self, obj):
        return obj.user1.get_full_name() or obj.user1.email

    def get_user2_name(self, obj):
        return obj.user2.get_full_name() or obj.user2.email

    def get_listing_title(self, obj):
        try:
            if obj.listing and hasattr(obj.listing, 'card') and obj.listing.card:
                return obj.listing.card.brand
        except Exception:
            pass
        return None

    def get_listing_reference(self, obj):
        if obj.listing:
            return obj.listing.reference
        return None

    def get_transaction_detail(self, obj):
        """Get transaction details for navigation - ALWAYS checks transaction_id first for P2P transactions"""
        if not obj.id:
            return None
        
        # CRITICAL: Always check raw transaction_id from database FIRST
        # This is the ONLY reliable way to identify P2P transactions
        # obj.transaction ForeignKey points to GiftCardTransaction, so it's unreliable for P2P
        transaction_id_from_db = None
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT transaction_id FROM conversations WHERE id = %s",
                    [obj.id]
                )
                result = cursor.fetchone()
                if result and result[0]:
                    transaction_id_from_db = result[0]
        except Exception as e:
            # If we can't get transaction_id from DB, continue to fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get transaction_id for conversation {obj.id}: {e}")
            pass
        
        # If we have a transaction_id from database, use it (P2P transactions use this)
        if transaction_id_from_db:
            # Try P2P transaction FIRST (most common case for transaction_id)
            try:
                from orders.p2p_models import P2PServiceTransaction
                p2p_transaction = P2PServiceTransaction.objects.get(id=transaction_id_from_db)
                return {
                    'id': p2p_transaction.id,
                    'reference': p2p_transaction.reference,
                    'type': 'p2p',
                    'url': f'/orders/p2p-services?transaction={p2p_transaction.id}'
                }
            except (P2PServiceTransaction.DoesNotExist, ImportError, AttributeError):
                # If not P2P, try gift card transaction
                try:
                    from orders.models import GiftCardTransaction
                    gift_card_transaction = GiftCardTransaction.objects.get(id=transaction_id_from_db)
                    return {
                        'id': gift_card_transaction.id,
                        'reference': gift_card_transaction.reference,
                        'type': 'gift_card',
                        'url': f'/orders/gift-cards?transaction={gift_card_transaction.id}'
                    }
                except GiftCardTransaction.DoesNotExist:
                    # transaction_id exists but points to neither - this shouldn't happen
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Conversation {obj.id} has transaction_id={transaction_id_from_db} but transaction not found in either P2P or GiftCard tables")
                    pass
        
        # ONLY if no transaction_id in database, fallback to obj.transaction (gift card only)
        # This handles legacy gift card conversations that use the ForeignKey
        if obj.transaction:
            try:
                transaction = obj.transaction
                return {
                    'id': transaction.id,
                    'reference': transaction.reference,
                    'type': 'gift_card',
                    'url': f'/orders/gift-cards?transaction={transaction.id}'
                }
            except Exception:
                pass
        
        return None

    def get_other_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Get the other user in the conversation
            if request.user == obj.user1:
                other = obj.user2
            elif request.user == obj.user2:
                other = obj.user1
            else:
                return None
            
            # Fetch fresh user instance from database to get latest last_seen
            # This ensures we have the most up-to-date status (including None when logged out)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                fresh_other = User.objects.only('id', 'email', 'username', 'first_name', 'last_name', 'last_seen').get(pk=other.id)
                # Force refresh from database to ensure we have the absolute latest last_seen
                fresh_other.refresh_from_db(fields=['last_seen'])
            except User.DoesNotExist:
                fresh_other = other
            
            # Calculate status - if last_seen is None, user is definitely offline (logged out)
            if not fresh_other.last_seen:
                status_info = {'status': 'offline', 'label': 'Offline'}
                is_online = False
            else:
                from django.utils import timezone
                from datetime import timedelta
                from django.core.cache import cache
                
                # Get status from user's get_status() method - this gives us proper "last seen" labels
                status_info = fresh_other.get_status() if hasattr(fresh_other, 'get_status') else {'status': 'offline', 'label': 'Offline'}
                
                # Check for recent activity to determine if user is currently online
                cache_key = f'last_seen_update_{fresh_other.id}'
                last_cache_update = cache.get(cache_key)
                
                now = timezone.now()
                time_since_last_seen = now - fresh_other.last_seen
                
                # User is online ONLY if BOTH conditions are met:
                # 1. last_seen is very recent (< 20 seconds) AND
                # 2. They have a recent cache entry (active within last 15 seconds)
                # This ensures users who closed browser/tab without logging out don't show as online
                # Cache expires after 10 seconds, so checking within 15 seconds is safe
                has_recent_cache = last_cache_update is not None
                is_very_recent = time_since_last_seen < timedelta(seconds=20)
                
                if has_recent_cache and is_very_recent:
                    is_online = True
                    status_info = {'status': 'online', 'label': 'Online'}
                else:
                    # User is offline - use the calculated status_info from get_status()
                    # which already includes proper "Last seen X minutes ago" labels
                    is_online = False
                    # status_info already has the correct label from get_status()
            
            # Get username or fallback to email prefix
            username = fresh_other.username if fresh_other.username and fresh_other.username.strip() else fresh_other.email.split('@')[0] if fresh_other.email else 'user'
            
            return {
                'id': fresh_other.id,
                'email': fresh_other.email,
                'username': username,
                'name': fresh_other.get_full_name() or username,
                'is_online': is_online,  # Explicitly False if last_seen is None
                'status': status_info.get('status', 'offline'),
                'status_label': status_info.get('label', 'Offline'),
                'last_seen': fresh_other.last_seen.isoformat() if fresh_other.last_seen else None,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Count unread messages that are not from the current user
            # System messages (message_type='system') are not counted as unread
            # Only count text messages as unread
            unread_messages = obj.messages.filter(
                read=False,
                message_type='text',
            )
            # Exclude messages sent by the current user (but include system messages where sender is None)
            unread_messages = unread_messages.exclude(
                sender=request.user
            )
            return unread_messages.count()
        return 0

    def get_last_message_preview(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        # Determine the other user in the conversation
        if request.user == obj.user1:
            other_user = obj.user2
        elif request.user == obj.user2:
            other_user = obj.user1
        else:
            return None
        
        # Get the last message from the other user (not from current user)
        # This way users only see messages from their partner in the preview
        last_message = obj.messages.filter(
            is_deleted=False,
            sender=other_user
        ).order_by('-created_at').first()
        
        if last_message:
            preview = last_message.content[:100]
            if len(last_message.content) > 100:
                preview += '...'
            return {
                'content': preview,
                'sender_id': last_message.sender.id if last_message.sender else None,
                'message_type': last_message.message_type,
                'created_at': last_message.created_at,
            }
        return None

    def get_is_archived(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if request.user == obj.user1:
                return obj.is_archived_user1
            elif request.user == obj.user2:
                return obj.is_archived_user2
        return False


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    sender_email = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()
    sender_detail = serializers.SerializerMethodField()
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'conversation_id', 'sender', 'sender_email', 'sender_name', 'sender_detail',
            'content', 'message_type', 'created_at', 'read', 'read_at',
            'flagged', 'scam_detected', 'metadata',
            'attachment', 'attachment_url', 'attachment_type', 'attachment_name', 'attachment_size',
            'is_edited', 'edited_at', 'is_deleted'
        ]
        read_only_fields = [
            'created_at', 'read', 'read_at', 'flagged', 'scam_detected', 'is_edited', 'edited_at', 'is_deleted'
        ]

    def get_sender_email(self, obj):
        """Get sender email, or None for system messages"""
        if obj.sender:
            return obj.sender.email
        return None

    def get_sender_name(self, obj):
        """Get sender name, or 'System' for system messages"""
        if obj.sender:
            # Use username if available, otherwise fallback to full name or email
            if obj.sender.username and obj.sender.username.strip():
                return obj.sender.username
            return obj.sender.get_full_name() or obj.sender.email.split('@')[0] if obj.sender.email else 'User'
        return 'System'

    def get_sender_detail(self, obj):
        """Get sender detail object for frontend"""
        if obj.sender:
            # Get username or fallback to email prefix
            username = obj.sender.username if obj.sender.username and obj.sender.username.strip() else obj.sender.email.split('@')[0] if obj.sender.email else 'user'
            
            return {
                'id': obj.sender.id,
                'email': obj.sender.email,
                'username': username,
                'name': obj.sender.get_full_name() or username,
            }
        return None

    def get_attachment_url(self, obj):
        """Get full URL for attachment"""
        if obj.attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating a new message"""
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    content = serializers.CharField(max_length=5000, min_length=1, required=False, allow_blank=True)
    attachment = serializers.FileField(required=False, allow_null=True)
    # Optional fields for auto-creating conversation
    user2_id = serializers.IntegerField(required=False, allow_null=True)
    listing_id = serializers.IntegerField(required=False, allow_null=True)
    transaction_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_content(self, value):
        """Validate message content"""
        # Content is optional if there's an attachment
        if value and value.strip():
            if len(value.strip()) > 5000:
                raise serializers.ValidationError("Message is too long (max 5000 characters)")
            return value.strip()
        return value or ''
    
    def validate_attachment(self, value):
        """Validate attachment file"""
        if value:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if value.size > max_size:
                raise serializers.ValidationError(f"File size must be less than 10MB. Current size: {value.size / 1024 / 1024:.2f}MB")
            
            # Check file type
            allowed_types = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain', 'text/csv',
                'video/mp4', 'video/quicktime',
                'audio/mpeg', 'audio/wav', 'audio/ogg'
            ]
            
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(f"File type {value.content_type} is not allowed. Allowed types: images, PDF, documents, videos, audio")
        
        return value
    
    def validate(self, attrs):
        """Validate that either content or attachment is provided"""
        content = attrs.get('content', '').strip()
        attachment = attrs.get('attachment')
        
        if not content and not attachment:
            raise serializers.ValidationError("Either message content or attachment must be provided")
        
        return attrs

    def validate(self, attrs):
        """Validate message creation - either conversation_id or conversation creation fields"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        # Validate that either content or attachment is provided
        content = attrs.get('content', '').strip()
        attachment = attrs.get('attachment')
        if not content and not attachment:
            raise serializers.ValidationError("Either message content or attachment must be provided")

        conversation_id = attrs.get('conversation_id')
        user2_id = attrs.get('user2_id')
        listing_id = attrs.get('listing_id')
        transaction_id = attrs.get('transaction_id')

        # Must have either conversation_id OR fields to create conversation
        if not conversation_id and not user2_id and not listing_id and not transaction_id:
            raise serializers.ValidationError(
                "Either provide conversation_id or (user2_id, listing_id, or transaction_id) to create a new conversation"
            )

        # If conversation_id provided, validate it exists and user has access
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                raise serializers.ValidationError("Conversation not found")

            # Check if user is part of conversation
            if request.user not in [conversation.user1, conversation.user2]:
                if not request.user.is_staff:
                    raise serializers.ValidationError("You don't have access to this conversation")

            # Check if conversation is locked
            if conversation.is_locked and not request.user.is_staff:
                raise serializers.ValidationError("This conversation is locked")

        return attrs


class ConversationCreateSerializer(serializers.Serializer):
    """Serializer for creating a new conversation"""
    user2_id = serializers.IntegerField(required=False)
    listing_id = serializers.IntegerField(required=False)
    transaction_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        """Validate conversation creation"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        user1 = request.user
        user2_id = attrs.get('user2_id')
        listing_id = attrs.get('listing_id')
        transaction_id = attrs.get('transaction_id')

        # Must have either listing_id or transaction_id (conversations must be linked to a trade)
        if not listing_id and not transaction_id:
            raise serializers.ValidationError("Conversations must be linked to a listing or transaction. Please provide listing_id or transaction_id.")

        # If transaction_id provided, get buyer/seller from transaction
        if transaction_id:
            transaction = None
            transaction_obj = None  # Store the actual transaction object
            is_p2p_transaction = False
            # Try GiftCardTransaction first
            try:
                transaction_obj = GiftCardTransaction.objects.get(id=transaction_id)
                transaction = transaction_obj  # For Conversation model compatibility
                # Ensure user is part of the transaction
                if request.user not in [transaction_obj.buyer, transaction_obj.seller]:
                    raise serializers.ValidationError("You are not part of this transaction")
                # Get the other user
                user2 = transaction_obj.seller if request.user == transaction_obj.buyer else transaction_obj.buyer
                listing = transaction_obj.listing
            except GiftCardTransaction.DoesNotExist:
                # Try P2PServiceTransaction if GiftCardTransaction not found
                if P2PServiceTransaction:
                    try:
                        transaction_obj = P2PServiceTransaction.objects.get(id=transaction_id)
                        is_p2p_transaction = True
                        # For P2P transactions, we can't assign directly to Conversation.transaction
                        # But we'll store the ID and handle it in the view
                        transaction = None  # Will be handled separately for P2P
                        # Ensure user is part of the transaction
                        if request.user not in [transaction_obj.buyer, transaction_obj.seller]:
                            raise serializers.ValidationError("You are not part of this transaction")
                        # Get the other user
                        user2 = transaction_obj.seller if request.user == transaction_obj.buyer else transaction_obj.buyer
                        listing = None  # P2P services don't use GiftCardListing
                    except (P2PServiceTransaction.DoesNotExist if P2PServiceTransaction else Exception):
                        raise serializers.ValidationError("Transaction not found")
                else:
                    raise serializers.ValidationError("Transaction not found")
        # If listing_id provided, get seller from listing
        elif listing_id:
            try:
                listing = GiftCardListing.objects.get(id=listing_id)
                user2 = listing.seller
                # Ensure user is not the seller
                if request.user == listing.seller:
                    raise serializers.ValidationError("You cannot message yourself")
            except GiftCardListing.DoesNotExist:
                raise serializers.ValidationError("Listing not found")
        else:
            raise serializers.ValidationError("Must provide listing_id or transaction_id")

        # Can't create conversation with yourself
        if user1 == user2:
            raise serializers.ValidationError("Cannot create conversation with yourself")

        # Ensure user1.id < user2.id for consistent unique_together constraint
        u1, u2 = (user1, user2) if user1.id < user2.id else (user2, user1)
        
        # Check if conversation already exists (including archived ones)
        # We check without filtering by archive status to find existing conversations
        # For transaction lookup, always use transaction_id to handle both GiftCardTransaction and P2PServiceTransaction
        # IMPORTANT: Check both possible user orderings since conversations might be created with different ordering
        if transaction_id:
            # First, find any conversation with this transaction_id (most reliable for GiftCard transactions)
            # This catches conversations regardless of how they were created
            existing_by_transaction = Conversation.objects.filter(
                transaction_id=transaction_id
            ).first()
            
            # If found, verify the users match (check both possible orderings)
            if existing_by_transaction:
                if ((existing_by_transaction.user1 == u1 and existing_by_transaction.user2 == u2) or
                    (existing_by_transaction.user1 == u2 and existing_by_transaction.user2 == u1)):
                    existing = existing_by_transaction
                else:
                    # Transaction ID matches but users don't - this shouldn't happen, but use it anyway
                    # since transaction_id is the primary identifier
                    existing = existing_by_transaction
            else:
                # For P2P transactions, transaction_id won't be set in the ForeignKey field
                # So we need to check conversations between these users and look for messages with this transaction_id
                if is_p2p_transaction:
                    from .models import Message
                    potential_conversations = Conversation.objects.filter(
                        (Q(user1=u1) & Q(user2=u2)) | (Q(user1=u2) & Q(user2=u1)),
                        transaction=None,
                        listing=None
                    )
                    
                    for conv in potential_conversations:
                        # Check if any message in this conversation has our transaction_id in metadata
                        if Message.objects.filter(
                            conversation=conv,
                            metadata__transaction_id=transaction_id
                        ).exists():
                            existing = conv
                            break
                    if 'existing' not in locals():
                        existing = None
                else:
                    existing = None
        else:
            # For listings, check both user orderings
            existing = Conversation.objects.filter(
                (Q(user1=u1) & Q(user2=u2)) | (Q(user1=u2) & Q(user2=u1)),
                listing=listing,
                transaction=transaction
            ).first()

        if existing:
            # Don't raise error, just return existing conversation data
            # The view will handle returning the existing conversation
            pass

        attrs['user1'] = u1
        attrs['user2'] = u2
        attrs['existing_conversation'] = existing  # Pass existing to view
        attrs['transaction_id'] = transaction_id  # Store transaction_id for lookup
        attrs['is_p2p_transaction'] = is_p2p_transaction if transaction_id else False
        if listing_id:
            attrs['listing'] = listing
        if transaction_id:
            # Store transaction object if it's a GiftCardTransaction (for Conversation model compatibility)
            # For P2PServiceTransaction, we'll handle it in the view
            if transaction_obj and not is_p2p_transaction:
                attrs['transaction'] = transaction_obj
            elif transaction_obj and is_p2p_transaction:
                # For P2P transactions, we can't assign to Conversation.transaction directly
                # The view will need to handle this differently
                attrs['p2p_transaction'] = transaction_obj
                attrs['transaction'] = None  # Will be None for P2P transactions

        return attrs


class MessageReportSerializer(serializers.ModelSerializer):
    """Serializer for message reports"""
    reported_by_email = serializers.EmailField(source='reported_by.email', read_only=True)
    message_content = serializers.CharField(source='message.content', read_only=True)

    class Meta:
        model = MessageReport
        fields = [
            'id', 'message', 'message_content', 'reported_by', 'reported_by_email',
            'reason', 'created_at', 'reviewed', 'reviewed_by', 'reviewed_at', 'admin_notes'
        ]
        read_only_fields = ['created_at', 'reviewed', 'reviewed_by', 'reviewed_at']

