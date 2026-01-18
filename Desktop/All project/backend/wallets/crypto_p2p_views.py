"""
Crypto P2P Trading API Views - Binance-Style Peer-to-Peer Crypto Trading
Complete endpoints for listing creation, transaction management, and verification
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal
import logging

from wallets.models import Wallet
from wallets.crypto_p2p_models import (
    CryptoListing,
    CryptoP2PTransaction,
    CryptoTransactionAuditLog,
    CryptoTransactionDispute,
)
from wallets.crypto_p2p_serializers import (
    CryptoListingSerializer,
    CryptoListingDetailSerializer,
    CryptoTransactionSerializer,
    CreateCryptoTransactionSerializer,
    MarkPaymentSentSerializer,
    ConfirmPaymentSerializer,
    SendCryptoSerializer,
    VerifyCryptoSerializer,
    CryptoTransactionAuditLogSerializer,
    CryptoTransactionDisputeSerializer,
    CryptoListingSearchSerializer,
)

logger = logging.getLogger(__name__)


def log_audit_action(transaction, action, performed_by, notes='', metadata=None):
    """
    Log transaction action to audit trail with HMAC signature
    """
    import hashlib
    import hmac
    from django.conf import settings
    
    audit_log = CryptoTransactionAuditLog.objects.create(
        transaction=transaction,
        action=action,
        performed_by=performed_by,
        notes=notes,
        metadata=metadata or {}
    )
    
    # Create HMAC signature for integrity
    log_string = f"{audit_log.id}|{transaction.id}|{action}|{performed_by.id if performed_by else 'system'}|{audit_log.created_at}"
    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        log_string.encode(),
        hashlib.sha256
    ).hexdigest()
    audit_log.signature = signature
    audit_log.save()
    
    return audit_log


class CryptoListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Crypto Listings - Buy/Sell listings for crypto trading
    
    Endpoints:
    - GET /api/crypto/listings/ - List all active listings
    - POST /api/crypto/listings/ - Create new listing (seller only)
    - GET /api/crypto/listings/{id}/ - Get listing details
    - PUT /api/crypto/listings/{id}/ - Update listing
    - DELETE /api/crypto/listings/{id}/ - Cancel listing
    - GET /api/crypto/listings/search/ - Search listings
    """
    
    queryset = CryptoListing.objects.filter(status='active')
    serializer_class = CryptoListingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'crypto_type', 'seller__email']
    ordering_fields = ['rate_cedis_per_crypto', 'created_at', 'views_count']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CryptoListingDetailSerializer
        elif self.action == 'search':
            return CryptoListingSearchSerializer
        return CryptoListingSerializer
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return CryptoListing.objects.all()
        return CryptoListing.objects.filter(status='active')
    
    def perform_create(self, serializer):
        """Create new crypto listing"""
        listing = serializer.save(seller=self.request.user, status='under_review')
        logger.info(f"Created crypto listing: {listing.reference} by {self.request.user.email}")
    
    def perform_update(self, serializer):
        """Update crypto listing"""
        listing = serializer.save()
        logger.info(f"Updated crypto listing: {listing.reference}")
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_listings(self, request):
        """Get current user's crypto listings"""
        listings = CryptoListing.objects.filter(seller=request.user)
        serializer = self.get_serializer(listings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def search(self, request):
        """Search crypto listings with filters"""
        serializer = CryptoListingSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        queryset = self.get_queryset()
        
        # Apply filters
        if serializer.validated_data.get('crypto_type'):
            queryset = queryset.filter(crypto_type=serializer.validated_data['crypto_type'])
        
        if serializer.validated_data.get('listing_type'):
            queryset = queryset.filter(listing_type=serializer.validated_data['listing_type'])
        
        if serializer.validated_data.get('min_rate'):
            queryset = queryset.filter(
                rate_cedis_per_crypto__gte=serializer.validated_data['min_rate']
            )
        
        if serializer.validated_data.get('max_rate'):
            queryset = queryset.filter(
                rate_cedis_per_crypto__lte=serializer.validated_data['max_rate']
            )
        
        # Apply ordering
        ordering = serializer.validated_data.get('ordering', 'newest')
        if ordering == 'rate_asc':
            queryset = queryset.order_by('rate_cedis_per_crypto')
        elif ordering == 'rate_desc':
            queryset = queryset.order_by('-rate_cedis_per_crypto')
        elif ordering == 'oldest':
            queryset = queryset.order_by('created_at')
        else:  # newest
            queryset = queryset.order_by('-created_at')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel a crypto listing"""
        listing = self.get_object()
        
        if listing.seller != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Only the seller can cancel this listing'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        listing.status = 'cancelled'
        listing.save()
        
        logger.info(f"Cancelled crypto listing: {listing.reference}")
        return Response({'message': 'Listing cancelled successfully'})


class CryptoTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Crypto Transactions - Binance-style P2P transaction flow
    
    Endpoints:
    - POST /api/crypto/transactions/ - Buyer initiates transaction (escrow locked)
    - GET /api/crypto/transactions/{id}/ - Get transaction details
    - POST /api/crypto/transactions/{id}/mark_paid/ - Buyer marks payment sent
    - POST /api/crypto/transactions/{id}/confirm_payment/ - Seller confirms payment
    - POST /api/crypto/transactions/{id}/send_crypto/ - Seller sends crypto
    - POST /api/crypto/transactions/{id}/verify/ - Buyer verifies crypto received
    - GET /api/crypto/transactions/my_transactions/ - Get user's transactions
    """
    
    queryset = CryptoP2PTransaction.objects.all()
    serializer_class = CryptoTransactionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return CryptoP2PTransaction.objects.all()
        return (CryptoP2PTransaction.objects.filter(
            buyer=user) | CryptoP2PTransaction.objects.filter(seller=user)
        ).distinct()
    
    def create(self, request, *args, **kwargs):
        """
        Buyer initiates crypto transaction
        - Escrow locked atomically
        - Payment deadline set (15 minutes)
        - Transaction created with status='payment_received'
        """
        serializer = CreateCryptoTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        listing = serializer.validated_data['listing']
        amount_crypto = serializer.validated_data['amount_crypto']
        buyer_wallet_address = serializer.validated_data['buyer_wallet_address']
        buyer_payment_details = serializer.validated_data['buyer_payment_details']
        
        # Validate listing
        if listing.status != 'active':
            return Response(
                {'error': 'This listing is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if listing.listing_type == 'sell':
            # Buyer is purchasing crypto from seller
            seller = listing.seller
            rate = listing.rate_cedis_per_crypto
        else:
            # Seller is selling crypto to buyer (this shouldn't happen here)
            return Response(
                {'error': 'Cannot initiate transaction on buy listing'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate amounts
        amount_cedis = amount_crypto * rate
        
        # Atomic transaction: Lock escrow before creating transaction
        try:
            with db_transaction.atomic():
                # Get buyer's wallet with row-level locking
                buyer_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=request.user)
                
                # Check sufficient balance
                if buyer_wallet.cedis_balance < amount_cedis:
                    return Response(
                        {'error': f'Insufficient balance. Need ₵{amount_cedis}, have ₵{buyer_wallet.cedis_balance}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Lock cedis to escrow atomically
                buyer_wallet.lock_cedis_to_escrow_atomic(amount_cedis)
                
                # Create transaction
                crypto_transaction = CryptoP2PTransaction.objects.create(
                    listing=listing,
                    buyer=request.user,
                    seller=seller,
                    amount_crypto=amount_crypto,
                    amount_cedis=amount_cedis,
                    rate_applied=rate,
                    escrow_locked=True,
                    escrow_amount_cedis=amount_cedis,
                    buyer_wallet_address=buyer_wallet_address,
                    buyer_payment_details=buyer_payment_details,
                    status='payment_received',
                    payment_deadline=timezone.now() + timedelta(minutes=15),
                    risk_score=Decimal('5.00')  # Low risk for new transaction
                )
                
                # Log audit
                log_audit_action(
                    crypto_transaction,
                    'created',
                    request.user,
                    'Transaction created and escrow locked',
                    {'amount_cedis': str(amount_cedis)}
                )
                
                logger.info(
                    f"Created crypto transaction: {crypto_transaction.reference} "
                    f"Buyer: {request.user.email}, Seller: {seller.email}, "
                    f"Amount: {amount_crypto} {listing.get_crypto_type_display()}, "
                    f"Escrow locked: ₵{amount_cedis}"
                )
        
        except ValidationError as ve:
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating crypto transaction: {str(e)}")
            return Response(
                {'error': 'Failed to create transaction'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(crypto_transaction)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], 
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def mark_paid(self, request, pk=None):
        """
        Buyer marks payment as sent (for seller-side payment)
        Uploads screenshot of payment proof
        """
        transaction = self.get_object()
        
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can mark payment as sent'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'payment_received':
            return Response(
                {'error': f'Cannot mark paid for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = MarkPaymentSentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        payment_screenshot = request.FILES.get('payment_screenshot')
        notes = serializer.validated_data.get('notes', '')
        
        try:
            with db_transaction.atomic():
                transaction.buyer_marked_paid = True
                transaction.buyer_marked_paid_at = timezone.now()
                transaction.payment_screenshot = payment_screenshot
                transaction.status = 'buyer_marked_paid'
                transaction.seller_confirmation_deadline = timezone.now() + timedelta(minutes=15)
                transaction.save()
                
                log_audit_action(
                    transaction,
                    'marked_paid',
                    request.user,
                    f'Buyer marked payment sent: {notes}',
                    {'screenshot_uploaded': True}
                )
                
                logger.info(f"Payment marked for transaction: {transaction.reference}")
        
        except Exception as e:
            logger.error(f"Error marking payment: {str(e)}")
            return Response(
                {'error': 'Failed to mark payment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(transaction)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        """
        Seller confirms payment received
        Transitions to next stage where seller sends crypto
        """
        transaction = self.get_object()
        
        if transaction.seller != request.user:
            return Response(
                {'error': 'Only the seller can confirm payment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'buyer_marked_paid':
            return Response(
                {'error': f'Cannot confirm payment for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ConfirmPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notes = serializer.validated_data.get('notes', '')
        
        try:
            with db_transaction.atomic():
                transaction.seller_confirmed_payment = True
                transaction.seller_confirmed_payment_at = timezone.now()
                transaction.status = 'seller_confirmed_payment'
                transaction.seller_response_deadline = timezone.now() + timedelta(minutes=15)
                transaction.seller_confirmation_deadline = None  # Clear this deadline
                transaction.save()
                
                log_audit_action(
                    transaction,
                    'payment_confirmed',
                    request.user,
                    f'Seller confirmed payment received: {notes}'
                )
                
                logger.info(f"Payment confirmed for transaction: {transaction.reference}")
        
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return Response(
                {'error': 'Failed to confirm payment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(transaction)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated],
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def send_crypto(self, request, pk=None):
        """
        Seller sends crypto to buyer
        Provides transaction hash and optional proof image
        """
        transaction = self.get_object()
        
        if transaction.seller != request.user:
            return Response(
                {'error': 'Only the seller can send crypto'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'seller_confirmed_payment':
            return Response(
                {'error': f'Cannot send crypto for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SendCryptoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        transaction_hash = serializer.validated_data['transaction_hash']
        proof_image = request.FILES.get('proof_image')
        
        try:
            with db_transaction.atomic():
                transaction.crypto_sent = True
                transaction.crypto_sent_at = timezone.now()
                transaction.transaction_hash = transaction_hash
                if proof_image:
                    transaction.crypto_proof_image = proof_image
                transaction.status = 'crypto_sent'
                transaction.buyer_verification_deadline = timezone.now() + timedelta(minutes=15)
                transaction.seller_response_deadline = None  # Clear this deadline
                transaction.save()
                
                log_audit_action(
                    transaction,
                    'crypto_sent',
                    request.user,
                    f'Crypto sent with hash: {transaction_hash}',
                    {'transaction_hash': transaction_hash}
                )
                
                logger.info(f"Crypto sent for transaction: {transaction.reference}, Hash: {transaction_hash}")
        
        except Exception as e:
            logger.error(f"Error sending crypto: {str(e)}")
            return Response(
                {'error': 'Failed to send crypto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(transaction)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        """
        Buyer verifies crypto received
        If verified: Transaction completes and escrow released to seller
        If not verified: Dispute created
        """
        transaction = self.get_object()
        
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can verify crypto'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'crypto_sent':
            return Response(
                {'error': f'Cannot verify crypto for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = VerifyCryptoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        verified = serializer.validated_data.get('verified', True)
        notes = serializer.validated_data.get('notes', '')
        
        try:
            with db_transaction.atomic():
                transaction.buyer_verified = verified
                transaction.buyer_verification_notes = notes
                transaction.verified_at = timezone.now()
                
                if verified:
                    # Release escrow to seller atomically
                    seller_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=transaction.seller)
                    seller_wallet.release_cedis_from_escrow_atomic(transaction.escrow_amount_cedis)
                    
                    transaction.status = 'completed'
                    transaction.completed_at = timezone.now()
                    transaction.escrow_locked = False
                    
                    log_audit_action(
                        transaction,
                        'completed',
                        request.user,
                        f'Crypto verified. Escrow released to seller: {notes}',
                        {'escrow_released': True}
                    )
                    
                    logger.info(f"Transaction completed and escrow released: {transaction.reference}")
                
                else:
                    # Create dispute
                    transaction.status = 'disputed'
                    transaction.has_dispute = True
                    
                    dispute = CryptoTransactionDispute.objects.create(
                        transaction=transaction,
                        raised_by=request.user,
                        dispute_type='crypto_not_received',
                        description=notes or 'Crypto not received or incorrect amount'
                    )
                    
                    log_audit_action(
                        transaction,
                        'disputed',
                        request.user,
                        f'Buyer marked transaction disputed: {notes}',
                        {'dispute_id': str(dispute.id)}
                    )
                    
                    logger.info(f"Dispute created for transaction: {transaction.reference}")
                
                transaction.buyer_verification_deadline = None  # Clear this deadline
                transaction.save()
        
        except ValidationError as ve:
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error verifying crypto: {str(e)}")
            return Response(
                {'error': 'Failed to verify crypto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(transaction)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_transactions(self, request):
        """Get current user's crypto transactions"""
        transactions = self.get_queryset()
        
        status_filter = request.query_params.get('status')
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def audit_trail(self, request, pk=None):
        """Get audit trail for transaction"""
        transaction = self.get_object()
        audit_logs = transaction.audit_logs.all()
        serializer = CryptoTransactionAuditLogSerializer(audit_logs, many=True)
        return Response(serializer.data)
