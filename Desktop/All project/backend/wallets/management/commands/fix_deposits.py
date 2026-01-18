"""
Management command to fix approved deposits that weren't credited to wallets
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from wallets.models import Deposit, Wallet, WalletTransaction


class Command(BaseCommand):
    help = 'Fix approved deposits that were not credited to user wallets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--deposit-id',
            type=int,
            help='Specific deposit ID to fix (optional, if not provided, fixes all approved deposits without transactions)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually fixing it',
        )

    def handle(self, *args, **options):
        deposit_id = options.get('deposit_id')
        dry_run = options.get('dry_run', False)

        if deposit_id:
            deposits = Deposit.objects.filter(id=deposit_id, status='approved')
        else:
            # Find approved deposits that don't have corresponding wallet transactions
            deposits = Deposit.objects.filter(status='approved').exclude(
                reference__in=WalletTransaction.objects.filter(
                    transaction_type='deposit',
                    status='completed'
                ).values_list('reference', flat=True)
            )

        if not deposits.exists():
            self.stdout.write(self.style.SUCCESS('No deposits to fix.'))
            return

        self.stdout.write(f'Found {deposits.count()} deposit(s) to fix:')
        for deposit in deposits:
            wallet, created = Wallet.objects.get_or_create(user=deposit.user)
            self.stdout.write(
                f'  Deposit ID: {deposit.id}, User: {deposit.user.email}, '
                f'Amount: {deposit.amount}, Reference: {deposit.reference}, '
                f'Wallet Balance: {wallet.balance_cedis}'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run - no changes made.'))
            return

        fixed_count = 0
        for deposit in deposits:
            try:
                with transaction.atomic():
                    wallet, created = Wallet.objects.get_or_create(user=deposit.user)
                    balance_before = wallet.balance_cedis

                    if deposit.deposit_type == 'momo':
                        amount = deposit.amount
                        wallet.add_cedis(amount)
                        balance_after = wallet.balance_cedis
                    else:
                        # For crypto deposits, we'd need to check the conversion
                        # For now, skip crypto deposits that weren't converted
                        if deposit.amount == 0:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Skipping deposit {deposit.id} - crypto deposit with no cedis amount'
                                )
                            )
                            continue
                        amount = deposit.amount
                        wallet.add_cedis(amount)
                        balance_after = wallet.balance_cedis

                    # Create wallet transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='deposit',
                        amount=amount,
                        currency='cedis',
                        status='completed',
                        reference=deposit.reference,
                        description=f"Deposit via {deposit.deposit_type}. Ref: {deposit.reference}. Fixed by management command.",
                        balance_before=balance_before,
                        balance_after=balance_after
                    )

                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  [OK] Fixed deposit {deposit.id} - Credited {amount} cedis to {deposit.user.email}'
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  [ERROR] Error fixing deposit {deposit.id}: {str(e)}')
                )

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully fixed {fixed_count} deposit(s).'))
