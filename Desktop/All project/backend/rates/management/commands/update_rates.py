"""
Management command to update crypto rates
"""
from django.core.management.base import BaseCommand
from rates.tasks import update_crypto_rates


class Command(BaseCommand):
    help = 'Update crypto rates from CoinGecko API'

    def handle(self, *args, **options):
        self.stdout.write('Fetching crypto rates from CoinGecko...')
        
        result = update_crypto_rates()
        
        if result['status'] == 'success':
            self.stdout.write(
                self.style.SUCCESS(f"✓ {result['message']}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ {result['message']}")
            )
