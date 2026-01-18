"""
FIX #3: Celery tasks for automatic transaction timeout handling
Handles auto-cancellation and auto-release of transactions that exceed their deadlines
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import logging
from .models import GiftCardTransaction, P2PServiceTransaction
from wallets.models import Wallet
from notifications.models import Notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_transaction_timeouts(self):
    """
    ✅ FIX #3: Process timeouts for GiftCardTransactions
    - Auto-cancel if seller doesn't respond by seller_response_deadline
    - Auto-release escrow if no payment received by auto_release_at
    """
    try:
        with db_transaction.atomic():
            now = timezone.now()
            
            # 1️⃣ HANDLE SELLER RESPONSE TIMEOUT
            # Auto-cancel transactions where seller didn't respond within 24 hours
            timed_out_transactions = GiftCardTransaction.objects.select_for_update().filter(
                status='payment_received',  # Awaiting seller confirmation
                seller_response_deadline__lt=now,  # Deadline passed
                auto_cancelled=False  # Not already cancelled
            )
            
            for txn in timed_out_transactions:
                try:
                    _auto_cancel_transaction(txn)
                except Exception as e:
                    logger.error(f"Failed to auto-cancel transaction {txn.id}: {str(e)}", exc_info=True)
                    # Continue processing other transactions
            
            # 2️⃣ HANDLE AUTO-RELEASE TIMEOUT
            # Auto-release escrow if admin didn't complete within auto_release_at deadline
            auto_release_transactions = GiftCardTransaction.objects.select_for_update().filter(
                status__in=['payment_verified', 'funds_released_pending'],  # Awaiting final release
                auto_release_at__lt=now,  # Auto-release deadline passed
                escrow_released=False  # Escrow not yet released
            )
            
            for txn in auto_release_transactions:
                try:
                    _auto_release_transaction(txn)
                except Exception as e:
                    logger.error(f"Failed to auto-release transaction {txn.id}: {str(e)}", exc_info=True)
                    # Continue processing other transactions
            
            logger.info(
                f"Timeout processing complete: {timed_out_transactions.count()} "
                f"cancellations, {auto_release_transactions.count()} auto-releases"
            )
            
    except Exception as e:
        logger.error(f"Transaction timeout processing failed: {str(e)}", exc_info=True)
        # Retry with exponential backoff (5s, 25s, 125s)
        raise self.retry(exc=e, countdown=5 ** self.request.retries)


def _auto_cancel_transaction(txn):
    """
    Auto-cancel a transaction when seller doesn't respond within deadline
    Refund buyer's escrowed funds
    """
    logger.info(f"Auto-cancelling transaction {txn.id} - seller response timeout")
    
    with db_transaction.atomic():
        # Refund buyer's escrowed funds
        buyer_wallet = Wallet.objects.select_for_update().get(user=txn.buyer)
        
        try:
            # ✅ FIX #1: Use atomic release from escrow
            buyer_wallet.release_cedis_from_escrow_atomic(txn.escrow_amount_cedis)
            
            # Update transaction status
            txn.status = 'auto_cancelled'
            txn.auto_cancelled = True
            txn.cancellation_reason = 'seller_response_timeout'
            txn.save(update_fields=['status', 'auto_cancelled', 'cancellation_reason', 'updated_at'])
            
            # Create audit log
            from .models import TransactionAuditLog
            TransactionAuditLog.objects.create(
                transaction_type='gift_card',
                transaction_id=txn.id,
                action='auto_cancelled',
                performed_by=None,  # System action
                previous_state={'status': 'payment_received'},
                new_state={'status': 'auto_cancelled'},
                notes=f'Auto-cancelled: Seller did not respond within 24 hours'
            )
            
            # Notify buyer
            Notification.objects.create(
                user=txn.buyer,
                notification_type='transaction_auto_cancelled',
                title='Order Auto-Cancelled',
                message=f"Order #{txn.reference} was auto-cancelled because the seller didn't respond. "
                        f"₵{txn.escrow_amount_cedis:.2f} has been refunded to your wallet.",
                related_object_type='gift_card_transaction',
                related_object_id=txn.id,
                metadata={
                    'transaction_id': txn.id,
                    'reference': txn.reference,
                    'amount_refunded': float(txn.escrow_amount_cedis)
                }
            )
            
            # Notify seller
            Notification.objects.create(
                user=txn.seller,
                notification_type='transaction_auto_cancelled',
                title='Order Auto-Cancelled - No Response',
                message=f"Order #{txn.reference} was auto-cancelled because you didn't respond within 24 hours.",
                related_object_type='gift_card_transaction',
                related_object_id=txn.id
            )
            
            logger.info(f"Transaction {txn.id} auto-cancelled successfully, buyer refunded ₵{txn.escrow_amount_cedis}")
            
        except Exception as e:
            logger.error(f"Failed to auto-cancel transaction {txn.id}: {str(e)}", exc_info=True)
            raise


def _auto_release_transaction(txn):
    """
    Auto-release escrowed funds to seller when admin deadline is exceeded
    Prevents funds from being locked indefinitely
    """
    logger.info(f"Auto-releasing transaction {txn.id} - admin deadline exceeded")
    
    with db_transaction.atomic():
        # Get seller's wallet
        seller_wallet = Wallet.objects.select_for_update().get(user=txn.seller)
        buyer_wallet = Wallet.objects.select_for_update().get(user=txn.buyer)
        
        try:
            # ✅ FIX #1: Release from buyer's escrow and add to seller's balance
            buyer_wallet.deduct_from_escrow_atomic(txn.escrow_amount_cedis)
            seller_wallet.add_cedis_atomic(txn.escrow_amount_cedis)
            
            # Update transaction status
            txn.status = 'completed'
            txn.escrow_released = True
            txn.escrow_released_at = timezone.now()
            txn.save(update_fields=['status', 'escrow_released', 'escrow_released_at', 'updated_at'])
            
            # Create audit log
            from .models import TransactionAuditLog
            TransactionAuditLog.objects.create(
                transaction_type='gift_card',
                transaction_id=txn.id,
                action='auto_released',
                performed_by=None,  # System action
                previous_state={'status': txn.status, 'escrow_released': False},
                new_state={'status': 'completed', 'escrow_released': True},
                notes=f'Auto-released: Admin did not complete transaction within deadline'
            )
            
            # Notify seller
            Notification.objects.create(
                user=txn.seller,
                notification_type='escrow_auto_released',
                title='Funds Auto-Released',
                message=f"Order #{txn.reference} completed automatically. ₵{txn.escrow_amount_cedis:.2f} "
                        f"has been released to your wallet.",
                related_object_type='gift_card_transaction',
                related_object_id=txn.id,
                metadata={
                    'transaction_id': txn.id,
                    'reference': txn.reference,
                    'amount_released': float(txn.escrow_amount_cedis)
                }
            )
            
            # Notify buyer
            Notification.objects.create(
                user=txn.buyer,
                notification_type='escrow_auto_released',
                title='Order Completed',
                message=f"Order #{txn.reference} has been completed and funds released to seller.",
                related_object_type='gift_card_transaction',
                related_object_id=txn.id
            )
            
            logger.info(f"Transaction {txn.id} auto-released successfully, seller credited ₵{txn.escrow_amount_cedis}")
            
        except Exception as e:
            logger.error(f"Failed to auto-release transaction {txn.id}: {str(e)}", exc_info=True)
            raise


@shared_task(bind=True, max_retries=3)
def send_transaction_reminders(self):
    """
    ✅ FIX #3: Send reminder notifications to sellers about pending responses
    Notify 1 hour before seller_response_deadline
    """
    try:
        with db_transaction.atomic():
            now = timezone.now()
            from datetime import timedelta
            
            # Find transactions nearing deadline (within 1 hour)
            reminder_window_start = now + timedelta(minutes=50)  # 50 min before deadline
            reminder_window_end = now + timedelta(minutes=70)    # 70 min before deadline
            
            pending_reminders = GiftCardTransaction.objects.filter(
                status='payment_received',
                seller_response_deadline__gte=reminder_window_start,
                seller_response_deadline__lt=reminder_window_end,
                seller_reminder_sent=False
            )
            
            for txn in pending_reminders:
                try:
                    # Send notification to seller
                    Notification.objects.create(
                        user=txn.seller,
                        notification_type='seller_response_reminder',
                        title='Action Required: Respond to Order',
                        message=f"Order #{txn.reference} requires your response. You have 1 hour to confirm "
                                f"the payment of ₵{txn.escrow_amount_cedis:.2f}. If you don't respond, "
                                f"the order will be automatically cancelled.",
                        related_object_type='gift_card_transaction',
                        related_object_id=txn.id,
                        is_urgent=True,
                        metadata={
                            'transaction_id': txn.id,
                            'reference': txn.reference,
                            'deadline_minutes': 60
                        }
                    )
                    
                    # Mark reminder as sent
                    txn.seller_reminder_sent = True
                    txn.save(update_fields=['seller_reminder_sent'])
                    
                    logger.info(f"Reminder sent for transaction {txn.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send reminder for transaction {txn.id}: {str(e)}", exc_info=True)
                    # Continue with next transaction
            
            logger.info(f"Reminder processing complete: {pending_reminders.count()} reminders sent")
            
    except Exception as e:
        logger.error(f"Transaction reminder processing failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=5 ** self.request.retries)


@shared_task
def cleanup_expired_temp_data():
    """
    ✅ FIX #3: Clean up temporary transaction data
    Removes old cancelled/completed transactions older than 90 days
    """
    from datetime import timedelta
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        
        deleted_count, _ = GiftCardTransaction.objects.filter(
            status__in=['auto_cancelled', 'completed'],
            updated_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleanup complete: Deleted {deleted_count} old transactions")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        raise
