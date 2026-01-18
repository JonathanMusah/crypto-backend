"""
Management command to unarchive conversations but keep them locked
This allows users to view conversation history but prevents new messages
"""
from django.core.management.base import BaseCommand
from messaging.models import Conversation

# Try to import P2P service transaction
try:
    from orders.p2p_models import P2PServiceTransaction
except ImportError:
    P2PServiceTransaction = None


class Command(BaseCommand):
    help = 'Unarchive conversations for completed transactions but keep them locked'

    def add_arguments(self, parser):
        parser.add_argument('--reference', type=str, help='Transaction reference (e.g., PPT-61F2BDCABC7A)')
        parser.add_argument('--all-completed', action='store_true', help='Unarchive all completed P2P transactions')

    def handle(self, *args, **options):
        if options.get('reference') and P2PServiceTransaction:
            transaction = P2PServiceTransaction.objects.filter(reference=options['reference']).first()
            if not transaction:
                self.stdout.write(self.style.ERROR(f'Transaction {options["reference"]} not found'))
                return
            
            # Find conversations by users
            conversations = Conversation.objects.filter(
                user1__in=[transaction.buyer, transaction.seller],
                user2__in=[transaction.buyer, transaction.seller]
            ).filter(is_locked=True)
            
            self.unarchive_conversations(conversations, transaction)
            
        elif options.get('all_completed') and P2PServiceTransaction:
            # Find all completed P2P transactions
            completed_transactions = P2PServiceTransaction.objects.filter(status='completed')
            
            for transaction in completed_transactions:
                conversations = Conversation.objects.filter(
                    user1__in=[transaction.buyer, transaction.seller],
                    user2__in=[transaction.buyer, transaction.seller]
                ).filter(is_locked=True)
                
                self.unarchive_conversations(conversations, transaction)
        else:
            self.stdout.write(self.style.ERROR('Please provide either --reference or --all-completed'))

    def unarchive_conversations(self, conversations, transaction=None):
        unarchived_count = 0
        
        for conv in conversations:
            # Unarchive but keep locked
            conv.is_archived_user1 = False
            conv.is_archived_user2 = False
            conv.save(update_fields=['is_archived_user1', 'is_archived_user2'])
            
            unarchived_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Unarchived conversation {conv.id} (still locked) for transaction {transaction.reference if transaction else "N/A"}'
                )
            )
        
        if unarchived_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\nUnarchived {unarchived_count} conversation(s) (kept locked)')
            )
        else:
            self.stdout.write(self.style.WARNING('No locked conversations found to unarchive'))

