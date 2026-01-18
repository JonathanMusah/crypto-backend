"""
Celery app configuration
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('crypto_platform')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'update-crypto-rates-every-15-seconds': {
        'task': 'rates.update_crypto_rates',
        'schedule': 15.0,  # Every 15 seconds
    },
    'cleanup-old-rates-every-hour': {
        'task': 'rates.cleanup_old_rates',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-expired-cache-every-5-minutes': {
        'task': 'rates.cleanup_expired_cache',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # ✅ FIX #3: Transaction timeout processing
    'process-transaction-timeouts-every-5-minutes': {
        'task': 'orders.tasks.process_transaction_timeouts',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes - checks for timeouts
    },
    'send-transaction-reminders-every-10-minutes': {
        'task': 'orders.tasks.send_transaction_reminders',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes - sends reminders 1 hour before deadline
    },
    'cleanup-expired-transactions-daily': {
        'task': 'orders.tasks.cleanup_expired_temp_data',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM UTC
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
