"""
Django signals for wallet operations
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Deposit, Withdrawal, Wallet, WalletTransaction
from notifications.utils import create_notification
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Deposit)
def handle_deposit_status_change(sender, instance, created, **kwargs):
    """
    Handle deposit status changes and ensure wallet is properly credited
    - Approved: Credit wallet
    - Rejected: No wallet action needed (deposit was never credited)
    """
    # Skip on creation
    if created:
        return
    
    # Only process approved deposits
    if instance.status != 'approved':
        return
    
    # Check if this deposit already has a wallet transaction
    existing_transaction = WalletTransaction.objects.filter(
        reference=instance.reference,
        transaction_type='deposit',
        status='completed'
    ).first()
    
    if existing_transaction:
        # Already processed, skip
        logger.debug(f"Deposit {instance.reference} already has transaction, skipping signal")
        return
    
    # Process even if reviewed_by/reviewed_at are not set (some approval paths might skip this)
    # The key check is: status='approved' and no existing transaction
    
    try:
        with transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(user=instance.user)
            balance_before = wallet.balance_cedis
            
            if instance.deposit_type == 'momo':
                amount = instance.amount
                if amount <= 0:
                    logger.warning(f"Deposit {instance.reference} has invalid amount: {amount}")
                    return
                wallet.add_cedis(amount)
                wallet.refresh_from_db()
                balance_after = wallet.balance_cedis
            else:
                # For crypto deposits, we need the rate - skip if not available
                # The approval action should handle this
                logger.debug(f"Skipping crypto deposit {instance.reference} in signal - approval action should handle")
                return
            
            # Create wallet transaction if it doesn't exist
            WalletTransaction.objects.get_or_create(
                reference=instance.reference,
                defaults={
                    'wallet': wallet,
                    'transaction_type': 'deposit',
                    'amount': amount,
                    'currency': 'cedis',
                    'status': 'completed',
                    'description': f"Deposit via {instance.deposit_type}. Ref: {instance.reference}. Auto-credited via signal.",
                    'balance_before': balance_before,
                    'balance_after': balance_after
                }
            )
            
            logger.info(f"✅ Auto-credited deposit {instance.reference} via signal. Amount: {amount}, Balance: {balance_before} -> {balance_after}")
    except Exception as e:
        logger.error(f"❌ Error in deposit signal handler for {instance.reference}: {str(e)}", exc_info=True)


@receiver(post_save, sender=Withdrawal)
def handle_withdrawal_status_change(sender, instance, created, **kwargs):
    """
    Handle withdrawal status changes and ensure escrow is properly managed
    - Approved: Deduct from escrow
    - Rejected: Release escrow back to balance
    - Completed: Verify escrow was already deducted (no action needed)
    """
    # Skip on creation
    if created:
        logger.debug(f"Withdrawal {instance.reference} created, skipping signal")
        return
    
    # Process both MoMo and crypto withdrawals
    # Both use escrow now (platform is fiat-only, crypto withdrawals convert cedis to crypto)
    if instance.withdrawal_type == 'crypto':
        # Handle crypto withdrawal escrow management (same as MoMo)
        # Check if escrow lock exists
        escrow_lock = WalletTransaction.objects.filter(
            reference=instance.reference,
            transaction_type='escrow_lock',
            status='completed'
        ).first()
        
        if not escrow_lock:
            logger.debug(f"Crypto withdrawal {instance.reference} has no escrow lock, skipping signal")
            return
        
        try:
            with transaction.atomic():
                wallet, _ = Wallet.objects.get_or_create(user=instance.user)
                total_amount = instance.total_amount  # Total amount (cedis_amount + fee)
                
                if total_amount <= 0:
                    logger.warning(f"Crypto withdrawal {instance.reference} has invalid total_amount: {total_amount}")
                    return
                
                if instance.status == 'approved':
                    # Check if escrow was already deducted
                    existing_withdraw = WalletTransaction.objects.filter(
                        reference__startswith=instance.reference,
                        transaction_type='withdraw',
                        currency='cedis',
                        status='completed'
                    ).first()
                    
                    if existing_withdraw:
                        logger.debug(f"Crypto withdrawal {instance.reference} already has withdraw transaction, skipping signal")
                        return
                    
                    # Deduct from escrow
                    if wallet.escrow_balance < total_amount:
                        logger.error(f"Insufficient escrow balance for crypto withdrawal {instance.reference}. Escrow: {wallet.escrow_balance}, Total Amount: {total_amount}")
                        return
                    
                    escrow_before = wallet.escrow_balance
                    wallet.deduct_from_escrow(total_amount)
                    wallet.refresh_from_db()
                    escrow_after = wallet.escrow_balance
                    
                    # Create wallet transaction
                    import uuid
                    unique_ref = f"{instance.reference}-{uuid.uuid4().hex[:8]}"
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='withdraw',
                        amount=total_amount,
                        currency='cedis',
                        status='completed',
                        reference=unique_ref,
                        description=f"Crypto withdrawal approved: {instance.crypto_amount} {instance.crypto_id.upper()} sent (₵{instance.amount:.2f} + ₵{instance.fee:.2f} fee = ₵{total_amount:.2f} deducted). Ref: {instance.reference}. Auto-deducted via signal.",
                        balance_before=wallet.balance_cedis + escrow_before,
                        balance_after=wallet.balance_cedis + escrow_after
                    )
                    logger.info(f"✅ Auto-deducted escrow for crypto withdrawal {instance.reference} via signal. Total: {total_amount}, Escrow: {escrow_before} -> {escrow_after}")
                
                elif instance.status == 'rejected':
                    # Check if escrow was already released
                    existing_release = WalletTransaction.objects.filter(
                        reference__startswith=instance.reference,
                        transaction_type='escrow_release',
                        status='completed'
                    ).first()
                    
                    if existing_release:
                        logger.debug(f"Crypto withdrawal {instance.reference} already has escrow release transaction, skipping signal")
                        return
                    
                    # Release from escrow back to balance
                    if wallet.escrow_balance < total_amount:
                        logger.error(f"Insufficient escrow balance to release for crypto withdrawal {instance.reference}. Escrow: {wallet.escrow_balance}, Total Amount: {total_amount}")
                        return
                    
                    balance_before = wallet.balance_cedis
                    escrow_before = wallet.escrow_balance
                    wallet.release_cedis_from_escrow(total_amount)
                    wallet.refresh_from_db()
                    balance_after = wallet.balance_cedis
                    escrow_after = wallet.escrow_balance
                    
                    # Create escrow release transaction with unique reference
                    import uuid
                    unique_ref = f"{instance.reference}-RELEASE-{uuid.uuid4().hex[:8]}"
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='escrow_release',
                        amount=total_amount,
                        currency='cedis',
                        status='completed',
                        reference=unique_ref,
                        description=f"Crypto withdrawal rejected, funds released from escrow: {instance.amount:.2f} + {instance.fee:.2f} fee = {total_amount:.2f} cedis. Ref: {instance.reference}. Auto-released via signal.",
                        balance_before=balance_before,
                        balance_after=balance_after
                    )
                    logger.info(f"✅ Auto-released escrow for rejected crypto withdrawal {instance.reference} via signal. Total: {total_amount}, Escrow: {escrow_before} -> {escrow_after}, Balance: {balance_before} -> {balance_after}")
        except Exception as e:
            logger.error(f"❌ Error in crypto withdrawal signal handler for {instance.reference}: {str(e)}", exc_info=True)
        
        return  # Exit early for crypto withdrawals
    
    # Continue with MoMo withdrawal logic (escrow handling)
    
    # Log status change for debugging
    logger.debug(f"Withdrawal {instance.reference} status changed to: {instance.status}")
    
    # Check if escrow lock exists
    escrow_lock = WalletTransaction.objects.filter(
        reference=instance.reference,
        transaction_type='escrow_lock',
        status='completed'
    ).first()
    
    if not escrow_lock:
        # No escrow lock found, skip
        logger.debug(f"Withdrawal {instance.reference} has no escrow lock, skipping signal")
        return
    
    try:
        with transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(user=instance.user)
            total_amount = instance.total_amount  # Total amount (amount + fee)
            
            if total_amount <= 0:
                logger.warning(f"Withdrawal {instance.reference} has invalid total_amount: {total_amount}")
                return
            
            # Handle APPROVED status - Deduct from escrow
            if instance.status == 'approved':
                # Check if escrow was already deducted
                existing_withdraw = WalletTransaction.objects.filter(
                    reference__startswith=instance.reference,
                    transaction_type='withdraw',
                    currency='cedis',
                    status='completed'
                ).first()
                
                if existing_withdraw:
                    # Already processed, skip
                    logger.debug(f"Withdrawal {instance.reference} already has transaction, skipping signal")
                    return
                
                escrow_before = wallet.escrow_balance
                
                # Deduct from escrow
                if wallet.escrow_balance < total_amount:
                    logger.error(f"Insufficient escrow balance for withdrawal {instance.reference}. Escrow: {wallet.escrow_balance}, Total Amount: {total_amount}")
                    return
                
                wallet.deduct_from_escrow(total_amount)
                wallet.refresh_from_db()
                escrow_after = wallet.escrow_balance
                
                # Create wallet transaction if it doesn't exist
                import uuid
                unique_ref = f"{instance.reference}-{uuid.uuid4().hex[:8]}"
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='withdraw',
                    amount=total_amount,
                    currency='cedis',
                    status='completed',
                    reference=unique_ref,
                    description=f"Withdrawal via MoMo to {instance.momo_number}: ₵{instance.amount:.2f} + ₵{instance.fee:.2f} fee = ₵{total_amount:.2f}. Ref: {instance.reference}. Auto-deducted via signal.",
                    balance_before=wallet.balance_cedis + escrow_before,
                    balance_after=wallet.balance_cedis + escrow_after
                )
                
                logger.info(f"✅ Auto-deducted escrow for withdrawal {instance.reference} via signal. Total: {total_amount}, Escrow: {escrow_before} -> {escrow_after}")
            
            # Handle REJECTED status - Release escrow back to balance
            elif instance.status == 'rejected':
                logger.info(f"Processing rejected withdrawal {instance.reference} in signal")
                
                # Check if escrow was already released (check by reference pattern, not exact match)
                # Since we use unique refs, check if any escrow_release exists for this withdrawal
                existing_release = WalletTransaction.objects.filter(
                    reference__startswith=instance.reference,
                    transaction_type='escrow_release',
                    status='completed'
                ).first()
                
                if existing_release:
                    # Already processed, skip
                    logger.debug(f"Withdrawal {instance.reference} already has escrow release transaction ({existing_release.reference}), skipping signal")
                    return
                
                escrow_before = wallet.escrow_balance
                balance_before = wallet.balance_cedis
                
                # Release from escrow back to balance
                if wallet.escrow_balance < total_amount:
                    logger.error(f"Insufficient escrow balance to release for withdrawal {instance.reference}. Escrow: {wallet.escrow_balance}, Total Amount: {total_amount}")
                    return
                
                wallet.release_cedis_from_escrow(total_amount)
                wallet.refresh_from_db()
                escrow_after = wallet.escrow_balance
                balance_after = wallet.balance_cedis
                
                # Create wallet transaction if it doesn't exist
                # Check if escrow release transaction already exists (use startswith since we use unique refs)
                existing_release_txn = WalletTransaction.objects.filter(
                    reference__startswith=instance.reference,
                    transaction_type='escrow_release'
                ).first()
                
                if not existing_release_txn:
                    # Create new transaction with unique reference
                    import uuid
                    unique_ref = f"{instance.reference}-{uuid.uuid4().hex[:8]}"
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='escrow_release',
                        amount=total_amount,
                        currency='cedis',
                        status='completed',
                        reference=unique_ref,
                        description=f"Withdrawal rejected, funds released from escrow: ₵{instance.amount:.2f} + ₵{instance.fee:.2f} fee = ₵{total_amount:.2f}. Ref: {instance.reference}. Auto-released via signal.",
                        balance_before=balance_before,
                        balance_after=balance_after
                    )
                elif existing_release_txn.status != 'completed':
                    # Update existing pending transaction to completed
                    existing_release_txn.status = 'completed'
                    existing_release_txn.balance_before = balance_before
                    existing_release_txn.balance_after = balance_after
                    existing_release_txn.save()
                
                logger.info(f"✅ Auto-released escrow for rejected withdrawal {instance.reference} via signal. Total: {total_amount}, Escrow: {escrow_before} -> {escrow_after}, Balance: {balance_before} -> {balance_after}")
            
            # Handle COMPLETED status - Just verify escrow was deducted (no action needed)
            elif instance.status == 'completed':
                # Verify escrow was deducted
                existing_withdraw = WalletTransaction.objects.filter(
                    reference=instance.reference,
                    transaction_type='withdraw',
                    status='completed'
                ).first()
                
                if not existing_withdraw:
                    logger.warning(f"Withdrawal {instance.reference} marked as completed but no withdraw transaction found. Escrow may not have been deducted.")
                else:
                    logger.debug(f"Withdrawal {instance.reference} completed - escrow already deducted")
    
    except ValidationError as e:
        logger.error(f"❌ Validation error in withdrawal signal handler for {instance.reference}: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error in withdrawal signal handler for {instance.reference}: {str(e)}", exc_info=True)

