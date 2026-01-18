"""
Management command to lock conversations for completed P2P service transactions
This fixes conversations that were completed before the signal handler was added
"""
from django.core.management.base import BaseCommand
from messaging.models import Conversation, Message

# Try to import P2P service transaction
try:
    from orders.p2p_models import P2PServiceTransaction
except ImportError:
    P2PServiceTransaction = None


class Command(BaseCommand):
    help = 'Lock conversations for completed P2P service transactions'

    def handle(self, *args, **options):
        if not P2PServiceTransaction:
            self.stdout.write(self.style.WARNING('P2PServiceTransaction model not found'))
            return
        
        # Find all completed P2P transactions
        completed_transactions = P2PServiceTransaction.objects.filter(status='completed')
        
        self.stdout.write(f'Found {completed_transactions.count()} completed P2P transactions')
        
        locked_count = 0
        not_found_count = 0
        
        for transaction in completed_transactions:
            # Find conversation by transaction_id (works for both GiftCard and P2P)
            conversation = Conversation.objects.filter(transaction_id=transaction.id).first()
            
            if not conversation:
                not_found_count += 1
                self.stdout.write(
                    self.style.WARNING(f'No conversation found for transaction {transaction.reference} (ID: {transaction.id})')
                )
                continue
            
            # Check if already locked
            if conversation.is_locked:
                self.stdout.write(
                    self.style.SUCCESS(f'Conversation {conversation.id} for transaction {transaction.reference} is already locked')
                )
                continue
            
            # Lock and archive the conversation
            conversation.is_locked = True
            conversation.is_archived_user1 = True
            conversation.is_archived_user2 = True
            conversation.save(update_fields=['is_locked', 'is_archived_user1', 'is_archived_user2'])
            
            # Create system message if it doesn't exist
            Message.objects.get_or_create(
                conversation=conversation,
                sender=transaction.seller,
                content="✅ Transaction completed. Escrow released to seller. Conversation has been archived.",
                message_type='system',
                defaults={
                    'metadata': {'system_action': 'transaction_completed', 'transaction_id': transaction.id}
                }
            )
            
            locked_count += 1
            self.stdout.write(
                self.style.SUCCESS(f'Locked conversation {conversation.id} for transaction {transaction.reference}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary:\n'
                f'  - Locked: {locked_count}\n'
                f'  - Already locked: {completed_transactions.count() - locked_count - not_found_count}\n'
                f'  - Not found: {not_found_count}'
            )
        )

