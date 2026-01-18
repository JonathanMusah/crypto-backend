"""
P2P Service Views for PayPal, CashApp, and Zelle
Following the same pattern as GiftCard views
"""
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
from datetime import timedelta
from decimal import Decimal
import logging
import json
import re
import uuid

from wallets.models import Wallet, WalletTransaction
from wallets.views import log_wallet_activity
from notifications.utils import create_notification
from orders.security import calculate_risk_score, get_client_ip

def calculate_transaction_risk_score(user, request, transaction_type='p2p_service_transaction'):
    """Wrapper for calculate_risk_score to match gift card pattern"""
    risk_score, risk_factors = calculate_risk_score(user, request)
    device_fingerprint = None  # Can be added later if needed
    return risk_score, risk_factors, device_fingerprint
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip
from authentication.models import BannedIP
from .p2p_models import (
    P2PServiceListing,
    P2PServiceTransaction,
    P2PServiceDispute,
    P2PServiceTransactionRating,
    P2PServiceTransactionLog,
    P2PServiceDisputeLog,
    SellerApplication,
)
from .p2p_serializers import (
    P2PServiceListingSerializer,
    P2PServiceListingCreateSerializer,
    P2PServiceTransactionSerializer,
    P2PServiceTransactionCreateSerializer,
    P2PServiceDisputeSerializer,
    P2PServiceDisputeCreateSerializer,
    P2PServiceTransactionRatingSerializer,
    P2PServiceTransactionRatingCreateSerializer,
)

logger = logging.getLogger(__name__)


# Helper functions
def log_p2p_transaction_action(transaction, action, performed_by=None, notes='', metadata=None):
    """Helper function to log P2P transaction actions"""
    P2PServiceTransactionLog.objects.create(
        transaction=transaction,
        action=action,
        performed_by=performed_by,
        notes=notes
    )


def log_p2p_dispute_action(dispute, action, performed_by=None, notes='', metadata=None):
    """Helper function to log P2P dispute actions"""
    P2PServiceDisputeLog.objects.create(
        dispute=dispute,
        action=action,
        performed_by=performed_by,
        notes=notes
    )


