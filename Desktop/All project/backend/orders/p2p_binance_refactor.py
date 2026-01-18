"""
Binance-Style P2P System Refactoring Implementation

This module contains the refactored code for implementing a fully Binance-style
P2P system with proper deadlines, automatic matching, and enhanced security.

Key Changes:
1. Fixed deadline inconsistencies (15 minutes for all deadlines)
2. Fixed BUY listing escrow logic (refund to buyer, not seller)
3. Added missing auto-actions for all deadlines
4. Enhanced security and validation
5. Automatic matching system (to be implemented)
"""

from django.utils import timezone
from django.db import transaction as db_transaction
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Configuration constants
PAYMENT_DEADLINE_MINUTES = 15
SELLER_CONFIRMATION_DEADLINE_MINUTES = 15
SELLER_RESPONSE_DEADLINE_MINUTES = 15
BUYER_VERIFICATION_DEADLINE_MINUTES = 15
AUTO_RELEASE_DELAY_MINUTES = 15
MAX_ACTIVE_TRANSACTIONS = 5


def create_p2p_transaction_with_deadlines(listing, buyer, amount_usd, agreed_price_cedis, 
                                         buyer_service_identifier='', selected_payment_method='',
                                         payment_method_details=None, risk_score=None, 
                                         risk_factors=None, device_fingerprint=None):
    """
    Create a P2P transaction with proper deadlines set.
    
    This replaces the transaction creation logic in P2PServiceTransactionViewSet.create
    to ensure all deadlines are properly set.
    
    Returns: P2PServiceTransaction instance
    """
    from orders.p2p_models import P2PServiceTransaction
    from wallets.models import Wallet
    
    now = timezone.now()
    
    # Set deadlines based on listing type
    if listing.listing_type == 'sell':
        # SELL listings: buyer needs to mark payment, then seller confirms, then seller provides service
        payment_deadline = now + timedelta(minutes=PAYMENT_DEADLINE_MINUTES)
        seller_response_deadline = None  # Will be set after seller confirms payment
    else:
        # BUY listings: seller provides service directly (no payment confirmation needed)
        payment_deadline = None  # Not applicable for BUY listings
        seller_response_deadline = now + timedelta(minutes=SELLER_RESPONSE_DEADLINE_MINUTES)
    
    transaction = P2PServiceTransaction.objects.create(
        listing=listing,
        buyer=buyer,
        seller=listing.seller,
        amount_usd=amount_usd,
        agreed_price_cedis=agreed_price_cedis,
        escrow_amount_cedis=agreed_price_cedis,
        selected_payment_method=selected_payment_method,
        payment_method_details=payment_method_details or {},
        buyer_service_identifier=buyer_service_identifier if listing.listing_type == 'buy' else '',
        status='payment_received',
        payment_deadline=payment_deadline,
        seller_response_deadline=seller_response_deadline,
        risk_score=risk_score,
        risk_factors=risk_factors or {},
        device_fingerprint=device_fingerprint
    )
    
    return transaction


def update_seller_confirmation_deadline(transaction):
    """
    Set seller confirmation deadline after buyer marks payment as complete.
    Called from mark_payment_complete action.
    """
    from orders.p2p_models import P2PServiceTransaction
    
    if transaction.listing.listing_type == 'sell':
        transaction.seller_confirmation_deadline = timezone.now() + timedelta(
            minutes=SELLER_CONFIRMATION_DEADLINE_MINUTES
        )
        transaction.save(update_fields=['seller_confirmation_deadline'])


def update_seller_response_deadline_after_confirmation(transaction):
    """
    Set seller response deadline after seller confirms payment.
    Called from confirm_payment action.
    """
    from orders.p2p_models import P2PServiceTransaction
    
    if transaction.listing.listing_type == 'sell':
        transaction.seller_response_deadline = timezone.now() + timedelta(
            minutes=SELLER_RESPONSE_DEADLINE_MINUTES
        )
        transaction.save(update_fields=['seller_response_deadline'])


