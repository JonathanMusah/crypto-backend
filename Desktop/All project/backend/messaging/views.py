"""
API views for messaging system
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q, Count
from django_ratelimit.decorators import ratelimit
from django.core.cache import cache
import logging
import sys

from .models import Conversation, Message, MessageReport
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    ConversationCreateSerializer,
    MessageReportSerializer
)
from .scam_detection import analyze_message
from notifications.utils import create_notification

logger = logging.getLogger(__name__)


class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversations
    """
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return conversations for the current user"""
        user = self.request.user
        queryset = Conversation.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).select_related('user1', 'user2', 'listing', 'listing__card', 'transaction').prefetch_related('messages')
        
        # Refresh user objects to get latest last_seen values for status calculation
        # This ensures we have fresh data when calculating online status

        # Filter archived conversations
        archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        if archived:
            # When viewing archived, only show conversations where user has archived them
            queryset = queryset.filter(
                Q(user1=user, is_archived_user1=True) |
                Q(user2=user, is_archived_user2=True)
            )
        else:
            # When viewing non-archived, exclude conversations where user has archived them
            queryset = queryset.filter(
                Q(user1=user, is_archived_user1=False) |
                Q(user2=user, is_archived_user2=False)
            )

        # Log query for debugging
        logger.info(f"Fetching conversations for user {user.email}. Archived={archived}. "
                   f"Total conversations found: {queryset.count()}")

        return queryset.order_by('-last_message_at', '-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def list(self, request, *args, **kwargs):
        """List conversations with error handling"""
        try:
            # Update user's last_seen when they fetch conversations (they're active)
            if request.user.is_authenticated:
                request.user.last_seen = timezone.now()
                request.user.save(update_fields=['last_seen'])
                
                # Clear cache to allow immediate updates
                from django.core.cache import cache
                cache_key = f'last_seen_update_{request.user.id}'
                cache.delete(cache_key)
            
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to load conversations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def start(self, request):
        """Start a new conversation"""
        try:
            serializer = ConversationCreateSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                user1 = serializer.validated_data['user1']
                user2 = serializer.validated_data['user2']
                listing = serializer.validated_data.get('listing')
                transaction = serializer.validated_data.get('transaction')
                p2p_transaction = serializer.validated_data.get('p2p_transaction')
                transaction_id = serializer.validated_data.get('transaction_id')
                existing = serializer.validated_data.get('existing_conversation')

                # Log for debugging
                logger.info(f"[CONVERSATION START] User: {request.user.email}, transaction_id: {transaction_id}, existing: {existing.id if existing else None}")

                # If conversation already exists, return it (even if archived)
                # BUT don't unarchive if the transaction is completed/cancelled/disputed
                if existing:
                    logger.info(f"[CONVERSATION START] Found existing conversation {existing.id}")
                    
                    # Check if conversation is linked to a completed/cancelled transaction
                    should_stay_archived = False
                    if existing.transaction:
                        # GiftCard transaction
                        if existing.transaction.status in ['completed', 'cancelled', 'disputed']:
                            should_stay_archived = True
                    elif transaction_id:
                        # Check if it's a P2P transaction
                        try:
                            from orders.p2p_models import P2PServiceTransaction
                            p2p_txn = P2PServiceTransaction.objects.filter(id=transaction_id).first()
                            if p2p_txn and p2p_txn.status in ['completed', 'cancelled', 'disputed']:
                                should_stay_archived = True
                        except:
                            pass
                    
                    # Only unarchive if transaction is NOT completed/cancelled/disputed
                    if not should_stay_archived and (existing.is_archived_user1 or existing.is_archived_user2):
                        logger.info(f"[CONVERSATION START] Unarchiving conversation {existing.id}")
                        if user1 == existing.user1:
                            existing.is_archived_user1 = False
                        if user2 == existing.user2:
                            existing.is_archived_user2 = False
                        existing.save(update_fields=['is_archived_user1', 'is_archived_user2'])
                    elif should_stay_archived:
                        logger.info(f"[CONVERSATION START] Conversation {existing.id} linked to completed/cancelled transaction, keeping archived")
                    
                    return Response(
                        ConversationSerializer(existing, context={'request': request}).data,
                        status=status.HTTP_200_OK
                    )

                # Create conversation (user1 and user2 are already ordered by serializer)
                # Ensure conversations are not archived by default
                # For P2P transactions, check if conversation already exists by looking at message metadata
                logger.info(f"[CONVERSATION START] Creating new conversation for transaction_id: {transaction_id}")
                
                # For P2P transactions, check if a conversation already exists for this transaction
                # by looking for conversations between these users with messages containing this transaction_id
                conversation = None
                if p2p_transaction and transaction_id:
                    from .models import Message
                    existing_conversations = Conversation.objects.filter(
                        user1=user1,
                        user2=user2,
                        transaction=None,
                        listing=None
                    )
                    
                    for conv in existing_conversations:
                        # Check if any message in this conversation has our transaction_id in metadata
                        if Message.objects.filter(
                            conversation=conv,
                            metadata__transaction_id=transaction_id
                        ).exists():
                            conversation = conv
                            logger.info(f"[CONVERSATION START] Found existing conversation {conversation.id} for P2P transaction_id={transaction_id}")
                            
                            # Check if transaction is completed/cancelled/disputed - if so, keep archived
                            should_stay_archived = False
                            if p2p_transaction and p2p_transaction.status in ['completed', 'cancelled', 'disputed']:
                                should_stay_archived = True
                            
                            # Only unarchive if transaction is NOT completed/cancelled/disputed
                            if not should_stay_archived and (conversation.is_archived_user1 or conversation.is_archived_user2):
                                logger.info(f"[CONVERSATION START] Unarchiving conversation {conversation.id}")
                                if user1 == conversation.user1:
                                    conversation.is_archived_user1 = False
                                if user2 == conversation.user2:
                                    conversation.is_archived_user2 = False
                                conversation.save(update_fields=['is_archived_user1', 'is_archived_user2'])
                            elif should_stay_archived:
                                logger.info(f"[CONVERSATION START] Conversation {conversation.id} linked to completed/cancelled P2P transaction, keeping archived")
                            
                            # Return existing conversation - don't create "Chat started" message
                            return Response(
                                ConversationSerializer(conversation, context={'request': request}).data,
                                status=status.HTTP_200_OK
                            )
                
                # If no existing conversation found, create a new one
                if not conversation:
                    conversation = Conversation.objects.create(
                        user1=user1,
                        user2=user2,
                        listing=listing,
                        transaction=transaction,  # Will be None for P2P transactions
                        is_archived_user1=False,  # Explicitly set to False
                        is_archived_user2=False   # Explicitly set to False
                    )
                    logger.info(f"[CONVERSATION START] Created new conversation {conversation.id} for transaction_id={transaction_id}")

                    # Only create "Chat started" message for NEW conversations
                    # BUT first check if there are already transaction-related messages (payment details, escrow, etc.)
                    # This prevents redundant "Chat started" messages if conversation was created earlier with transaction messages
                    from .models import Message
                    has_txn_messages = Message.objects.filter(
                        conversation=conversation
                    ).filter(
                        Q(content__icontains='Payment Details') |
                        Q(content__icontains='Escrow started') |
                        Q(metadata__system_action__in=['payment_details_sent', 'escrow_started', 'buyer_marked_paid', 'seller_confirmed_payment'])
                    ).exists()
                    
                    if not has_txn_messages:
                        # No transaction messages exist yet, safe to create "Chat started"
                        message_content = "Conversation started"
                        if p2p_transaction:
                            message_content = f"Chat started for transaction {p2p_transaction.reference}"
                        elif transaction:
                            message_content = f"Chat started for transaction {transaction.reference}"
                        elif listing:
                            message_content = f"Chat started for listing {listing.reference}"

                        # Create system message (use user1 as sender for system messages since sender is required)
                        Message.objects.create(
                            conversation=conversation,
                            sender=user1,  # System messages use first user as sender (required field)
                            content=message_content,
                            message_type='system',
                            metadata={'system_action': 'conversation_started'}
                        )
                    else:
                        logger.info(f"[CONVERSATION START] Conversation {conversation.id} already has transaction messages, skipping 'Chat started' message")
                else:
                    # Conversation already exists, don't create "Chat started" message
                    logger.info(f"[CONVERSATION START] Conversation {conversation.id} already exists, skipping 'Chat started' message")

                # Update last_message_at
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=['last_message_at'])

                return Response(
                    ConversationSerializer(conversation, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            logger.error(f"Error starting conversation: {str(e)}", exc_info=True)
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'Failed to start conversation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive/unarchive conversation"""
        # For archive action, we need to access conversations regardless of archive status
        # So we get the conversation directly without using get_queryset() which filters archived ones
        user = request.user
        try:
            conversation = Conversation.objects.filter(
                pk=pk
            ).filter(
                Q(user1=user) | Q(user2=user)
            ).first()
            
            if not conversation:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            logger.error(f"Error fetching conversation for archive: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if conversation is linked to a completed/cancelled transaction
        # If so, prevent unarchiving (users can only archive, not unarchive)
        should_stay_archived = False
        if conversation.transaction:
            # GiftCard transaction
            if conversation.transaction.status in ['completed', 'cancelled', 'disputed']:
                should_stay_archived = True
        else:
            # Check if it's a P2P transaction by looking at message metadata
            from .models import Message
            p2p_messages = Message.objects.filter(
                conversation=conversation,
                metadata__transaction_id__isnull=False
            ).values_list('metadata__transaction_id', flat=True).distinct()
            
            if p2p_messages:
                try:
                    from orders.p2p_models import P2PServiceTransaction
                    for txn_id in p2p_messages:
                        try:
                            p2p_txn = P2PServiceTransaction.objects.get(id=txn_id)
                            if p2p_txn.status in ['completed', 'cancelled', 'disputed']:
                                should_stay_archived = True
                                break
                        except:
                            pass
                except:
                    pass

        # Determine if user wants to archive or unarchive
        if user == conversation.user1:
            current_archived = conversation.is_archived_user1
            wants_to_unarchive = current_archived and not should_stay_archived
            if wants_to_unarchive:
                conversation.is_archived_user1 = False
                conversation.save(update_fields=['is_archived_user1'])
            elif not current_archived:
                conversation.is_archived_user1 = True
                conversation.save(update_fields=['is_archived_user1'])
            elif should_stay_archived and current_archived:
                # User trying to unarchive a completed transaction - not allowed
                return Response(
                    {'error': 'Cannot unarchive conversation for completed/cancelled transaction'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif user == conversation.user2:
            current_archived = conversation.is_archived_user2
            wants_to_unarchive = current_archived and not should_stay_archived
            if wants_to_unarchive:
                conversation.is_archived_user2 = False
                conversation.save(update_fields=['is_archived_user2'])
            elif not current_archived:
                conversation.is_archived_user2 = True
                conversation.save(update_fields=['is_archived_user2'])
            elif should_stay_archived and current_archived:
                # User trying to unarchive a completed transaction - not allowed
                return Response(
                    {'error': 'Cannot unarchive conversation for completed/cancelled transaction'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'error': 'You are not part of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'message': 'Conversation archived' if (conversation.is_archived_user1 or conversation.is_archived_user2) else 'Conversation unarchived',
            'data': ConversationSerializer(conversation, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def lock(self, request, pk=None):
        """Lock conversation (admin only) - also archives automatically"""
        conversation = self.get_object()
        reason = request.data.get('reason', '')

        conversation.is_locked = True
        conversation.locked_by = request.user
        conversation.locked_reason = reason
        # Auto-archive when locked
        conversation.is_archived_user1 = True
        conversation.is_archived_user2 = True
        conversation.save()

        # Create system message
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=f"Conversation locked by admin. Reason: {reason}",
            message_type='system',
            metadata={'system_action': 'conversation_locked', 'admin_id': request.user.id}
        )

        return Response({
            'message': 'Conversation locked and archived',
            'data': ConversationSerializer(conversation, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def unlock(self, request, pk=None):
        """Unlock conversation (admin only)"""
        conversation = self.get_object()

        conversation.is_locked = False
        conversation.locked_by = None
        conversation.locked_reason = ''
        conversation.save()

        # Create system message
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content="Conversation unlocked by admin",
            message_type='system',
            metadata={'system_action': 'conversation_unlocked', 'admin_id': request.user.id}
        )

        return Response({
            'message': 'Conversation unlocked',
            'data': ConversationSerializer(conversation, context={'request': request}).data
        })


class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing messages
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to log send requests"""
        if 'send' in request.path or request.path.endswith('/send/'):
            logger.info(f"Message send request: {request.method} {request.path} by user {request.user.id if request.user.is_authenticated else 'ANONYMOUS'}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Return messages for conversations the user is part of"""
        user = self.request.user
        conversation_id = self.request.query_params.get('conversation_id')
        search_query = self.request.query_params.get('search', '').strip()

        queryset = Message.objects.filter(
            conversation__user1=user
        ) | Message.objects.filter(
            conversation__user2=user
        )

        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)

        # Add search functionality
        if search_query:
            queryset = queryset.filter(
                Q(content__icontains=search_query) |
                Q(attachment_name__icontains=search_query)
            )

        return queryset.filter(is_deleted=False).select_related('sender', 'conversation', 'conversation__user1', 'conversation__user2').order_by('created_at')
    
    def list(self, request, *args, **kwargs):
        """List messages with error handling"""
        try:
            # Update current user's last_seen immediately when fetching messages
            # This marks them as active/online
            if request.user.is_authenticated:
                from django.core.cache import cache
                cache_key = f'last_seen_update_{request.user.id}'
                
                # Force immediate update (bypass cache throttling)
                request.user.last_seen = timezone.now()
                request.user.save(update_fields=['last_seen'])
                cache.set(cache_key, timezone.now(), 15)
            
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing messages: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to load messages: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # @ratelimit(key='user', rate='1/s', block=True)  # Temporarily disabled for debugging
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def send(self, request):
        """Send a new message. Auto-creates conversation if it doesn't exist."""
        # Log message send request
        logger.info(f"Message send: User {request.user.id} ({request.user.email if request.user.is_authenticated else 'N/A'}), Conversation: {request.data.get('conversation_id')}, Content length: {len(request.data.get('content', ''))}")
        
        try:
            serializer = MessageCreateSerializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            conversation_id = serializer.validated_data.get('conversation_id')
            content = serializer.validated_data.get('content', '') or ''
            # Optional: allow creating conversation on the fly
            user2_id = serializer.validated_data.get('user2_id')
            listing_id = serializer.validated_data.get('listing_id')
            transaction_id = serializer.validated_data.get('transaction_id')

            conversation = None
            
            # If conversation_id provided, try to get it
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                except Conversation.DoesNotExist:
                    # Conversation doesn't exist, but we might be able to create it
                    if not user2_id and not listing_id and not transaction_id:
                        return Response(
                            {'error': 'Conversation not found. Please provide user2_id, listing_id, or transaction_id to create a new conversation.'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    # Fall through to create conversation below
            
            # If no conversation and we have enough info, create it
            if not conversation and (user2_id or listing_id or transaction_id):
                try:
                    from .serializers import ConversationCreateSerializer as ConvCreateSerializer
                    conv_serializer = ConvCreateSerializer(
                        data={
                            'user2_id': user2_id,
                            'listing_id': listing_id,
                            'transaction_id': transaction_id
                        },
                        context={'request': request}
                    )
                    if conv_serializer.is_valid():
                        user1 = conv_serializer.validated_data['user1']
                        user2 = conv_serializer.validated_data['user2']
                        listing = conv_serializer.validated_data.get('listing')
                        transaction = conv_serializer.validated_data.get('transaction')
                        existing = conv_serializer.validated_data.get('existing_conversation')
                        
                        if existing:
                            conversation = existing
                        else:
                            # Ensure conversations are not archived by default
                            conversation = Conversation.objects.create(
                                user1=user1,
                                user2=user2,
                                listing=listing,
                                transaction=transaction,
                                is_archived_user1=False,  # Explicitly set to False
                                is_archived_user2=False   # Explicitly set to False
                            )
                            
                            # Generate conversation started message with order/transaction details
                            message_content = "Conversation started"
                            if transaction:
                                message_content = f"Chat started for transaction {transaction.reference}"
                            elif listing:
                                message_content = f"Chat started for listing {listing.reference}"
                            
                            # Create system message
                            Message.objects.create(
                                conversation=conversation,
                                sender=None,  # System message
                                content=message_content,
                                message_type='system',
                                metadata={'system_action': 'conversation_started'}
                            )
                            conversation.last_message_at = timezone.now()
                            conversation.save(update_fields=['last_message_at'])
                    else:
                        return Response(
                            {'error': f'Failed to create conversation: {conv_serializer.errors}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except Exception as e:
                    logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
                    return Response(
                        {'error': f'Failed to create conversation: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            # If still no conversation, return error
            if not conversation:
                return Response(
                    {'error': 'Conversation not found and could not be created. Please provide conversation_id or (user2_id, listing_id, or transaction_id).'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if user can send message
            if not conversation.can_user_send_message(request.user):
                return Response(
                    {'error': 'You cannot send messages in this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Analyze message content (only if content is provided)
            filtered_content = content
            has_forbidden = False
            has_scam = False
            risk_score = 0
            analysis = {
                'original_content': content,
                'scam_patterns': [],
                'forbidden_patterns': [],
            }
            
            if content and content.strip():
                try:
                    analysis = analyze_message(content)
                    filtered_content = analysis['filtered_content']
                    has_forbidden = analysis['has_forbidden']
                    has_scam = analysis['has_scam']
                    risk_score = analysis['risk_score']
                except Exception as e:
                    logger.error(f"Error analyzing message: {str(e)}", exc_info=True)
                    # Fallback to basic analysis
                    filtered_content = content
                    has_forbidden = False
                    has_scam = False
                    risk_score = 0
                    analysis = {
                        'original_content': content,
                        'scam_patterns': [],
                        'forbidden_patterns': [],
                    }

            # Handle file attachment
            attachment = serializer.validated_data.get('attachment')
            attachment_type = None
            attachment_name = None
            attachment_size = None
            
            if attachment:
                # Determine attachment type
                content_type = attachment.content_type
                if content_type.startswith('image/'):
                    attachment_type = 'image'
                    # Watermark images that users will see (to prevent fraud/scams)
                    try:
                        from orders.image_utils import process_uploaded_image
                        attachment.seek(0)
                        attachment = process_uploaded_image(attachment, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                    except Exception as e:
                        logger.warning(f"Failed to watermark message image: {str(e)}")
                        # Continue with original image if watermarking fails
                        attachment.seek(0)
                elif content_type.startswith('video/'):
                    attachment_type = 'video'
                elif content_type.startswith('audio/'):
                    attachment_type = 'audio'
                elif content_type in ['application/pdf', 'application/msword', 
                                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                     'text/plain', 'text/csv']:
                    attachment_type = 'document'
                else:
                    attachment_type = 'file'
                
                attachment_name = attachment.name
                attachment_size = attachment.size
            
            # Create message
            try:
                message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=filtered_content,
                    original_content=analysis.get('original_content', '') if has_forbidden else '',
                    message_type='text',
                    attachment=attachment,
                    attachment_type=attachment_type,
                    attachment_name=attachment_name,
                    attachment_size=attachment_size,
                    flagged=has_scam or has_forbidden,
                    flagged_reason='Scam pattern detected' if has_scam else 'Forbidden content detected' if has_forbidden else '',
                    scam_detected=has_scam,
                    scam_patterns=analysis.get('scam_patterns', []),
                    metadata={
                        'forbidden_patterns': analysis.get('forbidden_patterns', []),
                        'risk_score': risk_score,
                    }
                )
                logger.info(f"Message {message.id} created successfully in conversation {conversation.id} by user {request.user.id} with attachment: {bool(attachment)}")
            except Exception as e:
                print(f"[MESSAGE CREATE] ERROR: {str(e)}")
                sys.stdout.flush()
                logger.error(f"Error creating message: {str(e)}", exc_info=True)
                raise

            # Update conversation scam score
            if risk_score > 0:
                conversation.update_scam_score(risk_score)

            # Update conversation last_message_at
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=['last_message_at'])
            
            # Broadcast message via WebSocket
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                
                channel_layer = get_channel_layer()
                if channel_layer:
                    # Serialize message for WebSocket
                    serialized_message = MessageSerializer(message, context={'request': request}).data
                    
                    # Broadcast to conversation room
                    async_to_sync(channel_layer.group_send)(
                        f'messages_{conversation.id}',
                        {
                            'type': 'new_message',
                            'message': serialized_message
                        }
                    )
                    logger.info(f"Message {message.id} broadcasted via WebSocket to conversation {conversation.id}")
            except ImportError:
                # Channels not installed or configured - this is OK
                pass
            except Exception as e:
                # Don't fail message send if WebSocket fails
                # This is expected if running with runserver (which doesn't support WebSockets)
                # Only log at debug level to avoid noise
                logger.debug(f"WebSocket broadcast skipped: {str(e)}")
            
            # Log conversation details for debugging
            logger.info(f"Message sent in conversation {conversation.id} by user {request.user.email}. "
                       f"Conversation: user1={conversation.user1.email}, user2={conversation.user2.email}, "
                       f"listing={conversation.listing_id}, transaction={conversation.transaction_id}")

            # If forbidden content detected, create warning message
            if has_forbidden:
                try:
                    warning_message = Message.objects.create(
                        conversation=conversation,
                        sender=None,  # System message (null sender)
                        content="⚠️ Sharing external contact details is not allowed for your safety. Please complete all transactions through the platform.",
                        message_type='warning',
                        metadata={'system_action': 'forbidden_content_warning'}
                    )
                    conversation.last_message_at = timezone.now()
                    conversation.save(update_fields=['last_message_at'])
                except Exception as e:
                    logger.error(f"Failed to create forbidden content warning: {str(e)}")

            # If scam detected, create warning and notify admin
            if has_scam:
                try:
                    warning_message = Message.objects.create(
                        conversation=conversation,
                        sender=None,  # System message (null sender)
                        content="⚠️ This message looks unsafe. For your protection, complete all payments inside the platform. Never send money or codes outside escrow.",
                        message_type='warning',
                        metadata={'system_action': 'scam_warning', 'risk_score': risk_score}
                    )
                    conversation.last_message_at = timezone.now()
                    conversation.save(update_fields=['last_message_at'])
                except Exception as e:
                    logger.error(f"Failed to create scam warning: {str(e)}")

                # Notify admin
                try:
                    from notifications.utils import create_notification
                    create_notification(
                        user=None,
                        notification_type='SCAM_MESSAGE_DETECTED',
                        title='Scam Message Detected',
                        message=f'Scam pattern detected in conversation {conversation.id}. Risk score: {risk_score}',
                        related_object_type='conversation',
                        related_object_id=conversation.id,
                        is_admin_notification=True
                    )
                except Exception as e:
                    logger.error(f"Failed to create admin notification: {str(e)}")
                    # Don't fail the message send if notification fails

            # Notify other user (but NEVER notify the sender)
            try:
                # Refresh conversation from database to ensure we have latest data
                conversation.refresh_from_db()
                
                # Get IDs for comparison
                sender_id = request.user.id
                sender_email = request.user.email
                user1_id = conversation.user1.id if conversation.user1 else None
                user2_id = conversation.user2.id if conversation.user2 else None
                
                logger.info(f"[NOTIFICATION] Processing notification for conversation {conversation.id}: sender={sender_id}, user1={user1_id}, user2={user2_id}")
                logger.info(f"[NOTIFICATION] Sender: {sender_id} ({sender_email})")
                logger.info(f"[NOTIFICATION] Conversation {conversation.id}: user1={user1_id}, user2={user2_id}")
                
                # CRITICAL CHECK 1: Ensure sender is part of conversation
                if sender_id not in [user1_id, user2_id]:
                    logger.error(f"[NOTIFICATION] BLOCKED: Sender {sender_id} not in conversation {conversation.id}")
                # CRITICAL CHECK 2: Ensure conversation doesn't have duplicate users
                elif user1_id == user2_id:
                    logger.error(f"[NOTIFICATION] BLOCKED: Conversation {conversation.id} has duplicate users: {user1_id}")
                else:
                    # Determine other user using explicit ID comparison (most reliable)
                    if sender_id == user1_id:
                        other_user = conversation.user2
                        logger.info(f"[NOTIFICATION] Sender is user1 ({user1_id}), other_user is user2 ({conversation.user2.id if conversation.user2 else None})")
                    elif sender_id == user2_id:
                        other_user = conversation.user1
                        logger.info(f"[NOTIFICATION] Sender is user2 ({user2_id}), other_user is user1 ({conversation.user1.id if conversation.user1 else None})")
                    else:
                        other_user = None
                        logger.error(f"[NOTIFICATION] ERROR: Could not determine other user for conversation {conversation.id}")
                    
                    # Validate other_user exists and is not the sender
                    if not other_user:
                        logger.error(f"[NOTIFICATION] BLOCKED: other_user is None")
                    elif other_user.id == sender_id:
                        logger.error(f"[NOTIFICATION] BLOCKED: Attempted to notify sender (user {sender_id})")
                        print(f"[NOTIFICATION] CRITICAL: other_user.id ({other_user.id}) == sender_id ({sender_id}) - BLOCKING!")
                    else:
                        # All checks passed - create notification
                        logger.info(f"[NOTIFICATION] ✓ All checks passed. Creating notification for user {other_user.id} ({other_user.email}), sender is {sender_id} ({sender_email})")
                        print(f"[NOTIFICATION] Creating notification - Recipient: {other_user.id} ({other_user.email}), Sender: {sender_id} ({sender_email})")
                        
                        from notifications.utils import create_notification
                        result = create_notification(
                            user=other_user,
                            notification_type='NEW_MESSAGE',
                            title='New Message',
                            message=f'You have a new message from {request.user.get_full_name() or request.user.email}',
                            related_object_type='conversation',
                            related_object_id=conversation.id,
                            sender_user=request.user,  # Pass sender to prevent self-notification
                        )
                        
                        if result:
                            logger.info(f"[NOTIFICATION] Notification created: ID {result.id} for user {result.user.id} ({result.user.email})")
                            print(f"[NOTIFICATION] ✓ Notification created: ID {result.id} for user {result.user.id} ({result.user.email})")
                        else:
                            logger.warning(f"[NOTIFICATION] Notification blocked by create_notification()")
                            print(f"[NOTIFICATION] ⚠ Notification was blocked by create_notification()")
            except Exception as e:
                logger.error(f"[NOTIFICATION] EXCEPTION: {str(e)}", exc_info=True)
                # Don't fail the message send if notification fails

            # Serialize and return the message
            try:
                # Refresh from database to ensure we have latest data
                message.refresh_from_db()
                
                serialized_message = MessageSerializer(message, context={'request': request}).data
                logger.info(f"Message {message.id} successfully serialized and returned")
                return Response(
                    serialized_message,
                    status=status.HTTP_201_CREATED
                )
            except Exception as serialization_error:
                logger.error(f"Error serializing message: {str(serialization_error)}", exc_info=True)
                # Return basic message data if serialization fails
                try:
                    return Response(
                        {
                            'id': message.id,
                            'conversation': message.conversation.id,
                            'sender': message.sender.id if message.sender else None,
                            'sender_email': message.sender.email if message.sender else None,
                            'sender_name': (message.sender.get_full_name() or message.sender.email) if message.sender else 'System',
                            'content': message.content,
                            'message_type': message.message_type,
                            'created_at': message.created_at.isoformat(),
                        },
                        status=status.HTTP_201_CREATED
                    )
                except Exception as fallback_error:
                    logger.error(f"Error in fallback response: {str(fallback_error)}", exc_info=True)
                    return Response(
                        {'error': f'Failed to serialize message: {str(serialization_error)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': f'An error occurred while sending the message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read"""
        message = self.get_object()

        # Only mark as read if user is not the sender
        if message.sender != request.user:
            message.mark_as_read(request.user)

        return Response({
            'message': 'Message marked as read',
            'data': MessageSerializer(message, context={'request': request}).data
        })

    @action(detail=True, methods=['patch', 'put'])
    def edit(self, request, pk=None):
        """Edit a message (only by sender, within time limit, with scam detection)"""
        message = self.get_object()
        
        # Only sender can edit
        if message.sender != request.user:
            return Response(
                {'error': 'You can only edit your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Can't edit system messages
        if message.message_type in ['system', 'warning']:
            return Response(
                {'error': 'System messages cannot be edited'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Can't edit deleted messages
        if message.is_deleted:
            return Response(
                {'error': 'Deleted messages cannot be edited'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Time limit: can only edit within 15 minutes of sending
        from django.utils import timezone
        time_since_creation = timezone.now() - message.created_at
        if time_since_creation.total_seconds() > 15 * 60:  # 15 minutes
            return Response(
                {'error': 'Messages can only be edited within 15 minutes of sending'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new content
        new_content = request.data.get('content', '').strip()
        if not new_content:
            return Response(
                {'error': 'Message content cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_content) > 5000:
            return Response(
                {'error': 'Message is too long (max 5000 characters)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CRITICAL: Re-analyze edited content for scams and forbidden patterns
        # Import is already at top: from .scam_detection import analyze_message
        analysis = analyze_message(new_content)
        has_scam = analysis.get('has_scam', False)
        has_forbidden = analysis.get('has_forbidden', False)
        risk_score = analysis.get('risk_score', 0)
        filtered_content = analysis.get('filtered_content', new_content)
        
        # If scam detected in edited content, block the edit
        if has_scam:
            logger.warning(f"Edit blocked: Scam detected in edited message {message.id} by user {request.user.id}")
            return Response(
                {'error': 'This message contains suspicious content and cannot be edited. Please contact support if you believe this is an error.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If forbidden content detected, block the edit
        if has_forbidden:
            logger.warning(f"Edit blocked: Forbidden content in edited message {message.id} by user {request.user.id}")
            return Response(
                {'error': 'This message contains prohibited content and cannot be edited.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store original content before edit for audit trail
        original_content_before_edit = message.content
        
        # Update message with filtered content
        message.content = filtered_content
        message.original_content = original_content_before_edit  # Keep original for audit
        message.is_edited = True
        message.edited_at = timezone.now()
        
        # Update scam detection flags (even if no scam, update metadata)
        message.flagged = has_scam or has_forbidden
        message.scam_detected = has_scam
        message.scam_patterns = analysis.get('scam_patterns', [])
        message.metadata = {
            **message.metadata,
            'edit_history': message.metadata.get('edit_history', []) + [{
                'edited_at': timezone.now().isoformat(),
                'original_content': original_content_before_edit,
                'new_content': filtered_content,
                'edited_by': request.user.id,
            }],
            'forbidden_patterns': analysis.get('forbidden_patterns', []),
            'risk_score': risk_score,
        }
        
        message.save()
        
        # Log edit for security audit
        logger.info(f"Message {message.id} edited by user {request.user.id}. Original: '{original_content_before_edit[:50]}...', New: '{filtered_content[:50]}...'")
        
        # If risk score increased, update conversation scam score
        if risk_score > 0:
            message.conversation.update_scam_score(risk_score)
        
        # Broadcast update via WebSocket
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if channel_layer:
                serialized_message = MessageSerializer(message, context={'request': request}).data
                async_to_sync(channel_layer.group_send)(
                    f'messages_{message.conversation.id}',
                    {
                        'type': 'message_updated',
                        'message': serialized_message
                    }
                )
        except Exception:
            pass  # WebSocket not critical for edit
        
        return Response({
            'message': 'Message updated successfully',
            'data': MessageSerializer(message, context={'request': request}).data
        })
    
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None):
        """Delete a message - DISABLED for security and audit purposes"""
        # Message deletion is disabled to prevent:
        # 1. Scammers from deleting evidence
        # 2. Loss of important transaction records
        # 3. Audit trail issues
        
        return Response(
            {'error': 'Message deletion is disabled for security and audit purposes. Messages are permanently stored for transaction records and fraud prevention.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Report a message"""
        message = self.get_object()
        reason = request.data.get('reason', '')

        if not reason:
            return Response(
                {'error': 'Reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already reported by this user
        existing_report = MessageReport.objects.filter(
            message=message,
            reported_by=request.user
        ).first()

        if existing_report:
            return Response(
                {'error': 'You have already reported this message'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create report
        report = MessageReport.objects.create(
            message=message,
            reported_by=request.user,
            reason=reason
        )

        # Notify admin
        create_notification(
            user=None,
            notification_type='MESSAGE_REPORTED',
            title='Message Reported',
            message=f'Message {message.id} reported by {request.user.email}. Reason: {reason}',
            related_object_type='message',
            related_object_id=message.id,
            is_admin_notification=True
        )

        return Response({
            'message': 'Message reported successfully',
            'data': MessageReportSerializer(report, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class MessageReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing message reports (admin only)
    """
    serializer_class = MessageReportSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """Return all message reports"""
        return MessageReport.objects.select_related(
            'message', 'reported_by', 'reviewed_by'
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Review a message report (admin only)"""
        report = self.get_object()
        admin_notes = request.data.get('admin_notes', '')

        report.reviewed = True
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.admin_notes = admin_notes
        report.save()

        return Response({
            'message': 'Report reviewed',
            'data': MessageReportSerializer(report, context={'request': request}).data
        })

