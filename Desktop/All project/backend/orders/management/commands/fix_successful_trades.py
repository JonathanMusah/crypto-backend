"""
Management command to retroactively update successful_trades for completed transactions.
This fixes the issue where completed transactions didn't increment successful_trades.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from orders.models import GiftCardTransaction
from authentication.models import User
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Retroactively update successful_trades for all completed gift card transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all completed transactions
        completed_transactions = GiftCardTransaction.objects.filter(status='completed')
        self.stdout.write(f'Found {completed_transactions.count()} completed transactions')
        
        # Track users and their counts
        user_trade_counts = {}
        
        for txn in completed_transactions:
            buyer = txn.buyer
            seller = txn.seller
            
            # Count trades per user
            if buyer.id not in user_trade_counts:
                user_trade_counts[buyer.id] = {'buyer': 0, 'seller': 0, 'user': buyer}
            if seller.id not in user_trade_counts:
                user_trade_counts[seller.id] = {'buyer': 0, 'seller': 0, 'user': seller}
            
            user_trade_counts[buyer.id]['buyer'] += 1
            user_trade_counts[seller.id]['seller'] += 1
        
        self.stdout.write(f'\nUsers to update: {len(user_trade_counts)}')
        
        if not dry_run:
            with transaction.atomic():
                for user_id, counts in user_trade_counts.items():
                    user = counts['user']
                    total_trades = counts['buyer'] + counts['seller']
                    current_trades = user.successful_trades
                    
                    # Only update if current count is less than what it should be
                    if current_trades < total_trades:
                        old_count = user.successful_trades
                        user.successful_trades = total_trades
                        user.update_trust_score()  # This will recalculate trust score
                        user.save()
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Updated {user.email}: {old_count} -> {user.successful_trades} trades '
                                f'(Trust score: {user.get_effective_trust_score()})'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipped {user.email}: already has {current_trades} trades (should be {total_trades})'
                            )
                        )
        else:
            # Dry run - just show what would be updated
            for user_id, counts in user_trade_counts.items():
                user = counts['user']
                total_trades = counts['buyer'] + counts['seller']
                current_trades = user.successful_trades
                
                if current_trades < total_trades:
                    self.stdout.write(
                        f'Would update {user.email}: {current_trades} -> {total_trades} trades'
                    )
                else:
                    self.stdout.write(
                        f'Would skip {user.email}: already has {current_trades} trades'
                    )
        
        self.stdout.write(self.style.SUCCESS('\nDone!'))

