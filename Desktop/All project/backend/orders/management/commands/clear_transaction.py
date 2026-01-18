"""
Management command to clear/cancel a P2P service transaction and refund escrow
"""
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone
from orders.p2p_models import P2PServiceTransaction
from wallets.models import Wallet, WalletTransaction
import uuid


class Command(BaseCommand):
    help = 'Clear/cancel a P2P service transaction and refund escrow to buyer'

    def add_arguments(self, parser):
        parser.add_argument('reference', type=str, help='Transaction reference (e.g., CAT-4EAF79B5CB60)')
        parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')

    def handle(self, *args, **options):
        reference = options['reference']
        
        try:
            txn = P2PServiceTransaction.objects.get(reference=reference)
        except P2PServiceTransaction.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Transaction {reference} not found'))
            return
        
        self.stdout.write(f'Found transaction: {txn.reference}')
        self.stdout.write(f'Status: {txn.status}')
        self.stdout.write(f'Buyer: {txn.buyer.email}')
        self.stdout.write(f'Seller: {txn.seller.email}')
        self.stdout.write(f'Escrow Amount: ₵{txn.escrow_amount_cedis}')
        self.stdout.write(f'Escrow Released: {txn.escrow_released}')
        
        if txn.escrow_released:
            self.stdout.write(self.style.WARNING('Escrow has already been released. Proceeding with cancellation only.'))
        else:
            # Get buyer wallet
            buyer_wallet, _ = Wallet.objects.get_or_create(user=txn.buyer)
            escrow_before = buyer_wallet.escrow_balance
            balance_before = buyer_wallet.balance_cedis
            
            self.stdout.write(f'Buyer escrow before: ₵{escrow_before}')
            self.stdout.write(f'Buyer balance before: ₵{balance_before}')
            
            if buyer_wallet.escrow_balance < txn.escrow_amount_cedis:
                self.stdout.write(self.style.ERROR(
                    f'Insufficient escrow balance. Escrow: ₵{buyer_wallet.escrow_balance}, Required: ₵{txn.escrow_amount_cedis}'
                ))
                return
        
        # Confirm (unless --yes flag is provided)
        if not options.get('yes'):
            confirm = input(f'\nAre you sure you want to cancel transaction {reference} and refund escrow? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cancelled by user'))
                return
        
        try:
            with db_transaction.atomic():
                if not txn.escrow_released:
                    # Deduct from escrow
                    buyer_wallet.deduct_from_escrow(txn.escrow_amount_cedis)
                    buyer_wallet.refresh_from_db()
                    
                    # Add to balance
                    buyer_wallet.add_cedis(txn.escrow_amount_cedis)
                    buyer_wallet.refresh_from_db()
                    
                    # Create wallet transactions
                    refund_ref = f'{txn.reference}-REFUND-{uuid.uuid4().hex[:8]}'
                    WalletTransaction.objects.create(
                        wallet=buyer_wallet,
                        transaction_type='escrow_release',
                        amount=txn.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=refund_ref,
                        description=f'Refund for cancelled transaction {txn.reference}',
                        balance_before=escrow_before,
                        balance_after=buyer_wallet.escrow_balance
                    )
                    
                    credit_ref = f'{txn.reference}-CREDIT-{uuid.uuid4().hex[:8]}'
                    WalletTransaction.objects.create(
                        wallet=buyer_wallet,
                        transaction_type='credit',
                        amount=txn.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=credit_ref,
                        description=f'Credit for cancelled transaction {txn.reference}',
                        balance_before=balance_before,
                        balance_after=buyer_wallet.balance_cedis
                    )
                    
                    self.stdout.write(f'Refunded ₵{txn.escrow_amount_cedis} to buyer')
                    self.stdout.write(f'Buyer escrow after: ₵{buyer_wallet.escrow_balance}')
                    self.stdout.write(f'Buyer balance after: ₵{buyer_wallet.balance_cedis}')
                
                # Update transaction
                txn.status = 'cancelled'
                txn.escrow_released = True
                txn.escrow_released_at = timezone.now()
                txn.save()
                
                self.stdout.write(self.style.SUCCESS(f'Transaction {reference} has been cancelled successfully'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error cancelling transaction: {str(e)}'))
            raise