def release_escrow_for_buy_listing(transaction, buyer_wallet, seller_wallet):
    """
    Release escrow for BUY listings - refund to buyer (they're buying service, not selling).
    
    For BUY listings:
    - Buyer's funds are locked in escrow
    - After seller provides service and buyer verifies, escrow is refunded to buyer
    - Seller doesn't receive payment (they're providing service, not receiving payment)
    
    For SELL listings:
    - Buyer's funds are locked in escrow
    - After seller provides service and buyer verifies, escrow is released to seller
    - Seller receives payment for providing service
    """
    from wallets.models import WalletTransaction
    import uuid
    
    escrow_before = buyer_wallet.escrow_balance
    
    if transaction.listing.listing_type == 'buy':
        # BUY listing: Refund escrow to buyer
        buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
        buyer_wallet.refresh_from_db()
        
        # Create wallet transaction for refund
        buyer_txn_ref = f"{transaction.reference}-REFUND-{uuid.uuid4().hex[:8]}"
        WalletTransaction.objects.create(
            wallet=buyer_wallet,
            transaction_type='escrow_release',
            amount=transaction.escrow_amount_cedis,
            currency='cedis',
            status='completed',
            reference=buyer_txn_ref,
            description=f"Escrow refunded for BUY listing transaction. Service verified. Ref: {transaction.reference}",
            balance_before=escrow_before,
            balance_after=buyer_wallet.escrow_balance
        )
        
        logger.info(f"Escrow refunded to buyer for BUY listing transaction {transaction.reference}")
        
    else:
        # SELL listing: Release escrow to seller
        seller_balance_before = seller_wallet.balance_cedis
        
        buyer_wallet.deduct_from_escrow(transaction.escrow_amount_cedis)
        buyer_wallet.refresh_from_db()
        
        seller_wallet.add_cedis(transaction.escrow_amount_cedis)
        seller_wallet.refresh_from_db()
        
        # Create wallet transactions
        buyer_txn_ref = f"{transaction.reference}-RELEASE-{uuid.uuid4().hex[:8]}"
        seller_txn_ref = f"{transaction.reference}-CREDIT-{uuid.uuid4().hex[:8]}"
        
        WalletTransaction.objects.create(
            wallet=buyer_wallet,
            transaction_type='escrow_release',
            amount=transaction.escrow_amount_cedis,
            currency='cedis',
            status='completed',
            reference=buyer_txn_ref,
            description=f"Escrow released to seller for SELL listing transaction. Ref: {transaction.reference}",
            balance_before=escrow_before,
            balance_after=buyer_wallet.escrow_balance
        )
        
        WalletTransaction.objects.create(
            wallet=seller_wallet,
            transaction_type='credit',
            amount=transaction.escrow_amount_cedis,
            currency='cedis',
            status='completed',
            reference=seller_txn_ref,
            description=f"Payment received for SELL listing transaction. Ref: {transaction.reference}",
            balance_before=seller_balance_before,
            balance_after=seller_wallet.balance_cedis
        )
        
        logger.info(f"Escrow released to seller for SELL listing transaction {transaction.reference}")


