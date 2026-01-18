from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction as db_transaction
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.mail import send_mail
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from wallets.models import Wallet, WalletTransaction
from wallets.views import log_wallet_activity
from notifications.utils import create_notification
from .security import calculate_risk_score, get_client_ip, get_user_agent, generate_device_fingerprint
from authentication.models import BannedIP
import logging
import uuid

logger = logging.getLogger(__name__)
from .models import GiftCard, GiftCardOrder, Order, Trade, GiftCardListing, GiftCardTransaction, GiftCardDispute, GiftCardTransactionRating, GiftCardTransactionLog, GiftCardDisputeLog

# Helper function to create transaction logs
def log_transaction_action(transaction, action, performed_by=None, notes='', metadata=None):
    """Helper function to log transaction actions"""
    GiftCardTransactionLog.objects.create(
        transaction=transaction,
        action=action,
        performed_by=performed_by,
        notes=notes,
        metadata=metadata or {}
    )

# Helper function to create dispute logs
def log_dispute_action(dispute, action, performed_by=None, comment='', metadata=None):
    """Helper function to log dispute actions (audit-proof)"""
    GiftCardDisputeLog.objects.create(
        dispute=dispute,
        action=action,
        performed_by=performed_by,
        comment=comment,
        metadata=metadata or {}
    )

from .serializers import (
    GiftCardSerializer, GiftCardOrderSerializer, GiftCardOrderCreateSerializer,
    GiftCardRateUpdateSerializer, OrderSerializer, TradeSerializer,
    GiftCardListingSerializer, GiftCardListingCreateSerializer,
    GiftCardTransactionSerializer, GiftCardTransactionCreateSerializer,
    GiftCardDisputeSerializer, GiftCardTransactionRatingSerializer
)


class GiftCardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Gift Card CRUD operations.
    - List: Public (only active cards)
    - Retrieve: Public
    - Create/Update/Delete: Admin only
    """
    queryset = GiftCard.objects.all()
    serializer_class = GiftCardSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand', 'is_active']
    search_fields = ['name', 'brand']
    ordering_fields = ['brand', 'name', 'created_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Return active cards for non-admin users, all cards for admin"""
        queryset = GiftCard.objects.all()
        if self.action == 'list' and not (self.request.user.is_authenticated and self.request.user.is_staff):
            # For non-admin users, only return active cards
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('brand', 'name')

    def get_permissions(self):
        """Admin only for create, update, delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_context(self):
        """Add request to context for image URL generation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def update_rates(self, request, pk=None):
        """Update gift card rates (admin only)"""
        gift_card = self.get_object()
        serializer = GiftCardRateUpdateSerializer(gift_card, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Gift card rates updated successfully',
                'data': GiftCardSerializer(gift_card, context={'request': request}).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GiftCardOrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Gift Card Orders.
    - List: User sees own orders, admin sees all
    - Create: Authenticated users
    - Upload proof: Authenticated users (own orders)
    - Status update: Admin only
    """
    serializer_class = GiftCardOrderSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'card', 'order_type']
    ordering_fields = ['created_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Users see their own orders, admins see all"""
        if self.request.user.is_staff:
            return GiftCardOrder.objects.all().select_related('user', 'card')
        return GiftCardOrder.objects.filter(user=self.request.user).select_related('user', 'card')

    def get_serializer_class(self):
        """Use different serializer for creation"""
        if self.action == 'create':
            return GiftCardOrderCreateSerializer
        return GiftCardOrderSerializer

    def get_serializer_context(self):
        """Add request to context for image URL generation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Create order with current user"""
        serializer.save(user=self.request.user, status='pending')


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def order(self, request):
        """
        Create a new gift card order (buy or sell).
        Endpoint: /api/orders/giftcard-orders/order/
        For frontend: /giftcards/order
        """
        serializer = GiftCardOrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save(user=request.user, status='pending')
            # Notification will be created by signal
            
            return Response(
                GiftCardOrderSerializer(order, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def upload_proof(self, request, pk=None):
        """
        Upload proof image for a gift card order.
        Endpoint: /api/orders/giftcard-orders/{id}/upload_proof/
        For frontend: /giftcards/upload-proof
        """
        order = self.get_object()
        
        # Check if user owns the order or is admin
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to upload proof for this order'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if proof image is provided
        if 'proof_image' not in request.FILES:
            return Response(
                {'error': 'proof_image is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        proof_image = request.FILES['proof_image']
        if not proof_image.content_type.startswith('image/'):
            return Response(
                {'error': 'File must be an image'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 10MB)
        if proof_image.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'File size must be less than 10MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update order with proof image
        order.proof_image = proof_image
        order.save()
        # Notification will be created by signal if needed
        
        return Response(
            GiftCardOrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Update gift card order status (admin only).
        Endpoint: /api/orders/giftcard-orders/{id}/update_status/
        """
        order = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response(
                {'error': 'status field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_statuses = [choice[0] for choice in GiftCardOrder.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = order.status
        order.status = new_status
        order.save()
        # Notification will be created by signal
        
        return Response({
            'message': f'Order status updated from {old_status} to {new_status}',
            'data': GiftCardOrderSerializer(order, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve gift card order (admin only)"""
        order = self.get_object()
        if order.status != 'pending':
            return Response(
                {'error': f'Cannot approve order with status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = 'approved'
        order.save()
        # Notification will be created by signal
        
        return Response({
            'message': 'Gift card order approved',
            'data': GiftCardOrderSerializer(order, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Decline gift card order (admin only)"""
        order = self.get_object()
        if order.status != 'pending':
            return Response(
                {'error': f'Cannot decline order with status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = 'declined'
        order.save()
        # Notification will be created by signal
        
        return Response({
            'message': 'Gift card order declined',
            'data': GiftCardOrderSerializer(order, context={'request': request}).data
        })


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_type', 'status', 'currency_pair']
    search_fields = ['currency_pair']
    ordering_fields = ['created_at', 'price', 'amount']

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status == 'PENDING':
            order.status = 'CANCELLED'
            order.save()
            return Response({'message': 'Order cancelled'})
        return Response({'error': 'Only pending orders can be cancelled'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def trades(self, request, pk=None):
        order = self.get_object()
        trades = Trade.objects.filter(order=order)
        serializer = TradeSerializer(trades, many=True)
        return Response(serializer.data)


class TradeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TradeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'price']

    def get_queryset(self):
        return Trade.objects.filter(buyer=self.request.user) | Trade.objects.filter(seller=self.request.user)


# P2P Marketplace ViewSets

class GiftCardListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Gift Card Listings
    - List: Public (only active listings)
    - Retrieve: Public
    - Create: Authenticated users
    - Update/Delete: Owner or admin
    """
    queryset = GiftCardListing.objects.all()
    serializer_class = GiftCardListingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'card', 'card__brand', 'is_negotiable']
    search_fields = ['card__name', 'card__brand', 'reference']
    ordering_fields = ['created_at', 'asking_price_cedis', 'views_count']  # Only model fields, not SerializerMethodFields
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Return active listings for non-admin users, all for admin"""
        queryset = GiftCardListing.objects.select_related('seller', 'card', 'reviewed_by').all()
        if self.action == 'list':
            # Check if user wants to see their own listings (via query param)
            if self.request.query_params.get('my_listings') == 'true' and self.request.user.is_authenticated:
                # Return user's own listings regardless of status
                queryset = queryset.filter(seller=self.request.user)
            elif not self.request.user.is_staff:
                # For non-admin users, only return active listings
                queryset = queryset.filter(status='active')
        # Order by trust score (higher first), then by creation date
        # Use Coalesce to prioritize override, then calculated score
        from django.db.models import F, Case, When, Value, IntegerField
        queryset = queryset.annotate(
            effective_trust_score=Case(
                When(seller__trust_score_override__isnull=False, then=F('seller__trust_score_override')),
                default=F('seller__trust_score'),
                output_field=IntegerField()
            )
        ).order_by('-effective_trust_score', '-created_at')
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return GiftCardListingCreateSerializer
        return GiftCardListingSerializer

    def get_permissions(self):
        """Authenticated users can create, owner/admin can update/delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @ratelimit(key='user', rate='10/h', block=True)  # Limit: 10 listings per hour per user
    def create(self, request, *args, **kwargs):
        """Create listing with rate limiting and email alerts"""
        # Check IP ban
        client_ip = get_client_ip(request)
        if BannedIP.is_ip_banned(client_ip):
            return Response(
                {'error': 'Access denied. Your IP address has been banned.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check email verification (required)
        if not request.user.email_verified:
            return Response(
                {'error': 'Email verification is required to create listings. Please verify your email first.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save(status='under_review')
        
        # Send email alert for listing creation
        try:
            send_mail(
                subject=f'Gift Card Listing Created - {listing.reference}',
                message=f'''
Hello {request.user.get_full_name() or request.user.email},

Your gift card listing has been created successfully!

Listing Details:
- Reference: {listing.reference}
- Gift Card: {listing.card.brand} {listing.gift_card_value} {listing.currency}
- Asking Price: ₵{listing.asking_price_cedis}
- Status: Under Review

Your listing is now pending admin review. You will be notified once it's approved and goes live.

If you did not create this listing, please contact support immediately.

Best regards,
CryptoGhana Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning(f"Failed to send listing creation email to {request.user.email}: {str(e)}")
        
        # Create notification
        create_notification(
            user=self.request.user,
            notification_type='GIFT_CARD_LISTING_CREATED',
            title='Gift Card Listing Created',
            message=f'Your gift card listing {listing.reference} has been created and is under review.',
            related_object_type='gift_card_listing',
            related_object_id=listing.id,
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        """Increment views count when listing is viewed"""
        instance = self.get_object()
        if not request.user.is_staff and instance.status == 'active':
            instance.views_count += 1
            instance.save(update_fields=['views_count'])
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def track_view(self, request, pk=None):
        """Track a view for a listing (called from frontend when listing is displayed)"""
        listing = self.get_object()
        # Only increment views for active listings and not by staff/admin
        if listing.status == 'active' and (not request.user.is_authenticated or not request.user.is_staff):
            listing.views_count += 1
            listing.save(update_fields=['views_count'])
        return Response({
            'views_count': listing.views_count,
            'status': 'success'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve listing (admin only)"""
        listing = self.get_object()
        if listing.status != 'under_review':
            return Response(
                {'error': f'Cannot approve listing with status: {listing.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        listing.status = 'active'
        listing.reviewed_by = request.user
        listing.reviewed_at = timezone.now()
        listing.save()
        
        create_notification(
            user=listing.seller,
            notification_type='GIFT_CARD_LISTING_APPROVED',
            title='Gift Card Listing Approved',
            message=f'Your gift card listing {listing.reference} has been approved and is now active.',
            related_object_type='gift_card_listing',
            related_object_id=listing.id,
        )
        
        return Response({
            'message': 'Listing approved successfully',
            'data': GiftCardListingSerializer(listing, context={'request': request}).data
        })

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject listing (admin only)"""
        listing = self.get_object()
        if listing.status != 'under_review':
            return Response(
                {'error': f'Cannot reject listing with status: {listing.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        listing.status = 'cancelled'
        listing.reviewed_by = request.user
        listing.reviewed_at = timezone.now()
        listing.save()
        
        create_notification(
            user=listing.seller,
            notification_type='GIFT_CARD_LISTING_REJECTED',
            title='Gift Card Listing Rejected',
            message=f'Your gift card listing {listing.reference} has been rejected. Please contact support for more information.',
            related_object_type='gift_card_listing',
            related_object_id=listing.id,
        )
        
        return Response({
            'message': 'Listing rejected',
            'data': GiftCardListingSerializer(listing, context={'request': request}).data
        })


class GiftCardTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Gift Card Transactions with Escrow
    """
    serializer_class = GiftCardTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'listing', 'buyer', 'seller']
    ordering_fields = ['created_at', 'agreed_price_cedis']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users see their own transactions, admins see all"""
        if self.request.user.is_staff:
            return GiftCardTransaction.objects.select_related('buyer', 'seller', 'listing', 'listing__card').all()
        return GiftCardTransaction.objects.filter(
            buyer=self.request.user
        ) | GiftCardTransaction.objects.filter(
            seller=self.request.user
        ).select_related('buyer', 'seller', 'listing', 'listing__card')

    def get_serializer_class(self):
        if self.action == 'create':
            return GiftCardTransactionCreateSerializer
        return GiftCardTransactionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def _get_client_ip(self, request):
        """✅ FIX #6: Extract client IP for audit logging"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def create(self, request, *args, **kwargs):
        """Create transaction and lock buyer's funds in escrow"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        listing = serializer.validated_data['listing']
        buyer = request.user
        required_amount = listing.asking_price_cedis
        
        try:
            # ✅ FIX #2: Row-level locking with select_for_update()
            with db_transaction.atomic():
                wallet, _ = Wallet.objects.select_for_update().get_or_create(user=buyer)
                available_balance = wallet.balance_cedis  # Balance available (not in escrow)
                
                # Check buyer has sufficient balance (including escrow)
                if available_balance < required_amount:
                    shortfall = required_amount - available_balance
                    return Response(
                        {
                            'error': f'Insufficient balance. You need ₵{required_amount:.2f} but only have ₵{available_balance:.2f} available. Please deposit ₵{shortfall:.2f} to your wallet.',
                            'required_amount': float(required_amount),
                            'available_balance': float(available_balance),
                            'shortfall': float(shortfall)
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # ✅ FIX #1: Lock funds in escrow using atomic operation
                balance_before = wallet.balance_cedis
                try:
                    wallet.lock_cedis_to_escrow_atomic(listing.asking_price_cedis)
                except ValidationError as ve:
                    return Response(
                        {'error': str(ve)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Set seller response deadline (24 hours from now)
                from datetime import timedelta
                seller_deadline = timezone.now() + timedelta(hours=24)
                
                # Create transaction
                transaction = GiftCardTransaction.objects.create(
                    listing=listing,
                    buyer=buyer,
                    seller=listing.seller,
                    agreed_price_cedis=listing.asking_price_cedis,
                    escrow_amount_cedis=listing.asking_price_cedis,
                    status='payment_received',
                    seller_response_deadline=seller_deadline
                )
                
                # ✅ FIX #6: Create audit log for transaction creation
                from .models import TransactionAuditLog
                TransactionAuditLog.create_audit_log(
                    transaction_type='gift_card',
                    transaction_id=transaction.id,
                    action='created',
                    performed_by=buyer,
                    previous_state={},
                    new_state={
                        'status': 'payment_received',
                        'escrow_amount': float(listing.asking_price_cedis),
                        'seller_deadline': seller_deadline.isoformat()
                    },
                    notes=f'Transaction created. Funds locked in escrow: ₵{listing.asking_price_cedis}',
                    metadata={
                        'listing_id': listing.id,
                        'listing_reference': listing.reference,
                        'amount': float(listing.asking_price_cedis)
                    },
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # ✅ FIX #6: Create audit log for escrow lock
                TransactionAuditLog.create_audit_log(
                    transaction_type='gift_card',
                    transaction_id=transaction.id,
                    action='payment_locked',
                    performed_by=None,  # System action
                    previous_state={'balance': float(balance_before), 'escrow': 0},
                    new_state={'balance': float(wallet.balance_cedis), 'escrow': float(wallet.escrow_balance)},
                    notes=f'Payment of ₵{listing.asking_price_cedis} locked in escrow',
                    metadata={
                        'amount': float(listing.asking_price_cedis),
                        'balance_before': float(balance_before),
                        'balance_after': float(wallet.balance_cedis),
                        'escrow_balance': float(wallet.escrow_balance)
                    }
                )
                
                # Mark listing as sold
                listing.status = 'sold'
                listing.save()
                
                # Create conversation for this transaction
                from messaging.models import Conversation, Message
                conversation, created = Conversation.objects.get_or_create(
                    user1=buyer,
                    user2=listing.seller,
                    listing=listing,
                    defaults={'transaction': transaction}
                )
                if not created:
                    # Update transaction reference if conversation already existed
                    conversation.transaction = transaction
                    conversation.save(update_fields=['transaction'])
                
                # Create system message about escrow
                Message.objects.create(
                    conversation=conversation,
                    sender=buyer,  # System message
                    content="💰 Escrow started. Payment received and locked.",
                    message_type='system',
                    metadata={'system_action': 'escrow_started', 'transaction_id': transaction.id}
                )
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='escrow_lock',
                    amount=listing.asking_price_cedis,
                    currency='cedis',
                    status='completed',
                    reference=transaction.reference,
                    description=f"Gift card purchase escrow: {listing.card.brand} {listing.gift_card_value} {listing.currency} for ₵{listing.asking_price_cedis}. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )
                
                # Log wallet activity
                wallet.refresh_from_db()
                log_wallet_activity(
                    user=buyer,
                    amount=listing.asking_price_cedis,
                    log_type='escrow_lock',
                    balance_after=wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                # Notifications
                create_notification(
                    user=buyer,
                    notification_type='GIFT_CARD_PURCHASE_INITIATED',
                    title='Purchase Initiated',
                    message=f'Your purchase of {listing.card.brand} gift card has been initiated. ₵{listing.asking_price_cedis} locked in escrow. Seller has 24 hours to provide card details. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=listing.seller,
                    notification_type='GIFT_CARD_SALE_INITIATED',
                    title='Sale Initiated - Action Required',
                    message=f'Your {listing.card.brand} gift card listing has been purchased. Please provide the gift card code and proof image within 24 hours. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    GiftCardTransactionSerializer(transaction, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def provide_card(self, request, pk=None):
        """Seller provides gift card code/pin and proof image"""
        transaction = self.get_object()
        
        if transaction.seller != request.user:
            return Response(
                {'error': 'Only the seller can provide gift card details'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'payment_received':
            return Response(
                {'error': f'Cannot provide card details for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        gift_card_code = request.data.get('gift_card_code', '').strip()
        gift_card_pin = request.data.get('gift_card_pin', '').strip()
        card_proof_image = request.FILES.get('card_proof_image')
        
        # Validate gift card code
        if not gift_card_code:
            return Response(
                {'error': 'Gift card code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate code format (alphanumeric, dashes, spaces allowed, min 4 chars)
        import re
        if not re.match(r'^[A-Za-z0-9\s\-]{4,}$', gift_card_code):
            return Response(
                {'error': 'Invalid gift card code format. Code must be alphanumeric and at least 4 characters long.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicate gift card (compute hash and check)
        card_hash = GiftCardListing.compute_card_hash(gift_card_code, gift_card_pin)
        
        # Check in active listings (excluding current transaction's listing)
        from orders.models import GiftCardListing
        existing_listing = GiftCardListing.objects.filter(
            card_hash=card_hash,
            status__in=['active', 'under_review', 'sold']
        ).exclude(
            id=transaction.listing.id  # Exclude the listing for this transaction
        ).exclude(
            # Exclude listings with disputes
            transactions__has_dispute=True
        ).first()
        
        if existing_listing:
            return Response(
                {
                    'error': 'This gift card has already been listed. Duplicate or reused cards are not allowed.',
                    'duplicate_listing_reference': existing_listing.reference
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Also check in transactions that have the same hash
        existing_transaction = GiftCardTransaction.objects.filter(
            listing__card_hash=card_hash
        ).exclude(
            id=transaction.id
        ).filter(
            status__in=['payment_received', 'card_provided', 'verifying', 'completed']
        ).exclude(
            has_dispute=True
        ).first()
        
        if existing_transaction:
            return Response(
                {
                    'error': 'This gift card code has already been used in another transaction. Duplicate or reused cards are not allowed.',
                    'duplicate_transaction_reference': existing_transaction.reference
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate image if provided
        if card_proof_image:
            # Check file size (max 5MB)
            if card_proof_image.size > 5 * 1024 * 1024:
                return Response(
                    {'error': 'Proof image size must be less than 5MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if card_proof_image.content_type not in allowed_types:
                return Response(
                    {'error': 'Invalid image format. Please upload a JPEG, PNG, or WebP image.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            with db_transaction.atomic():
                # Update transaction
                transaction.gift_card_code = gift_card_code
                transaction.gift_card_pin = gift_card_pin
                if card_proof_image:
                    transaction.card_proof_image = card_proof_image
                transaction.card_provided_at = timezone.now()
                transaction.status = 'card_provided'
                
                # Update listing with card hash if not already set
                if not transaction.listing.card_hash:
                    transaction.listing.card_hash = card_hash
                    transaction.listing.gift_card_code = gift_card_code
                    transaction.listing.gift_card_pin = gift_card_pin
                    transaction.listing.save(update_fields=['card_hash', 'gift_card_code', 'gift_card_pin'])
                
                # Check for duplicate proof image if provided
                if card_proof_image:
                    # Watermark the image before saving (users will see this)
                    try:
                        from orders.image_utils import process_uploaded_image
                        card_proof_image.seek(0)
                        card_proof_image = process_uploaded_image(card_proof_image, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                    except Exception as e:
                        logger.warning(f"Failed to watermark gift card transaction proof image: {str(e)}")
                        # Continue with original image if watermarking fails
                        card_proof_image.seek(0)
                    
                    card_proof_image.seek(0)  # Reset file pointer
                    image_hash = GiftCardListing.compute_proof_image_hash(card_proof_image)
                    
                    if image_hash:
                        # Check for similar images in listings
                        from orders.models import GiftCardListing
                        existing_listings = GiftCardListing.objects.filter(
                            proof_image_hash__isnull=False
                        ).exclude(id=transaction.listing.id)
                        
                        try:
                            import imagehash
                            current_hash = imagehash.hex_to_hash(image_hash)
                            
                            for listing in existing_listings:
                                if not listing.proof_image_hash:
                                    continue
                                
                                try:
                                    existing_hash = imagehash.hex_to_hash(listing.proof_image_hash)
                                    distance = current_hash - existing_hash
                                    similarity = ((64 - distance) / 64) * 100
                                    
                                    if similarity > 85:
                                        return Response(
                                            {
                                                'error': f'This proof image has been used before (similarity: {similarity:.1f}%). Reused photos are not allowed. Please upload a unique image of your gift card.',
                                                'duplicate_listing_reference': listing.reference
                                            },
                                            status=status.HTTP_400_BAD_REQUEST
                                        )
                                except (ValueError, TypeError):
                                    continue
                        except ImportError:
                            # Fallback: exact match if imagehash not available
                            exact_match = existing_listings.filter(
                                proof_image_hash=image_hash
                            ).first()
                            if exact_match:
                                return Response(
                                    {
                                        'error': 'This proof image has been used before. Reused photos are not allowed. Please upload a unique image of your gift card.',
                                        'duplicate_listing_reference': exact_match.reference
                                    },
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                
                # Set buyer verification deadline (48 hours from now)
                from datetime import timedelta
                buyer_deadline = timezone.now() + timedelta(hours=48)
                transaction.buyer_verification_deadline = buyer_deadline
                
                transaction.save()
                
                # Log action
                log_transaction_action(
                    transaction=transaction,
                    action='card_provided',
                    performed_by=request.user,
                    notes=f'Gift card code and proof provided. Buyer has 48 hours to verify.',
                    metadata={
                        'code_length': len(gift_card_code),
                        'has_pin': bool(gift_card_pin),
                        'has_proof_image': bool(card_proof_image),
                        'buyer_deadline': buyer_deadline.isoformat()
                    }
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer,
                    notification_type='GIFT_CARD_PROVIDED',
                    title='Gift Card Details Provided',
                    message=f'Seller has provided gift card details. Please verify the card works within 48 hours. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='GIFT_CARD_DETAILS_SUBMITTED',
                    title='Details Submitted',
                    message=f'You have successfully provided gift card details. Waiting for buyer verification. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    GiftCardTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            logger.error(f'Error providing card details: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to save gift card details. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        """Buyer verifies gift card works"""
        transaction = self.get_object()
        
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can verify the gift card'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'card_provided':
            return Response(
                {'error': f'Cannot verify transaction with status: {transaction.status}. Card details must be provided by seller first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Ensure card was actually provided
        if not transaction.gift_card_code:
            return Response(
                {'error': 'Gift card code has not been provided by seller yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        verification_notes = request.data.get('verification_notes', '').strip()
        is_valid = request.data.get('is_valid', True)
        
        if not is_valid:
            # Buyer says card doesn't work - create dispute automatically
            try:
                with db_transaction.atomic():
                    transaction.status = 'disputed'
                    transaction.has_dispute = True
                    transaction.buyer_verified = False
                    transaction.buyer_verification_notes = verification_notes or 'Gift card does not work'
                    transaction.verified_at = timezone.now()
                    transaction.save()
                    
                    # Log rejection
                    log_transaction_action(
                        transaction=transaction,
                        action='card_rejected',
                        performed_by=request.user,
                        notes=f'Buyer rejected gift card: {verification_notes or "Card does not work"}',
                        metadata={
                            'verification_notes': verification_notes,
                            'rejected_at': timezone.now().isoformat()
                        }
                    )
                    
                    # Create dispute
                    dispute = GiftCardDispute.objects.create(
                        transaction=transaction,
                        raised_by=request.user,
                        dispute_type='invalid_code',
                        description=verification_notes or 'Gift card code provided does not work or is invalid',
                        status='open'
                    )
                    
                    # Log dispute creation
                    log_transaction_action(
                        transaction=transaction,
                        action='dispute_created',
                        performed_by=request.user,
                        notes=f'Dispute created automatically after card rejection',
                        metadata={
                            'dispute_id': dispute.id,
                            'dispute_type': 'invalid_code'
                        }
                    )
                    
                    create_notification(
                        user=transaction.seller,
                        notification_type='GIFT_CARD_DISPUTE_RAISED',
                        title='Dispute Raised',
                        message=f'Buyer has rejected the gift card and raised a dispute for transaction {transaction.reference}. Admin will review.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    create_notification(
                        user=transaction.buyer,
                        notification_type='GIFT_CARD_DISPUTE_RAISED',
                        title='Dispute Created',
                        message=f'You have raised a dispute for transaction {transaction.reference}. Admin will review your case.',
                        related_object_type='gift_card_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    return Response(
                        GiftCardTransactionSerializer(transaction, context={'request': request}).data
                    )
            except Exception as e:
                logger.error(f'Error creating dispute: {str(e)}', exc_info=True)
                return Response(
                    {'error': 'Failed to create dispute. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Card is valid - complete transaction and increment successful trades
        try:
            with db_transaction.atomic():
                from datetime import timedelta
                
                # Set verification and auto-release time (1 hour from now)
                transaction.buyer_verified = True
                transaction.buyer_verification_notes = verification_notes
                transaction.verified_at = timezone.now()
                transaction.status = 'verifying'  # Status before auto-release
                transaction.auto_release_at = timezone.now() + timedelta(hours=1)
                transaction.save()
                
                # Log verification
                log_transaction_action(
                    transaction=transaction,
                    action='card_verified',
                    performed_by=request.user,
                    notes=f'Buyer verified gift card works. Auto-release scheduled in 1 hour.',
                    metadata={
                        'verification_notes': verification_notes,
                        'verified_at': transaction.verified_at.isoformat(),
                        'auto_release_at': transaction.auto_release_at.isoformat()
                    }
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer,
                    notification_type='GIFT_CARD_VERIFIED',
                    title='Gift Card Verified',
                    message=f'You have verified the gift card. Funds will be released to seller in 1 hour. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='GIFT_CARD_VERIFIED',
                    title='Gift Card Verified by Buyer',
                    message=f'Buyer has verified the gift card. Funds will be released to your wallet in 1 hour. Ref: {transaction.reference}',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    GiftCardTransactionSerializer(transaction, context={'request': request}).data
                )
        except ValidationError as e:
            logger.error(f"Validation error in verify transaction {transaction.reference}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error in verify transaction {transaction.reference}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'A database error occurred while processing your request. Please try again or contact support.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in verify transaction {transaction.reference}: {str(e)}", exc_info=True)
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel transaction and refund buyer"""
        transaction = self.get_object()
        
        # Only buyer or seller can cancel (before card is provided)
        if transaction.buyer != request.user and transaction.seller != request.user:
            return Response(
                {'error': 'Only buyer or seller can cancel this transaction'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status not in ['pending_payment', 'payment_received']:
            return Response(
                {'error': f'Cannot cancel transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Refund buyer if payment was received
                if transaction.status == 'payment_received':
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
                        reference=f"{transaction.reference}-CANCEL",
                        description=f"Gift card transaction cancelled. Escrow refunded. Ref: {transaction.reference}",
                        balance_before=balance_before,
                        balance_after=buyer_wallet.balance_cedis
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=transaction.buyer,
                        amount=transaction.escrow_amount_cedis,
                        log_type='escrow_refund',
                        balance_after=buyer_wallet.balance_cedis,
                        transaction_id=transaction.reference
                    )
                
                # Reactivate listing
                listing = transaction.listing
                listing.status = 'active'
                listing.save()
                
                # Update transaction
                transaction.status = 'cancelled'
                transaction.cancelled_at = timezone.now()
                transaction.save()
                
                create_notification(
                    user=transaction.buyer if transaction.buyer != request.user else transaction.seller,
                    notification_type='GIFT_CARD_TRANSACTION_CANCELLED',
                    title='Transaction Cancelled',
                    message=f'Transaction {transaction.reference} has been cancelled.',
                    related_object_type='gift_card_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    GiftCardTransactionSerializer(transaction, context={'request': request}).data
                )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GiftCardDisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Gift Card Disputes
    """
    serializer_class = GiftCardDisputeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'dispute_type', 'transaction']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Users see disputes for their transactions, admins see all"""
        if self.request.user.is_staff:
            return GiftCardDispute.objects.select_related('transaction', 'raised_by', 'assigned_to', 'resolved_by').all()
        return GiftCardDispute.objects.filter(
            transaction__buyer=self.request.user
        ) | GiftCardDispute.objects.filter(
            transaction__seller=self.request.user
        ).select_related('transaction', 'raised_by', 'assigned_to', 'resolved_by')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        """Create dispute with evidence file handling"""
        # Prepare data for serializer
        data = request.data.copy()
        
        # Handle file uploads - files are saved in serializer
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        dispute = serializer.save()
        
        # Update trust score - increment disputes_filed for user who raised dispute
        request.user.increment_dispute_filed()
        
        # Create notification for the other party
        transaction = dispute.transaction
        other_party = transaction.seller if transaction.buyer == request.user else transaction.buyer
        
        create_notification(
            user=other_party,
            notification_type='GIFT_CARD_DISPUTE_RAISED',
            title='Dispute Raised',
            message=f'A dispute has been raised for transaction {transaction.reference}. Admin will review.',
            related_object_type='gift_card_dispute',
            related_object_id=dispute.id,
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

def resolve_dispute_helper(dispute, resolution, resolution_notes, resolved_by, buyer_refund_amount=None, seller_amount=None):
    """
    Helper function to resolve a dispute. Can be called from admin or API.
    Returns (success: bool, error_message: str or None)
    """
    # Ensure only admins can finalize disputes
    if not resolved_by.is_staff:
        return False, 'Only administrators can finalize disputes'
    
    if dispute.status == 'resolved':
        return False, 'Dispute is already resolved'
    
    if not resolution:
        return False, 'Resolution is required'
    
    valid_resolutions = [choice[0] for choice in GiftCardDispute.RESOLUTION_CHOICES]
    if resolution not in valid_resolutions:
        return False, f'Invalid resolution. Must be one of: {", ".join(valid_resolutions)}'
    
    transaction = dispute.transaction
    old_status = dispute.status
    
    try:
        with db_transaction.atomic():
            buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
            seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
            
            if resolution == 'refund_buyer':
                # Refund buyer from escrow
                escrow_before = buyer_wallet.escrow_balance
                buyer_wallet.release_cedis_from_escrow(transaction.escrow_amount_cedis)
                buyer_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=transaction.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-DISPUTE-REFUND-{uuid.uuid4().hex[:8]}",
                    description=f"Dispute resolved: Refund to buyer. Ref: {transaction.reference}",
                    balance_before=buyer_wallet.balance_cedis - transaction.escrow_amount_cedis,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=transaction.buyer,
                    amount=transaction.escrow_amount_cedis,
                    log_type='escrow_refund',
                    balance_after=buyer_wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                transaction.status = 'refunded'
                
            elif resolution == 'release_to_seller':
                # Release escrow to seller
                seller_balance_before = seller_wallet.balance_cedis
                buyer_wallet.deduct_from_escrow(transaction.escrow_amount_cedis)
                seller_wallet.add_cedis(transaction.escrow_amount_cedis)
                seller_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=seller_wallet,
                    transaction_type='credit',
                    amount=transaction.escrow_amount_cedis,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-DISPUTE-RELEASE-{uuid.uuid4().hex[:8]}",
                    description=f"Dispute resolved: Release to seller. Ref: {transaction.reference}",
                    balance_before=seller_balance_before,
                    balance_after=seller_wallet.balance_cedis
                )
                
                # Log wallet activity for seller
                log_wallet_activity(
                    user=transaction.seller,
                    amount=transaction.escrow_amount_cedis,
                    log_type='deposit',
                    balance_after=seller_wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                
            elif resolution == 'partial_refund':
                # Partial refund - need amounts
                if not buyer_refund_amount or not seller_amount:
                    return False, 'buyer_refund_amount and seller_amount are required for partial refund'
                
                from decimal import Decimal
                buyer_refund = Decimal(str(buyer_refund_amount))
                seller_amount_decimal = Decimal(str(seller_amount))
                
                if buyer_refund + seller_amount_decimal != transaction.escrow_amount_cedis:
                    return False, 'buyer_refund_amount + seller_amount must equal escrow_amount'
                
                # Refund buyer
                buyer_wallet.release_cedis_from_escrow(buyer_refund)
                buyer_wallet.refresh_from_db()
                
                # Pay seller
                seller_balance_before = seller_wallet.balance_cedis
                buyer_wallet.deduct_from_escrow(seller_amount_decimal)
                seller_wallet.add_cedis(seller_amount_decimal)
                seller_wallet.refresh_from_db()
                
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_release',
                    amount=buyer_refund,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-DISPUTE-PARTIAL-REFUND-{uuid.uuid4().hex[:8]}",
                    description=f"Dispute resolved: Partial refund to buyer. Ref: {transaction.reference}",
                    balance_before=buyer_wallet.balance_cedis - buyer_refund,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                WalletTransaction.objects.create(
                    wallet=seller_wallet,
                    transaction_type='credit',
                    amount=seller_amount_decimal,
                    currency='cedis',
                    status='completed',
                    reference=f"{transaction.reference}-DISPUTE-PARTIAL-RELEASE-{uuid.uuid4().hex[:8]}",
                    description=f"Dispute resolved: Partial release to seller. Ref: {transaction.reference}",
                    balance_before=seller_balance_before,
                    balance_after=seller_wallet.balance_cedis
                )
                
                # Log wallet activities
                log_wallet_activity(
                    user=transaction.buyer,
                    amount=buyer_refund,
                    log_type='escrow_refund',
                    balance_after=buyer_wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                log_wallet_activity(
                    user=transaction.seller,
                    amount=seller_amount_decimal,
                    log_type='deposit',
                    balance_after=seller_wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
            
            # Update dispute
            dispute.status = 'resolved'
            dispute.resolution = resolution
            dispute.resolution_notes = resolution_notes
            dispute.resolved_by = resolved_by
            dispute.resolved_at = timezone.now()
            dispute.save()
            
            # Log status change
            log_dispute_action(
                dispute=dispute,
                action='status_changed',
                performed_by=resolved_by,
                comment=f"Status changed from {old_status} to resolved",
                metadata={
                    'old_status': old_status,
                    'new_status': 'resolved'
                }
            )
            
            # Log resolution finalization
            log_dispute_action(
                dispute=dispute,
                action='resolution_finalized',
                performed_by=resolved_by,
                comment=resolution_notes or f"Dispute resolved: {dispute.get_resolution_display()}",
                metadata={
                    'resolution': resolution,
                    'buyer_refund_amount': float(buyer_refund_amount) if buyer_refund_amount else None,
                    'seller_amount': float(seller_amount) if seller_amount else None,
                    'resolved_at': dispute.resolved_at.isoformat()
                }
            )
            
            # Update transaction
            transaction.dispute_resolved = True
            transaction.dispute_resolution = resolution_notes
            transaction.save()
            
            # Update trust scores based on dispute resolution
            if resolution == 'refund_buyer':
                # Seller lost - increment disputes_against for seller
                transaction.seller.increment_dispute_against()
            elif resolution == 'release_to_seller':
                # Buyer lost - increment disputes_against for buyer
                transaction.buyer.increment_dispute_against()
            elif resolution == 'partial_refund':
                # Both parties partially at fault - increment disputes_against for both
                transaction.seller.increment_dispute_against()
                transaction.buyer.increment_dispute_against()
            
            # Notifications
            create_notification(
                user=transaction.buyer,
                notification_type='GIFT_CARD_DISPUTE_RESOLVED',
                title='Dispute Resolved',
                message=f'Dispute for transaction {transaction.reference} has been resolved. {resolution_notes}',
                related_object_type='gift_card_dispute',
                related_object_id=dispute.id,
            )
            
            create_notification(
                user=transaction.seller,
                notification_type='GIFT_CARD_DISPUTE_RESOLVED',
                title='Dispute Resolved',
                message=f'Dispute for transaction {transaction.reference} has been resolved. {resolution_notes}',
                related_object_type='gift_card_dispute',
                related_object_id=dispute.id,
            )
            
            return True, None
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"Error resolving dispute {dispute.id}: {str(e)}", exc_info=True)
        return False, f'Error resolving dispute: {str(e)}'
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def upload_evidence(self, request, pk=None):
        """Upload evidence images or text for a dispute (buyers and sellers can upload)"""
        dispute = self.get_object()
        
        # Security: Only buyer or seller can upload evidence
        if dispute.transaction.buyer != request.user and dispute.transaction.seller != request.user:
            return Response(
                {'error': 'You can only upload evidence for disputes you are involved in'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if dispute.status in ['resolved', 'closed']:
            return Response(
                {'error': 'Cannot upload evidence to a resolved or closed dispute'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        evidence_text = request.data.get('evidence_text', '').strip()
        files = request.FILES.getlist('evidence_images')
        
        if not files and not evidence_text:
            return Response(
                {'error': 'Either evidence_images or evidence_text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(files) > 5:
            return Response(
                {'error': 'Maximum 5 evidence images allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_urls = []
        for file in files:
            # Validate file type
            if not file.content_type.startswith('image/'):
                return Response(
                    {'error': f'File {file.name} must be an image'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file size (max 5MB per image)
            if file.size > 5 * 1024 * 1024:
                return Response(
                    {'error': f'File {file.name} must be less than 5MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Watermark the image before saving (users will see this in disputes)
            try:
                from orders.image_utils import process_uploaded_image
                file.seek(0)
                file = process_uploaded_image(file, add_watermark_flag=True, watermark_text="CryptoGhana.com")
            except Exception as e:
                logger.warning(f"Failed to watermark dispute evidence image: {str(e)}")
                # Continue with original image if watermarking fails
                file.seek(0)
            
            # Save file
            from django.core.files.storage import default_storage
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f'dispute_evidence/{dispute.id}/{timestamp}_{file.name}'
            saved_path = default_storage.save(filename, file)
            file_url = default_storage.url(saved_path)
            uploaded_urls.append(file_url)
        
        try:
            with db_transaction.atomic():
                # Update dispute with new evidence
                existing_evidence = dispute.evidence_images or []
                dispute.evidence_images = existing_evidence + uploaded_urls
                
                # Store evidence text if provided (in metadata or separate field)
                evidence_data = {
                    'images_uploaded': len(uploaded_urls),
                    'file_names': [f.name for f in files],
                    'has_text': bool(evidence_text)
                }
                
                if evidence_text:
                    # Store text evidence in a separate JSON field or append to description
                    # For now, we'll store it in metadata of the log
                    evidence_data['text_evidence'] = evidence_text
                
                dispute.save()
                
                # Log evidence upload
                log_dispute_action(
                    dispute=dispute,
                    action='evidence_uploaded' if files else 'comment_added',
                    performed_by=request.user,
                    comment=evidence_text or f"Uploaded {len(uploaded_urls)} evidence image(s)",
                    metadata=evidence_data
                )
                
                # Notify the other party
                transaction = dispute.transaction
                other_party = transaction.seller if transaction.buyer == request.user else transaction.buyer
                
                create_notification(
                    user=other_party,
                    notification_type='GIFT_CARD_DISPUTE_EVIDENCE_ADDED',
                    title='New Evidence Added',
                    message=f'{request.user.email} has added new evidence to dispute for transaction {transaction.reference}.',
                    related_object_type='gift_card_dispute',
                    related_object_id=dispute.id,
                )
                
                return Response({
                    'message': f'Evidence uploaded successfully. {len(uploaded_urls)} image(s) and text evidence added.',
                    'evidence_images': dispute.evidence_images,
                    'evidence_text': evidence_text if evidence_text else None
                })
        except Exception as e:
            logger.error(f'Error uploading evidence: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to upload evidence. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def resolve(self, request, pk=None):
        """Resolve dispute (admin only)"""
        dispute = self.get_object()
        
        resolution = request.data.get('resolution')
        resolution_notes = request.data.get('resolution_notes', '').strip()
        buyer_refund_amount = request.data.get('buyer_refund_amount')
        seller_amount = request.data.get('seller_amount')
        
        success, error_message = resolve_dispute_helper(
            dispute, resolution, resolution_notes, request.user,
            buyer_refund_amount, seller_amount
        )
        
        if not success:
            return Response(
                {'error': error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            GiftCardDisputeSerializer(dispute, context={'request': request}).data
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """Update dispute status (admin only)"""
        dispute = self.get_object()
        new_status = request.data.get('status')
        comment = request.data.get('comment', '').strip()
        
        if new_status not in [choice[0] for choice in GiftCardDispute.STATUS_CHOICES]:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_status = dispute.status
        dispute.status = new_status
        dispute.save()
        
        # Log status change
        log_dispute_action(
            dispute=dispute,
            action='status_changed',
            performed_by=request.user,
            comment=comment or f"Status changed from {old_status} to {new_status}",
            metadata={
                'old_status': old_status,
                'new_status': new_status
            }
        )
        
        return Response(
            GiftCardDisputeSerializer(dispute, context={'request': request}).data
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign(self, request, pk=None):
        """Assign dispute to admin (admin only)"""
        dispute = self.get_object()
        assigned_to_id = request.data.get('assigned_to')
        comment = request.data.get('comment', '').strip()
        
        if assigned_to_id:
            from authentication.models import User
            try:
                assigned_user = User.objects.get(id=assigned_to_id, is_staff=True)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Invalid admin user ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Assign to current user
            assigned_user = request.user
        
        old_assigned = dispute.assigned_to
        dispute.assigned_to = assigned_user
        dispute.save()
        
        # Log assignment
        log_dispute_action(
            dispute=dispute,
            action='assigned' if old_assigned != assigned_user else 'assigned',
            performed_by=request.user,
            comment=comment or f"Dispute assigned to {assigned_user.email}",
            metadata={
                'assigned_to_id': assigned_user.id,
                'assigned_to_email': assigned_user.email,
                'previous_assigned_to_id': old_assigned.id if old_assigned else None
            }
        )
        
        return Response(
            GiftCardDisputeSerializer(dispute, context={'request': request}).data
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_comment(self, request, pk=None):
        """Add comment to dispute (buyers, sellers, and admins can comment)"""
        dispute = self.get_object()
        comment_text = request.data.get('comment', '').strip()
        
        if not comment_text:
            return Response(
                {'error': 'Comment is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Security: Only involved parties or admins can comment
        transaction = dispute.transaction
        if (transaction.buyer != request.user and 
            transaction.seller != request.user and 
            not request.user.is_staff):
            return Response(
                {'error': 'You can only comment on disputes you are involved in'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if dispute.status in ['resolved', 'closed']:
            return Response(
                {'error': 'Cannot add comments to a resolved or closed dispute'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log comment
        log_dispute_action(
            dispute=dispute,
            action='comment_added',
            performed_by=request.user,
            comment=comment_text,
            metadata={
                'user_role': 'admin' if request.user.is_staff else ('buyer' if transaction.buyer == request.user else 'seller')
            }
        )
        
        # Notify the other party
        other_party = transaction.seller if transaction.buyer == request.user else transaction.buyer
        if other_party != request.user:
            create_notification(
                user=other_party,
                notification_type='GIFT_CARD_DISPUTE_COMMENT_ADDED',
                title='New Comment on Dispute',
                message=f'{request.user.email} added a comment to dispute for transaction {transaction.reference}.',
                related_object_type='gift_card_dispute',
                related_object_id=dispute.id,
            )
        
        return Response({
            'message': 'Comment added successfully',
            'comment': comment_text
        })
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def timeline(self, request, pk=None):
        """Get dispute timeline/logs (buyers, sellers, and admins can view)"""
        dispute = self.get_object()
        
        # Security: Only involved parties or admins can view timeline
        transaction = dispute.transaction
        if (transaction.buyer != request.user and 
            transaction.seller != request.user and 
            not request.user.is_staff):
            return Response(
                {'error': 'You can only view timeline for disputes you are involved in'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all logs for this dispute
        logs = dispute.logs.all().select_related('performed_by')
        
        from .serializers import GiftCardDisputeLogSerializer
        serializer = GiftCardDisputeLogSerializer(logs, many=True, context={'request': request})
        
        return Response({
            'dispute_id': dispute.id,
            'dispute_reference': transaction.reference,
            'timeline': serializer.data
        })


class GiftCardTransactionRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Transaction Ratings
    """
    serializer_class = GiftCardTransactionRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Users see ratings they gave or received, admins see all"""
        if self.request.user.is_staff:
            return GiftCardTransactionRating.objects.select_related(
                'transaction', 'rater', 'rated_user'
            ).all()
        return GiftCardTransactionRating.objects.filter(
            rater=self.request.user
        ) | GiftCardTransactionRating.objects.filter(
            rated_user=self.request.user
        ).select_related('transaction', 'rater', 'rated_user')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def for_seller(self, request):
        """Get all ratings for a specific seller"""
        seller_id = request.query_params.get('seller_id')
        if not seller_id:
            return Response(
                {'error': 'seller_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ratings = GiftCardTransactionRating.objects.filter(
            rated_user_id=seller_id,
            is_visible=True
        ).select_related('transaction', 'rater', 'rated_user').order_by('-created_at')
        
        serializer = self.get_serializer(ratings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def seller_stats(self, request):
        """Get rating statistics for a seller"""
        seller_id = request.query_params.get('seller_id')
        if not seller_id:
            return Response(
                {'error': 'seller_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ratings = GiftCardTransactionRating.objects.filter(
            rated_user_id=seller_id,
            is_visible=True
        )
        
        total_ratings = ratings.count()
        if total_ratings == 0:
            return Response({
                'total_ratings': 0,
                'average_rating': 0,
                'rating_breakdown': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            })
        
        average_rating = ratings.aggregate(
            avg=models.Avg('rating')
        )['avg'] or 0
        
        rating_breakdown = {
            1: ratings.filter(rating=1).count(),
            2: ratings.filter(rating=2).count(),
            3: ratings.filter(rating=3).count(),
            4: ratings.filter(rating=4).count(),
            5: ratings.filter(rating=5).count(),
        }
        
        return Response({
            'total_ratings': total_ratings,
            'average_rating': round(average_rating, 2),
            'rating_breakdown': rating_breakdown
        })

