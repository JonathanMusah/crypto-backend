from django.core.management.base import BaseCommand
from wallets.models import Withdrawal, Wallet, WalletTransaction
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix rejected withdrawals that still have locked escrow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            help='Fix withdrawals for a specific user email',
        )
        parser.add_argument(
            '--reference',
            type=str,
            help='Fix a specific withdrawal by reference',
        )

    def handle(self, *args, **options):
        user_email = options.get('user_email')
        reference = options.get('reference')

        # Get rejected withdrawals that need fixing
        queryset = Withdrawal.objects.filter(status='rejected')
        
        if user_email:
            queryset = queryset.filter(user__email=user_email)
        if reference:
            queryset = queryset.filter(reference=reference)

        fixed_count = 0
        for withdrawal in queryset:
            # Use total_amount if available, otherwise use amount (for old withdrawals)
            release_amount = withdrawal.total_amount if withdrawal.total_amount > 0 else withdrawal.amount
            
            if release_amount <= 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipping {withdrawal.reference}: both total_amount and amount are 0 or negative'
                    )
                )
                continue

            # Check if escrow was already released
            existing_release = WalletTransaction.objects.filter(
                reference__startswith=withdrawal.reference,
                transaction_type='escrow_release',
                status='completed'
            ).first()

            if existing_release:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Skipping {withdrawal.reference}: escrow already released'
                    )
                )
                continue

            try:
                with transaction.atomic():
                    wallet, _ = Wallet.objects.get_or_create(user=withdrawal.user)
                    
                    # Check if escrow has the locked amount
                    if wallet.escrow_balance < release_amount:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipping {withdrawal.reference}: insufficient escrow. '
                                f'Escrow: {wallet.escrow_balance}, Needed: {release_amount}'
                            )
                        )
                        continue

                    balance_before = wallet.balance_cedis
                    escrow_before = wallet.escrow_balance

                    # Release escrow
                    wallet.release_cedis_from_escrow(release_amount)
                    wallet.refresh_from_db()

                    balance_after = wallet.balance_cedis
                    escrow_after = wallet.escrow_balance

                    # Create escrow release transaction with unique reference
                    import uuid
                    unique_ref = f"{withdrawal.reference}-RELEASE-{uuid.uuid4().hex[:8]}"
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='escrow_release',
                        amount=release_amount,
                        currency='cedis',
                        status='completed',
                        reference=unique_ref,
                        description=f"Fixed: Rejected withdrawal escrow release. Amount: {withdrawal.amount:.2f} + Fee: {withdrawal.fee:.2f} = Total: {release_amount:.2f} cedis. Ref: {withdrawal.reference}",
                        balance_before=balance_before,
                        balance_after=balance_after
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Fixed {withdrawal.reference}: Released {release_amount:.2f} cedis from escrow. '
                            f'Balance: {balance_before} -> {balance_after}, '
                            f'Escrow: {escrow_before} -> {escrow_after}'
                        )
                    )
                    fixed_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error fixing {withdrawal.reference}: {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nFixed {fixed_count} withdrawal(s).'
            )
        )
