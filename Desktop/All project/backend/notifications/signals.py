from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from orders.models import Order, GiftCardOrder
from wallets.models import CryptoTransaction, Deposit, Withdrawal
from kyc.models import KYCVerification
from .utils import create_notification

# Store old status before save
_status_cache = {}


@receiver(post_save, sender=Order)
def create_order_notification(sender, instance, created, **kwargs):
    if instance.status == 'COMPLETED':
        create_notification(
            user=instance.user,
            notification_type='ORDER_COMPLETED',
            title='Order Completed',
            message=f'Your {instance.order_type} order for {instance.currency_pair} has been completed.',
            related_object_type='order',
            related_object_id=instance.id,
        )
    elif instance.status == 'CANCELLED':
        create_notification(
            user=instance.user,
            notification_type='ORDER_CANCELLED',
            title='Order Cancelled',
            message=f'Your {instance.order_type} order for {instance.currency_pair} has been cancelled.',
            related_object_type='order',
            related_object_id=instance.id,
        )


@receiver(pre_save, sender=CryptoTransaction)
def cache_transaction_status(sender, instance, **kwargs):
    """Cache old status before save"""
    if instance.pk:
        try:
            old_instance = CryptoTransaction.objects.get(pk=instance.pk)
            _status_cache[instance.pk] = old_instance.status
        except CryptoTransaction.DoesNotExist:
            pass


@receiver(post_save, sender=CryptoTransaction)
def create_transaction_notification(sender, instance, created, **kwargs):
    """Create notifications when transaction is created or status changes"""
    if created:
        # Transaction just created - notify user
        create_notification(
            user=instance.user,
            notification_type='TRANSACTION_CREATED',
            title=f'Transaction {instance.type.capitalize()} Order Placed',
            message=f'Your {instance.type} order for {instance.crypto_id.upper()} ({instance.crypto_amount} {instance.crypto_id.upper()}) has been placed. Reference: {instance.reference}',
            related_object_type='transaction',
            related_object_id=instance.id,
        )
    elif not created and instance.pk in _status_cache:
        old_status = _status_cache.pop(instance.pk)
        if old_status != instance.status:
            if instance.status == 'completed':
                create_notification(
                    user=instance.user,
                    notification_type='TRANSACTION_APPROVED',
                    title='Transaction Approved',
                    message=f'Your {instance.type} transaction of {instance.cedis_amount} GHS has been approved and completed. Reference: {instance.reference}',
                    related_object_type='transaction',
                    related_object_id=instance.id,
                )
            elif instance.status == 'declined':
                create_notification(
                    user=instance.user,
                    notification_type='TRANSACTION_REJECTED',
                    title='Transaction Rejected',
                    message=f'Your {instance.type} transaction of {instance.cedis_amount} GHS has been rejected. Reference: {instance.reference}',
                    related_object_type='transaction',
                    related_object_id=instance.id,
                )


@receiver(pre_save, sender=GiftCardOrder)
def cache_giftcard_order_status(sender, instance, **kwargs):
    """Cache old status before save"""
    if instance.pk:
        try:
            old_instance = GiftCardOrder.objects.get(pk=instance.pk)
            _status_cache[f'giftcard_{instance.pk}'] = old_instance.status
        except GiftCardOrder.DoesNotExist:
            pass


@receiver(post_save, sender=GiftCardOrder)
def create_giftcard_order_notification(sender, instance, created, **kwargs):
    """Create notifications for gift card order status changes"""
    if created:
        # Order created
        create_notification(
            user=instance.user,
            notification_type='GIFT_CARD_ORDER_CREATED',
            title='Gift Card Order Created',
            message=f'Your {instance.order_type} order for {instance.card.name} (Amount: {instance.amount}) has been created.',
            related_object_type='gift_card_order',
            related_object_id=instance.id,
        )
    else:
        # Status changed
        cache_key = f'giftcard_{instance.pk}'
        if cache_key in _status_cache:
            old_status = _status_cache.pop(cache_key)
            if old_status != instance.status:
                if instance.status == 'approved':
                    create_notification(
                        user=instance.user,
                        notification_type='GIFT_CARD_ORDER_APPROVED',
                        title='Gift Card Order Approved',
                        message=f'Your {instance.order_type} order for {instance.card.name} has been approved.',
                        related_object_type='gift_card_order',
                        related_object_id=instance.id,
                    )
                elif instance.status == 'declined':
                    create_notification(
                        user=instance.user,
                        notification_type='GIFT_CARD_ORDER_DECLINED',
                        title='Gift Card Order Declined',
                        message=f'Your {instance.order_type} order for {instance.card.name} has been declined.',
                        related_object_type='gift_card_order',
                        related_object_id=instance.id,
                    )
                elif instance.status == 'completed':
                    create_notification(
                        user=instance.user,
                        notification_type='GIFT_CARD_ORDER_COMPLETED',
                        title='Gift Card Order Completed',
                        message=f'Your {instance.order_type} order for {instance.card.name} has been completed.',
                        related_object_type='gift_card_order',
                        related_object_id=instance.id,
                    )


# Store old status before save for KYC
_kyc_status_cache = {}


@receiver(pre_save, sender=KYCVerification)
def cache_kyc_status(sender, instance, **kwargs):
    """Cache old status before save"""
    if instance.pk:
        try:
            old_instance = KYCVerification.objects.get(pk=instance.pk)
            _kyc_status_cache[instance.pk] = old_instance.status
        except KYCVerification.DoesNotExist:
            pass


