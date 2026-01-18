"""
Signals for messaging system
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Message, Conversation
from orders.models import GiftCardTransaction

# Try to import P2P service transaction (may not exist in all environments)
try:
    from orders.p2p_models import P2PServiceTransaction
except ImportError:
    P2PServiceTransaction = None


@receiver(post_save, sender=GiftCardTransaction)
def create_escrow_system_messages(sender, instance, created, **kwargs):
    """
    Create system messages when transaction status changes
    """
    if not created:
        # Transaction status changed
        conversation = Conversation.objects.filter(transaction=instance).first()
        if not conversation:
            return

        # Create system messages based on status
        # Use seller as sender for system messages (they're system-generated)
        if instance.status == 'payment_received':
            Message.objects.get_or_create(
                conversation=conversation,
                sender=instance.seller,  # System message sender
                content="💰 Escrow started. Payment received and locked.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'escrow_started', 'transaction_id': instance.id}
                }
            )
        elif instance.status == 'card_provided':
            Message.objects.get_or_create(
                conversation=conversation,
                sender=instance.seller,  # System message sender
                content="📦 Seller submitted gift card details.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'card_provided', 'transaction_id': instance.id}
                }
            )
        elif instance.status == 'completed':
            Message.objects.get_or_create(
                conversation=conversation,
                sender=instance.seller,  # System message sender
                content="✅ Transaction completed. Escrow released to seller. Conversation has been archived.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'transaction_completed', 'transaction_id': instance.id}
                }
            )
            # Lock and archive conversation after completion
            conversation.is_locked = True
            conversation.is_archived_user1 = True
            conversation.is_archived_user2 = True
            conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
        elif instance.status == 'disputed':
            Message.objects.get_or_create(
                conversation=conversation,
                sender=instance.seller,  # System message sender
                content="⚠️ Transaction disputed. Conversation locked for admin review.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'transaction_disputed', 'transaction_id': instance.id}
                }
            )
            # Lock and archive conversation during dispute
            conversation.is_locked = True
            conversation.is_archived_user1 = True
            conversation.is_archived_user2 = True
            conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
        elif instance.status == 'cancelled':
            Message.objects.get_or_create(
                conversation=conversation,
                sender=instance.seller,  # System message sender
                content="❌ Transaction cancelled. Conversation locked.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'transaction_cancelled', 'transaction_id': instance.id}
                }
            )
            # Lock and archive conversation after cancellation
            conversation.is_locked = True
            conversation.is_archived_user1 = True
            conversation.is_archived_user2 = True
            conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])


@receiver(post_save, sender=P2PServiceTransaction)
def create_p2p_escrow_system_messages(sender, instance, created, **kwargs):
    """
    Create system messages and manage conversation lock/archive status when P2P transaction status changes
    """
    if not P2PServiceTransaction:
        return
    
    # Only process status changes (not creation)
    if created:
        return
        
    # Transaction status changed
    # Find conversation by transaction_id
    # For P2P transactions, conversation.transaction is None (FK points to GiftCardTransaction only)
    # However, some old conversations might have transaction_id set directly (before the fix)
    # So we check both: conversations with transaction_id set, AND conversations with transaction=None that have messages with transaction_id in metadata
    from django.db import connection
    conversation = None
    
    # First, try to find by transaction_id using raw SQL (works for old conversations that have it set)
    # This will work even though the ForeignKey points to GiftCardTransaction - we're just checking the raw transaction_id value
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM conversations WHERE transaction_id = %s LIMIT 1",
            [instance.id]
        )
        result = cursor.fetchone()
        if result:
            conversation_id = result[0]
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                # Verify this conversation is actually for this transaction by checking users match
                u1, u2 = (instance.buyer, instance.seller) if instance.buyer.id < instance.seller.id else (instance.seller, instance.buyer)
                if (conversation.user1 == u1 and conversation.user2 == u2) or (conversation.user1 == u2 and conversation.user2 == u1):
                    # Valid conversation found
                    pass
                else:
                    # Users don't match, this might be a false match (shouldn't happen but be safe)
                    conversation = None
            except Conversation.DoesNotExist:
                pass
    
    # If not found by transaction_id, find by users and check message metadata
    if not conversation:
        # Find conversations between buyer and seller
        u1, u2 = (instance.buyer, instance.seller) if instance.buyer.id < instance.seller.id else (instance.seller, instance.buyer)
        potential_conversations = Conversation.objects.filter(user1=u1, user2=u2, transaction=None)
        
        # Check message metadata for transaction_id
        for conv in potential_conversations:
            # Check if any message in this conversation has our transaction_id in metadata
            matching_message = Message.objects.filter(
                conversation=conv,
                metadata__transaction_id=instance.id
            ).first()
            if matching_message:
                conversation = conv
                break
    
    if not conversation:
        return

    # Create system messages based on status (Binance-style)
    if instance.status == 'buyer_marked_paid':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=None,
            content="✅ Buyer has marked payment as complete. Waiting for seller confirmation.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'buyer_marked_paid', 'transaction_id': instance.id}
            }
        )
    elif instance.status == 'seller_confirmed_payment':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=None,
            content="✅ Seller has confirmed payment receipt. Seller will provide service details within 15 minutes.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'seller_confirmed_payment', 'transaction_id': instance.id}
            }
        )
    elif instance.status == 'service_provided':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=None,
            content="📦 Seller has provided service details. Buyer has 15 minutes to verify.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'service_provided', 'transaction_id': instance.id}
            }
        )
    elif instance.status == 'completed':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=instance.seller,  # System message sender
            content="✅ Transaction completed. Escrow released to seller. Conversation has been archived.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'transaction_completed', 'transaction_id': instance.id}
            }
        )
        # Lock and archive conversation after completion
        conversation.is_locked = True
        conversation.is_archived_user1 = True
        conversation.is_archived_user2 = True
        conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
    elif instance.status == 'disputed':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=instance.seller,  # System message sender
            content="⚠️ Transaction disputed. Conversation locked for admin review and archived.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'transaction_disputed', 'transaction_id': instance.id}
            }
        )
        # Lock and archive conversation during dispute
        conversation.is_locked = True
        conversation.is_archived_user1 = True
        conversation.is_archived_user2 = True
        conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
    elif instance.status == 'cancelled':
        Message.objects.get_or_create(
            conversation=conversation,
            sender=instance.seller,  # System message sender
            content="❌ Transaction cancelled. Conversation locked and archived.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'transaction_cancelled', 'transaction_id': instance.id}
            }
        )
        # Lock and archive conversation after cancellation
        conversation.is_locked = True
        conversation.is_archived_user1 = True
        conversation.is_archived_user2 = True
        conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
