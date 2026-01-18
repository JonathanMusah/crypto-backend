from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from django.core.cache import cache
from decimal import Decimal
import logging

from .models import CryptoRate, RateCache
from .serializers import (
    CryptoRateSerializer,
    ConvertCryptoSerializer,
    BuyCryptoSerializer,
    SellCryptoSerializer
)
from .services import get_coingecko_service
from wallets.models import Wallet, WalletTransaction, CryptoTransaction

logger = logging.getLogger(__name__)


class CryptoRateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for crypto rates
    Provides read-only access to live crypto rates
    """
    queryset = CryptoRate.objects.filter(is_active=True)
    serializer_class = CryptoRateSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Get latest rates for each crypto"""
        queryset = CryptoRate.objects.filter(is_active=True)
        
        # Filter by crypto_id if provided
        crypto_id = self.request.query_params.get('crypto_id')
        if crypto_id:
            queryset = queryset.filter(crypto_id=crypto_id)
        
        # Get only the latest rate for each crypto
        latest_rates = []
        seen_cryptos = set()
        
        for rate in queryset:
            if rate.crypto_id not in seen_cryptos:
                latest_rates.append(rate.id)
                seen_cryptos.add(rate.crypto_id)
        
        return CryptoRate.objects.filter(id__in=latest_rates)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def latest(self, request):
        """Get latest rates for all supported cryptos"""
        # Try to get from cache first
        cache_key = 'crypto_rates_latest'
        cached_rates = cache.get(cache_key)
        
        if cached_rates:
            return Response(cached_rates)
        
        latest_rates = CryptoRate.get_all_latest_rates()
        
        if not latest_rates:
            # Try to fetch from API if no rates in DB
            service = get_coingecko_service()
            rates_data = service.get_live_rates()
            
            if rates_data:
                # Save to database
                for rate_data in rates_data:
                    CryptoRate.objects.create(**rate_data)
                
                # Fetch again
                latest_rates = CryptoRate.get_all_latest_rates()
        
        serializer = self.get_serializer(list(latest_rates.values()), many=True)
        response_data = serializer.data
        
        # Cache for 5 minutes
        cache.set(cache_key, response_data, 300)
        
        return Response(response_data)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def convert(self, request):
        """
        Convert between crypto and cedis
        POST /api/rates/convert/
        {
            "crypto_id": "bitcoin",
            "amount": 1.5,
            "direction": "crypto_to_cedis"  // or "cedis_to_crypto"
        }
        """
        serializer = ConvertCryptoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        crypto_id = serializer.validated_data['crypto_id']
        amount = serializer.validated_data['amount']
        direction = serializer.validated_data['direction']
        
        # Try to get rate from cache first
        cache_key = f"crypto_rate_{crypto_id}"
        rate = cache.get(cache_key)
        
        if not rate:
            # Get from database
            rate = CryptoRate.get_latest_rate(crypto_id)
            
            if not rate:
                # Try to fetch from API
                service = get_coingecko_service()
                rate_data = service.get_single_rate(crypto_id)
                
                if rate_data:
                    rate = CryptoRate.objects.create(**rate_data)
                    # Cache for 5 minutes
                    cache.set(cache_key, rate, 300)
                else:
                    return Response(
                        {'error': 'Unable to fetch rate for this cryptocurrency'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
            else:
                # Cache for 5 minutes
                cache.set(cache_key, rate, 300)
        
        # Calculate conversion
        if direction == 'crypto_to_cedis':
            result = amount * rate.cedis_price
            result_currency = 'cedis'
        else:  # cedis_to_crypto
            if rate.cedis_price > 0:
                result = amount / rate.cedis_price
                result_currency = 'crypto'
            else:
                return Response(
                    {'error': 'Invalid rate'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response({
            'crypto_id': crypto_id,
            'symbol': rate.symbol,
            'input_amount': float(amount),
            'input_currency': 'crypto' if direction == 'crypto_to_cedis' else 'cedis',
            'output_amount': float(result),
            'output_currency': result_currency,
            'rate_cedis': float(rate.cedis_price),
            'rate_usd': float(rate.usd_price),
            'timestamp': rate.timestamp
        })


class CryptoTradingViewSet(viewsets.ViewSet):
    """
    ViewSet for crypto trading operations (buy/sell)
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def buy(self, request):
        """
        Buy crypto endpoint
        POST /api/crypto/buy/
        {
            "crypto_id": "bitcoin",
            "cedis_amount": 500.00
        }
        """
        serializer = BuyCryptoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        crypto_id = serializer.validated_data['crypto_id']
        cedis_amount = serializer.validated_data['cedis_amount']
        
        # Try to get rate from cache first
        cache_key = f"crypto_rate_{crypto_id}"
        rate = cache.get(cache_key)
        
        if not rate:
            # Get latest rate
            rate = CryptoRate.get_latest_rate(crypto_id)
            
            if not rate:
                # Try to fetch from API
                service = get_coingecko_service()
                rate_data = service.get_single_rate(crypto_id)
                
                if rate_data:
                    rate = CryptoRate.objects.create(**rate_data)
                    # Cache for 5 minutes
                    cache.set(cache_key, rate, 300)
                else:
                    return Response(
                        {'error': 'Unable to fetch rate for this cryptocurrency'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
            else:
                # Cache for 5 minutes
                cache.set(cache_key, rate, 300)
        
        # Calculate crypto amount
        crypto_amount = cedis_amount / rate.cedis_price
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        # Check sufficient balance
        if not wallet.has_sufficient_cedis(cedis_amount):
            return Response(
                {'error': 'Insufficient cedis balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Lock cedis to escrow
                wallet.lock_cedis_to_escrow(cedis_amount)
                
                # Create crypto transaction
                crypto_txn = CryptoTransaction.objects.create(
                    user=request.user,
                    type='buy',
                    cedis_amount=cedis_amount,
                    crypto_amount=crypto_amount,
                    rate=rate.cedis_price,
                    status='pending',
                    payment_method='wallet',
                    reference=CryptoTransaction.generate_reference('BUY'),
                    escrow_locked=True
                )
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='escrow_lock',
                    amount=cedis_amount,
                    currency='cedis',
                    status='completed',
                    reference=crypto_txn.reference,
                    description=f"Buy {rate.symbol}: {crypto_amount} {rate.symbol} at ₵{rate.cedis_price}",
                    balance_before=wallet.balance_cedis + cedis_amount,
                    balance_after=wallet.balance_cedis
                )
                
                return Response({
                    'message': 'Buy order created successfully. Pending admin approval.',
                    'transaction': {
                        'reference': crypto_txn.reference,
                        'crypto_id': crypto_id,
                        'symbol': rate.symbol,
                        'cedis_amount': float(cedis_amount),
                        'crypto_amount': float(crypto_amount),
                        'rate': float(rate.cedis_price),
                        'status': 'pending',
                        'escrow_locked': True
                    },
                    'wallet': {
                        'balance_cedis': float(wallet.balance_cedis),
                        'balance_crypto': float(wallet.balance_crypto),
                        'escrow_balance': float(wallet.escrow_balance)
                    }
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in buy crypto: {e}")
            return Response(
                {'error': 'An error occurred processing your request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def sell(self, request):
        """
        Sell crypto endpoint
        POST /api/crypto/sell/
        {
            "crypto_id": "bitcoin",
            "crypto_amount": 0.01
        }
        """
        serializer = SellCryptoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        crypto_id = serializer.validated_data['crypto_id']
        crypto_amount = serializer.validated_data['crypto_amount']
        
        # Try to get rate from cache first
        cache_key = f"crypto_rate_{crypto_id}"
        rate = cache.get(cache_key)
        
        if not rate:
            # Get latest rate
            rate = CryptoRate.get_latest_rate(crypto_id)
            
            if not rate:
                # Try to fetch from API
                service = get_coingecko_service()
                rate_data = service.get_single_rate(crypto_id)
                
                if rate_data:
                    rate = CryptoRate.objects.create(**rate_data)
                    # Cache for 5 minutes
                    cache.set(cache_key, rate, 300)
                else:
                    return Response(
                        {'error': 'Unable to fetch rate for this cryptocurrency'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
            else:
                # Cache for 5 minutes
                cache.set(cache_key, rate, 300)
        
        # Calculate cedis amount
        cedis_amount = crypto_amount * rate.cedis_price
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        # Check sufficient crypto balance
        if not wallet.has_sufficient_crypto(crypto_amount):
            return Response(
                {'error': 'Insufficient crypto balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Deduct crypto from wallet
                wallet.deduct_crypto(crypto_amount)
                
                # Create crypto transaction
                crypto_txn = CryptoTransaction.objects.create(
                    user=request.user,
                    type='sell',
                    cedis_amount=cedis_amount,
                    crypto_amount=crypto_amount,
                    rate=rate.cedis_price,
                    status='pending',
                    payment_method='crypto',
                    reference=CryptoTransaction.generate_reference('SELL'),
                    escrow_locked=True
                )
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='crypto_sell',
                    amount=crypto_amount,
                    currency='crypto',
                    status='pending',
                    reference=crypto_txn.reference,
                    description=f"Sell {rate.symbol}: {crypto_amount} {rate.symbol} at ₵{rate.cedis_price}",
                    balance_before=wallet.balance_crypto + crypto_amount,
                    balance_after=wallet.balance_crypto
                )
                
                return Response({
                    'message': 'Sell order created successfully. Pending admin approval.',
                    'transaction': {
                        'reference': crypto_txn.reference,
                        'crypto_id': crypto_id,
                        'symbol': rate.symbol,
                        'cedis_amount': float(cedis_amount),
                        'crypto_amount': float(crypto_amount),
                        'rate': float(rate.cedis_price),
                        'status': 'pending',
                        'escrow_locked': True
                    },
                    'wallet': {
                        'balance_cedis': float(wallet.balance_cedis),
                        'balance_crypto': float(wallet.balance_crypto),
                        'escrow_balance': float(wallet.escrow_balance)
                    }
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in sell crypto: {e}")
            return Response(
                {'error': 'An error occurred processing your request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )