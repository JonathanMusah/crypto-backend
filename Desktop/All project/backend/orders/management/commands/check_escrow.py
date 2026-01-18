"""
Management command to diagnose wallet escrow balance issues
Usage: python manage.py check_escrow <user_email>
"""
from django.core.management.base import BaseCommand
from wallets.models import Wallet
from orders.p2p_models import P2PServiceTransaction
from orders.models import GiftCardTransaction
from wallets.models import Withdrawal
from authentication.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Check which transactions are holding escrow for a user'

    def add_arguments(self, parser):
        parser.add_argument('user_email', type=str, help='User email to check')

    def handle(self, *args, **options):
        user_email = options['user_email']
        
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User {user_email} not found"))
            return
        
        wallet, _ = Wallet.objects.get_or_create(user=user)
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS(f"ESCROW DIAGNOSTIC FOR: {user_email}"))
        self.stdout.write(self.style.SUCCESS(f"{'='*80}"))
        self.stdout.write(f"\nWallet Balance: GHS {wallet.balance_cedis}")
        self.stdout.write(f"Escrow Balance: GHS {wallet.escrow_balance}")
        self.stdout.write(f"Total Balance: GHS {wallet.balance_cedis + wallet.escrow_balance}")
        
        # Check P2P transactions holding escrow (including completed/cancelled that might not have released)
        self.stdout.write(f"\n--- P2P Service Transactions (All Statuses) ---")
        p2p_transactions = P2PServiceTransaction.objects.filter(
            buyer=user,
            escrow_amount_cedis__gt=0
        ).order_by('-created_at')
        
        total_p2p_escrow = Decimal('0.00')
        for txn in p2p_transactions:
            status_style = 'NORMAL'
            if txn.status in ['completed', 'cancelled', 'refunded']:
                status_style = 'WARNING'
            
            self.stdout.write(f"\n  Transaction: {txn.reference}")
            if status_style == 'WARNING':
                self.stdout.write(self.style.WARNING(f"    Status: {txn.status} (SHOULD HAVE RELEASED ESCROW)"))
            else:
                self.stdout.write(f"    Status: {txn.status}")
            self.stdout.write(f"    Escrow Amount: GHS {txn.escrow_amount_cedis}")
            self.stdout.write(f"    Amount USD: ${txn.amount_usd}")
            self.stdout.write(f"    Created: {txn.created_at}")
            if txn.auto_release_at:
                from django.utils import timezone
                if txn.auto_release_at <= timezone.now():
                    self.stdout.write(self.style.WARNING(f"    WARNING: Auto-release time PASSED: {txn.auto_release_at}"))
                else:
                    self.stdout.write(f"    Auto-release at: {txn.auto_release_at}")
            if txn.status in ['payment_received', 'service_provided', 'verifying']:
                total_p2p_escrow += txn.escrow_amount_cedis
        
        self.stdout.write(f"\n  Total P2P Escrow: GHS {total_p2p_escrow}")
        
        # Check Gift Card transactions (all statuses)
        self.stdout.write(f"\n--- Gift Card Transactions (All Statuses) ---")
        giftcard_transactions = GiftCardTransaction.objects.filter(
            buyer=user,
            escrow_amount_cedis__gt=0
        ).order_by('-created_at')
        
        total_gc_escrow = Decimal('0.00')
        for txn in giftcard_transactions:
            status_style = 'NORMAL'
            if txn.status in ['completed', 'cancelled', 'refunded']:
                status_style = 'WARNING'
            
            self.stdout.write(f"\n  Transaction: {txn.reference}")
            if status_style == 'WARNING':
                self.stdout.write(self.style.WARNING(f"    Status: {txn.status} (SHOULD HAVE RELEASED ESCROW)"))
            else:
                self.stdout.write(f"    Status: {txn.status}")
            self.stdout.write(f"    Escrow Amount: GHS {txn.escrow_amount_cedis}")
            self.stdout.write(f"    Created: {txn.created_at}")
            if txn.auto_release_at:
                from django.utils import timezone
                if txn.auto_release_at <= timezone.now():
                    self.stdout.write(self.style.WARNING(f"    WARNING: Auto-release time PASSED: {txn.auto_release_at}"))
                else:
                    self.stdout.write(f"    Auto-release at: {txn.auto_release_at}")
            if txn.status in ['payment_received', 'gift_card_provided', 'verifying']:
                total_gc_escrow += txn.escrow_amount_cedis
        
        self.stdout.write(f"\n  Total Gift Card Escrow: GHS {total_gc_escrow}")
        
        # Check Withdrawals holding escrow
        self.stdout.write(f"\n--- Withdrawals Holding Escrow ---")
        withdrawals = Withdrawal.objects.filter(
            user=user,
            status__in=['awaiting_admin', 'approved'],
            total_amount__gt=0
        ).order_by('-created_at')
        
        total_withdrawal_escrow = Decimal('0.00')
        for wd in withdrawals:
            self.stdout.write(f"\n  Withdrawal: {wd.reference}")
            self.stdout.write(f"    Status: {wd.status}")
            self.stdout.write(f"    Total Amount: GHS {wd.total_amount} (Amount: GHS {wd.amount} + Fee: GHS {wd.fee})")
            self.stdout.write(f"    Created: {wd.created_at}")
            total_withdrawal_escrow += wd.total_amount
        
        self.stdout.write(f"\n  Total Withdrawal Escrow: GHS {total_withdrawal_escrow}")
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n{'='*80}"))
        self.stdout.write(self.style.SUCCESS(f"SUMMARY"))
        self.stdout.write(self.style.SUCCESS(f"{'='*80}"))
        self.stdout.write(f"Actual Escrow Balance: GHS {wallet.escrow_balance}")
        self.stdout.write(f"Calculated Escrow (P2P): GHS {total_p2p_escrow}")
        self.stdout.write(f"Calculated Escrow (Gift Cards): GHS {total_gc_escrow}")
        self.stdout.write(f"Calculated Escrow (Withdrawals): GHS {total_withdrawal_escrow}")
        self.stdout.write(f"Total Calculated: GHS {total_p2p_escrow + total_gc_escrow + total_withdrawal_escrow}")
        
        difference = wallet.escrow_balance - (total_p2p_escrow + total_gc_escrow + total_withdrawal_escrow)
        if abs(difference) > Decimal('0.01'):
            self.stdout.write(self.style.ERROR(f"\nWARNING: DISCREPANCY DETECTED: GHS {difference}"))
            self.stdout.write(self.style.ERROR(f"This indicates a potential issue with escrow tracking."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Escrow balance matches calculated total"))
        
        # Check for transactions that should have been auto-released
        from django.utils import timezone
        overdue_releases = P2PServiceTransaction.objects.filter(
            buyer=user,
            status='verifying',
            auto_release_at__lte=timezone.now(),
            buyer_verified=True
        )
        
        if overdue_releases.exists():
            self.stdout.write(self.style.WARNING(f"\n⚠️  FOUND {overdue_releases.count()} TRANSACTION(S) THAT SHOULD HAVE BEEN AUTO-RELEASED:"))
            for txn in overdue_releases:
                self.stdout.write(self.style.WARNING(f"  - {txn.reference}: Auto-release was due at {txn.auto_release_at}"))
            self.stdout.write(self.style.WARNING(f"\n  Run: python manage.py process_p2p_auto_actions"))

