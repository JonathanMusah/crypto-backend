"""
Management command to manually release escrow for completed transactions
Usage: python manage.py fix_escrow_release <transaction_reference>
"""
from django.core.management.base import BaseCommand
from wallets.models import Wallet, WalletTransaction
from orders.p2p_models import P2PServiceTransaction
from orders.models import GiftCardTransaction
from django.db import transaction as db_transaction
from django.utils import timezone
from notifications.utils import create_notification
from orders.p2p_views import log_p2p_transaction_action
from wallets.views import log_wallet_activity
import uuid
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manually release escrow for a completed transaction'

    def add_arguments(self, parser):
        parser.add_argument('transaction_ref', type=str, help='Transaction reference (e.g., PPT-61F2BDCABC7A)')

    def handle(self, *args, **options):
        transaction_ref = options['transaction_ref']
        
        # Try P2P transaction first
        try:
            txn = P2PServiceTransaction.objects.get(reference=transaction_ref)
            transaction_type = 'p2p'
        except P2PServiceTransaction.DoesNotExist:
            # Try Gift Card transaction
            try:
                txn = GiftCardTransaction.objects.get(reference=transaction_ref)
                transaction_type = 'giftcard'
            except GiftCardTransaction.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Transaction {transaction_ref} not found"))
                return
        
        if txn.status != 'completed':
            self.stdout.write(self.style.WARNING(
                f"Transaction {transaction_ref} is not completed (status: {txn.status}). "
                f"Are you sure you want to release escrow?"
            ))
            confirm = input("Continue anyway? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("Cancelled.")
                return
        
        if txn.escrow_amount_cedis <= 0:
            self.stdout.write(self.style.ERROR(f"Transaction {transaction_ref} has no escrow amount"))
            return
        
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=txn.buyer)
                seller_wallet, _ = Wallet.objects.get_or_create(user=txn.seller)
                
                escrow_before = buyer_wallet.escrow_balance
                seller_balance_before = seller_wallet.balance_cedis
                
                # Validate escrow balance
                if buyer_wallet.escrow_balance < txn.escrow_amount_cedis:
                    self.stdout.write(self.style.ERROR(
                        f"Insufficient escrow balance. Escrow: {buyer_wallet.escrow_balance}, "
                        f"Required: {txn.escrow_amount_cedis}"
                    ))
                    return
                
                # Deduct from buyer's escrow
                buyer_wallet.deduct_from_escrow(txn.escrow_amount_cedis)
                buyer_wallet.refresh_from_db()
                
                # Add to seller's balance
                seller_wallet.add_cedis(txn.escrow_amount_cedis)
                seller_wallet.refresh_from_db()
                
                # Create wallet transactions
                buyer_txn_ref = f"{txn.reference}-MANUAL-RELEASE-{uuid.uuid4().hex[:8]}"
                seller_txn_ref = f"{txn.reference}-MANUAL-CREDIT-{uuid.uuid4().hex[:8]}"
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=txn.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=buyer_txn_ref,
                    description=f"Manual escrow release for {transaction_type} transaction. Ref: {txn.reference}",
                    balance_before=escrow_before,
                    balance_after=buyer_wallet.escrow_balance
                )
                
                WalletTransaction.objects.create(
                    wallet=seller_wallet,
                    transaction_type='credit',
                    amount=txn.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=seller_txn_ref,
                    description=f"Payment received for {transaction_type} transaction. Ref: {txn.reference}",
                    balance_before=seller_balance_before,
                    balance_after=seller_wallet.balance_cedis
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=txn.seller,
                    amount=txn.escrow_amount_cedis,
                    log_type='deposit',
                    balance_after=seller_wallet.balance_cedis,
                    transaction_id=txn.reference
                )
                
                # Log transaction action (for P2P)
                if transaction_type == 'p2p':
                    log_p2p_transaction_action(
                        transaction=txn,
                        action='manual_escrow_release',
                        performed_by=None,
                        notes=f'Escrow manually released via management command. Amount: GHS {txn.escrow_amount_cedis}'
                    )
                
                # Notifications
                create_notification(
                    user=txn.buyer,
                    notification_type='P2P_SERVICE_COMPLETED' if transaction_type == 'p2p' else 'GIFT_CARD_COMPLETED',
                    title='Escrow Released',
                    message=f'Escrow of GHS {txn.escrow_amount_cedis} has been released for transaction {txn.reference}',
                    related_object_type='p2p_service_transaction' if transaction_type == 'p2p' else 'gift_card_transaction',
                    related_object_id=txn.id,
                )
                
                create_notification(
                    user=txn.seller,
                    notification_type='P2P_SERVICE_COMPLETED' if transaction_type == 'p2p' else 'GIFT_CARD_COMPLETED',
                    title='Payment Received',
                    message=f'Payment of GHS {txn.escrow_amount_cedis} has been released to your wallet. Ref: {txn.reference}',
                    related_object_type='p2p_service_transaction' if transaction_type == 'p2p' else 'gift_card_transaction',
                    related_object_id=txn.id,
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f"\nSuccessfully released escrow for transaction {transaction_ref}\n"
                    f"  Amount: GHS {txn.escrow_amount_cedis}\n"
                    f"  Buyer escrow before: GHS {escrow_before}\n"
                    f"  Buyer escrow after: GHS {buyer_wallet.escrow_balance}\n"
                    f"  Seller balance before: GHS {seller_balance_before}\n"
                    f"  Seller balance after: GHS {seller_wallet.balance_cedis}"
                ))
                
        except Exception as e:
            logger.error(f"Error releasing escrow for {transaction_ref}: {str(e)}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))

