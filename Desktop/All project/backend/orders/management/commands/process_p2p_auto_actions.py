"""
Management command to process auto-actions for P2P service transactions
This should be run periodically (e.g., every 5-10 minutes) via cron or scheduled task
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction
from orders.p2p_models import P2PServiceTransaction
from wallets.models import Wallet, WalletTransaction
from notifications.utils import create_notification
from orders.p2p_views import log_p2p_transaction_action
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process auto-actions for P2P service transactions (auto-releases after verification)'

    def handle(self, *args, **options):
        from orders.p2p_binance_refactor import process_auto_actions_enhanced
        
        processed = process_auto_actions_enhanced()
        
        # Summary
        total_processed = sum(processed.values())
        if total_processed > 0:
            summary_parts = []
            if processed.get('payment_timeout', 0) > 0:
                summary_parts.append(f"{processed['payment_timeout']} payment timeouts")
            if processed.get('seller_confirmation_timeout', 0) > 0:
                summary_parts.append(f"{processed['seller_confirmation_timeout']} seller confirmation timeouts")
            if processed.get('seller_response_timeout', 0) > 0:
                summary_parts.append(f"{processed['seller_response_timeout']} seller response timeouts")
            if processed.get('buyer_verification_timeout', 0) > 0:
                summary_parts.append(f"{processed['buyer_verification_timeout']} buyer verification timeouts")
            if processed.get('auto_released', 0) > 0:
                summary_parts.append(f"{processed['auto_released']} auto-releases")
            if processed.get('safety_net_releases', 0) > 0:
                summary_parts.append(f"{processed['safety_net_releases']} safety net releases")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully processed: {', '.join(summary_parts)}"
                )
            )
        else:
            self.stdout.write("No auto-actions to process")
