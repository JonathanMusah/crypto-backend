"""
Signals for orders app - handles escrow release and transaction completion
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction as db_transaction
from django.utils import timezone
from wallets.models import Wallet, WalletTransaction
from wallets.views import log_wallet_activity
from notifications.utils import create_notification
from .p2p_models import P2PServiceTransaction
# Import log function - defined in p2p_views
try:
    from .p2p_views import log_p2p_transaction_action
except ImportError:
    # Fallback if import fails
    def log_p2p_transaction_action(*args, **kwargs):
        pass
import logging
import uuid

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=P2PServiceTransaction)
def ensure_escrow_release_on_completion(sender, instance, **kwargs):
    """
    Ensure escrow is released when transaction status changes to 'completed'
    This prevents completed transactions from having locked escrow
    """
    if not instance.pk:
        return  # New instance, no old status to compare
    
    # Skip if this is already being processed (prevent recursion)
    if hasattr(instance, '_releasing_escrow'):
        return
    
    try:
        old_instance = P2PServiceTransaction.objects.get(pk=instance.pk)
        old_status = old_instance.status
        old_escrow_released = old_instance.escrow_released
    except P2PServiceTransaction.DoesNotExist:
        return
    
    # Check if status is changing to 'completed'
    status_changing_to_completed = (old_status != 'completed' and instance.status == 'completed')
    
    # If status is changing to 'completed' and escrow hasn't been released
    if status_changing_to_completed and not instance.escrow_released:
        if old_status != 'completed' or not old_escrow_released:
            # Check if escrow amount exists
            if instance.escrow_amount_cedis > 0:
                # Release escrow synchronously to prevent data inconsistency
                try:
                    with db_transaction.atomic():
                        buyer_wallet, _ = Wallet.objects.get_or_create(user=instance.buyer)
                        seller_wallet, _ = Wallet.objects.get_or_create(user=instance.seller)
                        
                        escrow_before = buyer_wallet.escrow_balance
                        seller_balance_before = seller_wallet.balance_cedis
                        
                        # Validate escrow balance
                        if buyer_wallet.escrow_balance < instance.escrow_amount_cedis:
                            logger.error(
                                f"Insufficient escrow balance for transaction {instance.reference}. "
                                f"Escrow: {buyer_wallet.escrow_balance}, Required: {instance.escrow_amount_cedis}"
                            )
                            # Don't prevent save, but log error
                            return
                        
                        # Use helper function to release escrow (handles both BUY and SELL listings correctly)
                        from orders.p2p_binance_refactor import release_escrow_for_buy_listing
                        release_escrow_for_buy_listing(instance, buyer_wallet, seller_wallet)
                        
                        # Refresh wallets to get updated balances
                        buyer_wallet.refresh_from_db()
                        seller_wallet.refresh_from_db()
                        
                        # Log wallet activity (only for SELL listings where seller receives payment)
                        if instance.listing.listing_type == 'sell':
                            log_wallet_activity(
                                user=instance.seller,
                                amount=instance.escrow_amount_cedis,
                                log_type='deposit',
                                balance_after=seller_wallet.balance_cedis,
                                transaction_id=instance.reference
                            )
                        
                        # Mark escrow as released (set flag to prevent recursion)
                        instance._releasing_escrow = True
                        instance.escrow_released = True
                        instance.escrow_released_at = timezone.now()
                        
                        # Log transaction action (use old_instance to avoid recursion)
                        log_p2p_transaction_action(
                            transaction=old_instance,
                            action='auto_released',
                            performed_by=None,
                            notes=f'Escrow automatically released via signal handler when status changed to completed. Amount: GHS {instance.escrow_amount_cedis}'
                        )
                        
                        logger.info(f"Escrow released for transaction {instance.reference} via signal handler")
                        
                except Exception as e:
                    logger.error(
                        f"Error releasing escrow for transaction {instance.reference} via signal: {str(e)}",
                        exc_info=True
                    )
                    # Don't prevent save, but log error
                    # The auto-release command will catch this later
    
    # Increment successful trades when status changes to 'completed' (regardless of escrow release)
    # This ensures both buyer and seller get credit for completed transactions
    if status_changing_to_completed:
        try:
            # Refresh users from DB to get latest trade counts
            instance.buyer.refresh_from_db()
            instance.seller.refresh_from_db()
            
            # Increment successful trades for both buyer and seller
            instance.buyer.increment_successful_trade()
            instance.seller.increment_successful_trade()
            
            logger.info(
                f"Trades incremented for transaction {instance.reference}: "
                f"Buyer {instance.buyer.email} ({instance.buyer.successful_trades} trades), "
                f"Seller {instance.seller.email} ({instance.seller.successful_trades} trades)"
            )
        except Exception as e:
            logger.error(
                f"Error incrementing trades for transaction {instance.reference}: {str(e)}",
                exc_info=True
            )
            # Don't prevent save, but log error


# Note: Notifications are handled by the auto-release command and view actions
# This signal handler ensures escrow is released and trades are incremented when status changes to 'completed'

