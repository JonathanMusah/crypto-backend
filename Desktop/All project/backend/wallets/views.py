from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging
from .models import Wallet, WalletTransaction, CryptoTransaction, AdminCryptoAddress, AdminPaymentDetails, Deposit, Withdrawal, WalletLog
from .serializers import (
    WalletSerializer, 
    WalletTransactionSerializer,
    DepositSerializer,
    MomoDepositSerializer,
    CryptoDepositSerializer,
    WithdrawSerializer,
    MomoWithdrawalSerializer,
    CryptoWithdrawalSerializer,
    WithdrawalSerializer,
    CryptoBuySerializer,
    CryptoSellSerializer,
    CryptoTransactionSerializer,
    CryptoTransactionApprovalSerializer,
    AdminCryptoAddressSerializer
)

logger = logging.getLogger(__name__)


def log_wallet_activity(user, amount, log_type, balance_after, transaction_id=None):
    """Helper function to log wallet activities"""
    WalletLog.objects.create(
        user=user,
        amount=amount,
        log_type=log_type,
        transaction_id=transaction_id,
        balance_after=balance_after
    )


class WalletViewSet(viewsets.ModelViewSet):
    serializer_class = WalletSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['updated_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Wallet.objects.all()
        return Wallet.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get user's wallet balance"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(wallet)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def deposit(self, request):
        """Simulate deposit (add funds to wallet)"""
        logger.info(f"Deposit attempt by user {request.user.email}")
        serializer = DepositSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Deposit validation failed for user {request.user.email}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wallet, created = Wallet.objects.get_or_create(user=request.user)
        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']
        payment_ref = serializer.validated_data.get('payment_reference', '')

        try:
            with db_transaction.atomic():
                # Record balance before
                balance_before = wallet.balance_cedis

                # Add funds
                wallet.add_cedis(amount)
                wallet.refresh_from_db()

                # Create transaction record
                wallet_txn = WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='deposit',
                    amount=amount,
                    currency='cedis',
                    status='completed',
                    reference=WalletTransaction.generate_reference('DEP'),
                    description=f"Deposit via {payment_method}. Ref: {payment_ref}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=request.user,
                    amount=amount,
                    log_type='deposit',
                    balance_after=wallet.balance_cedis,
                    transaction_id=wallet_txn.reference
                )

                logger.info(f"Deposit successful for user {request.user.email}: {amount} cedis")
                return Response({
                    'message': 'Deposit successful',
                    'transaction': WalletTransactionSerializer(wallet_txn).data,
                    'wallet': WalletSerializer(wallet).data
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Deposit failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def withdraw(self, request):
        """Simulate withdrawal (remove funds from wallet)"""
        serializer = WithdrawSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wallet, created = Wallet.objects.get_or_create(user=request.user)
        amount = serializer.validated_data['amount']
        withdrawal_method = serializer.validated_data['withdrawal_method']
        account_number = serializer.validated_data['account_number']

        # Check sufficient balance
        if not wallet.has_sufficient_cedis(amount):
            return Response(
                {'error': 'Insufficient balance'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                # Record balance before
                balance_before = wallet.balance_cedis

                # Deduct funds
                wallet.balance_cedis -= amount
                wallet.save()

                # Create transaction record
                wallet_txn = WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='withdraw',
                    amount=amount,
                    currency='cedis',
                    status='completed',
                    reference=WalletTransaction.generate_reference('WTH'),
                    description=f"Withdrawal via {withdrawal_method} to {account_number}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )

                return Response({
                    'message': 'Withdrawal successful',
                    'transaction': WalletTransactionSerializer(wallet_txn).data,
                    'wallet': WalletSerializer(wallet).data
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def buy_crypto(self, request):
        """Buy crypto - user pays via MoMo externally, admin sends crypto to user's address"""
        logger.info(f"Buy crypto attempt by user {request.user.email}")
        
        # ✅ FIX #5: Enhanced validation serializer
        from .validation_serializers import CryptoBuyValidationSerializer
        serializer = CryptoBuyValidationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Buy crypto validation failed for user {request.user.email}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        crypto_amount = serializer.validated_data['crypto_amount']
        rate = serializer.validated_data['rate']
        cedis_amount = serializer.validated_data['cedis_amount']
        payment_method = serializer.validated_data['payment_method']
        crypto_id = serializer.validated_data.get('crypto_id', '')
        network = serializer.validated_data.get('network', '')
        user_address = serializer.validated_data.get('user_address', '')

        # NO BALANCE CHECK - User pays externally via MoMo
        try:
            # ✅ FIX #2: Row-level locking with select_for_update()
            with db_transaction.atomic():
                wallet, created = Wallet.objects.select_for_update().get_or_create(user=request.user)
                
                # Create crypto transaction with status 'awaiting_admin'
                crypto_txn = CryptoTransaction.objects.create(
                    user=request.user,
                    type='buy',
                    crypto_id=crypto_id,
                    network=network,
                    cedis_amount=cedis_amount,
                    crypto_amount=crypto_amount,
                    rate=rate,
                    status='awaiting_admin',  # Changed from 'pending' to 'awaiting_admin'
                    payment_method=payment_method,
                    user_address=user_address,
                    reference=CryptoTransaction.generate_reference('BUY'),
                    escrow_locked=False  # No escrow needed - user pays externally
                )

                logger.info(f"Buy crypto order created for user {request.user.email}: {crypto_amount} crypto")
                return Response({
                    'message': 'Buy order created. Please make payment via MoMo. Order pending admin confirmation.',
                    'transaction': CryptoTransactionSerializer(crypto_txn).data,
                    'wallet': WalletSerializer(wallet).data
                }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            logger.warning(f"Buy crypto validation error for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Buy crypto failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def sell_crypto(self, request):
        """Sell crypto - user sends crypto externally, admin credits wallet after verification"""
        # ✅ FIX #5: Enhanced validation serializer
        from .validation_serializers import CryptoSellValidationSerializer
        serializer = CryptoSellValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        crypto_amount = serializer.validated_data['crypto_amount']
        rate = serializer.validated_data['rate']
        cedis_amount = serializer.validated_data['cedis_amount']
        crypto_id = serializer.validated_data.get('crypto_id', '')
        network = serializer.validated_data.get('network', '')
        momo_number = serializer.validated_data.get('momo_number', '')
        momo_name = serializer.validated_data.get('momo_name', '')
        transaction_id = serializer.validated_data.get('transaction_id', '')
        payment_proof = serializer.validated_data.get('payment_proof')

        # NO BALANCE CHECK - User sends crypto externally
        try:
            # ✅ FIX #2: Row-level locking with select_for_update()
            with db_transaction.atomic():
                wallet, created = Wallet.objects.select_for_update().get_or_create(user=request.user)
                
                # Get admin's receiving address for this crypto+network
                admin_address_obj = AdminCryptoAddress.objects.filter(
                    crypto_id=crypto_id,
                    network=network,
                    is_active=True
                ).first()
                
                admin_address = admin_address_obj.address if admin_address_obj else ''
                
                if not admin_address:
                    logger.warning(f"No admin address found for {crypto_id} on {network}")
                    # Still create the order, admin can add address later

                # Create crypto transaction with status 'awaiting_admin'
                crypto_txn = CryptoTransaction.objects.create(
                    user=request.user,
                    type='sell',
                    crypto_id=crypto_id,
                    network=network,
                    cedis_amount=cedis_amount,
                    crypto_amount=crypto_amount,
                    rate=rate,
                    status='awaiting_admin',  # Changed from 'pending' to 'awaiting_admin'
                    payment_method='crypto',
                    admin_address=admin_address,
                    momo_number=momo_number,
                    momo_name=momo_name,
                    transaction_id=transaction_id,
                    payment_proof=payment_proof,
                    reference=CryptoTransaction.generate_reference('SELL'),
                    escrow_locked=False  # No escrow needed - user sends externally
                )

                logger.info(f"Sell crypto order created for user {request.user.email}: {crypto_amount} crypto")
                return Response({
                    'message': 'Sell order created. Please send crypto to admin address. Order pending admin confirmation.',
                    'transaction': CryptoTransactionSerializer(crypto_txn, context={'request': request}).data,
                    'wallet': WalletSerializer(wallet).data
                }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Sell crypto failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Get user's wallet transaction history"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        transactions = WalletTransaction.objects.filter(wallet=wallet)
        
        # Apply filters
        transaction_type = request.query_params.get('type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        serializer = WalletTransactionSerializer(transactions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def escrow_status(self, request):
        """Get user's escrow status and pending transactions"""
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        pending_crypto_txns = CryptoTransaction.objects.filter(
            user=request.user,
            status__in=['pending', 'awaiting_admin']
        )

        return Response({
            'escrow_balance': float(wallet.escrow_balance),
            'pending_transactions': CryptoTransactionSerializer(pending_crypto_txns, many=True).data,
            'total_pending': pending_crypto_txns.count()
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def activity_logs(self, request):
        """Get user's wallet activity logs"""
        # Users see only their logs, admins can see all or filter by user
        if request.user.is_staff:
            user_id = request.query_params.get('user_id')
            if user_id:
                logs = WalletLog.objects.filter(user_id=user_id)
            else:
                logs = WalletLog.objects.all()
        else:
            logs = WalletLog.objects.filter(user=request.user)
        
        # Apply filters
        log_type = request.query_params.get('log_type')
        if log_type:
            logs = logs.filter(log_type=log_type)
        
        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(logs, request)
        
        from .serializers import WalletLogSerializer
        serializer = WalletLogSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)


class CryptoTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = CryptoTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'status', 'payment_method']
    search_fields = ['reference']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CryptoTransaction.objects.all()
        return CryptoTransaction.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve crypto transaction - for BUY: send crypto to user, for SELL: credit wallet"""
        logger.info(f"Admin {request.user.email} approving transaction {pk}")
        crypto_txn = self.get_object()
        
        if crypto_txn.status != 'awaiting_admin':
            logger.warning(f"Transaction {pk} is not awaiting admin, status: {crypto_txn.status}")
            return Response(
                {'error': 'Transaction is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CryptoTransactionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Approval validation failed for transaction {pk}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_note = serializer.validated_data.get('admin_note', '')

        try:
            with db_transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=crypto_txn.user)

                if crypto_txn.type == 'buy':
                    # Admin has verified MoMo payment and sends crypto to user's external address
                    # Platform doesn't hold crypto - crypto is sent externally, no wallet update needed
                    # Just record the transaction for history
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='crypto_buy',
                        amount=crypto_txn.cedis_amount,  # Record the cedis amount paid
                        currency='cedis',  # Platform is fiat-only
                        status='completed',
                        reference=crypto_txn.reference,
                        description=f"Crypto buy completed: {crypto_txn.crypto_amount} {crypto_txn.crypto_id} sent to {crypto_txn.user_address}. Paid {crypto_txn.cedis_amount} cedis via {crypto_txn.payment_method}",
                        balance_before=wallet.balance_cedis,  # No change to wallet balance
                        balance_after=wallet.balance_cedis
                    )

                else:  # sell
                    # Admin has verified crypto receipt and credits user's wallet with cedis
                    balance_before = wallet.balance_cedis
                    wallet.add_cedis(crypto_txn.cedis_amount)
                    wallet.refresh_from_db()

                    # Create wallet transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='crypto_sell',
                        amount=crypto_txn.cedis_amount,
                        currency='cedis',
                        status='completed',
                        reference=crypto_txn.reference,
                        description=f"Crypto sell completed: {crypto_txn.crypto_amount} {crypto_txn.crypto_id} received, {crypto_txn.cedis_amount} cedis credited. MoMo: {crypto_txn.momo_number}",
                        balance_before=balance_before,
                        balance_after=wallet.balance_cedis
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=crypto_txn.user,
                        amount=crypto_txn.cedis_amount,
                        log_type='deposit',
                        balance_after=wallet.balance_cedis,
                        transaction_id=crypto_txn.reference
                    )

                # Update crypto transaction
                crypto_txn.status = 'completed'
                crypto_txn.escrow_locked = False
                crypto_txn.admin_note = admin_note
                crypto_txn.save()

                logger.info(f"Transaction {pk} approved successfully for user {crypto_txn.user.email}")
                return Response({
                    'message': 'Transaction approved and completed successfully',
                    'transaction': CryptoTransactionSerializer(crypto_txn).data,
                    'wallet': WalletSerializer(wallet).data
                })

        except Exception as e:
            logger.error(f"Transaction approval failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def decline(self, request, pk=None):
        """Admin: Decline crypto transaction"""
        crypto_txn = self.get_object()
        
        if crypto_txn.status != 'awaiting_admin':
            return Response(
                {'error': 'Transaction is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CryptoTransactionApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_note = serializer.validated_data.get('admin_note', '')

        try:
            with db_transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=crypto_txn.user)

                # No funds to release - user paid/sent externally
                # Just mark transaction as declined

                # Update crypto transaction
                crypto_txn.status = 'declined'
                crypto_txn.escrow_locked = False
                crypto_txn.admin_note = admin_note
                crypto_txn.save()

                logger.info(f"Transaction {pk} declined by admin {request.user.email}")
                return Response({
                    'message': 'Transaction declined successfully',
                    'transaction': CryptoTransactionSerializer(crypto_txn).data,
                    'wallet': WalletSerializer(wallet).data
                })

        except Exception as e:
            logger.error(f"Transaction decline failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminCryptoAddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing admin crypto receiving addresses"""
    serializer_class = AdminCryptoAddressSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['crypto_id', 'network', 'is_active']
    search_fields = ['crypto_id', 'network', 'address']
    ordering_fields = ['crypto_id', 'network', 'created_at']

    def get_queryset(self):
        # Only show active addresses to regular users, all addresses to admins
        if self.request.user.is_staff:
            return AdminCryptoAddress.objects.all()
        return AdminCryptoAddress.objects.filter(is_active=True)

    def get_permissions(self):
        # Allow read access to all authenticated users, write access only to admins
        if self.action in ['list', 'retrieve', 'get_address']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def get_address(self, request):
        """Get admin address for a specific crypto and network (read-only for all authenticated users)"""
        crypto_id = request.query_params.get('crypto_id')
        network = request.query_params.get('network')
        
        if not crypto_id or not network:
            return Response(
                {'error': 'crypto_id and network are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        address_obj = AdminCryptoAddress.objects.filter(
            crypto_id=crypto_id,
            network=network,
            is_active=True
        ).first()
        
        if not address_obj:
            return Response(
                {'error': 'No active address found for this crypto and network'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'address': address_obj.address,
            'crypto_id': address_obj.crypto_id,
            'network': address_obj.network
        })


class DepositViewSet(viewsets.ModelViewSet):
    """ViewSet for managing wallet deposits"""
    serializer_class = DepositSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deposit_type', 'status']
    search_fields = ['reference', 'momo_number', 'momo_transaction_id', 'transaction_id']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Deposit.objects.all()
        return Deposit.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            # Will be determined by deposit_type in create method
            return DepositSerializer
        return DepositSerializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def payment_details(self, request):
        """Get active admin payment details for deposits (read-only for all authenticated users)"""
        payment_type = request.query_params.get('payment_type', 'momo')  # momo or bank
        
        payment_details = AdminPaymentDetails.objects.filter(
            payment_type=payment_type,
            is_active=True
        ).order_by('momo_network' if payment_type == 'momo' else 'bank_name')
        
        from .serializers import AdminPaymentDetailsSerializer
        serializer = AdminPaymentDetailsSerializer(payment_details, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def momo_deposit(self, request):
        """Create a Mobile Money deposit request - user only provides payment proof"""
        serializer = MomoDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        admin_payment_detail_id = serializer.validated_data['admin_payment_detail_id']
        momo_network = serializer.validated_data['momo_network']
        momo_transaction_id = serializer.validated_data['momo_transaction_id']
        momo_proof = serializer.validated_data['momo_proof']

        # Get admin payment detail
        try:
            admin_payment_detail = AdminPaymentDetails.objects.get(
                id=admin_payment_detail_id,
                is_active=True,
                payment_type='momo',
                momo_network=momo_network
            )
        except AdminPaymentDetails.DoesNotExist:
            return Response(
                {'error': 'Invalid or inactive admin payment detail'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                deposit = Deposit.objects.create(
                    user=request.user,
                    deposit_type='momo',
                    amount=amount,
                    status='awaiting_admin',
                    reference=Deposit.generate_reference('MOMO'),
                    admin_payment_detail=admin_payment_detail,
                    momo_network=momo_network,
                    momo_transaction_id=momo_transaction_id,
                    momo_proof=momo_proof
                )

                logger.info(f"MoMo deposit created for user {request.user.email}: {amount} cedis to {admin_payment_detail.momo_number}")
                return Response({
                    'message': 'Deposit request submitted. Awaiting admin confirmation.',
                    'deposit': DepositSerializer(deposit, context={'request': request}).data
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"MoMo deposit failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def crypto_deposit(self, request):
        """Create a Crypto deposit request - user only provides payment proof"""
        serializer = CryptoDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        crypto_id = serializer.validated_data['crypto_id']
        crypto_amount = serializer.validated_data['crypto_amount']
        network = serializer.validated_data['network']
        transaction_id = serializer.validated_data['transaction_id']
        crypto_proof = serializer.validated_data['crypto_proof']
        admin_crypto_address_id = serializer.validated_data.get('admin_crypto_address_id')

        # Verify admin crypto address exists if provided
        admin_crypto_address = None
        if admin_crypto_address_id:
            try:
                admin_crypto_address = AdminCryptoAddress.objects.get(
                    id=admin_crypto_address_id,
                    is_active=True,
                    crypto_id=crypto_id,
                    network=network
                )
            except AdminCryptoAddress.DoesNotExist:
                return Response(
                    {'error': 'Invalid or inactive admin crypto address'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Amount will be calculated by admin during approval
        amount = Decimal('0.00')

        try:
            with db_transaction.atomic():
                deposit = Deposit.objects.create(
                    user=request.user,
                    deposit_type='crypto',
                    amount=amount,  # Will be updated by admin during approval
                    crypto_amount=crypto_amount,
                    crypto_id=crypto_id,
                    network=network,
                    transaction_id=transaction_id,
                    crypto_proof=crypto_proof,
                    status='awaiting_admin',
                    reference=Deposit.generate_reference('CRYPTO')
                )

                logger.info(f"Crypto deposit created for user {request.user.email}: {crypto_amount} {crypto_id} on {network}")
                return Response({
                    'message': 'Crypto deposit request submitted. Awaiting admin confirmation.',
                    'deposit': DepositSerializer(deposit, context={'request': request}).data
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Crypto deposit failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve deposit and credit user's wallet"""
        from django.utils import timezone
        from notifications.utils import create_notification
        
        deposit = self.get_object()
        
        if deposit.status != 'awaiting_admin':
            return Response(
                {'error': 'Deposit is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        admin_note = request.data.get('admin_note', '')
        
        try:
            with db_transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=deposit.user)
                balance_before = wallet.balance_cedis
                logger.info(f"Deposit approval - Wallet before: {balance_before}, Deposit amount: {deposit.amount}")

                if deposit.deposit_type == 'momo':
                    # Credit cedis to wallet (user sent MoMo, admin confirms, credit cedis)
                    amount = deposit.amount
                    wallet.add_cedis(amount)
                    wallet.refresh_from_db()  # Ensure we have the latest balance
                    balance_after = wallet.balance_cedis
                    logger.info(f"Deposit approval - Wallet after add_cedis: {balance_after}, Expected: {float(balance_before) + float(amount)}")
                    currency = 'cedis'
                else:  # crypto deposit
                    # User sent crypto, admin confirms receipt, convert to cedis and credit
                    # Admin provides the cedis amount (converted from crypto at current rate)
                    if 'amount' in request.data:
                        # Admin manually sets the cedis amount after converting crypto
                        amount = Decimal(str(request.data['amount']))
                    else:
                        # Auto-calculate from crypto amount using current rate
                        from rates.models import CryptoRate
                        crypto_rate = CryptoRate.get_latest_rate(deposit.crypto_id)
                        if crypto_rate:
                            amount = Decimal(str(deposit.crypto_amount)) * crypto_rate.cedis_price
                        else:
                            return Response(
                                {'error': f'Unable to get current rate for {deposit.crypto_id}. Please provide amount manually.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    
                    # Update deposit amount to the cedis value
                    deposit.amount = amount
                    # Credit cedis (not crypto) - platform doesn't hold crypto
                    wallet.add_cedis(amount)
                    balance_after = wallet.balance_cedis
                    currency = 'cedis'

                # Create wallet transaction record
                transaction_amount = amount  # Always in cedis now
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='deposit',
                    amount=transaction_amount,
                    currency='cedis',  # Always cedis - crypto deposits are converted
                    status='completed',
                    reference=deposit.reference,
                    description=f"Deposit via {deposit.deposit_type}. Ref: {deposit.reference}. " + 
                              (f"Crypto {deposit.crypto_amount} {deposit.crypto_id} converted to {amount} cedis" if deposit.deposit_type == 'crypto' else ""),
                    balance_before=balance_before,
                    balance_after=balance_after
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=deposit.user,
                    amount=amount,
                    log_type='deposit',
                    balance_after=balance_after,
                    transaction_id=deposit.reference
                )

                # Update deposit
                deposit.status = 'approved'
                deposit.reviewed_by = request.user
                deposit.reviewed_at = timezone.now()
                deposit.admin_note = admin_note
                deposit.save()

                # Create notification
                deposit_message = (
                    f'Your {deposit.deposit_type} deposit of ₵{amount} has been approved and credited to your wallet.'
                    if deposit.deposit_type == 'momo'
                    else f'Your crypto deposit of {deposit.crypto_amount} {deposit.crypto_id} has been converted to ₵{amount} and credited to your wallet.'
                )
                create_notification(
                    user=deposit.user,
                    notification_type='DEPOSIT_APPROVED',
                    title='Deposit Approved',
                    message=deposit_message,
                    related_object_type='deposit',
                    related_object_id=deposit.id,
                )

                # Final verification
                wallet.refresh_from_db()
                final_balance = wallet.balance_cedis
                logger.info(f"Deposit {pk} approved by admin {request.user.email}. Final wallet balance: {final_balance}")
                
                return Response({
                    'message': 'Deposit approved and wallet credited successfully',
                    'deposit': DepositSerializer(deposit, context={'request': request}).data,
                    'wallet': WalletSerializer(wallet).data
                })

        except Exception as e:
            logger.error(f"Deposit approval failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin: Reject deposit"""
        from django.utils import timezone
        from notifications.utils import create_notification
        
        deposit = self.get_object()
        
        if deposit.status != 'awaiting_admin':
            return Response(
                {'error': 'Deposit is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        admin_note = request.data.get('admin_note', '')
        if not admin_note:
            return Response(
                {'error': 'Admin note is required when rejecting a deposit'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                # Update deposit
                deposit.status = 'rejected'
                deposit.reviewed_by = request.user
                deposit.reviewed_at = timezone.now()
                deposit.admin_note = admin_note
                deposit.save()

                # Create notification
                create_notification(
                    user=deposit.user,
                    notification_type='DEPOSIT_REJECTED',
                    title='Deposit Rejected',
                    message=f'Your {deposit.deposit_type} deposit has been rejected. Reason: {admin_note}',
                    related_object_type='deposit',
                    related_object_id=deposit.id,
                )

                logger.info(f"Deposit {pk} rejected by admin {request.user.email}")
                return Response({
                    'message': 'Deposit rejected successfully',
                    'deposit': DepositSerializer(deposit, context={'request': request}).data
                })

        except Exception as e:
            logger.error(f"Deposit rejection failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WithdrawalViewSet(viewsets.ModelViewSet):
    """ViewSet for managing wallet withdrawals"""
    serializer_class = WithdrawalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['withdrawal_type', 'status']
    search_fields = ['reference', 'momo_number', 'crypto_address']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Withdrawal.objects.all()
        return Withdrawal.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def calculate_fee(self, request):
        """Calculate withdrawal fee before submission"""
        from analytics.models import Settings
        from rates.models import CryptoRate
        
        withdrawal_type = request.data.get('withdrawal_type')
        amount = request.data.get('amount')  # For MoMo: cedis amount, For crypto: crypto amount
        
        if not withdrawal_type or not amount:
            return Response(
                {'error': 'withdrawal_type and amount are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
            settings = Settings.get_settings()
            
            if withdrawal_type == 'momo':
                fee = settings.calculate_momo_withdrawal_fee(amount)
                total_amount = amount + fee
                # Get USD equivalent of fee for display
                from rates.models import CryptoRate
                usd_to_cedis = settings.get_usd_to_cedis_rate()
                fee_usd = fee / usd_to_cedis
                
                return Response({
                    'withdrawal_type': 'momo',
                    'amount': float(amount),
                    'fee': float(fee),
                    'fee_usd': float(fee_usd),
                    'total_amount': float(total_amount),
                    'fee_percentage': float(settings.momo_withdrawal_fee_percent),
                    'fee_fixed_usd': float(settings.momo_withdrawal_fee_fixed_usd),
                    'fee_min_usd': float(settings.momo_withdrawal_min_fee_usd),
                    'fee_max_usd': float(settings.momo_withdrawal_max_fee_usd),
                })
            
            elif withdrawal_type == 'crypto':
                crypto_id = request.data.get('crypto_id')
                if not crypto_id:
                    return Response(
                        {'error': 'crypto_id is required for crypto withdrawals'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Get rate and calculate cedis equivalent
                crypto_rate = CryptoRate.get_latest_rate(crypto_id)
                if not crypto_rate:
                    return Response(
                        {'error': f'No rate set for {crypto_id.upper()}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cedis_amount = amount * crypto_rate.cedis_price
                fee = settings.calculate_crypto_withdrawal_fee(cedis_amount)
                total_amount = cedis_amount + fee
                
                # Get USD equivalent of fee for display
                usd_to_cedis = settings.get_usd_to_cedis_rate()
                fee_usd = fee / usd_to_cedis
                
                return Response({
                    'withdrawal_type': 'crypto',
                    'crypto_id': crypto_id,
                    'crypto_amount': float(amount),
                    'cedis_amount': float(cedis_amount),
                    'fee': float(fee),
                    'fee_usd': float(fee_usd),
                    'total_amount': float(total_amount),
                    'rate': float(crypto_rate.cedis_price),
                    'fee_percentage': float(settings.crypto_withdrawal_fee_percent),
                    'fee_fixed_usd': float(settings.crypto_withdrawal_fee_fixed_usd),
                    'fee_min_usd': float(settings.crypto_withdrawal_min_fee_usd),
                    'fee_max_usd': float(settings.crypto_withdrawal_max_fee_usd),
                })
            
            else:
                return Response(
                    {'error': 'Invalid withdrawal_type. Must be "momo" or "crypto"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Exception as e:
            logger.error(f"Fee calculation failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def momo_withdrawal(self, request):
        """Create a Mobile Money withdrawal request"""
        serializer = MomoWithdrawalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wallet, created = Wallet.objects.get_or_create(user=request.user)
        amount = serializer.validated_data['amount']
        momo_number = serializer.validated_data['momo_number']
        momo_name = serializer.validated_data['momo_name']
        momo_network = serializer.validated_data['momo_network']

        # Calculate withdrawal fee
        from analytics.models import Settings
        settings = Settings.get_settings()
        fee = settings.calculate_momo_withdrawal_fee(amount)
        total_amount = amount + fee  # Total amount to deduct (amount + fee)

        # Check sufficient balance (user needs amount + fee)
        if not wallet.has_sufficient_cedis(total_amount):
            return Response(
                {'error': f'Insufficient balance. You need ₵{total_amount:.2f} (₵{amount:.2f} + ₵{fee:.2f} fee)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                # Lock total amount (amount + fee) to escrow
                balance_before = wallet.balance_cedis
                wallet.lock_cedis_to_escrow(total_amount)
                wallet.refresh_from_db()

                withdrawal = Withdrawal.objects.create(
                    user=request.user,
                    withdrawal_type='momo',
                    amount=amount,  # Amount user requested (before fee)
                    fee=fee,  # Withdrawal fee
                    total_amount=total_amount,  # Total amount deducted (amount + fee)
                    status='awaiting_admin',
                    reference=Withdrawal.generate_reference('MOMO-WTH'),
                    momo_number=momo_number,
                    momo_name=momo_name,
                    momo_network=momo_network
                )

                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='escrow_lock',
                    amount=total_amount,  # Lock total amount (amount + fee)
                    currency='cedis',
                    status='completed',
                    reference=withdrawal.reference,
                    description=f"Withdrawal request locked to escrow: ₵{amount:.2f} + ₵{fee:.2f} fee = ₵{total_amount:.2f}. Ref: {withdrawal.reference}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=request.user,
                    amount=total_amount,
                    log_type='escrow_lock',
                    balance_after=wallet.balance_cedis,
                    transaction_id=withdrawal.reference
                )

                logger.info(f"MoMo withdrawal created for user {request.user.email}: ₵{amount:.2f} + ₵{fee:.2f} fee = ₵{total_amount:.2f}")
                return Response({
                    'message': f'Withdrawal request submitted. ₵{total_amount:.2f} locked in escrow (₵{amount:.2f} + ₵{fee:.2f} fee). Awaiting admin confirmation.',
                    'withdrawal': WithdrawalSerializer(withdrawal, context={'request': request}).data,
                    'fee': float(fee),
                    'total_amount': float(total_amount)
                }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"MoMo withdrawal failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def crypto_withdrawal(self, request):
        """Create a Crypto withdrawal request - converts cedis to crypto at current rate"""
        serializer = CryptoWithdrawalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        wallet, created = Wallet.objects.get_or_create(user=request.user)
        crypto_id = serializer.validated_data['crypto_id']
        crypto_amount = serializer.validated_data['crypto_amount']
        network = serializer.validated_data['network']
        crypto_address = serializer.validated_data['crypto_address']

        # Get admin-set rate for conversion
        from rates.models import CryptoRate
        crypto_rate = CryptoRate.get_latest_rate(crypto_id)
        if not crypto_rate:
            return Response(
                {'error': f'No rate set for {crypto_id.upper()}. Please contact admin or try a different cryptocurrency.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate cedis equivalent
        cedis_amount = Decimal(str(crypto_amount)) * crypto_rate.cedis_price

        # Calculate withdrawal fee
        from analytics.models import Settings
        settings = Settings.get_settings()
        fee = settings.calculate_crypto_withdrawal_fee(cedis_amount)
        total_amount = cedis_amount + fee  # Total amount to deduct (cedis_amount + fee)

        # Check sufficient cedis balance (platform is fiat-only, user needs cedis_amount + fee)
        if not wallet.has_sufficient_cedis(total_amount):
            return Response(
                {'error': f'Insufficient balance. You need ₵{total_amount:.2f} (₵{cedis_amount:.2f} + ₵{fee:.2f} fee) to withdraw {crypto_amount} {crypto_id.upper()}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                # Lock total amount (cedis_amount + fee) to escrow
                balance_before = wallet.balance_cedis
                escrow_before = wallet.escrow_balance
                wallet.lock_cedis_to_escrow(total_amount)
                wallet.refresh_from_db()

                withdrawal = Withdrawal.objects.create(
                    user=request.user,
                    withdrawal_type='crypto',
                    amount=cedis_amount,  # Cedis amount for crypto (before fee)
                    fee=fee,  # Withdrawal fee
                    total_amount=total_amount,  # Total amount deducted (cedis_amount + fee)
                    crypto_amount=crypto_amount,
                    crypto_id=crypto_id,
                    network=network,
                    crypto_address=crypto_address,
                    status='awaiting_admin',
                    reference=Withdrawal.generate_reference('CRYPTO-WTH')
                )

                # Create escrow lock transaction
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='escrow_lock',
                    amount=total_amount,  # Lock total amount (cedis_amount + fee)
                    currency='cedis',
                    status='completed',
                    reference=withdrawal.reference,
                    description=f"Crypto withdrawal request: {crypto_amount} {crypto_id.upper()} (₵{cedis_amount:.2f} + ₵{fee:.2f} fee = ₵{total_amount:.2f} locked). Ref: {withdrawal.reference}",
                    balance_before=balance_before,
                    balance_after=wallet.balance_cedis
                )
                
                # Log wallet activity
                log_wallet_activity(
                    user=request.user,
                    amount=total_amount,
                    log_type='escrow_lock',
                    balance_after=wallet.balance_cedis,
                    transaction_id=withdrawal.reference
                )

                logger.info(f"Crypto withdrawal created for user {request.user.email}: {crypto_amount} {crypto_id} (₵{cedis_amount:.2f} + ₵{fee:.2f} fee = ₵{total_amount:.2f} locked)")
                return Response({
                    'message': f'Crypto withdrawal request submitted. ₵{total_amount:.2f} locked in escrow (₵{cedis_amount:.2f} + ₵{fee:.2f} fee). Awaiting admin confirmation.',
                    'withdrawal': WithdrawalSerializer(withdrawal, context={'request': request}).data,
                    'cedis_amount': float(cedis_amount),
                    'fee': float(fee),
                    'total_amount': float(total_amount),
                    'rate': float(crypto_rate.cedis_price)
                }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Crypto withdrawal failed for user {request.user.email}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: Approve withdrawal and process transfer"""
        from django.utils import timezone
        from notifications.utils import create_notification
        
        withdrawal = self.get_object()
        
        if withdrawal.status != 'awaiting_admin':
            return Response(
                {'error': 'Withdrawal is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        admin_note = request.data.get('admin_note', '')
        transaction_id = request.data.get('transaction_id', '')

        try:
            with db_transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=withdrawal.user)

                if withdrawal.withdrawal_type == 'momo':
                    # Deduct total amount from escrow (amount + fee were already locked)
                    balance_before = wallet.escrow_balance
                    wallet.deduct_from_escrow(withdrawal.total_amount)  # Deduct total (amount + fee)
                    wallet.refresh_from_db()
                    balance_after = wallet.escrow_balance

                    # Create wallet transaction record for withdrawal
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='withdraw',
                        amount=withdrawal.total_amount,  # Total amount deducted (amount + fee)
                        currency='cedis',
                        status='completed',
                        reference=withdrawal.reference,
                        description=f"Withdrawal via MoMo to {withdrawal.momo_number}: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}",
                        balance_before=wallet.balance_cedis + balance_before,
                        balance_after=wallet.balance_cedis + balance_after
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=withdrawal.user,
                        amount=withdrawal.total_amount,
                        log_type='withdrawal',
                        balance_after=wallet.balance_cedis,
                        transaction_id=withdrawal.reference
                    )

                else:  # crypto
                    # Deduct total amount from escrow (cedis_amount + fee were locked when withdrawal was created)
                    # Platform is fiat-only: we convert cedis to crypto at current rate
                    escrow_before = wallet.escrow_balance
                    wallet.deduct_from_escrow(withdrawal.total_amount)  # Deduct total (cedis_amount + fee)
                    wallet.refresh_from_db()
                    escrow_after = wallet.escrow_balance

                    # Create wallet transaction record for withdrawal
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='withdraw',
                        amount=withdrawal.total_amount,  # Total amount deducted (cedis_amount + fee)
                        currency='cedis',
                        status='completed',
                        reference=withdrawal.reference,
                        description=f"Crypto withdrawal approved: {withdrawal.crypto_amount} {withdrawal.crypto_id.upper()} sent (₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f} deducted). Ref: {withdrawal.reference}. Admin: {request.user.email}",
                        balance_before=wallet.balance_cedis + escrow_before,
                        balance_after=wallet.balance_cedis + escrow_after
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=withdrawal.user,
                        amount=withdrawal.total_amount,
                        log_type='withdrawal',
                        balance_after=wallet.balance_cedis,
                        transaction_id=withdrawal.reference
                    )

                # Update withdrawal
                withdrawal.status = 'approved'
                withdrawal.reviewed_by = request.user
                withdrawal.reviewed_at = timezone.now()
                withdrawal.admin_note = admin_note
                if transaction_id:
                    withdrawal.transaction_id = transaction_id
                withdrawal.save()

                # Create notification
                create_notification(
                    user=withdrawal.user,
                    notification_type='WITHDRAWAL_APPROVED',
                    title='Withdrawal Approved',
                    message=f'Your {withdrawal.withdrawal_type} withdrawal of {withdrawal.amount if withdrawal.withdrawal_type == "momo" else withdrawal.crypto_amount} has been approved and will be processed shortly.',
                    related_object_type='withdrawal',
                    related_object_id=withdrawal.id,
                )
                
                # Send email alert for withdrawal
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    send_mail(
                        subject=f'Withdrawal Approved - {withdrawal.reference}',
                        message=f'''
Hello {withdrawal.user.get_full_name() or withdrawal.user.email},

Your withdrawal request has been approved!

Withdrawal Details:
- Reference: {withdrawal.reference}
- Type: {withdrawal.get_withdrawal_type_display()}
- Amount: {"₵" + str(withdrawal.amount) if withdrawal.withdrawal_type == "momo" else str(withdrawal.crypto_amount) + " " + withdrawal.crypto_id.upper()}
- Status: Approved

Your withdrawal will be processed shortly. You will receive another notification once it's completed.

If you did not request this withdrawal, please contact support immediately.

Best regards,
CryptoGhana Team
                        ''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[withdrawal.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.warning(f"Failed to send withdrawal email to {withdrawal.user.email}: {str(e)}")

                logger.info(f"Withdrawal {pk} approved by admin {request.user.email}")
                return Response({
                    'message': 'Withdrawal approved successfully',
                    'withdrawal': WithdrawalSerializer(withdrawal, context={'request': request}).data,
                    'wallet': WalletSerializer(wallet).data
                })

        except Exception as e:
            logger.error(f"Withdrawal approval failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin: Reject withdrawal and release escrow"""
        from django.utils import timezone
        from notifications.utils import create_notification
        
        withdrawal = self.get_object()
        
        if withdrawal.status != 'awaiting_admin':
            return Response(
                {'error': 'Withdrawal is not awaiting admin confirmation'},
                status=status.HTTP_400_BAD_REQUEST
            )

        admin_note = request.data.get('admin_note', '')
        if not admin_note:
            return Response(
                {'error': 'Admin note is required when rejecting a withdrawal'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=withdrawal.user)

                if withdrawal.withdrawal_type == 'momo':
                    # Release total amount from escrow back to balance (amount + fee)
                    balance_before = wallet.balance_cedis
                    wallet.release_cedis_from_escrow(withdrawal.total_amount)
                    wallet.refresh_from_db()

                    # Create wallet transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='escrow_release',
                        amount=withdrawal.total_amount,  # Release total (amount + fee)
                        currency='cedis',
                        status='completed',
                        reference=withdrawal.reference,
                        description=f"Withdrawal rejected, funds released from escrow: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}",
                        balance_before=balance_before,
                        balance_after=wallet.balance_cedis
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=withdrawal.user,
                        amount=withdrawal.total_amount,
                        log_type='escrow_refund',
                        balance_after=wallet.balance_cedis,
                        transaction_id=withdrawal.reference
                    )
                else:  # crypto
                    # Release total amount from escrow back to balance (cedis_amount + fee)
                    balance_before = wallet.balance_cedis
                    escrow_before = wallet.escrow_balance
                    wallet.release_cedis_from_escrow(withdrawal.total_amount)  # Release total (cedis_amount + fee)
                    wallet.refresh_from_db()
                    balance_after = wallet.balance_cedis
                    escrow_after = wallet.escrow_balance

                    # Create escrow release transaction
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='escrow_release',
                        amount=withdrawal.total_amount,  # Release total (cedis_amount + fee)
                        currency='cedis',
                        status='completed',
                        reference=withdrawal.reference,
                        description=f"Crypto withdrawal rejected, funds released from escrow: ₵{withdrawal.amount:.2f} + ₵{withdrawal.fee:.2f} fee = ₵{withdrawal.total_amount:.2f}. Ref: {withdrawal.reference}. Reason: {admin_note}",
                        balance_before=balance_before,
                        balance_after=balance_after
                    )
                    
                    # Log wallet activity
                    log_wallet_activity(
                        user=withdrawal.user,
                        amount=withdrawal.total_amount,
                        log_type='escrow_refund',
                        balance_after=balance_after,
                        transaction_id=withdrawal.reference
                    )

                # Update withdrawal
                withdrawal.status = 'rejected'
                withdrawal.reviewed_by = request.user
                withdrawal.reviewed_at = timezone.now()
                withdrawal.admin_note = admin_note
                withdrawal.save()

                # Create notification
                create_notification(
                    user=withdrawal.user,
                    notification_type='WITHDRAWAL_REJECTED',
                    title='Withdrawal Rejected',
                    message=f'Your {withdrawal.withdrawal_type} withdrawal has been rejected. Reason: {admin_note}. Funds have been returned to your wallet.',
                    related_object_type='withdrawal',
                    related_object_id=withdrawal.id,
                )

                logger.info(f"Withdrawal {pk} rejected by admin {request.user.email}")
                return Response({
                    'message': 'Withdrawal rejected and funds returned successfully',
                    'withdrawal': WithdrawalSerializer(withdrawal, context={'request': request}).data,
                    'wallet': WalletSerializer(wallet).data
                })

        except Exception as e:
            logger.error(f"Withdrawal rejection failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def complete(self, request, pk=None):
        """Admin: Mark withdrawal as completed (after transfer is confirmed)"""
        from django.utils import timezone
        from notifications.utils import create_notification
        
        withdrawal = self.get_object()
        
        if withdrawal.status != 'approved':
            return Response(
                {'error': 'Withdrawal must be approved before it can be completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        transaction_id = request.data.get('transaction_id', '')
        if not transaction_id:
            return Response(
                {'error': 'Transaction ID is required when completing a withdrawal'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with db_transaction.atomic():
                # Update withdrawal
                withdrawal.status = 'completed'
                withdrawal.transaction_id = transaction_id
                withdrawal.completed_at = timezone.now()
                withdrawal.save()

                # Create notification
                create_notification(
                    user=withdrawal.user,
                    notification_type='WITHDRAWAL_COMPLETED',
                    title='Withdrawal Completed',
                    message=f'Your {withdrawal.withdrawal_type} withdrawal has been completed. Transaction ID: {transaction_id}',
                    related_object_type='withdrawal',
                    related_object_id=withdrawal.id,
                )

                logger.info(f"Withdrawal {pk} completed by admin {request.user.email}")
                return Response({
                    'message': 'Withdrawal marked as completed successfully',
                    'withdrawal': WithdrawalSerializer(withdrawal, context={'request': request}).data
                })

        except Exception as e:
            logger.error(f"Withdrawal completion failed for {pk}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

