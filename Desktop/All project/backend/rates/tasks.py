"""
Celery tasks for crypto rate updates
"""
from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging

from .models import CryptoRate, RateCache
from .services import get_coingecko_service

logger = logging.getLogger(__name__)


@shared_task(name='rates.update_crypto_rates')
def update_crypto_rates():
    """
    Periodic task to update crypto rates from CoinGecko
    Runs every 15 seconds
    """
    logger.info("Starting crypto rate update task")
    
    try:
        # Get CoinGecko service
        service = get_coingecko_service()
        
        # Fetch live rates
        rates_data = service.get_live_rates()
        
        if not rates_data:
            logger.warning("No rates data received from CoinGecko")
            return {
                'status': 'failed',
                'message': 'No data received',
                'count': 0
            }
        
        # Save rates to database
        created_count = 0
        for rate_data in rates_data:
            try:
                rate = CryptoRate.objects.create(
                    crypto_id=rate_data['crypto_id'],
                    symbol=rate_data['symbol'],
                    usd_price=rate_data['usd_price'],
                    cedis_price=rate_data['cedis_price'],
                    usd_to_cedis_rate=rate_data['usd_to_cedis_rate'],
                    market_cap=rate_data.get('market_cap'),
                    volume_24h=rate_data.get('volume_24h'),
                    price_change_24h=rate_data.get('price_change_24h'),
                    price_change_percentage_24h=rate_data.get('price_change_percentage_24h'),
                    timestamp=timezone.now(),
                    is_active=True
                )
                created_count += 1
                
                # Update cache (convert Decimals to float for JSON serialization)
                cache_key = f"rate:{rate_data['crypto_id']}"
                cache_data = {
                    k: float(v) if isinstance(v, Decimal) else v 
                    for k, v in rate_data.items()
                }
                try:
                    RateCache.set_cached(cache_key, cache_data, ttl_seconds=15)
                except Exception as cache_error:
                    logger.warning(f"Cache error for {rate_data['crypto_id']}: {cache_error}")
                
            except Exception as e:
                logger.error(f"Error saving rate for {rate_data.get('crypto_id')}: {e}")
        
        logger.info(f"Successfully updated {created_count} crypto rates")
        
        # Clean old rates (keep last 1000 per crypto) - async if possible
        try:
            cleanup_old_rates.delay()
        except Exception:
            # If Celery/Redis not available, skip async cleanup
            pass
        
        return {
            'status': 'success',
            'message': f'Updated {created_count} rates',
            'count': created_count
        }
        
    except Exception as e:
        logger.error(f"Error in update_crypto_rates task: {e}")
        return {
            'status': 'failed',
            'message': str(e),
            'count': 0
        }


@shared_task(name='rates.cleanup_old_rates')
def cleanup_old_rates():
    """
    Cleanup old rate records to prevent database bloat
    Keep last 1000 records per crypto
    """
    logger.info("Starting cleanup of old crypto rates")
    
    try:
        deleted_count = 0
        
        for crypto_id, _ in CryptoRate.CRYPTO_CHOICES:
            # Get IDs to keep (last 1000)
            ids_to_keep = CryptoRate.objects.filter(
                crypto_id=crypto_id
            ).values_list('id', flat=True)[:1000]
            
            # Delete old records
            deleted = CryptoRate.objects.filter(
                crypto_id=crypto_id
            ).exclude(id__in=list(ids_to_keep)).delete()
            
            deleted_count += deleted[0]
        
        logger.info(f"Cleaned up {deleted_count} old rate records")
        
        return {
            'status': 'success',
            'deleted': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_rates task: {e}")
        return {
            'status': 'failed',
            'message': str(e)
        }


@shared_task(name='rates.cleanup_expired_cache')
def cleanup_expired_cache():
    """
    Remove expired cache entries
    """
    logger.info("Starting cleanup of expired cache")
    
    try:
        deleted = RateCache.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        logger.info(f"Cleaned up {deleted[0]} expired cache entries")
        
        return {
            'status': 'success',
            'deleted': deleted[0]
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_cache task: {e}")
        return {
            'status': 'failed',
            'message': str(e)
        }
