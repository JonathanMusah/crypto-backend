"""
Django management command to fix approved withdrawals that weren't deducted from escrow
"""
import sys
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from wallets.models import Withdrawal, Wallet, WalletTransaction
from decimal import Decimal
from django.utils import timezone

class Command(BaseCommand):
    help = 'Fixes approved withdrawals that were not deducted from escrow.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user_email',
            type=str,
            help='Filter withdrawals for a specific user email.',
        )
        parser.add_argument(
            '--withdrawal_id',
            type=int,
            help='Fix a specific withdrawal by ID.',
        )
        parser.add_argument(
            '--reference',
            type=str,
            help='Fix a specific withdrawal by reference.',
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help='Do not make any changes, just show what would be done.',
        )

    def handle(self, *args, **options):
        # Ensure stdout can handle Unicode characters
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
            sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

        user_email = options['user_email']
        withdrawal_id = options['withdrawal_id']
        reference = options['reference']
        dry_run = options['dry_run']

        User = get_user_model()
        withdrawals_to_fix = []

        # Check both approved and completed withdrawals (completed should have already deducted escrow)
        queryset = Withdrawal.objects.filter(status__in=['approved', 'completed'], withdrawal_type='momo')

        if user_email:
            try:
                user = User.objects.get(email=user_email)
                queryset = queryset.filter(user=user)
            except User.DoesNotExist:
                raise CommandError(f'User with email "{user_email}" does not exist.')
        
        if withdrawal_id:
            queryset = queryset.filter(id=withdrawal_id)
        
        if reference:
            queryset = queryset.filter(reference=reference)

        for withdrawal in queryset:
            # Check if escrow was deducted (look for completed withdraw transaction)
            withdraw_txn = WalletTransaction.objects.filter(
                reference=withdrawal.reference,
                transaction_type='withdraw',
                status='completed'
            ).first()
            
            # Check if escrow lock exists
            escrow_lock = WalletTransaction.objects.filter(
                reference=withdrawal.reference,
                transaction_type='escrow_lock',
                status='completed'
            ).first()
            
            if escrow_lock and not withdraw_txn:
                # Escrow was locked but not deducted - needs fixing
                withdrawals_to_fix.append(withdrawal)

        if not withdrawals_to_fix:
            self.stdout.write(self.style.SUCCESS('No approved withdrawals found that need fixing.'))
            return

        self.stdout.write(f'Found {len(withdrawals_to_fix)} withdrawal(s) to fix:')

        fixed_count = 0
        for withdrawal in withdrawals_to_fix:
            try:
                wallet, created = Wallet.objects.get_or_create(user=withdrawal.user)
                
                # Ensure amount is Decimal
                amount = Decimal(str(withdrawal.amount))

                self.stdout.write(
                    f'  Withdrawal ID: {withdrawal.id}, User: {withdrawal.user.email}, Amount: {amount}, '
                    f'Reference: {withdrawal.reference}, Escrow Balance: {wallet.escrow_balance}'
                )

                if not dry_run:
                    with transaction.atomic():
                        escrow_before = wallet.escrow_balance
                        wallet.deduct_from_escrow(amount)
                        
                        # Check if a withdraw transaction already exists
                        existing_withdraw = WalletTransaction.objects.filter(
                            reference=withdrawal.reference,
                            transaction_type='withdraw'
                        ).first()
                        
                        if not existing_withdraw:
                            # Create new transaction with unique reference
                            import uuid
                            unique_ref = f"{withdrawal.reference}-{uuid.uuid4().hex[:8]}"
                            WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type='withdraw',
                                amount=amount,
                                currency='cedis',
                                status='completed',
                                reference=unique_ref,
                                description=f'Withdrawal via MoMo to {withdrawal.momo_number}. Ref: {withdrawal.reference}. Manual fix for approved withdrawal.',
                                balance_before=wallet.balance_cedis + escrow_before,
                                balance_after=wallet.balance_cedis + wallet.escrow_balance
                            )
                        elif existing_withdraw.status != 'completed':
                            # Update existing pending transaction to completed
                            existing_withdraw.status = 'completed'
                            existing_withdraw.balance_before = wallet.balance_cedis + escrow_before
                            existing_withdraw.balance_after = wallet.balance_cedis + wallet.escrow_balance
                            existing_withdraw.save()
                        wallet.refresh_from_db()
                        fixed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  [OK] Fixed withdrawal {withdrawal.id} - Deducted {amount} from escrow for {withdrawal.user.email}'
                            )
                        )
                else:
                    self.stdout.write(f'  [DRY RUN] Would fix withdrawal {withdrawal.id} - Deduct {amount} from escrow for {withdrawal.user.email}')

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  [ERROR] Error fixing withdrawal {withdrawal.id}: {str(e)}')
                )

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully fixed {fixed_count} withdrawal(s).'))

