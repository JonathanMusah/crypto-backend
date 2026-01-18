from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import SupportTicket, SupportTicketResponse, ContactEnquiry, SpecialRequest, PayPalRequest, PayPalTransaction, PayPalPurchaseRequest, CashAppRequest, CashAppTransaction, CashAppPurchaseRequest, ZelleRequest, ZelleTransaction
from .serializers import (
    SupportTicketSerializer,
    SupportTicketCreateSerializer,
    SupportTicketResponseSerializer,
    SupportTicketResponseCreateSerializer,
    ContactEnquirySerializer,
    ContactEnquiryCreateSerializer,
    SpecialRequestSerializer,
    SpecialRequestCreateSerializer,
    PayPalRequestSerializer,
    PayPalRequestCreateSerializer,
    PayPalTransactionSerializer,
    PayPalTransactionCreateSerializer,
    PayPalTransactionPaymentProofSerializer,
    PayPalPurchaseRequestSerializer,
    PayPalPurchaseRequestCreateSerializer,
    CashAppRequestSerializer,
    CashAppRequestCreateSerializer,
    CashAppTransactionSerializer,
    CashAppTransactionCreateSerializer,
    CashAppTransactionPaymentProofSerializer,
    CashAppPurchaseRequestSerializer,
    CashAppPurchaseRequestCreateSerializer,
    ZelleRequestSerializer,
    ZelleRequestCreateSerializer,
    ZelleTransactionSerializer,
    ZelleTransactionCreateSerializer,
    ZelleTransactionPaymentProofSerializer
)
from analytics.models import Settings
from notifications.utils import create_notification
from django.utils import timezone


class SupportTicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'category']
    search_fields = ['subject', 'message']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return SupportTicket.objects.all()
        return SupportTicket.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return SupportTicketCreateSerializer
        return SupportTicketSerializer

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        ticket = self.get_object()
        serializer = SupportTicketResponseCreateSerializer(
            data=request.data,
            context={'request': request, 'ticket': ticket}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        ticket = self.get_object()
        if not request.user.is_staff and ticket.user != request.user:
            return Response(
                {'error': 'You do not have permission to close this ticket.'},
                status=status.HTTP_403_FORBIDDEN
            )
        ticket.status = 'closed'
        ticket.save()
        return Response({'status': 'Ticket closed successfully'})


class SupportTicketResponseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SupportTicketResponseSerializer

    def get_queryset(self):
        ticket_id = self.request.query_params.get('ticket', None)
        if ticket_id:
            return SupportTicketResponse.objects.filter(ticket_id=ticket_id)
        if self.request.user.is_staff:
            return SupportTicketResponse.objects.all()
        return SupportTicketResponse.objects.filter(user=self.request.user)


class ContactEnquiryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for public contact enquiries (non-authenticated users)
    - Create: Public access (AllowAny)
    - List/Retrieve/Update: Admin only
    """
    queryset = ContactEnquiry.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'category']
    search_fields = ['name', 'email', 'subject', 'message']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        """Allow public creation, admin for everything else"""
        if self.action == 'create':
            return [AllowAny()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ContactEnquiryCreateSerializer
        return ContactEnquirySerializer

    def create(self, request, *args, **kwargs):
        """Create a new contact enquiry (public access)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        enquiry = serializer.save()
        
        # If user is authenticated, link it to their account
        if request.user.is_authenticated:
            enquiry.user = request.user
            enquiry.save()
        
        return Response(
            ContactEnquirySerializer(enquiry).data,
            status=status.HTTP_201_CREATED
        )


class SpecialRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for special requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'request_type']
    search_fields = ['title', 'description', 'reference']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return SpecialRequest.objects.all()
        return SpecialRequest.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return SpecialRequestCreateSerializer
        return SpecialRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new special request (check if feature is enabled)"""
        # Check if special requests are enabled
        settings = Settings.get_settings()
        if not settings.special_requests_enabled:
            return Response(
                {'error': 'Special requests feature is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        # Create notification for admin
        create_notification(
            user=request.user,
            notification_type='SPECIAL_REQUEST_CREATED',
            title='New Special Request',
            message=f'Your special request "{request_obj.title}" has been submitted and is pending review.',
            related_object_type='special_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            SpecialRequestSerializer(request_obj).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve special request"""
        request_obj = self.get_object()
        request_obj.status = 'approved'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='SPECIAL_REQUEST_APPROVED',
            title='Special Request Approved',
            message=f'Your special request "{request_obj.title}" has been approved. {request_obj.quote_notes or "Please check your request for details."}',
            related_object_type='special_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline special request"""
        request_obj = self.get_object()
        request_obj.status = 'declined'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        if request.data.get('admin_notes'):
            request_obj.admin_notes = request.data.get('admin_notes')
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='SPECIAL_REQUEST_DECLINED',
            title='Special Request Declined',
            message=f'Your special request "{request_obj.title}" has been declined. Please contact support for more information.',
            related_object_type='special_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request declined successfully'})


class PayPalRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for PayPal requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'transaction_type']
    search_fields = ['reference', 'paypal_email', 'recipient_email', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return PayPalRequest.objects.all().select_related('user', 'assigned_to', 'reviewed_by')
        return PayPalRequest.objects.filter(user=self.request.user).select_related('user', 'assigned_to', 'reviewed_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return PayPalRequestCreateSerializer
        return PayPalRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new PayPal request (check if feature is enabled)"""
        # Check if PayPal service is enabled
        settings = Settings.get_settings()
        if not settings.paypal_enabled:
            return Response(
                {'error': 'PayPal service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        # Create notification for admin
        create_notification(
            user=request.user,
            notification_type='PAYPAL_REQUEST_CREATED',
            title='New PayPal Request',
            message=f'Your PayPal request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been submitted and is pending review.',
            related_object_type='paypal_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            PayPalRequestSerializer(request_obj).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve PayPal request"""
        request_obj = self.get_object()
        request_obj.status = 'approved'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='PAYPAL_REQUEST_APPROVED',
            title='PayPal Request Approved',
            message=f'Your PayPal request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been approved. {request_obj.quote_notes or "Please check your request for details."}',
            related_object_type='paypal_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline PayPal request"""
        request_obj = self.get_object()
        request_obj.status = 'declined'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        if request.data.get('admin_notes'):
            request_obj.admin_notes = request.data.get('admin_notes')
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='PAYPAL_REQUEST_DECLINED',
            title='PayPal Request Declined',
            message=f'Your PayPal request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been declined. Please contact support for more information.',
            related_object_type='paypal_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request declined successfully'})


class PayPalTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for Buy/Sell PayPal transactions"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'transaction_type', 'current_step']
    search_fields = ['reference', 'paypal_email', 'payment_details']
    ordering_fields = ['created_at', 'updated_at', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return PayPalTransaction.objects.all().select_related('user', 'verified_by')
        return PayPalTransaction.objects.filter(user=self.request.user).select_related('user', 'verified_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return PayPalTransactionCreateSerializer
        elif self.action == 'upload_payment_proof':
            return PayPalTransactionPaymentProofSerializer
        return PayPalTransactionSerializer

    def create(self, request, *args, **kwargs):
        """Create a new PayPal transaction (Step 1: Details)"""
        # Check if PayPal service is enabled
        settings = Settings.get_settings()
        if not settings.paypal_enabled:
            return Response(
                {'error': 'PayPal service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        # Calculate amount in GHS using the appropriate rate
        if transaction.transaction_type == 'sell':
            # User sells PayPal, we pay them in GHS (using sell rate - what we pay)
            transaction.exchange_rate = settings.paypal_sell_rate
            transaction.amount_cedis = transaction.amount_usd * settings.paypal_sell_rate
            # Set admin PayPal email (where user should send PayPal to)
            if settings.admin_paypal_email:
                transaction.admin_paypal_email = settings.admin_paypal_email
        else:  # buy
            # User buys PayPal, they pay us in GHS (using buy rate - what they pay)
            transaction.exchange_rate = settings.paypal_buy_rate
            transaction.amount_cedis = transaction.amount_usd * settings.paypal_buy_rate
        
        transaction.save()
        
        # Create notification
        create_notification(
            user=request.user,
            notification_type='PAYPAL_TRANSACTION_CREATED',
            title='PayPal Transaction Created',
            message=f'Your {transaction.get_transaction_type_display()} transaction for ${transaction.amount_usd} has been created. Please proceed to upload payment proof.',
            related_object_type='paypal_transaction',
            related_object_id=transaction.id,
        )
        
        return Response(
            PayPalTransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_payment_proof(self, request, pk=None):
        """Upload payment proof (Step 2: Payment Proof)"""
        transaction = self.get_object()
        
        # Verify user owns this transaction
        if transaction.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to modify this transaction.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already has payment proof
        if transaction.payment_proof:
            return Response(
                {'error': 'Payment proof already uploaded. Please contact support if you need to update it.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PayPalTransactionPaymentProofSerializer(transaction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        # Update status and step
        transaction.status = 'payment_sent'
        transaction.current_step = 'payment_proof'
        transaction.payment_sent_at = timezone.now()
        transaction.save()
        
        # Create notification for admin
        create_notification(
            user=request.user,
            notification_type='PAYPAL_PAYMENT_PROOF_UPLOADED',
            title='Payment Proof Uploaded',
            message=f'Payment proof has been uploaded for transaction {transaction.reference}. Awaiting admin verification.',
            related_object_type='paypal_transaction',
            related_object_id=transaction.id,
        )
        
        return Response(
            PayPalTransactionSerializer(transaction).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify_payment(self, request, pk=None):
        """Admin: Verify payment proof"""
        transaction = self.get_object()
        transaction.status = 'payment_verified'
        transaction.current_step = 'verified'
        transaction.payment_verified_at = timezone.now()
        transaction.verified_by = request.user
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='PAYPAL_PAYMENT_VERIFIED',
            title='Payment Verified',
            message=f'Your payment for transaction {transaction.reference} has been verified. Processing will begin shortly.',
            related_object_type='paypal_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Payment verified successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark transaction as completed"""
        transaction = self.get_object()
        transaction.status = 'completed'
        transaction.current_step = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='PAYPAL_TRANSACTION_COMPLETED',
            title='Transaction Completed',
            message=f'Your {transaction.get_transaction_type_display()} transaction {transaction.reference} has been completed.',
            related_object_type='paypal_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction completed successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline transaction"""
        transaction = self.get_object()
        transaction.status = 'declined'
        if request.data.get('admin_notes'):
            transaction.admin_notes = request.data.get('admin_notes')
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='PAYPAL_TRANSACTION_DECLINED',
            title='Transaction Declined',
            message=f'Your transaction {transaction.reference} has been declined. Please contact support for more information.',
            related_object_type='paypal_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction declined successfully'})


class PayPalPurchaseRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for PayPal Purchase Requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority']
    search_fields = ['reference', 'item_name', 'recipient_paypal_email', 'item_description']
    ordering_fields = ['created_at', 'updated_at', 'amount_usd', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return PayPalPurchaseRequest.objects.all().select_related('user', 'assigned_to', 'reviewed_by')
        return PayPalPurchaseRequest.objects.filter(user=self.request.user).select_related('user', 'assigned_to', 'reviewed_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return PayPalPurchaseRequestCreateSerializer
        return PayPalPurchaseRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new PayPal purchase request (check if feature is enabled)"""
        # Check if PayPal service is enabled
        settings_obj = Settings.get_settings()
        if not settings_obj.paypal_enabled:
            return Response(
                {'error': 'PayPal service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        # Create notification for admin
        create_notification(
            user=request.user,
            notification_type='PAYPAL_PURCHASE_REQUEST_CREATED',
            title='New PayPal Purchase Request',
            message=f'Your purchase request for "{request_obj.item_name}" (${request_obj.amount_usd}) has been submitted and is pending review.',
            related_object_type='paypal_purchase_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            PayPalPurchaseRequestSerializer(request_obj, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def provide_quote(self, request, pk=None):
        """Admin: Provide quote for the purchase request"""
        purchase_request = self.get_object()
        quote_amount_cedis = request.data.get('quote_amount_cedis')
        exchange_rate = request.data.get('exchange_rate')
        service_fee = request.data.get('service_fee', 0)
        quote_notes = request.data.get('quote_notes', '')
        
        if not quote_amount_cedis:
            return Response(
                {'error': 'Quote amount in cedis is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        purchase_request.status = 'quoted'
        purchase_request.quote_amount_cedis = quote_amount_cedis
        purchase_request.exchange_rate = exchange_rate or Settings.get_settings().paypal_buy_rate
        purchase_request.service_fee = service_fee
        purchase_request.quote_notes = quote_notes
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_QUOTE_PROVIDED',
            title='Purchase Request Quote Provided',
            message=f'A quote has been provided for your purchase request "{purchase_request.item_name}". Please review and confirm to proceed. Amount: ₵{quote_amount_cedis}',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Quote provided successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve purchase request"""
        purchase_request = self.get_object()
        purchase_request.status = 'approved'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        if request.data.get('assigned_to'):
            purchase_request.assigned_to_id = request.data.get('assigned_to')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_APPROVED',
            title='Purchase Request Approved',
            message=f'Your purchase request for "{purchase_request.item_name}" has been approved. Please proceed with payment of ₵{purchase_request.quote_amount_cedis or "TBD"}.',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline purchase request"""
        purchase_request = self.get_object()
        purchase_request.status = 'declined'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        if request.data.get('admin_notes'):
            purchase_request.admin_notes = request.data.get('admin_notes')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_DECLINED',
            title='Purchase Request Declined',
            message=f'Your purchase request for "{purchase_request.item_name}" has been declined. Please contact support for more information.',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request declined successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_paid(self, request, pk=None):
        """Admin: Mark user payment as received"""
        purchase_request = self.get_object()
        purchase_request.status = 'processing'
        purchase_request.paid_at = timezone.now()
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_PAYMENT_RECEIVED',
            title='Payment Received',
            message=f'Your payment for purchase request "{purchase_request.item_name}" has been received. We will now process your purchase.',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Payment marked as received'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_purchased(self, request, pk=None):
        """Admin: Mark purchase as completed (PayPal payment made)"""
        purchase_request = self.get_object()
        purchase_request.status = 'processing'
        purchase_request.purchased_at = timezone.now()
        if request.data.get('delivery_tracking'):
            purchase_request.delivery_tracking = request.data.get('delivery_tracking')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_COMPLETED',
            title='Purchase Completed',
            message=f'Your purchase for "{purchase_request.item_name}" has been completed. {f"Tracking: {purchase_request.delivery_tracking}" if purchase_request.delivery_tracking else "Please check your item/service."}',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Purchase marked as completed'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark request as fully completed"""
        purchase_request = self.get_object()
        purchase_request.status = 'completed'
        purchase_request.completed_at = timezone.now()
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='PAYPAL_PURCHASE_FULLY_COMPLETED',
            title='Request Fully Completed',
            message=f'Your purchase request for "{purchase_request.item_name}" has been fully completed. Thank you for using our service!',
            related_object_type='paypal_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request completed successfully'})


# CashApp ViewSets - Following the same pattern as PayPal
class CashAppRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for CashApp requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'transaction_type']
    search_fields = ['reference', 'cashapp_tag', 'recipient_tag', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return CashAppRequest.objects.all().select_related('user', 'assigned_to', 'reviewed_by')
        return CashAppRequest.objects.filter(user=self.request.user).select_related('user', 'assigned_to', 'reviewed_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return CashAppRequestCreateSerializer
        return CashAppRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new CashApp request (check if feature is enabled)"""
        settings = Settings.get_settings()
        if not settings.cashapp_enabled:
            return Response(
                {'error': 'CashApp service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        create_notification(
            user=request.user,
            notification_type='CASHAPP_REQUEST_CREATED',
            title='New CashApp Request',
            message=f'Your CashApp request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been submitted and is pending review.',
            related_object_type='cashapp_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            CashAppRequestSerializer(request_obj).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve CashApp request"""
        request_obj = self.get_object()
        request_obj.status = 'approved'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='CASHAPP_REQUEST_APPROVED',
            title='CashApp Request Approved',
            message=f'Your CashApp request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been approved. {request_obj.quote_notes or "Please check your request for details."}',
            related_object_type='cashapp_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline CashApp request"""
        request_obj = self.get_object()
        request_obj.status = 'declined'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        if request.data.get('admin_notes'):
            request_obj.admin_notes = request.data.get('admin_notes')
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='CASHAPP_REQUEST_DECLINED',
            title='CashApp Request Declined',
            message=f'Your CashApp request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been declined. Please contact support for more information.',
            related_object_type='cashapp_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request declined successfully'})


class CashAppTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for Buy/Sell CashApp transactions"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'transaction_type', 'current_step']
    search_fields = ['reference', 'cashapp_tag', 'payment_details']
    ordering_fields = ['created_at', 'updated_at', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return CashAppTransaction.objects.all().select_related('user', 'verified_by')
        return CashAppTransaction.objects.filter(user=self.request.user).select_related('user', 'verified_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return CashAppTransactionCreateSerializer
        elif self.action == 'upload_payment_proof':
            return CashAppTransactionPaymentProofSerializer
        return CashAppTransactionSerializer

    def create(self, request, *args, **kwargs):
        """Create a new CashApp transaction (Step 1: Details)"""
        settings = Settings.get_settings()
        if not settings.cashapp_enabled:
            return Response(
                {'error': 'CashApp service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        # Calculate amount in GHS using the appropriate rate
        if transaction.transaction_type == 'sell':
            transaction.exchange_rate = settings.cashapp_sell_rate
            transaction.amount_cedis = transaction.amount_usd * settings.cashapp_sell_rate
            if settings.admin_cashapp_tag:
                transaction.admin_cashapp_tag = settings.admin_cashapp_tag
        else:  # buy
            transaction.exchange_rate = settings.cashapp_buy_rate
            transaction.amount_cedis = transaction.amount_usd * settings.cashapp_buy_rate
        
        transaction.save()
        
        create_notification(
            user=request.user,
            notification_type='CASHAPP_TRANSACTION_CREATED',
            title='CashApp Transaction Created',
            message=f'Your {transaction.get_transaction_type_display()} transaction for ${transaction.amount_usd} has been created. Please proceed to upload payment proof.',
            related_object_type='cashapp_transaction',
            related_object_id=transaction.id,
        )
        
        return Response(
            CashAppTransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_payment_proof(self, request, pk=None):
        """Upload payment proof (Step 2: Payment Proof)"""
        transaction = self.get_object()
        
        if transaction.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to modify this transaction.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if transaction.payment_proof:
            return Response(
                {'error': 'Payment proof already uploaded. Please contact support if you need to update it.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CashAppTransactionPaymentProofSerializer(transaction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        transaction.status = 'payment_sent'
        transaction.current_step = 'payment_proof'
        transaction.payment_sent_at = timezone.now()
        transaction.save()
        
        create_notification(
            user=request.user,
            notification_type='CASHAPP_PAYMENT_PROOF_UPLOADED',
            title='Payment Proof Uploaded',
            message=f'Payment proof has been uploaded for transaction {transaction.reference}. Awaiting admin verification.',
            related_object_type='cashapp_transaction',
            related_object_id=transaction.id,
        )
        
        return Response(
            CashAppTransactionSerializer(transaction).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify_payment(self, request, pk=None):
        """Admin: Verify payment proof"""
        transaction = self.get_object()
        transaction.status = 'payment_verified'
        transaction.current_step = 'verified'
        transaction.payment_verified_at = timezone.now()
        transaction.verified_by = request.user
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='CASHAPP_PAYMENT_VERIFIED',
            title='Payment Verified',
            message=f'Your payment for transaction {transaction.reference} has been verified. Processing will begin shortly.',
            related_object_type='cashapp_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Payment verified successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark transaction as completed"""
        transaction = self.get_object()
        transaction.status = 'completed'
        transaction.current_step = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='CASHAPP_TRANSACTION_COMPLETED',
            title='Transaction Completed',
            message=f'Your {transaction.get_transaction_type_display()} transaction {transaction.reference} has been completed.',
            related_object_type='cashapp_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction completed successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline transaction"""
        transaction = self.get_object()
        transaction.status = 'declined'
        if request.data.get('admin_notes'):
            transaction.admin_notes = request.data.get('admin_notes')
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='CASHAPP_TRANSACTION_DECLINED',
            title='Transaction Declined',
            message=f'Your transaction {transaction.reference} has been declined. Please contact support for more information.',
            related_object_type='cashapp_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction declined successfully'})


class CashAppPurchaseRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for CashApp Purchase Requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority']
    search_fields = ['reference', 'item_name', 'recipient_cashapp_tag', 'item_description']
    ordering_fields = ['created_at', 'updated_at', 'amount_usd', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return CashAppPurchaseRequest.objects.all().select_related('user', 'assigned_to', 'reviewed_by')
        return CashAppPurchaseRequest.objects.filter(user=self.request.user).select_related('user', 'assigned_to', 'reviewed_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return CashAppPurchaseRequestCreateSerializer
        return CashAppPurchaseRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new CashApp purchase request (check if feature is enabled)"""
        settings_obj = Settings.get_settings()
        if not settings_obj.cashapp_enabled:
            return Response(
                {'error': 'CashApp service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        create_notification(
            user=request.user,
            notification_type='CASHAPP_PURCHASE_REQUEST_CREATED',
            title='New CashApp Purchase Request',
            message=f'Your purchase request for "{request_obj.item_name}" (${request_obj.amount_usd}) has been submitted and is pending review.',
            related_object_type='cashapp_purchase_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            CashAppPurchaseRequestSerializer(request_obj, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def provide_quote(self, request, pk=None):
        """Admin: Provide quote for the purchase request"""
        purchase_request = self.get_object()
        quote_amount_cedis = request.data.get('quote_amount_cedis')
        exchange_rate = request.data.get('exchange_rate')
        service_fee = request.data.get('service_fee', 0)
        quote_notes = request.data.get('quote_notes', '')
        
        if not quote_amount_cedis:
            return Response(
                {'error': 'Quote amount in cedis is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        purchase_request.status = 'quoted'
        purchase_request.quote_amount_cedis = quote_amount_cedis
        purchase_request.exchange_rate = exchange_rate or Settings.get_settings().cashapp_buy_rate
        purchase_request.service_fee = service_fee
        purchase_request.quote_notes = quote_notes
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_QUOTE_PROVIDED',
            title='Purchase Request Quote Provided',
            message=f'A quote has been provided for your purchase request "{purchase_request.item_name}". Please review and confirm to proceed. Amount: ₵{quote_amount_cedis}',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Quote provided successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve purchase request"""
        purchase_request = self.get_object()
        purchase_request.status = 'approved'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        if request.data.get('assigned_to'):
            purchase_request.assigned_to_id = request.data.get('assigned_to')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_APPROVED',
            title='Purchase Request Approved',
            message=f'Your purchase request for "{purchase_request.item_name}" has been approved. Please proceed with payment of ₵{purchase_request.quote_amount_cedis or "TBD"}.',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline purchase request"""
        purchase_request = self.get_object()
        purchase_request.status = 'declined'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.reviewed_by = request.user
        if request.data.get('admin_notes'):
            purchase_request.admin_notes = request.data.get('admin_notes')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_DECLINED',
            title='Purchase Request Declined',
            message=f'Your purchase request for "{purchase_request.item_name}" has been declined. Please contact support for more information.',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request declined successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_paid(self, request, pk=None):
        """Admin: Mark user payment as received"""
        purchase_request = self.get_object()
        purchase_request.status = 'processing'
        purchase_request.paid_at = timezone.now()
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_PAYMENT_RECEIVED',
            title='Payment Received',
            message=f'Your payment for purchase request "{purchase_request.item_name}" has been received. We will now process your purchase.',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Payment marked as received'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_purchased(self, request, pk=None):
        """Admin: Mark purchase as completed (CashApp payment made)"""
        purchase_request = self.get_object()
        purchase_request.status = 'processing'
        purchase_request.purchased_at = timezone.now()
        if request.data.get('delivery_tracking'):
            purchase_request.delivery_tracking = request.data.get('delivery_tracking')
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_COMPLETED',
            title='Purchase Completed',
            message=f'Your purchase for "{purchase_request.item_name}" has been completed. {f"Tracking: {purchase_request.delivery_tracking}" if purchase_request.delivery_tracking else "Please check your item/service."}',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Purchase marked as completed'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark request as fully completed"""
        purchase_request = self.get_object()
        purchase_request.status = 'completed'
        purchase_request.completed_at = timezone.now()
        purchase_request.save()
        
        create_notification(
            user=purchase_request.user,
            notification_type='CASHAPP_PURCHASE_FULLY_COMPLETED',
            title='Request Fully Completed',
            message=f'Your purchase request for "{purchase_request.item_name}" has been fully completed. Thank you for using our service!',
            related_object_type='cashapp_purchase_request',
            related_object_id=purchase_request.id,
        )
        
        return Response({'status': 'Request completed successfully'})


# Zelle ViewSets - Following the same pattern as PayPal and CashApp
class ZelleRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for Zelle requests"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'transaction_type']
    search_fields = ['reference', 'zelle_email', 'recipient_email', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return ZelleRequest.objects.all().select_related('user', 'assigned_to', 'reviewed_by')
        return ZelleRequest.objects.filter(user=self.request.user).select_related('user', 'assigned_to', 'reviewed_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return ZelleRequestCreateSerializer
        return ZelleRequestSerializer

    def create(self, request, *args, **kwargs):
        """Create a new Zelle request (check if feature is enabled)"""
        settings = Settings.get_settings()
        if not settings.zelle_enabled:
            return Response(
                {'error': 'Zelle service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()
        
        create_notification(
            user=request.user,
            notification_type='ZELLE_REQUEST_CREATED',
            title='New Zelle Request',
            message=f'Your Zelle request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been submitted and is pending review.',
            related_object_type='zelle_request',
            related_object_id=request_obj.id,
        )
        
        return Response(
            ZelleRequestSerializer(request_obj).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve Zelle request"""
        request_obj = self.get_object()
        request_obj.status = 'approved'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='ZELLE_REQUEST_APPROVED',
            title='Zelle Request Approved',
            message=f'Your Zelle request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been approved. {request_obj.quote_notes or "Please check your request for details."}',
            related_object_type='zelle_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request approved successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline Zelle request"""
        request_obj = self.get_object()
        request_obj.status = 'declined'
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        if request.data.get('admin_notes'):
            request_obj.admin_notes = request.data.get('admin_notes')
        request_obj.save()
        
        create_notification(
            user=request_obj.user,
            notification_type='ZELLE_REQUEST_DECLINED',
            title='Zelle Request Declined',
            message=f'Your Zelle request ({request_obj.get_transaction_type_display()}) for ${request_obj.amount_usd} has been declined. Please contact support for more information.',
            related_object_type='zelle_request',
            related_object_id=request_obj.id,
        )
        
        return Response({'status': 'Request declined successfully'})


class ZelleTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for Buy/Sell Zelle transactions"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'transaction_type', 'current_step']
    search_fields = ['reference', 'zelle_email', 'payment_details']
    ordering_fields = ['created_at', 'updated_at', 'amount_usd']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return ZelleTransaction.objects.all().select_related('user', 'verified_by')
        return ZelleTransaction.objects.filter(user=self.request.user).select_related('user', 'verified_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return ZelleTransactionCreateSerializer
        elif self.action == 'upload_payment_proof':
            return ZelleTransactionPaymentProofSerializer
        return ZelleTransactionSerializer

    def create(self, request, *args, **kwargs):
        """Create a new Zelle transaction (Step 1: Details)"""
        settings = Settings.get_settings()
        if not settings.zelle_enabled:
            return Response(
                {'error': 'Zelle service is currently disabled. Please contact support for assistance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        
        if transaction.transaction_type == 'sell':
            transaction.exchange_rate = settings.zelle_sell_rate
            transaction.amount_cedis = transaction.amount_usd * settings.zelle_sell_rate
            if settings.admin_zelle_email:
                transaction.admin_zelle_email = settings.admin_zelle_email
        else:  # buy
            transaction.exchange_rate = settings.zelle_buy_rate
            transaction.amount_cedis = transaction.amount_usd * settings.zelle_buy_rate
        
        transaction.save()
        
        create_notification(
            user=request.user,
            notification_type='ZELLE_TRANSACTION_CREATED',
            title='Zelle Transaction Created',
            message=f'Your {transaction.get_transaction_type_display()} transaction for ${transaction.amount_usd} has been created. Please proceed to upload payment proof.',
            related_object_type='zelle_transaction',
            related_object_id=transaction.id,
        )
        
        return Response(
            ZelleTransactionSerializer(transaction, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_payment_proof(self, request, pk=None):
        """Upload payment proof for a transaction"""
        transaction = self.get_object()
        
        # Only allow user to upload proof for their own transactions
        if transaction.user != request.user:
            return Response(
                {'error': 'You can only upload payment proof for your own transactions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ZelleTransactionPaymentProofSerializer(transaction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_transaction = serializer.save()
        
        create_notification(
            user=request.user,
            notification_type='ZELLE_PAYMENT_PROOF_UPLOADED',
            title='Payment Proof Uploaded',
            message=f'Payment proof for transaction {updated_transaction.reference} has been uploaded. Awaiting admin verification.',
            related_object_type='zelle_transaction',
            related_object_id=updated_transaction.id,
        )
        
        return Response(
            ZelleTransactionSerializer(updated_transaction, context={'request': request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify_payment(self, request, pk=None):
        """Admin: Verify payment proof"""
        transaction = self.get_object()
        transaction.status = 'payment_verified'
        transaction.current_step = 'verified'
        transaction.payment_verified_at = timezone.now()
        transaction.verified_by = request.user
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='ZELLE_PAYMENT_VERIFIED',
            title='Payment Verified',
            message=f'Your payment for transaction {transaction.reference} has been verified. Processing will begin shortly.',
            related_object_type='zelle_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Payment verified successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark transaction as completed"""
        transaction = self.get_object()
        transaction.status = 'completed'
        transaction.current_step = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='ZELLE_TRANSACTION_COMPLETED',
            title='Transaction Completed',
            message=f'Your {transaction.get_transaction_type_display()} transaction {transaction.reference} has been completed.',
            related_object_type='zelle_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction completed successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline transaction"""
        transaction = self.get_object()
        transaction.status = 'declined'
        if request.data.get('admin_notes'):
            transaction.admin_notes = request.data.get('admin_notes')
        transaction.save()
        
        create_notification(
            user=transaction.user,
            notification_type='ZELLE_TRANSACTION_DECLINED',
            title='Transaction Declined',
            message=f'Your transaction {transaction.reference} has been declined. Please contact support for more information.',
            related_object_type='zelle_transaction',
            related_object_id=transaction.id,
        )
        
        return Response({'status': 'Transaction declined successfully'})