class P2PServiceListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Service Listings (PayPal, CashApp, Zelle)
    - List: Public (only active listings)
    - Retrieve: Public
    - Create: Authenticated users
    - Update/Delete: Owner or admin
    """
    queryset = P2PServiceListing.objects.all()
    serializer_class = P2PServiceListingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'service_type', 'listing_type', 'is_negotiable']
    search_fields = ['paypal_email', 'cashapp_tag', 'zelle_email', 'reference']
    ordering_fields = ['created_at', 'rate_cedis_per_usd', 'max_rate_cedis_per_usd', 'views_count']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Return active listings for non-admin users, all for admin"""
        queryset = P2PServiceListing.objects.select_related('seller', 'reviewed_by').all()
        if self.action == 'list':
            if self.request.query_params.get('my_listings') == 'true' and self.request.user.is_authenticated:
                queryset = queryset.filter(seller=self.request.user)
            elif not self.request.user.is_staff:
                queryset = queryset.filter(status='active')
        # Order by trust score (higher first), then by creation date
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
            return P2PServiceListingCreateSerializer
        return P2PServiceListingSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Create listing with rate limiting and email alerts"""
        # Force immediate output to both stdout and stderr
        import sys
        try:
            sys.stdout.write("\n" + "=" * 80 + "\n")
            sys.stdout.write("P2P LISTING CREATE REQUEST - STDOUT\n")
            sys.stdout.flush()
            sys.stderr.write("\n" + "=" * 80 + "\n")
            sys.stderr.write("P2P LISTING CREATE REQUEST - STDERR\n")
            sys.stderr.flush()
        except:
            pass
        
        try:
            print("=" * 80)
            print("P2P LISTING CREATE REQUEST - PRINT STATEMENT")
            print(f"User: {request.user.email if request.user.is_authenticated else 'Anonymous'}")
            print(f"Request method: {request.method}")
            print(f"Content-Type: {request.content_type}")
            try:
                data_type = type(request.data)
                print(f"Request data type: {data_type}")
                if hasattr(request.data, 'keys'):
                    keys = list(request.data.keys())
                    print(f"Request data keys: {keys}")
                else:
                    print(f"Request data: {request.data}")
            except Exception as data_error:
                print(f"ERROR accessing request.data: {str(data_error)}")
                print(f"Request.POST keys: {list(request.POST.keys()) if hasattr(request.POST, 'keys') else 'N/A'}")
                print(f"Request.FILES keys: {list(request.FILES.keys()) if hasattr(request.FILES, 'keys') else 'N/A'}")
            print("=" * 80)
        except Exception as e:
            print(f"ERROR in initial print block: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # TEST: Try returning immediately to see if view is called
        # Uncomment below to test
        # return Response({'test': 'View is being called!'}, status=status.HTTP_200_OK)
        
        try:
            client_ip = get_client_ip(request)
            if BannedIP.is_ip_banned(client_ip):
                logger.warning(f"Banned IP attempted to create listing: {client_ip}")
                return Response(
                    {'error': 'Access denied. Your IP address has been banned.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not request.user.email_verified:
                logger.warning(f"Unverified user attempted to create listing: {request.user.email}")
                return Response(
                    {'error': 'Email verification is required to create listings. Please verify your email first.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            logger.info("Getting serializer...")
            print("Processing FormData...")
            
            # Parse FormData - handle QueryDict and JSON strings
            # QueryDict.copy() returns a shallow copy, we need to convert to dict
            data = dict(request.data)
            
            # QueryDict returns lists for values, get first item if it's a list
            for key in data:
                if isinstance(data[key], list) and len(data[key]) > 0:
                    data[key] = data[key][0]
            
            print(f"After QueryDict conversion, accepted_payment_methods: {data.get('accepted_payment_methods')}")
            print(f"Type: {type(data.get('accepted_payment_methods'))}")
            
            # Parse JSON string for accepted_payment_methods
            if 'accepted_payment_methods' in data:
                payment_methods = data['accepted_payment_methods']
                if isinstance(payment_methods, str):
                    try:
                        import json
                        data['accepted_payment_methods'] = json.loads(payment_methods)
                        print(f"Parsed accepted_payment_methods from JSON string: {data['accepted_payment_methods']}")
                        logger.info(f"Parsed accepted_payment_methods from JSON string")
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {str(e)}")
                        logger.error(f"Failed to parse accepted_payment_methods JSON: {str(e)}")
                        raise ValueError(f"Invalid JSON in accepted_payment_methods: {str(e)}")
            
            # Convert string numbers to proper types for FormData
            for field in ['min_amount_usd', 'max_amount_usd', 'available_amount_usd', 
                         'rate_cedis_per_usd', 'max_rate_cedis_per_usd']:
                if field in data:
                    value = data[field]
                    # Handle list from QueryDict
                    if isinstance(value, list) and len(value) > 0:
                        value = value[0]
                    if isinstance(value, str):
                        try:
                            data[field] = Decimal(value)
                        except (ValueError, TypeError) as e:
                            print(f"Error converting {field} to Decimal: {str(e)}")
                            pass
            
            print(f"Processed data keys: {list(data.keys())}")
            print(f"accepted_payment_methods type: {type(data.get('accepted_payment_methods'))}")
            print(f"accepted_payment_methods value: {data.get('accepted_payment_methods')}")
            
            logger.info(f"Processed data keys: {list(data.keys())}")
            logger.info(f"accepted_payment_methods type: {type(data.get('accepted_payment_methods'))}")
            
            serializer = self.get_serializer(data=data)
            logger.info("Validating serializer...")
            serializer.is_valid(raise_exception=True)
            logger.info("Serializer is valid. Validated data:")
            logger.info(f"  - listing_type: {serializer.validated_data.get('listing_type')}")
            logger.info(f"  - service_type: {serializer.validated_data.get('service_type')}")
            logger.info(f"  - rate_cedis_per_usd: {serializer.validated_data.get('rate_cedis_per_usd')}")
            logger.info(f"  - available_amount_usd: {serializer.validated_data.get('available_amount_usd')}")
            
            logger.info("Saving listing...")
            listing = serializer.save(seller=request.user, status='under_review')
            logger.info(f"Listing saved successfully! ID: {listing.id}, Reference: {listing.reference}")
        except Exception as e:
            # Print statements always show up
            print("=" * 80)
            print("ERROR CREATING P2P LISTING - PRINT STATEMENT")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Request data: {request.data}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            print("=" * 80)
            
            logger.error("=" * 80)
            logger.error("ERROR CREATING P2P LISTING")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Request data: {request.data}")
            logger.error("Full traceback:", exc_info=True)
            logger.error("=" * 80)
            return Response(
                {'error': f'Failed to create listing: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Send email alert (different message for buy vs sell)
        try:
            if listing.listing_type == 'buy':
                listing_type_text = 'buy order'
                details_text = f'''
- Reference: {listing.reference}
- Service: {listing.get_service_type_display()} (You want to BUY)
- Amount Needed: ${listing.available_amount_usd} USD
- Maximum Rate: ₵{listing.max_rate_cedis_per_usd or listing.rate_cedis_per_usd} per USD
- Payment Method: {listing.accepted_payment_methods[0].get('method', 'N/A').upper() if listing.accepted_payment_methods else 'N/A'}
- Status: Under Review

Sellers can now see your buy order and accept it if they can fulfill it at your rate or better.
                '''
            else:
                listing_type_text = 'listing'
                service_identifier = listing.get_service_identifier()
                details_text = f'''
- Reference: {listing.reference}
- Service: {listing.get_service_type_display()} - {service_identifier}
- Available Amount: ${listing.available_amount_usd} USD
- Your Rate: ₵{listing.rate_cedis_per_usd} per USD
- Accepted Payment Methods: {len(listing.accepted_payment_methods or [])} method(s)
- Status: Under Review
                '''
            
            send_mail(
                subject=f'P2P Service {listing_type_text.title()} Created - {listing.reference}',
                message=f'''
Hello {request.user.get_full_name() or request.user.email},

Your {listing.get_service_type_display()} {listing_type_text} has been created successfully!

Listing Details:
{details_text}

Your {listing_type_text} is now pending admin review. You will be notified once it's approved and goes live.

If you did not create this {listing_type_text}, please contact support immediately.

Best regards,
CryptoGhana Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning(f"Failed to send listing creation email: {str(e)}")
        
        listing_type_text = 'buy order' if listing.listing_type == 'buy' else 'listing'
        
        # Create notification
        try:
            create_notification(
                user=request.user,
                notification_type='P2P_SERVICE_LISTING_CREATED',
                title=f'P2P Service {listing_type_text.title()} Created',
                message=f'Your {listing.get_service_type_display()} {listing_type_text} {listing.reference} has been created and is under review.',
                related_object_type='p2p_service_listing',
                related_object_id=listing.id,
            )
        except Exception as e:
            logger.warning(f"Failed to create notification: {str(e)}")
        
        logger.info("=" * 80)
        logger.info(f"P2P LISTING CREATED SUCCESSFULLY")
        logger.info(f"Listing ID: {listing.id}, Reference: {listing.reference}")
        logger.info("=" * 80)
        
        serializer_response = P2PServiceListingSerializer(listing, context={'request': request})
        headers = self.get_success_headers(serializer_response.data)
        return Response(serializer_response.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        """Increment views count when listing is viewed"""
        instance = self.get_object()
        if not request.user.is_staff and instance.status == 'active':
            instance.views_count += 1
            instance.save(update_fields=['views_count'])
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def track_view(self, request, pk=None):
        """Track a view for a listing"""
        listing = self.get_object()
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
            notification_type='P2P_SERVICE_LISTING_APPROVED',
            title='P2P Service Listing Approved',
            message=f'Your {listing.get_service_type_display()} listing {listing.reference} has been approved and is now active.',
            related_object_type='p2p_service_listing',
            related_object_id=listing.id,
        )
        
        return Response({
            'message': 'Listing approved successfully',
            'data': P2PServiceListingSerializer(listing, context={'request': request}).data
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
            notification_type='P2P_SERVICE_LISTING_REJECTED',
            title='P2P Service Listing Rejected',
            message=f'Your {listing.get_service_type_display()} listing {listing.reference} has been rejected. Please contact support for more information.',
            related_object_type='p2p_service_listing',
            related_object_id=listing.id,
        )
        
        return Response({
            'message': 'Listing rejected',
            'data': P2PServiceListingSerializer(listing, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def accept_buy_order(self, request, pk=None):
        """Seller accepts a buy order (creates transaction)"""
        buy_listing = self.get_object()
        
        if buy_listing.listing_type != 'buy':
            return Response(
                {'error': 'This action is only for buy listings'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if buy_listing.status != 'active':
            return Response(
                {'error': f'Cannot accept buy order with status: {buy_listing.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if buy_listing.seller == request.user:
            return Response(
                {'error': 'You cannot accept your own buy order'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get seller's rate (must be <= buyer's max_rate)
        seller_rate = Decimal(request.data.get('seller_rate', '0'))
        if seller_rate <= 0:
            return Response(
                {'error': 'Seller rate must be provided and greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if seller_rate > (buy_listing.max_rate_cedis_per_usd or buy_listing.rate_cedis_per_usd):
            return Response(
                {'error': f'Your rate (₵{seller_rate}) exceeds buyer\'s maximum rate (₵{buy_listing.max_rate_cedis_per_usd or buy_listing.rate_cedis_per_usd})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get amount (default to available_amount_usd)
        amount_usd = Decimal(request.data.get('amount_usd', str(buy_listing.available_amount_usd)))
        if amount_usd < buy_listing.min_amount_usd:
            return Response(
                {'error': f'Amount must be at least ${buy_listing.min_amount_usd}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if buy_listing.max_amount_usd and amount_usd > buy_listing.max_amount_usd:
            return Response(
                {'error': f'Amount cannot exceed ${buy_listing.max_amount_usd}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if amount_usd > buy_listing.available_amount_usd:
            return Response(
                {'error': f'Amount cannot exceed available ${buy_listing.available_amount_usd}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get buyer's payment method
        buyer_payment_method = buy_listing.accepted_payment_methods[0] if buy_listing.accepted_payment_methods else {}
        
        try:
            with db_transaction.atomic():
                # Calculate price using seller's rate
                agreed_price = amount_usd * seller_rate
                
                # Check buyer has sufficient balance
                # ✅ FIX #2: Row-level locking with select_for_update()
                buyer_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=buy_listing.seller)  # seller field contains buyer for buy listings
                if buyer_wallet.balance_cedis < agreed_price:
                    return Response(
                        {
                            'error': f'Buyer has insufficient balance. Required: ₵{agreed_price:.2f}, Available: ₵{buyer_wallet.balance_cedis:.2f}',
                            'required_amount': float(agreed_price),
                            'available_balance': float(buyer_wallet.balance_cedis),
                            'shortfall': float(agreed_price - buyer_wallet.balance_cedis)
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Lock buyer's funds in escrow
                balance_before = buyer_wallet.balance_cedis
                # ✅ FIX #1: Use atomic operation instead of deprecated method
                try:
                    buyer_wallet.lock_cedis_to_escrow_atomic(agreed_price)
                except ValidationError as ve:
                    return Response(
                        {'error': str(ve)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate risk score
                risk_score, risk_factors, device_fingerprint = calculate_transaction_risk_score(
                    buy_listing.seller, request, transaction_type='p2p_service_transaction'
                )
                
                # Set seller response deadline (24 hours)
                seller_deadline = timezone.now() + timedelta(hours=24)
                
                # Create transaction
                # Note: For buy listings, the "seller" field in listing is actually the buyer
                # So: buyer = buy_listing.seller, seller = request.user (person accepting)
                transaction = P2PServiceTransaction.objects.create(
                    listing=buy_listing,
                    buyer=buy_listing.seller,  # The person who created the buy order
                    seller=request.user,  # The person accepting (has the service)
                    amount_usd=amount_usd,
                    agreed_price_cedis=agreed_price,
                    escrow_amount_cedis=agreed_price,
                    selected_payment_method=buyer_payment_method.get('method', 'momo'),
                    payment_method_details=buyer_payment_method,
                    status='payment_received',
                    seller_response_deadline=seller_deadline,
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    device_fingerprint=device_fingerprint
                )
                
                # Mark buy listing as sold
                buy_listing.status = 'sold'
                buy_listing.save()
                
                # Log transaction creation
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='created',
                    performed_by=request.user,
                    notes=f'Seller accepted buy order. Funds locked in escrow: ₵{agreed_price}'
                )
                
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='payment_locked',
                    performed_by=None,
                    notes=f'Payment of ₵{agreed_price} locked in escrow'
                )
                
                # Create conversation
                try:
                    from messaging.models import Conversation, Message
                    # Ensure user1.id < user2.id for consistent unique_together constraint
                    u1, u2 = (buy_listing.seller, request.user) if buy_listing.seller.id < request.user.id else (request.user, buy_listing.seller)
                    conversation, created = Conversation.objects.get_or_create(
                        user1=u1,
                        user2=u2,
                        listing=None,
                        transaction=None,  # Set to None initially since ForeignKey expects GiftCardTransaction
                        defaults={}
                    )
                    # For P2P transactions, manually set the transaction_id in the database
                    # since the ForeignKey field expects GiftCardTransaction but we're storing P2PServiceTransaction ID
                    if transaction.id:
                        from django.db import connection
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE conversations SET transaction_id = %s WHERE id = %s",
                                [transaction.id, conversation.id]
                            )
                        conversation.refresh_from_db()
                    
                    if created:
                        Message.objects.create(
                            conversation=conversation,
                            sender=None,
                            content=f"💰 Escrow started for {buy_listing.get_service_type_display()} transaction {transaction.reference}. Seller accepted your buy order. Payment received and locked.",
                            message_type='system',
                            metadata={'system_action': 'escrow_started', 'transaction_id': transaction.id}
                        )
                except Exception as e:
                    logger.error(f"Failed to create conversation: {str(e)}")
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=buyer_wallet,
                    transaction_type='escrow_lock',
                    amount=agreed_price,
                    currency='cedis',
                    status='completed',
                    reference=transaction.reference,
                    description=f"P2P {buy_listing.get_service_type_display()} purchase escrow: ₵{agreed_price}. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=buyer_wallet.balance_cedis
                )
                
                # Log wallet activity
                buyer_wallet.refresh_from_db()
                log_wallet_activity(
                    user=buy_listing.seller,
                    amount=agreed_price,
                    log_type='escrow_lock',
                    balance_after=buyer_wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                # Notifications
                create_notification(
                    user=buy_listing.seller,
                    notification_type='P2P_SERVICE_BUY_ORDER_ACCEPTED',
                    title='Buy Order Accepted!',
                    message=f'Your {buy_listing.get_service_type_display()} buy order has been accepted by a seller. ₵{agreed_price} locked in escrow. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=request.user,
                    notification_type='P2P_SERVICE_BUY_ORDER_ACCEPTED_BY_YOU',
                    title='Buy Order Accepted',
                    message=f'You accepted a {buy_listing.get_service_type_display()} buy order. Please provide service details within 24 hours. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'Error accepting buy order: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to accept buy order. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class P2PServiceTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Service Transactions with Escrow
    """
    serializer_class = P2PServiceTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'listing', 'buyer', 'seller']
    ordering_fields = ['created_at', 'agreed_price_cedis']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users see their own transactions, admins see all"""
        if self.request.user.is_staff:
            return P2PServiceTransaction.objects.select_related('buyer', 'seller', 'listing').all()
        # Use Q objects for proper OR query
        from django.db.models import Q
        return P2PServiceTransaction.objects.filter(
            Q(buyer=self.request.user) | Q(seller=self.request.user)
        ).select_related('buyer', 'seller', 'listing')

    def get_serializer_class(self):
        if self.action == 'create':
            return P2PServiceTransactionCreateSerializer
        return P2PServiceTransactionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Create transaction and lock buyer's funds in escrow - Binance-style with seller rates"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        listing_id = serializer.validated_data['listing_id']
        amount_usd = serializer.validated_data['amount_usd']
        selected_payment_method = serializer.validated_data['selected_payment_method']
        payment_method_details = serializer.validated_data.get('payment_method_details', {})
        
        listing = P2PServiceListing.objects.get(id=listing_id)
        buyer = request.user
        
        # Binance-style: Check if buyer has incomplete transactions (prevent multiple active transactions)
        incomplete_transactions = P2PServiceTransaction.objects.filter(
            buyer=buyer,
            status__in=['pending_payment', 'payment_received', 'service_provided', 'verifying']
        ).exclude(status='cancelled')
        
        if incomplete_transactions.exists():
            incomplete_refs = [txn.reference for txn in incomplete_transactions[:3]]
            return Response(
                {
                    'error': f'You have {incomplete_transactions.count()} incomplete transaction(s). Please complete or cancel them before starting a new one.',
                    'incomplete_transactions': incomplete_refs,
                    'count': incomplete_transactions.count()
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Binance-style: Check if seller has incomplete transactions (prevent seller from taking too many orders)
        seller_incomplete = P2PServiceTransaction.objects.filter(
            seller=listing.seller,
            status__in=['pending_payment', 'payment_received', 'service_provided', 'verifying']
        ).exclude(status='cancelled').count()
        
        # Limit seller to max 5 active transactions at once (prevent abuse)
        MAX_ACTIVE_SELLER_TRANSACTIONS = 5
        if seller_incomplete >= MAX_ACTIVE_SELLER_TRANSACTIONS:
            return Response(
                {
                    'error': f'Seller has reached the maximum number of active transactions ({MAX_ACTIVE_SELLER_TRANSACTIONS}). Please try another listing or wait for seller to complete existing transactions.',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check buyer qualification (Binance-style requirements)
        qualified, reason = listing.check_buyer_qualification(buyer, payment_method_details)
        if not qualified:
            return Response(
                {'error': reason or "You do not meet the buyer requirements for this listing."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculate agreed price using seller's rate
        agreed_price = listing.calculate_price_cedis(amount_usd)
        
        # Check buyer has sufficient balance
        # ✅ FIX #2: Row-level locking with select_for_update()
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=buyer)
        available_balance = wallet.balance_cedis
        
        if available_balance < agreed_price:
            shortfall = agreed_price - available_balance
            return Response(
                {
                    'error': f'Insufficient balance. You need ₵{agreed_price:.2f} but only have ₵{available_balance:.2f} available. Please deposit ₵{shortfall:.2f} to your wallet.',
                    'required_amount': float(agreed_price),
                    'available_balance': float(available_balance),
                    'shortfall': float(shortfall)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Lock funds in escrow
                balance_before = wallet.balance_cedis
                # ✅ FIX #1: Use atomic operation instead of deprecated method
                try:
                    wallet.lock_cedis_to_escrow_atomic(agreed_price)
                except ValidationError as ve:
                    return Response(
                        {'error': str(ve)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate risk score
                risk_score, risk_factors, device_fingerprint = calculate_transaction_risk_score(
                    buyer, request, transaction_type='p2p_service_transaction'
                )
                
                # Set deadlines based on listing type (Binance-style: 15 minutes for all deadlines)
                from datetime import timedelta
                now = timezone.now()
                
                # For SELL listings: Set payment deadline (buyer must mark payment within 15 minutes)
                # For BUY listings: Set seller response deadline (seller must provide service within 15 minutes)
                if listing.listing_type == 'sell':
                    payment_deadline = now + timedelta(minutes=15)
                    seller_response_deadline = None  # Will be set after seller confirms payment
                else:
                    payment_deadline = None  # Not applicable for BUY listings
                    seller_response_deadline = now + timedelta(minutes=15)
                
                # Get buyer_service_identifier for BUY listings
                buyer_service_identifier = serializer.validated_data.get('buyer_service_identifier', '').strip()
                
                # Create transaction
                transaction = P2PServiceTransaction.objects.create(
                    listing=listing,
                    buyer=buyer,
                    seller=listing.seller,
                    amount_usd=amount_usd,
                    agreed_price_cedis=agreed_price,
                    escrow_amount_cedis=agreed_price,
                    selected_payment_method=selected_payment_method,
                    payment_method_details=payment_method_details,
                    buyer_service_identifier=buyer_service_identifier if listing.listing_type == 'buy' else '',
                    status='payment_received',
                    payment_deadline=payment_deadline,
                    seller_response_deadline=seller_response_deadline,
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    device_fingerprint=device_fingerprint
                )
                
                # Log transaction creation
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='created',
                    performed_by=buyer,
                    notes=f'Transaction created. Funds locked in escrow: ₵{agreed_price}'
                )
                
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='payment_locked',
                    performed_by=None,
                    notes=f'Payment of ₵{agreed_price} locked in escrow'
                )
                
                # Binance-style: Decrease available amount and only mark as sold when depleted
                # This allows multiple buyers to purchase from the same listing
                if listing.listing_type == 'sell':
                    # Use F() to prevent race conditions when updating available_amount_usd
                    from django.db.models import F
                    listing.refresh_from_db()  # Get fresh data
                    listing.available_amount_usd = F('available_amount_usd') - amount_usd
                    listing.save(update_fields=['available_amount_usd'])
                    listing.refresh_from_db()  # Get updated value
                    
                    # Only mark as sold if available amount is depleted (less than min_amount)
                    # This allows the listing to remain active if there's still enough for a minimum purchase
                    if listing.available_amount_usd < listing.min_amount_usd:
                        listing.status = 'sold'
                        listing.save(update_fields=['status'])
                else:
                    # Buy listings are one-time, mark as sold immediately
                    listing.status = 'sold'
                    listing.save(update_fields=['status'])
                
                # Create conversation for this transaction
                try:
                    from messaging.models import Conversation, Message
                    # Ensure user1.id < user2.id for consistent unique_together constraint
                    u1, u2 = (buyer, listing.seller) if buyer.id < listing.seller.id else (listing.seller, buyer)
                    
                    # For P2P transactions, we cannot use the transaction ForeignKey field
                    # because it points to GiftCardTransaction, not P2PServiceTransaction
                    # The database foreign key constraint prevents us from setting transaction_id to a P2P transaction ID
                    # Instead, we'll check for existing conversations between these users and check message metadata
                    # to see if a conversation already exists for this transaction
                    
                    # First, check if a conversation already exists for this transaction
                    # by looking for conversations between these users with messages containing this transaction_id
                    existing_conversations = Conversation.objects.filter(
                        user1=u1,
                        user2=u2,
                        transaction=None,
                        listing=None
                    )
                    
                    conversation = None
                    for conv in existing_conversations:
                        # Check if any message in this conversation has our transaction_id in metadata
                        if Message.objects.filter(
                            conversation=conv,
                            metadata__transaction_id=transaction.id
                        ).exists():
                            conversation = conv
                            break
                    
                    # If no existing conversation found, create a new one
                    if not conversation:
                        conversation = Conversation.objects.create(
                            user1=u1,
                            user2=u2,
                            listing=None,  # P2P services don't use GiftCardListing
                            transaction=None,  # Must be None - ForeignKey constraint prevents P2P transaction IDs
                            is_archived_user1=False,
                            is_archived_user2=False
                        )
                    
                    # Binance-style: Send seller's payment details as a message
                    # Format payment details message
                    payment_method = transaction.selected_payment_method
                    payment_details = transaction.payment_method_details
                    
                    # Build payment details message
                    payment_details_text = f"💳 **Payment Details**\n\n"
                    payment_details_text += f"**Payment Method:** {payment_method.upper()}\n"
                    payment_details_text += f"**Amount:** ₵{agreed_price:.2f}\n\n"
                    
                    if payment_method == 'momo':
                        provider = payment_details.get('provider', 'N/A')
                        number = payment_details.get('number', 'N/A')
                        name = payment_details.get('name', 'N/A')
                        payment_details_text += f"**Provider:** {provider}\n"
                        payment_details_text += f"**Mobile Money Number:** {number}\n"
                        payment_details_text += f"**Account Name:** {name}\n"
                    elif payment_method == 'bank':
                        bank_name = payment_details.get('bank_name', 'N/A')
                        account_number = payment_details.get('account_number', 'N/A')
                        account_name = payment_details.get('account_name', 'N/A')
                        branch = payment_details.get('branch', '')
                        payment_details_text += f"**Bank:** {bank_name}\n"
                        payment_details_text += f"**Account Number:** {account_number}\n"
                        payment_details_text += f"**Account Name:** {account_name}\n"
                        if branch:
                            payment_details_text += f"**Branch:** {branch}\n"
                    else:
                        # Other payment methods
                        for key, value in payment_details.items():
                            if value:
                                payment_details_text += f"**{key.replace('_', ' ').title()}:** {value}\n"
                    
                    payment_details_text += f"\n⏱️ Please complete payment within 15 minutes and mark as paid."
                    
                    # Send payment details message from seller
                    Message.objects.create(
                        conversation=conversation,
                        sender=listing.seller,
                        content=payment_details_text,
                        message_type='text',
                        metadata={'system_action': 'payment_details_sent', 'transaction_id': transaction.id}
                    )
                    
                    # Send system message about escrow
                    Message.objects.create(
                        conversation=conversation,
                        sender=None,
                        content=f"💰 Escrow started. ₵{agreed_price:.2f} locked in escrow. Transaction: {transaction.reference}",
                        message_type='system',
                        metadata={'system_action': 'escrow_started', 'transaction_id': transaction.id}
                    )
                except Exception as e:
                    logger.error(f"Failed to create conversation: {str(e)}")
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='escrow_lock',
                    amount=agreed_price,
                    currency='cedis',
                    status='completed',
                    reference=transaction.reference,
                    description=f"P2P {listing.get_service_type_display()} purchase escrow: ₵{agreed_price}. Ref: {transaction.reference}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )
                
                # Log wallet activity
                wallet.refresh_from_db()
                log_wallet_activity(
                    user=buyer,
                    amount=agreed_price,
                    log_type='escrow_lock',
                    balance_after=wallet.balance_cedis,
                    transaction_id=transaction.reference
                )
                
                # Notifications
                create_notification(
                    user=buyer,
                    notification_type='P2P_SERVICE_PURCHASE_INITIATED',
                    title='Purchase Initiated',
                    message=f'Your purchase of {listing.get_service_type_display()} has been initiated. ₵{agreed_price} locked in escrow. Seller has 15 minutes to provide service details. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=listing.seller,
                    notification_type='P2P_SERVICE_SALE_INITIATED',
                    title='Sale Initiated - Action Required',
                    message=f'Your {listing.get_service_type_display()} listing has been purchased. Please provide the service email and proof within 15 minutes. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def mark_payment_complete(self, request, pk=None):
        """Binance-style: Buyer marks payment as complete and uploads screenshot (only for SELL listings)"""
        transaction = self.get_object()
        
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can mark payment as complete'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # For BUY listings, payment marking is not needed (buyer's money is already in escrow)
        if transaction.listing.listing_type == 'buy':
            return Response(
                {'error': 'Payment marking is not required for BUY listings. Your funds are already locked in escrow.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction.status != 'payment_received':
            return Response(
                {'error': f'Cannot mark payment as complete for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction.buyer_marked_paid:
            return Response(
                {'error': 'Payment has already been marked as complete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_screenshot = request.FILES.get('payment_screenshot')
        
        if not payment_screenshot:
            return Response(
                {'error': 'Payment screenshot is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate image
        if payment_screenshot.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Screenshot size must be less than 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if payment_screenshot.content_type not in allowed_types:
            return Response(
                {'error': 'Invalid image format. Please upload a JPEG, PNG, or WebP image.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Watermark screenshot
                try:
                    from orders.image_utils import process_uploaded_image
                    payment_screenshot.seek(0)
                    payment_screenshot = process_uploaded_image(payment_screenshot, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                except Exception as e:
                    logger.warning(f"Failed to watermark payment screenshot: {str(e)}")
                    payment_screenshot.seek(0)
                
                # Update transaction
                transaction.buyer_marked_paid = True
                transaction.buyer_marked_paid_at = timezone.now()
                transaction.payment_screenshot = payment_screenshot
                transaction.status = 'buyer_marked_paid'
                # Set seller confirmation deadline (15 minutes)
                transaction.seller_confirmation_deadline = timezone.now() + timedelta(minutes=15)
                transaction.save()
                
                # Send screenshot in message
                from messaging.models import Conversation, Message
                from django.db import connection
                conversation = None
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM conversations WHERE transaction_id = %s LIMIT 1",
                        [transaction.id]
                    )
                    result = cursor.fetchone()
                    if result:
                        try:
                            conversation = Conversation.objects.get(id=result[0])
                        except Conversation.DoesNotExist:
                            pass
                
                if conversation:
                    # Send screenshot as message
                    message = Message.objects.create(
                        conversation=conversation,
                        sender=transaction.buyer,
                        content="📸 Payment screenshot",
                        message_type='text',
                        metadata={'system_action': 'payment_screenshot_uploaded', 'transaction_id': transaction.id}
                    )
                    # Set attachment fields
                    message.attachment = payment_screenshot
                    message.attachment_name = payment_screenshot.name
                    message.attachment_type = 'image'
                    message.attachment_size = payment_screenshot.size
                    message.save()
                    
                    # Send system message
                    Message.objects.create(
                        conversation=conversation,
                        sender=None,
                        content=f"✅ Buyer has marked payment as complete. Waiting for seller confirmation.",
                        message_type='system',
                        metadata={'system_action': 'buyer_marked_paid', 'transaction_id': transaction.id}
                    )
                    
                    # Update conversation
                    conversation.last_message_at = timezone.now()
                    conversation.save(update_fields=['last_message_at'])
                
                # Log action
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='buyer_marked_paid',
                    performed_by=request.user,
                    notes='Buyer marked payment as complete and uploaded screenshot'
                )
                
                # Notifications
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_PAYMENT_MARKED_PAID',
                    title='Payment Marked as Complete',
                    message=f'Buyer has marked payment as complete for transaction {transaction.reference}. Please confirm payment receipt.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            logger.error(f'Error marking payment as complete: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to mark payment as complete. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        """Binance-style: Seller confirms payment receipt (only for SELL listings)"""
        transaction = self.get_object()
        
        if transaction.seller != request.user:
            return Response(
                {'error': 'Only the seller can confirm payment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # For BUY listings, payment confirmation is not needed (seller provides service directly)
        if transaction.listing.listing_type == 'buy':
            return Response(
                {'error': 'Payment confirmation is not required for BUY listings. You can provide service directly.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction.status != 'buyer_marked_paid':
            return Response(
                {'error': f'Cannot confirm payment for transaction with status: {transaction.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction.seller_confirmed_payment:
            return Response(
                {'error': 'Payment has already been confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Update transaction
                transaction.seller_confirmed_payment = True
                transaction.seller_confirmed_payment_at = timezone.now()
                transaction.status = 'seller_confirmed_payment'
                # Set seller response deadline (15 minutes to provide service)
                transaction.seller_response_deadline = timezone.now() + timedelta(minutes=15)
                # Clear seller confirmation deadline (no longer needed)
                transaction.seller_confirmation_deadline = None
                transaction.save()
                
                # Send system message
                from messaging.models import Conversation, Message
                from django.db import connection
                conversation = None
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM conversations WHERE transaction_id = %s LIMIT 1",
                        [transaction.id]
                    )
                    result = cursor.fetchone()
                    if result:
                        try:
                            conversation = Conversation.objects.get(id=result[0])
                        except Conversation.DoesNotExist:
                            pass
                
                if conversation:
                    Message.objects.create(
                        conversation=conversation,
                        sender=None,
                        content=f"✅ Seller has confirmed payment receipt. Seller will provide service details within 15 minutes.",
                        message_type='system',
                        metadata={'system_action': 'seller_confirmed_payment', 'transaction_id': transaction.id}
                    )
                    
                    conversation.last_message_at = timezone.now()
                    conversation.save(update_fields=['last_message_at'])
                
                # Log action
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='seller_confirmed_payment',
                    performed_by=request.user,
                    notes='Seller confirmed payment receipt'
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_PAYMENT_CONFIRMED',
                    title='Payment Confirmed',
                    message=f'Seller has confirmed payment receipt for transaction {transaction.reference}. Seller will provide service details shortly.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            logger.error(f'Error confirming payment: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to confirm payment. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def provide_service(self, request, pk=None):
        """Seller provides service identifier (email or tag) and proof image"""
        transaction = self.get_object()
        
        if transaction.seller != request.user:
            return Response(
                {'error': 'Only the seller can provide service details'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        listing = transaction.listing
        
        # For BUY listings: Seller can provide service directly after payment_received (skip payment confirmation)
        # For SELL listings: Seller must confirm payment first
        if listing.listing_type == 'buy':
            if transaction.status != 'payment_received':
                return Response(
                    {'error': f'Cannot provide service details. Transaction status must be payment_received. Current status: {transaction.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # SELL listings require payment confirmation first
            if transaction.status != 'seller_confirmed_payment':
                return Response(
                    {'error': f'Cannot provide service details. Payment must be confirmed first. Current status: {transaction.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        service_identifier = request.data.get('service_identifier', '').strip()
        service_proof_image = request.FILES.get('service_proof_image')
        
        # For BUY listings, use buyer's service identifier (where they want to receive service)
        # For SELL listings, seller provides their service identifier
        if listing.listing_type == 'buy':
            # Use buyer's service identifier that was provided when creating the transaction
            if not transaction.buyer_service_identifier:
                return Response(
                    {'error': 'Buyer service identifier is missing. This should have been provided when the transaction was created.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            service_identifier = transaction.buyer_service_identifier
        else:
            # For SELL listings, validate the service identifier provided by seller
            if listing.service_type == 'paypal' or listing.service_type == 'zelle':
                # Must be a valid email
                if not service_identifier or '@' not in service_identifier:
                    return Response(
                        {'error': 'Valid email address is required for this service type'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, service_identifier):
                    return Response(
                        {'error': 'Invalid email format'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif listing.service_type == 'cashapp':
                # Must be a valid CashApp tag (starts with $)
                if not service_identifier or not service_identifier.startswith('$'):
                    return Response(
                        {'error': 'Valid CashApp tag (starting with $) is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if not service_identifier:
                return Response(
                    {'error': 'Service identifier is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate image if provided
        if service_proof_image:
            if service_proof_image.size > 5 * 1024 * 1024:
                return Response(
                    {'error': 'Proof image size must be less than 5MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if service_proof_image.content_type not in allowed_types:
                return Response(
                    {'error': 'Invalid image format. Please upload a JPEG, PNG, or WebP image.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            with db_transaction.atomic():
                # Watermark proof image if provided (users will see this)
                if service_proof_image:
                    try:
                        from orders.image_utils import process_uploaded_image
                        service_proof_image.seek(0)
                        service_proof_image = process_uploaded_image(service_proof_image, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                    except Exception as e:
                        logger.warning(f"Failed to watermark P2P service transaction proof image: {str(e)}")
                        # Continue with original image if watermarking fails
                        service_proof_image.seek(0)
                
                # Update transaction
                transaction.service_identifier = service_identifier
                if service_proof_image:
                    transaction.service_proof_image = service_proof_image
                transaction.service_provided_at = timezone.now()
                transaction.status = 'service_provided'
                
                # Binance-style: Set buyer verification deadline (15 minutes)
                buyer_deadline = timezone.now() + timedelta(minutes=15)
                transaction.buyer_verification_deadline = buyer_deadline
                
                transaction.save()
                
                # Binance-style: Send service details in message
                from messaging.models import Conversation, Message
                from django.db import connection
                conversation = None
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM conversations WHERE transaction_id = %s LIMIT 1",
                        [transaction.id]
                    )
                    result = cursor.fetchone()
                    if result:
                        try:
                            conversation = Conversation.objects.get(id=result[0])
                        except Conversation.DoesNotExist:
                            pass
                
                if conversation:
                    # Build service details message
                    service_type = transaction.listing.get_service_type_display()
                    service_details_text = f"📦 **Service Details**\n\n"
                    service_details_text += f"**Service Type:** {service_type}\n"
                    
                    # For BUY listings, show that service was sent to buyer's identifier
                    if listing.listing_type == 'buy':
                        service_details_text += f"**Sent To:** {service_identifier}\n"
                        service_details_text += f"**Amount:** ${transaction.amount_usd:.2f} USD\n\n"
                        service_details_text += f"✅ {service_type} has been sent to your {service_identifier}. Please verify receipt within 15 minutes."
                    else:
                        # For SELL listings, show seller's identifier
                        service_details_text += f"**Service Identifier:** {service_identifier}\n"
                        service_details_text += f"**Amount:** ${transaction.amount_usd:.2f} USD\n\n"
                        service_details_text += f"⏱️ Please verify within 15 minutes."
                    
                    # Send service details from seller
                    message = Message.objects.create(
                        conversation=conversation,
                        sender=transaction.seller,
                        content=service_details_text,
                        message_type='text',
                        metadata={'system_action': 'service_details_provided', 'transaction_id': transaction.id}
                    )
                    
                    # Attach proof image if provided
                    if service_proof_image:
                        message.attachment = service_proof_image
                        message.attachment_name = service_proof_image.name
                        message.attachment_type = 'image'
                        message.save()
                    
                    # Send system message
                    Message.objects.create(
                        conversation=conversation,
                        sender=None,
                        content=f"✅ Seller has provided {service_type} service details. Buyer has 15 minutes to verify.",
                        message_type='system',
                        metadata={'system_action': 'service_provided', 'transaction_id': transaction.id}
                    )
                    
                    conversation.last_message_at = timezone.now()
                    conversation.save(update_fields=['last_message_at'])
                
                # Log action
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='service_provided',
                    performed_by=request.user,
                    notes=f'Service identifier ({service_identifier}) and proof provided. Buyer has 15 minutes to verify.'
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_PROVIDED',
                    title='Service Details Provided',
                    message=f'Seller has provided {transaction.listing.get_service_type_display()} service details. Please verify within 15 minutes. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_DETAILS_SUBMITTED',
                    title='Details Submitted',
                    message=f'You have successfully provided service details. Waiting for buyer verification. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            logger.error(f'Error providing service details: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to save service details. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def release_escrow(self, request, pk=None):
        """Manually release escrow for stuck transactions (verifying status with passed auto_release_at)"""
        transaction = self.get_object()
        
        # Only buyer can release escrow (it's their funds)
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can release escrow. These are your funds locked in escrow.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only allow if transaction is in verifying status and auto_release_at has passed
        if transaction.status != 'verifying':
            return Response(
                {'error': f'Cannot release escrow. Transaction status is {transaction.status}, not verifying.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not transaction.buyer_verified:
            return Response(
                {'error': 'Cannot release escrow. You must verify the service first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transaction.escrow_released:
            return Response(
                {'error': 'Escrow has already been released.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if auto_release_at has passed (or allow if it's None for old transactions)
        if transaction.auto_release_at and transaction.auto_release_at > timezone.now():
            time_remaining = (transaction.auto_release_at - timezone.now()).total_seconds() / 60
            return Response(
                {'error': f'Auto-release is scheduled. Please wait {int(time_remaining)} more minutes.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                seller_wallet, _ = Wallet.objects.get_or_create(user=transaction.seller)
                
                # Validate escrow balance
                if buyer_wallet.escrow_balance < transaction.escrow_amount_cedis:
                    return Response(
                        {
                            'error': f'Insufficient escrow balance. Escrow: ₵{buyer_wallet.escrow_balance}, Required: ₵{transaction.escrow_amount_cedis}'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Use helper function to release escrow (handles both BUY and SELL listings correctly)
                from orders.p2p_binance_refactor import release_escrow_for_buy_listing
                release_escrow_for_buy_listing(transaction, buyer_wallet, seller_wallet)
                
                # Update transaction status
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.escrow_released = True
                transaction.escrow_released_at = timezone.now()
                transaction.save()
                
                # Log action
                escrow_action = 'refunded to buyer' if transaction.listing.listing_type == 'buy' else 'released to seller'
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='manual_escrow_release',
                    performed_by=request.user,
                    notes=f'Escrow manually released by {request.user.email}. Amount: ₵{transaction.escrow_amount_cedis} ({escrow_action})'
                )
                
                # Notifications
                if transaction.listing.listing_type == 'buy':
                    create_notification(
                        user=transaction.buyer,
                        notification_type='P2P_SERVICE_COMPLETED',
                        title='Transaction Completed',
                        message=f'Transaction {transaction.reference} has been completed. Escrow refunded to you.',
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
                else:
                    create_notification(
                        user=transaction.buyer,
                        notification_type='P2P_SERVICE_COMPLETED',
                        title='Transaction Completed',
                        message=f'Transaction {transaction.reference} has been completed. Escrow released to seller.',
                        related_object_type='p2p_service_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    create_notification(
                        user=transaction.seller,
                        notification_type='P2P_SERVICE_COMPLETED',
                        title='Payment Received',
                        message=f'Payment of ₵{transaction.escrow_amount_cedis} has been released to your wallet. Ref: {transaction.reference}',
                        related_object_type='p2p_service_transaction',
                        related_object_id=transaction.id,
                    )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            error_msg = str(e)
            logger.error(f'Error manually releasing escrow for transaction {transaction.reference}: {error_msg}', exc_info=True)
            
            # Provide more specific error messages
            if 'escrow' in error_msg.lower() or 'balance' in error_msg.lower():
                error_detail = f'Escrow release failed: {error_msg}'
            elif 'database' in error_msg.lower() or 'transaction' in error_msg.lower():
                error_detail = 'Database error occurred. Please try again or contact support.'
            else:
                error_detail = f'Failed to release escrow: {error_msg}'
            
            return Response(
                {'error': error_detail},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verify(self, request, pk=None):
        """Buyer verifies service works"""
        transaction = self.get_object()
        
        if transaction.buyer != request.user:
            return Response(
                {'error': 'Only the buyer can verify the service'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.status != 'service_provided':
            return Response(
                {'error': f'Cannot verify transaction with status: {transaction.status}. Service details must be provided by seller first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not transaction.service_identifier:
            return Response(
                {'error': 'Service details have not been provided by seller yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        verification_notes = request.data.get('verification_notes', '').strip()
        is_valid = request.data.get('is_valid', True)
        
        if not is_valid:
            # Buyer says service doesn't work - create dispute automatically
            try:
                with db_transaction.atomic():
                    transaction.status = 'disputed'
                    transaction.has_dispute = True
                    transaction.buyer_verified = False
                    transaction.buyer_verification_notes = verification_notes or 'Service does not work'
                    transaction.verified_at = timezone.now()
                    transaction.save()
                    
                    # Log rejection
                    log_p2p_transaction_action(
                        transaction=transaction,
                        action='service_rejected',
                        performed_by=request.user,
                        notes=f'Buyer rejected service: {verification_notes or "Service does not work"}'
                    )
                    
                    # Create dispute
                    dispute = P2PServiceDispute.objects.create(
                        transaction=transaction,
                        raised_by=request.user,
                        dispute_type='service_not_received',
                        description=verification_notes or 'Service email provided does not work or is invalid',
                        status='open'
                    )
                    
                    log_p2p_transaction_action(
                        transaction=transaction,
                        action='dispute_created',
                        performed_by=request.user,
                        notes=f'Dispute created automatically after service rejection'
                    )
                    
                    create_notification(
                        user=transaction.seller,
                        notification_type='P2P_SERVICE_DISPUTE_RAISED',
                        title='Dispute Raised',
                        message=f'Buyer has rejected the service and raised a dispute for transaction {transaction.reference}. Admin will review.',
                        related_object_type='p2p_service_transaction',
                        related_object_id=transaction.id,
                    )
                    
                    return Response(
                        P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                    )
            except Exception as e:
                logger.error(f'Error creating dispute: {str(e)}', exc_info=True)
                return Response(
                    {'error': 'Failed to create dispute. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Service is valid - complete transaction
        try:
            with db_transaction.atomic():
                # Binance-style: Set verification and auto-release time (15 minutes from now)
                transaction.buyer_verified = True
                transaction.buyer_verification_notes = verification_notes
                transaction.verified_at = timezone.now()
                transaction.status = 'verifying'
                transaction.auto_release_at = timezone.now() + timedelta(minutes=15)
                transaction.save()
                
                # Log verification
                log_p2p_transaction_action(
                    transaction=transaction,
                    action='service_verified',
                    performed_by=request.user,
                    notes=f'Buyer verified service works. Auto-release scheduled in 15 minutes.'
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer,
                    notification_type='P2P_SERVICE_VERIFIED',
                    title='Service Verified',
                    message=f'You have verified the service. Funds will be released to seller in 15 minutes. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                create_notification(
                    user=transaction.seller,
                    notification_type='P2P_SERVICE_VERIFIED',
                    title='Service Verified by Buyer',
                    message=f'Buyer has verified the service. Funds will be released to your wallet in 15 minutes. Ref: {transaction.reference}',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except Exception as e:
            logger.error(f"Error verifying service: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel transaction and refund buyer"""
        transaction = self.get_object()
        
        if transaction.buyer != request.user and transaction.seller != request.user:
            return Response(
                {'error': 'Only buyer or seller can cancel this transaction'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Binance-style: Only allow cancellation in early stages
        if transaction.status not in ['pending_payment', 'payment_received']:
            return Response(
                {'error': f'Cannot cancel transaction with status: {transaction.status}. Please open a dispute instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Abuse prevention: Check cancellation rate (prevent users from cancelling too many transactions)
        user = request.user
        recent_cancellations = P2PServiceTransaction.objects.filter(
            Q(buyer=user) | Q(seller=user),
            status='cancelled',
            cancelled_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # If user has cancelled more than 3 transactions in the last 7 days, require admin approval
        MAX_CANCELLATIONS_PER_WEEK = 3
        if recent_cancellations >= MAX_CANCELLATIONS_PER_WEEK:
            return Response(
                {
                    'error': f'You have cancelled {recent_cancellations} transaction(s) in the last 7 days. Please contact support to cancel this transaction.',
                    'cancellation_count': recent_cancellations,
                    'max_allowed': MAX_CANCELLATIONS_PER_WEEK
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with db_transaction.atomic():
                # Refund buyer if payment was received
                if transaction.status == 'payment_received':
                    buyer_wallet, _ = Wallet.objects.get_or_create(user=transaction.buyer)
                    balance_before = buyer_wallet.balance_cedis
                    
                    # ✅ FIX #1: Use atomic operation instead of deprecated method
                    try:
                        buyer_wallet.release_cedis_from_escrow_atomic(transaction.escrow_amount_cedis)
                    except ValidationError as ve:
                        return Response(
                            {'error': str(ve)},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    buyer_wallet.refresh_from_db()
                    
                    WalletTransaction.objects.create(
                        wallet=buyer_wallet,
                        transaction_type='escrow_release',
                        amount=transaction.escrow_amount_cedis,
                        currency='cedis',
                        status='completed',
                        reference=f"{transaction.reference}-CANCEL",
                        description=f"P2P service transaction cancelled. Escrow refunded. Ref: {transaction.reference}",
                        balance_before=balance_before,
                        balance_after=buyer_wallet.balance_cedis
                    )
                    
                    log_wallet_activity(
                        user=transaction.buyer,
                        amount=transaction.escrow_amount_cedis,
                        log_type='escrow_refund',
                        balance_after=buyer_wallet.balance_cedis,
                        transaction_id=transaction.reference
                    )
                
                # Restore available amount for sell listings (Binance-style)
                listing = transaction.listing
                if listing.listing_type == 'sell':
                    from django.db.models import F
                    listing.refresh_from_db()  # Get fresh data
                    # Restore the transaction amount back to available_amount_usd
                    listing.available_amount_usd = F('available_amount_usd') + transaction.amount_usd
                    listing.save(update_fields=['available_amount_usd'])
                    listing.refresh_from_db()
                    # Reactivate listing if it was marked as sold
                    if listing.status == 'sold':
                        listing.status = 'active'
                        listing.save(update_fields=['status'])
                else:
                    # For buy listings, just reactivate
                    listing.status = 'active'
                    listing.save(update_fields=['status'])
                
                # Update transaction
                transaction.status = 'cancelled'
                transaction.cancelled_at = timezone.now()
                transaction.save()
                
                create_notification(
                    user=transaction.buyer if transaction.buyer != request.user else transaction.seller,
                    notification_type='P2P_SERVICE_TRANSACTION_CANCELLED',
                    title='Transaction Cancelled',
                    message=f'Transaction {transaction.reference} has been cancelled.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceTransactionSerializer(transaction, context={'request': request}).data
                )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class P2PServiceDisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Service Disputes
    """
    serializer_class = P2PServiceDisputeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'dispute_type', 'transaction']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Users see disputes for their transactions, admins see all"""
        if self.request.user.is_staff:
            return P2PServiceDispute.objects.select_related('transaction', 'raised_by', 'assigned_to').all()
        # Users see disputes for transactions they're involved in
        return P2PServiceDispute.objects.filter(
            transaction__buyer=self.request.user
        ) | P2PServiceDispute.objects.filter(
            transaction__seller=self.request.user
        ).select_related('transaction', 'raised_by', 'assigned_to')

    def get_serializer_class(self):
        if self.action == 'create':
            return P2PServiceDisputeCreateSerializer
        return P2PServiceDisputeSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Create dispute with evidence images"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        transaction = serializer.validated_data['transaction']
        
        # Ensure user is part of the transaction
        if transaction.buyer != request.user and transaction.seller != request.user:
            return Response(
                {'error': 'You are not part of this transaction'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Handle evidence images
        evidence_images = []
        if 'evidence_images' in request.FILES:
            from django.core.files.storage import default_storage
            from orders.image_utils import process_uploaded_image
            from django.utils import timezone
            
            for img in request.FILES.getlist('evidence_images'):
                # Watermark the image before saving (users will see this in disputes)
                try:
                    img.seek(0)
                    img = process_uploaded_image(img, add_watermark_flag=True, watermark_text="CryptoGhana.com")
                except Exception as e:
                    logger.warning(f"Failed to watermark P2P dispute evidence image: {str(e)}")
                    # Continue with original image if watermarking fails
                    img.seek(0)
                
                # Save image and get URL
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'p2p_dispute_evidence/{transaction.id}/{timestamp}_{img.name}'
                saved_path = default_storage.save(filename, img)
                file_url = default_storage.url(saved_path)
                evidence_images.append(file_url)
        
        try:
            with db_transaction.atomic():
                dispute = serializer.save(
                    raised_by=request.user,
                    evidence_images=evidence_images,
                    status='open'
                )
                
                # Update transaction
                transaction.has_dispute = True
                transaction.status = 'disputed'
                transaction.save()
                
                # Log dispute creation
                log_p2p_dispute_action(
                    dispute=dispute,
                    action='dispute_created',
                    performed_by=request.user,
                    notes=f'Dispute created: {dispute.get_dispute_type_display()}'
                )
                
                # Notifications
                create_notification(
                    user=transaction.buyer if transaction.buyer != request.user else transaction.seller,
                    notification_type='P2P_SERVICE_DISPUTE_RAISED',
                    title='Dispute Raised',
                    message=f'A dispute has been raised for transaction {transaction.reference}. Admin will review.',
                    related_object_type='p2p_service_transaction',
                    related_object_id=transaction.id,
                )
                
                return Response(
                    P2PServiceDisputeSerializer(dispute, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f'Error creating dispute: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to create dispute. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class P2PServiceTransactionRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for P2P Service Transaction Ratings
    """
    serializer_class = P2PServiceTransactionRatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Users see ratings they gave or received, admins see all"""
        if self.request.user.is_staff:
            return P2PServiceTransactionRating.objects.select_related(
                'transaction', 'rater', 'rated_user'
            ).all()
        return P2PServiceTransactionRating.objects.filter(
            rater=self.request.user
        ) | P2PServiceTransactionRating.objects.filter(
            rated_user=self.request.user
        ).select_related('transaction', 'rater', 'rated_user')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return P2PServiceTransactionRatingCreateSerializer
        return P2PServiceTransactionRatingSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        """Create rating and update seller's trust score"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        transaction = serializer.validated_data['transaction']
        rating_value = serializer.validated_data['rating']
        comment = serializer.validated_data.get('comment', '')
        
        try:
            with db_transaction.atomic():
                rating = serializer.save(
                    rater=request.user,
                    rated_user=transaction.seller
                )
                
                # Note: successful_trades are already incremented when transaction completes
                # (in process_p2p_auto_actions command or signal handler)
                # We just need to update trust score based on rating
                
                # Update trust score based on rating
                # Good ratings (4-5 stars) increase trust, bad ratings (1-2 stars) decrease
                if rating_value >= 4:
                    # Good rating - small trust boost
                    transaction.seller.update_trust_score()
                elif rating_value <= 2:
                    # Bad rating - small trust penalty
                    transaction.seller.update_trust_score()
                
                return Response(
                    P2PServiceTransactionRatingSerializer(rating, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f'Error creating rating: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to create rating. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def for_seller(self, request):
        """Get all ratings for a specific seller"""
        seller_id = request.query_params.get('seller_id')
        if not seller_id:
            return Response(
                {'error': 'seller_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ratings = P2PServiceTransactionRating.objects.filter(
            rated_user_id=seller_id
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
        
        ratings = P2PServiceTransactionRating.objects.filter(
            rated_user_id=seller_id
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


class SellerApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Seller Applications
    - List: Users can see their own applications, admins can see all
    - Create: Authenticated users can apply
    - Update/Approve/Reject: Admin only
    """
    queryset = SellerApplication.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'user']
    ordering_fields = ['created_at', 'reviewed_at']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            from .p2p_serializers import SellerApplicationCreateSerializer
            return SellerApplicationCreateSerializer
        from .p2p_serializers import SellerApplicationSerializer
        return SellerApplicationSerializer
    
    def get_queryset(self):
        """Users can only see their own applications, admins can see all"""
        queryset = SellerApplication.objects.select_related('user', 'reviewed_by').all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset
    
    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """Create seller application with better error handling"""
        try:
            logger.info(f"Seller application request from user: {request.user.email}")
            
            # Parse FormData - handle QueryDict and JSON strings
            # QueryDict.copy() returns a shallow copy, we need to convert to dict
            data = dict(request.data)
            
            # QueryDict returns lists for values, get first item if it's a list
            for key in data:
                if isinstance(data[key], list) and len(data[key]) > 0:
                    data[key] = data[key][0]
            
            # Parse JSON string for service_types (when sent from FormData)
            if 'service_types' in data:
                service_types = data['service_types']
                if isinstance(service_types, str):
                    try:
                        data['service_types'] = json.loads(service_types)
                        logger.info(f"Parsed service_types from JSON string: {data['service_types']}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse service_types JSON: {str(e)}")
                        # Let the serializer handle the validation error
            
            # Merge files from request.FILES into data
            if hasattr(request, 'FILES') and request.FILES:
                for key, file in request.FILES.items():
                    data[key] = file
            
            # Log request data safely (avoid Unicode issues in Windows console)
            try:
                # Log only the keys and lengths, not the full content (which may contain Unicode)
                data_summary = {
                    'reason_length': len(str(data.get('reason', ''))),
                    'experience_length': len(str(data.get('experience', ''))),
                    'service_types': data.get('service_types', []),
                    'has_proof_of_funds': 'proof_of_funds_image' in data
                }
                logger.info(f"Request data summary: {data_summary}")
            except Exception as log_error:
                logger.info("Request data received (summary omitted due to encoding)")
            
            # Create serializer with parsed data
            serializer = self.get_serializer(data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            # Log error safely
            try:
                error_msg = str(e).encode('ascii', 'replace').decode('ascii')
                logger.error(f"Error creating seller application: {error_msg}", exc_info=True)
            except:
                logger.error("Error creating seller application (details omitted due to encoding)")
            # Re-raise to let DRF handle it properly
            raise
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve a seller application (admin only)"""
        application = self.get_object()
        if application.status != 'pending':
            return Response(
                {'error': f'Application is already {application.status}. Cannot approve.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        application.approve(request.user)
        serializer = self.get_serializer(application)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject a seller application (admin only)"""
        application = self.get_object()
        if application.status != 'pending':
            return Response(
                {'error': f'Application is already {application.status}. Cannot reject.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('rejection_reason', '')
        application.reject(request.user, reason)
        serializer = self.get_serializer(application)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def revoke(self, request, pk=None):
        """Revoke seller privileges (admin only)"""
        application = self.get_object()
        if application.status != 'approved':
            return Response(
                {'error': f'Application is {application.status}. Can only revoke approved sellers.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('rejection_reason', '')
        application.revoke(request.user, reason)
        serializer = self.get_serializer(application)
        return Response(serializer.data)