@receiver(post_save, sender=KYCVerification)
def create_kyc_notification(sender, instance, created, **kwargs):
    """Create notifications for KYC status changes"""
    if not created and instance.pk in _kyc_status_cache:
        old_status = _kyc_status_cache.pop(instance.pk)
        if old_status != instance.status:
            if instance.status == 'APPROVED':
                create_notification(
                    user=instance.user,
                    notification_type='KYC_APPROVED',
                    title='KYC Approved',
                    message='Your KYC verification has been approved. You now have full access to all platform features.',
                    related_object_type='kyc_verification',
                    related_object_id=instance.id,
                )
            elif instance.status == 'REJECTED':
                rejection_reason = instance.rejection_reason or 'Please check your documents and resubmit.'
                create_notification(
                    user=instance.user,
                    notification_type='KYC_REJECTED',
                    title='KYC Rejected',
                    message=f'Your KYC verification has been rejected. Reason: {rejection_reason}. Please review and resubmit your documents.',
                    related_object_type='kyc_verification',
                    related_object_id=instance.id,
                )


# Store old status before save for Deposits
_deposit_status_cache = {}


@receiver(pre_save, sender=Deposit)
def cache_deposit_status(sender, instance, **kwargs):
    """Cache old status before save"""
    if instance.pk:
        try:
            old_instance = Deposit.objects.get(pk=instance.pk)
            _deposit_status_cache[instance.pk] = old_instance.status
        except Deposit.DoesNotExist:
            pass


@receiver(post_save, sender=Deposit)
def create_deposit_notification(sender, instance, created, **kwargs):
    """Create notifications for deposit status changes"""
    if created:
        # Deposit just created - notify user
        create_notification(
            user=instance.user,
            notification_type='DEPOSIT_RECEIVED',
            title='Deposit Request Submitted',
            message=f'Your {instance.deposit_type} deposit request for {instance.amount if instance.deposit_type == "momo" else instance.crypto_amount} has been submitted and is awaiting admin confirmation.',
            related_object_type='deposit',
            related_object_id=instance.id,
        )
    elif not created and instance.pk in _deposit_status_cache:
        old_status = _deposit_status_cache.pop(instance.pk)
        if old_status != instance.status:
            if instance.status == 'approved':
                create_notification(
                    user=instance.user,
                    notification_type='DEPOSIT_APPROVED',
                    title='Deposit Approved',
                    message=f'Your {instance.deposit_type} deposit of {instance.amount if instance.deposit_type == "momo" else instance.crypto_amount} has been approved and credited to your wallet.',
                    related_object_type='deposit',
                    related_object_id=instance.id,
                )
            elif instance.status == 'rejected':
                rejection_reason = instance.admin_note or 'Please check your deposit details and resubmit.'
                create_notification(
                    user=instance.user,
                    notification_type='DEPOSIT_REJECTED',
                    title='Deposit Rejected',
                    message=f'Your {instance.deposit_type} deposit has been rejected. Reason: {rejection_reason}',
                    related_object_type='deposit',
                    related_object_id=instance.id,
                )


# Store old status before save for Withdrawals
_withdrawal_status_cache = {}


@receiver(pre_save, sender=Withdrawal)
def cache_withdrawal_status(sender, instance, **kwargs):
    """Cache old status before save"""
    if instance.pk:
        try:
            old_instance = Withdrawal.objects.get(pk=instance.pk)
            _withdrawal_status_cache[instance.pk] = old_instance.status
        except Withdrawal.DoesNotExist:
            pass


@receiver(post_save, sender=Withdrawal)
def create_withdrawal_notification(sender, instance, created, **kwargs):
    """Create notifications for withdrawal status changes"""
    if created:
        # Withdrawal just created - notify user
        create_notification(
            user=instance.user,
            notification_type='WITHDRAWAL_REQUESTED',
            title='Withdrawal Request Submitted',
            message=f'Your {instance.withdrawal_type} withdrawal request for {instance.amount if instance.withdrawal_type == "momo" else instance.crypto_amount} has been submitted and is awaiting admin confirmation.',
            related_object_type='withdrawal',
            related_object_id=instance.id,
        )
    elif not created and instance.pk in _withdrawal_status_cache:
        old_status = _withdrawal_status_cache.pop(instance.pk)
        if old_status != instance.status:
            if instance.status == 'approved':
                create_notification(
                    user=instance.user,
                    notification_type='WITHDRAWAL_APPROVED',
                    title='Withdrawal Approved',
                    message=f'Your {instance.withdrawal_type} withdrawal of {instance.amount if instance.withdrawal_type == "momo" else instance.crypto_amount} has been approved and will be processed shortly.',
                    related_object_type='withdrawal',
                    related_object_id=instance.id,
                )
            elif instance.status == 'rejected':
                rejection_reason = instance.admin_note or 'Please check your withdrawal details and resubmit.'
                create_notification(
                    user=instance.user,
                    notification_type='WITHDRAWAL_REJECTED',
                    title='Withdrawal Rejected',
                    message=f'Your {instance.withdrawal_type} withdrawal has been rejected. Reason: {rejection_reason}. Funds have been returned to your wallet.',
                    related_object_type='withdrawal',
                    related_object_id=instance.id,
                )
            elif instance.status == 'completed':
                transaction_id = instance.transaction_id or 'N/A'
                create_notification(
                    user=instance.user,
                    notification_type='WITHDRAWAL_COMPLETED',
                    title='Withdrawal Completed',
                    message=f'Your {instance.withdrawal_type} withdrawal has been completed. Transaction ID: {transaction_id}',
                    related_object_type='withdrawal',
                    related_object_id=instance.id,
                )