def process_auto_actions_enhanced():
    """
    Enhanced auto-actions processor with all deadline checks.
    
    This should be called periodically (every 5-10 minutes) via cron.
    Replaces the existing process_p2p_auto_actions command logic.
    """
    from orders.p2p_models import P2PServiceTransaction
    from wallets.models import Wallet, WalletTransaction
    from notifications.utils import create_notification
    from orders.p2p_views import log_p2p_transaction_action
    import uuid
    
    now = timezone.now()
    processed = {
        'payment_timeout': 0,
        'seller_confirmation_timeout': 0,
        'seller_response_timeout': 0,
        'buyer_verification_timeout': 0,
        'auto_released': 0,
        'safety_net_releases': 0
    }
    
    # 1. Auto-cancel: Buyer didn't mark payment within deadline (SELL listings only)
    payment_timeout_transactions = P2PServiceTransaction.objects.filter(
        status='payment_received',
        payment_deadline__lte=now,
        payment_deadline__isnull=False,
        escrow_released=False,
        listing__listing_type='sell'
    )
    
    for transaction in payment_timeout_transactions:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                balance_before = buyer_wallet.balance_cedis
                
                buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
                buyer_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=transaction.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-PAYMENT-TIMEOUT",
                    description=f"Auto-cancelled: Buyer didn't mark payment in time. Escrow refunded. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                # Restore listing available amount
                listing = transaction.listing
                if listing.listing_type == 'sell':
                    from django.db.models import F
                    listing.refresh_from_db()
                    listing.available_amount_usd = F('available_amount_usd') + transaction.amount_usd
                    listing.save(update_fields=['available_amount_usd'])
                    listing.refresh_from_db()
                    if listing.status == 'sold':
                        listing.status = 'active'
                        listing.save(update_fields=['status'])
                
                transaction.status = 'cancelled'
                transaction.cancelled_at = now
                transaction.save()
                
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_CANCELLED',
                    title='Transaction Auto-Cancelled',
                    message=f'Transaction {transaction.reference} was auto-cancelled because payment was not marked within {PAYMENT_DEADLINE_MINUTES} minutes. Your payment has been refunded.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                processed['payment_timeout'] += 1
                logger.info(f"Auto-cancelled transaction {transaction.reference} due to payment timeout")
                
        except Exception as e:
            logger.error(f"Error processing payment timeout for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    # 2. Auto-cancel: Seller didn't confirm payment within deadline (SELL listings only)
    seller_confirmation_timeout_transactions = P2PServiceTransaction.objects.filter(
        status='buyer_marked_paid',
        seller_confirmation_deadline__lte=now,
        seller_confirmation_deadline__isnull=False,
        seller_confirmed_payment=False,
        escrow_released=False,
        listing__listing_type='sell'
    )
    
    for transaction in seller_confirmation_timeout_transactions:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                balance_before = buyer_wallet.balance_cedis
                
                buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
                buyer_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=transaction.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-SELLER-CONFIRM-TIMEOUT",
                    description=f"Auto-cancelled: Seller didn't confirm payment in time. Escrow refunded. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                # Restore listing available amount
                listing = transaction.listing
                if listing.listing_type == 'sell':
                    from django.db.models import F
                    listing.refresh_from_db()
                    listing.available_amount_usd = F('available_amount_usd') + transaction.amount_usd
                    listing.save(update_fields=['available_amount_usd'])
                    listing.refresh_from_db()
                    if listing.status == 'sold':
                        listing.status = 'active'
                        listing.save(update_fields=['status'])
                
                transaction.status = 'cancelled'
                transaction.cancelled_at = now
                transaction.save()
                
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_CANCELLED',
                    title='Transaction Auto-Cancelled',
                    message=f'Transaction {transaction.reference} was auto-cancelled because seller didn\'t confirm payment within {SELLER_CONFIRMATION_DEADLINE_MINUTES} minutes. Your payment has been refunded.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_CANCELLED',
                    title='Transaction Auto-Cancelled',
                    message=f'Transaction {transaction.reference} was auto-cancelled because you didn\'t confirm payment within {SELLER_CONFIRMATION_DEADLINE_MINUTES} minutes.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                processed['seller_confirmation_timeout'] += 1
                logger.info(f"Auto-cancelled transaction {transaction.reference} due to seller confirmation timeout")
                
        except Exception as e:
            logger.error(f"Error processing seller confirmation timeout for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    # 3. Auto-cancel: Seller didn't provide service within deadline
    seller_response_timeout_transactions = P2PServiceTransaction.objects.filter(
        status__in=['payment_received', 'seller_confirmed_payment'],
        seller_response_deadline__lte=now,
        seller_response_deadline__isnull=False,
        escrow_released=False
    )
    
    for transaction in seller_response_timeout_transactions:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                balance_before = buyer_wallet.balance_cedis
                
                buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
                buyer_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=transaction.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-SELLER-RESPONSE-TIMEOUT",
                    description=f"Auto-cancelled: Seller didn't provide service in time. Escrow refunded. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                # Restore listing available amount
                listing = transaction.listing
                if listing.listing_type == 'sell':
                    from django.db.models import F
                    listing.refresh_from_db()
                    listing.available_amount_usd = F('available_amount_usd') + transaction.amount_usd
                    listing.save(update_fields=['available_amount_usd'])
                    listing.refresh_from_db()
                    if listing.status == 'sold':
                        listing.status = 'active'
                        listing.save(update_fields=['status'])
                
                transaction.status = 'cancelled'
                transaction.cancelled_at = now
                transaction.save()
                
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_CANCELLED',
                    title='Transaction Auto-Cancelled',
                    message=f'Transaction {transaction.reference} was auto-cancelled because seller didn\'t provide service within {SELLER_RESPONSE_DEADLINE_MINUTES} minutes. Your payment has been refunded.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_CANCELLED',
                    title='Transaction Auto-Cancelled',
                    message=f'Transaction {transaction.reference} was auto-cancelled because you didn\'t provide service within {SELLER_RESPONSE_DEADLINE_MINUTES} minutes.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                processed['seller_response_timeout'] += 1
                logger.info(f"Auto-cancelled transaction {transaction.reference} due to seller response timeout")
                
        except Exception as e:
            logger.error(f"Error processing seller response timeout for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    # 4. Auto-complete: Buyer didn't verify within deadline (assume satisfied)
    buyer_verification_timeout_transactions = P2PServiceTransaction.objects.filter(
        status='service_provided',
        buyer_verification_deadline__lte=now,
        buyer_verification_deadline__isnull=False,
        buyer_verified=False,
        escrow_released=False
    )
    
    for transaction in buyer_verification_timeout_transactions:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
                
                # Release escrow based on listing type
                release_escrow_for_buy_listing(transaction, buyer_wallet, seller_wallet)
                
                transaction.status = 'completed'
                transaction.completed_at = now
                transaction.escrow_released = True
                transaction.escrow_released_at = now
                transaction.buyer_verified = True  # Assume satisfied if no response
                transaction.save()
                
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_COMPLETED',
                    title='Transaction Auto-Completed',
                    message=f'Transaction {transaction.reference} was auto-completed because you didn\'t verify within {BUYER_VERIFICATION_DEADLINE_MINUTES} minutes. Funds {"refunded" if transaction.listing.listing_type == "buy" else "released to seller"}.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_COMPLETED',
                    title='Transaction Completed',
                    message=f'Transaction {transaction.reference} was auto-completed due to buyer verification timeout.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                processed['buyer_verification_timeout'] += 1
                logger.info(f"Auto-completed transaction {transaction.reference} due to buyer verification timeout")
                
        except Exception as e:
            logger.error(f"Error processing buyer verification timeout for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    # 5. Auto-release: After buyer verification (15 minutes delay)
    auto_release_transactions = P2PServiceTransaction.objects.filter(
        status='verifying',
        auto_release_at__lte=now,
        auto_release_at__isnull=False,
        buyer_verified=True,
        escrow_released=False
    )
    
    for transaction in auto_release_transactions:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
                
                # Release escrow based on listing type
                release_escrow_for_buy_listing(transaction, buyer_wallet, seller_wallet)
                
                transaction.status = 'completed'
                transaction.completed_at = now
                transaction.escrow_released = True
                transaction.escrow_released_at = now
                transaction.save()
                
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_COMPLETED',
                    title='Transaction Completed',
                    message=f'Transaction {transaction.reference} has been completed. Escrow {"refunded" if transaction.listing.listing_type == "buy" else "released to seller"}.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_COMPLETED',
                    title='Transaction Completed',
                    message=f'Transaction {transaction.reference} has been completed.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                processed['auto_released'] += 1
                logger.info(f"Auto-released escrow for transaction {transaction.reference}")
                
        except Exception as e:
            logger.error(f"Error auto-releasing escrow for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    # 6. Safety net: Completed transactions with unreleased escrow
    completed_unreleased = P2PServiceTransaction.objects.filter(
        status='completed',
        escrow_released=False,
        escrow_amount_cedis__gt=0
    )
    
    for transaction in completed_unreleased:
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
                
                # Release escrow based on listing type
                release_escrow_for_buy_listing(transaction, buyer_wallet, seller_wallet)
                
                transaction.escrow_released = True
                transaction.escrow_released_at = now
                transaction.save(update_fields=['escrow_released', 'escrow_released_at'])
                
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='auto_released',
                    performed_by=None,
                    notes=f'Escrow automatically released for completed transaction (safety net). Amount: ₵{transaction.escrow_amount_cedis}'
                )
                
                processed['safety_net_releases'] += 1
                logger.info(f"Safety net: Released escrow for completed transaction {transaction.reference}")
                
        except Exception as e:
            logger.error(f"Error in safety net release for {transaction.reference}: {str(e)}", exc_info=True)
            continue
    
    return processed

