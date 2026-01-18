"""
Management command to lock a specific conversation for a P2P transaction
"""
from django.core.management.base import BaseCommand
from messaging.models import Conversation, Message

# Try to import P2P service transaction
try:
    from orders.p2p_models import P2PServiceTransaction
except ImportError:
    P2PServiceTransaction = None


class Command(BaseCommand):
    help = 'Lock conversation for a specific P2P transaction by reference'

    def add_arguments(self, parser):
        parser.add_argument('--reference', type=str, help='Transaction reference (e.g., PPT-61F2BDCABC7A)')
        parser.add_argument('--conversation-id', type=int, help='Conversation ID to lock directly')

    def handle(self, *args, **options):
        if options.get('conversation_id'):
            # Lock specific conversation
            try:
                conversation = Conversation.objects.get(id=options['conversation_id'])
                self.lock_conversation(conversation)
            except Conversation.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Conversation {options["conversation_id"]} not found'))
        elif options.get('reference') and P2PServiceTransaction:
            # Find by transaction reference
            transaction = P2PServiceTransaction.objects.filter(reference=options['reference']).first()
            if not transaction:
                self.stdout.write(self.style.ERROR(f'Transaction {options["reference"]} not found'))
                return
            
            self.stdout.write(f'Transaction: {transaction.reference} (ID: {transaction.id})')
            self.stdout.write(f'Buyer: {transaction.buyer.email} (ID: {transaction.buyer.id})')
            self.stdout.write(f'Seller: {transaction.seller.email} (ID: {transaction.seller.id})')
            
            # Find conversation by users
            conversations = Conversation.objects.filter(
                user1__in=[transaction.buyer, transaction.seller],
                user2__in=[transaction.buyer, transaction.seller]
            )
            
            self.stdout.write(f'\nFound {conversations.count()} conversations between these users:')
            for conv in conversations:
                self.stdout.write(f'  Conversation {conv.id}: user1={conv.user1.email}, user2={conv.user2.email}, transaction_id={conv.transaction_id}, is_locked={conv.is_locked}')
            
            # Lock the conversation(s)
            for conv in conversations:
                self.lock_conversation(conv, transaction)
        else:
            self.stdout.write(self.style.ERROR('Please provide either --reference or --conversation-id'))

    def lock_conversation(self, conversation, transaction=None):
        if conversation.is_locked:
            self.stdout.write(self.style.WARNING(f'Conversation {conversation.id} is already locked'))
            return
        
        # Lock and archive
        conversation.is_locked = True
        conversation.is_archived_user1 = True
        conversation.is_archived_user2 = True
        conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
        
        # Update transaction_id if transaction provided
        if transaction:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE conversations SET transaction_id = %s WHERE id = %s",
                    [transaction.id, conversation.id]
                )
            conversation.refresh_from_db()
        
        # Create system message
        sender = transaction.seller if transaction else conversation.user1
        Message.objects.get_or_create(
            conversation=conversation,
            sender=sender,
            content="✅ Transaction completed. Escrow released to seller. Conversation has been archived." if transaction else "Conversation locked.",
            message_type='system',
            defaults={
                'metadata': {'system_action': 'transaction_completed', 'transaction_id': transaction.id if transaction else None}
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'Locked conversation {conversation.id}'))

