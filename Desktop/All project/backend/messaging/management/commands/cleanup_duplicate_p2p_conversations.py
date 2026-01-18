"""
Management command to clean up duplicate conversations for P2P transactions
"""
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Q, Count
from messaging.models import Conversation, Message

# Try to import P2P service transaction
try:
    from orders.p2p_models import P2PServiceTransaction
    P2P_AVAILABLE = True
except ImportError:
    P2P_AVAILABLE = False


class Command(BaseCommand):
    help = 'Clean up duplicate conversations for P2P transactions by merging them into the oldest one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--transaction-id',
            type=int,
            help='Clean up duplicates for a specific transaction ID only',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        transaction_id = options.get('transaction_id')

        if not P2P_AVAILABLE:
            self.stdout.write(self.style.ERROR('P2P models not available'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))

        # Get all P2P transactions
        if transaction_id:
            transactions = P2PServiceTransaction.objects.filter(id=transaction_id)
        else:
            transactions = P2PServiceTransaction.objects.all()

        total_merged = 0
        total_deleted = 0

        for txn in transactions:
            self.stdout.write(f'\nProcessing transaction: {txn.reference} (ID: {txn.id})')
            
            # Get buyer and seller, ensuring consistent ordering
            u1, u2 = (txn.buyer, txn.seller) if txn.buyer.id < txn.seller.id else (txn.seller, txn.buyer)
            
            # Find all conversations between these users that might be for this transaction
            # P2P conversations have transaction=None and listing=None
            conversations = Conversation.objects.filter(
                user1=u1,
                user2=u2,
                transaction=None,
                listing=None
            ).order_by('created_at')
            
            # Check which conversations actually have messages with this transaction_id
            # Also check for "Chat started for transaction X" messages where X matches the reference
            conversations_with_txn = []
            for conv in conversations:
                # Check if any message has transaction_id in metadata
                has_txn_in_metadata = Message.objects.filter(
                    conversation=conv,
                    metadata__transaction_id=txn.id
                ).exists()
                
                # Also check if any message contains the transaction reference
                # (for "Chat started for transaction X" messages that might not have transaction_id)
                has_txn_reference = Message.objects.filter(
                    conversation=conv,
                    content__icontains=f'transaction {txn.reference}'
                ).exists()
                
                if has_txn_in_metadata or has_txn_reference:
                    conversations_with_txn.append(conv)
                    reason = 'metadata' if has_txn_in_metadata else 'reference in content'
                    self.stdout.write(f'  Found conversation {conv.id} with transaction messages (matched by {reason})')
            
            # If we have duplicates (more than one conversation for this transaction)
            if len(conversations_with_txn) > 1:
                self.stdout.write(self.style.WARNING(
                    f'  Found {len(conversations_with_txn)} duplicate conversations for transaction {txn.reference}'
                ))
                
                # Keep the oldest conversation (first one)
                keep_conversation = conversations_with_txn[0]
                duplicate_conversations = conversations_with_txn[1:]
                
                self.stdout.write(f'  Keeping conversation {keep_conversation.id} (oldest)')
                self.stdout.write(f'  Will merge/delete {len(duplicate_conversations)} duplicate(s)')
                
                if not dry_run:
                    try:
                        with db_transaction.atomic():
                            # Move all messages from duplicates to the kept conversation
                            for dup_conv in duplicate_conversations:
                                # Update all messages to point to the kept conversation
                                Message.objects.filter(conversation=dup_conv).update(
                                    conversation=keep_conversation
                                )
                                
                                # Update conversation last_message_at if needed
                                last_msg = Message.objects.filter(
                                    conversation=keep_conversation
                                ).order_by('-created_at').first()
                                
                                if last_msg:
                                    keep_conversation.last_message_at = last_msg.created_at
                                    keep_conversation.save(update_fields=['last_message_at'])
                                
                                # Delete the duplicate conversation
                                dup_conv.delete()
                                self.stdout.write(f'    Deleted duplicate conversation {dup_conv.id}')
                            
                            total_merged += len(duplicate_conversations)
                            total_deleted += len(duplicate_conversations)
                            self.stdout.write(self.style.SUCCESS(
                                f'  Successfully merged {len(duplicate_conversations)} duplicate(s) into conversation {keep_conversation.id}'
                            ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'  Error processing transaction {txn.reference}: {str(e)}'
                        ))
                        import traceback
                        self.stdout.write(traceback.format_exc())
                else:
                    total_merged += len(duplicate_conversations)
                    total_deleted += len(duplicate_conversations)
            else:
                self.stdout.write('  No duplicates found')

        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would merge {total_merged} duplicate conversations'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Successfully merged {total_merged} duplicate conversations'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {total_deleted} duplicate conversation records'
            ))

