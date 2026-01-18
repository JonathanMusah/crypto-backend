"""
Management command to process auto-actions for gift card transactions:
- Auto-cancel if seller doesn't respond in 24 hours
- Auto-dispute if buyer doesn't verify in 48 hours
- Auto-release funds 1 hour after buyer verification
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction
from datetime import timedelta
from orders.models import GiftCardTransaction, GiftCardDispute, GiftCardTransactionLog
from wallets.models import Wallet, WalletTransaction
from wallets.views import log_wallet_activity
from notifications.utils import create_notification
import uuid
import logging

logger = logging.getLogger(__name__)


def log_transaction_action(transaction, action, performed_by=None, notes='', metadata=None):
    """Helper function to log transaction actions"""
    GiftCardTransactionLog.objects.create(
        transaction=transaction,
        action=action,
        performed_by=performed_by,
        notes=notes,
        metadata=metadata or {}
    )


class Command(BaseCommand):
    help = 'Process auto-actions for gift card transactions (cancellations, disputes, releases)'

    def handle(self, *args, **options):
        now = timezone.now()
        processed = {
            'auto_cancelled': 0,
            'auto_disputed': 0,
            'auto_released': 0
        }
        
        # 1. Auto-cancel if seller doesn't respond in 24 hours
        pending_seller = GiftCardTransaction.objects.filter(
            status='payment_received',
            seller_response_deadline__lte=now
        )
        
        for transaction in pending_seller:
            try:
                with db_transaction.atomic():
                    buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                    
                    # Refund buyer
                    balance_before = buyer_wallet.balance_cedis
                    buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
                    buyer_wallet.refresh_from_db()
                    
                    # Create wallet transaction
                    WalletTransaction.objects.create(
                        wallet=buyer_wallet,
                        transaction_type='escrow_release',
                        amount=transaction.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=f"{transaction.reference}-AUTO-CANCEL-{uuid.uuid4().hex[:8]}",
                        description=f"Auto-cancelled: Seller did not provide card details within 24 hours. Ref: {transaction.reference}",
                        balance_before=balance_before,
                        balance_after=buyer_wallet.balance_cedis
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=transaction.buyer,
                        amount=transaction.escrow_amount_cedis,
                        log_type='escrow_refund',
                        balance_after=buyer_wallet.balance_cedis,
                        transaction_id=transaction.reference
                    )
                    
                    # Update transaction
                    transaction.status = 'cancelled'
                    transaction.cancelled_at = now
                    transaction.save()
                    
                    # Log action
                    log_transaction_action(
                        transaction=transaction,
                        action='auto_cancelled',
                        performed_by=None,
                        notes='Transaction auto-cancelled: Seller did not provide card details within 24 hours',
                        metadata={
                            'deadline': transaction.seller_response_deadline.isoformat() if transaction.seller_response_deadline else None,
                            'cancelled_at': now.isoformat()
                        }
                    )
                    
                    # Notifications
                    create_notification(
                        user=transaction.buyer,
                        notification_type='GIFT_CARD_TRANSACTION_CANCELLED',
                        title='Transaction Auto-Cancelled',
                        message=f'Transaction {transaction.reference} was auto-cancelled. Seller did not provide card details within 24 hours. Funds refunded to your wallet.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    create_notification(
                        user=transaction.seller,
                        notification_type='GIFT_CARD_TRANSACTION_CANCELLED',
                        title='Transaction Auto-Cancelled',
                        message=f'Transaction {transaction.reference} was auto-cancelled. You did not provide card details within 24 hours.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    processed['auto_cancelled'] += 1
                    self.stdout.write(
                        self.style.WARNING(f'Auto-cancelled transaction {transaction.reference}')
                    )
            except Exception as e:
                logger.error(f'Error auto-cancelling transaction {transaction.reference}: {str(e)}', exc_info=True)
        
        # 2. Auto-dispute if buyer doesn't verify in 48 hours
        pending_buyer = GiftCardTransaction.objects.filter(
            status='card_provided',
            buyer_verification_deadline__lte=now
        )
        
        for transaction in pending_buyer:
            try:
                with db_transaction.atomic():
                    # Create dispute
                    dispute = GiftCardDispute.objects.create(
                        transaction=transaction,
                        raised_by=transaction.buyer,
                        dispute_type='seller_not_responding',
                        description='Auto-disputed: Buyer did not verify gift card within 48 hours of receiving details',
                        status='open',
                        priority='high'
                    )
                    
                    # Update transaction
                    transaction.status = 'disputed'
                    transaction.has_dispute = True
                    transaction.save()
                    
                    # Log action
                    log_transaction_action(
                        transaction=transaction,
                        action='auto_disputed',
                        performed_by=None,
                        notes='Transaction auto-disputed: Buyer did not verify within 48 hours',
                        metadata={
                            'deadline': transaction.buyer_verification_deadline.isoformat() if transaction.buyer_verification_deadline else None,
                            'dispute_id': dispute.id,
                            'disputed_at': now.isoformat()
                        }
                    )
                    
                    # Notifications
                    create_notification(
                        user=transaction.buyer,
                        notification_type='GIFT_CARD_DISPUTE_RAISED',
                        title='Transaction Auto-Disputed',
                        message=f'Transaction {transaction.reference} was auto-disputed. You did not verify the gift card within 48 hours. Admin will review.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    create_notification(
                        user=transaction.seller,
                        notification_type='GIFT_CARD_DISPUTE_RAISED',
                        title='Transaction Auto-Disputed',
                        message=f'Transaction {transaction.reference} was auto-disputed. Buyer did not verify within 48 hours. Admin will review.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    processed['auto_disputed'] += 1
                    self.stdout.write(
                        self.style.WARNING(f'Auto-disputed transaction {transaction.reference}')
                    )
            except Exception as e:
                logger.error(f'Error auto-disputing transaction {transaction.reference}: {str(e)}', exc_info=True)
        
        # 3. Auto-release funds 1 hour after buyer verification
        pending_release = GiftCardTransaction.objects.filter(
            status='verifying',
            auto_release_at__lte=now,
            buyer_verified=True
        )
        
        for transaction in pending_release:
            try:
                with db_transaction.atomic():
                    buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                    seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
                    
                    escrow_before = buyer_wallet.escrow_balance
                    seller_balance_before = seller_wallet.balance_cedis
                    
                    # Validate escrow balance
                    if buyer_wallet.escrow_balance < transaction.escrow_amount_cedis:
                        logger.error(
                            f"Insufficient escrow balance for auto-release {transaction.reference}. "
                            f"Escrow: {buyer_wallet.escrow_balance}, Required: {transaction.escrow_amount_cedis}"
                        )
                        continue
                    
                    # Deduct from buyer's escrow
                    buyer_wallet.deduct_from_escrow(transaction.escrow_amount_cedis)
                    buyer_wallet.refresh_from_db()
                    
                    # Add to seller's balance
                    seller_balance_before = seller_wallet.balance_cedis
                    seller_wallet.add_cedis(transaction.escrow_amount_cedis)
                    seller_wallet.refresh_from_db()
                    
                    # Create wallet transactions
                    buyer_txn_ref = f"{transaction.reference}-AUTO-RELEASE-{uuid.uuid4().hex[:8]}"
                    seller_txn_ref = f"{transaction.reference}-AUTO-CREDIT-{uuid.uuid4().hex[:8]}"
                    
                    WalletTransaction.objects.create(
                        wallet=buyer_wallet,
                        transaction_type='escrow_release',
                        amount=transaction.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=buyer_txn_ref,
                        description=f"Auto-released: Gift card purchase completed. Escrow released to seller. Ref: {transaction.reference}",
                        balance_before=buyer_wallet.balance_cedis + transaction.escrow_amount_cedis,
                        balance_after=buyer_wallet.balance_cedis
                    )
                    
                    WalletTransaction.objects.create(
                        wallet=seller_wallet,
                        transaction_type='credit',
                        amount=transaction.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=seller_txn_ref,
                        description=f"Auto-released: Gift card sale completed. Received ₵{transaction.escrow_amount_cedis} from escrow. Ref: {transaction.reference}",
                        balance_before=seller_balance_before,
                        balance_after=seller_wallet.balance_cedis
                    )
                    
                    # Log wallet activities
                    log_wallet_activity(
                        user=transaction.seller,
                        amount=transaction.escrow_amount_cedis,
                        log_type='deposit',
                        balance_after=seller_wallet.balance_cedis,
                        transaction_id=transaction.reference
                    )
                    
                    # Update transaction
                    transaction.status = 'completed'
                    transaction.completed_at = now
                    transaction.save()
                    
                    # Update trust scores
                    transaction.buyer.increment_successful_trade()
                    transaction.seller.increment_successful_trade()
                    
                    # Log action
                    log_transaction_action(
                        transaction=transaction,
                        action='auto_released',
                        performed_by=None,
                        notes='Funds auto-released 1 hour after buyer verification',
                        metadata={
                            'auto_release_at': transaction.auto_release_at.isoformat() if transaction.auto_release_at else None,
                            'released_at': now.isoformat(),
                            'amount': float(transaction.escrow_amount_cedis)
                        }
                    )
                    
                    # Notifications
                    create_notification(
                        user=transaction.seller,
                        notification_type='GIFT_CARD_SALE_COMPLETED',
                        title='Sale Completed - Funds Released',
                        message=f'Buyer verified the gift card. Funds (₵{transaction.escrow_amount_cedis}) have been automatically released to your wallet. Ref: {transaction.reference}',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    create_notification(
                        user=transaction.buyer,
                        notification_type='GIFT_CARD_PURCHASE_COMPLETED',
                        title='Purchase Completed',
                        message=f'Gift card verified and transaction completed. Funds have been released to seller. Ref: {transaction.reference}',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    processed['auto_released'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Auto-released transaction {transaction.reference}')
                    )
            except Exception as e:
                logger.error(f'Error auto-releasing transaction {transaction.reference}: {str(e)}', exc_info=True)
        
        # Summary
        total = sum(processed.values())
        if total > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nProcessed {total} auto-actions: '
                    f'{processed["auto_cancelled"]} cancelled, '
                    f'{processed["auto_disputed"]} disputed, '
                    f'{processed["auto_released"]} released'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('No auto-actions to process'))

