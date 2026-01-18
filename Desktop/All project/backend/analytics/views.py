from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import Settings, AnalyticsEvent, UserMetric
from .serializers import SettingsSerializer, AnalyticsEventSerializer, UserMetricSerializer
from orders.models import Order, Trade
from orders.serializers import TradeSerializer


class SettingsViewSet(viewsets.ModelViewSet):
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer

    def get_permissions(self):
        # Allow public access to list, retrieve, feature_flags, paypal_rates, cashapp_rates, and zelle_rates
        if self.action in ['list', 'retrieve', 'feature_flags', 'paypal_rates', 'cashapp_rates', 'zelle_rates']:
            return [AllowAny()]
        return [IsAdminUser()]
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        settings = Settings.get_settings()
        # Clean up duplicates if any exist
        duplicates = Settings.objects.exclude(pk=settings.pk)
        if duplicates.exists():
            duplicates.delete()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def feature_flags(self, request):
        """Get feature flags (public endpoint)"""
        settings = Settings.get_settings()
        # Clean up duplicates if any exist
        duplicates = Settings.objects.exclude(pk=settings.pk)
        if duplicates.exists():
            duplicates.delete()
        return Response({
            'gift_cards_enabled': bool(settings.gift_cards_enabled),
            'special_requests_enabled': bool(settings.special_requests_enabled),
            'paypal_enabled': bool(settings.paypal_enabled),
            'cashapp_enabled': bool(settings.cashapp_enabled),
            'zelle_enabled': bool(settings.zelle_enabled),
        })
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def paypal_rates(self, request):
        """Get PayPal exchange rates (public endpoint)"""
        settings = Settings.get_settings()
        return Response({
            'sell_rate': float(settings.paypal_sell_rate),  # Rate when user sells PayPal (what we pay)
            'buy_rate': float(settings.paypal_buy_rate),    # Rate when user buys PayPal (what they pay)
            'admin_paypal_email': settings.admin_paypal_email or '',
            'admin_momo_details': settings.admin_momo_details or {},
        })
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def cashapp_rates(self, request):
        """Get CashApp exchange rates (public endpoint)"""
        settings = Settings.get_settings()
        return Response({
            'sell_rate': float(settings.cashapp_sell_rate),  # Rate when user sells CashApp (what we pay)
            'buy_rate': float(settings.cashapp_buy_rate),    # Rate when user buys CashApp (what they pay)
            'admin_cashapp_tag': settings.admin_cashapp_tag or '',
            'admin_momo_details': settings.admin_momo_details or {},
        })
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def zelle_rates(self, request):
        """Get Zelle exchange rates (public endpoint)"""
        settings = Settings.get_settings()
        return Response({
            'sell_rate': float(settings.zelle_sell_rate),  # Rate when user sells Zelle (what we pay)
            'buy_rate': float(settings.zelle_buy_rate),    # Rate when user buys Zelle (what they pay)
            'admin_zelle_email': settings.admin_zelle_email or '',
            'admin_momo_details': settings.admin_momo_details or {},
        })


class AnalyticsEventViewSet(viewsets.ModelViewSet):
    serializer_class = AnalyticsEventSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type']
    ordering_fields = ['created_at']

    def get_queryset(self):
        if self.request.user.is_staff:
            return AnalyticsEvent.objects.all()
        return AnalyticsEvent.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(user=request.user if request.user.is_authenticated else None)
        return Response(AnalyticsEventSerializer(event).data, status=status.HTTP_201_CREATED)


class UserMetricViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserMetricSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserMetric.objects.all()
        return UserMetric.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        user = request.user
        metrics, _ = UserMetric.objects.get_or_create(user=user)
        
        # Calculate additional stats
        orders = Order.objects.filter(user=user)
        trades = Trade.objects.filter(Q(buyer=user) | Q(seller=user))
        
        stats = {
            'total_orders': orders.count(),
            'pending_orders': orders.filter(status='PENDING').count(),
            'completed_orders': orders.filter(status='COMPLETED').count(),
            'total_trades': trades.count(),
            'total_volume': trades.aggregate(Sum('total'))['total__sum'] or 0,
            'recent_trades': TradeSerializer(trades[:5], many=True).data if trades.exists() else [],
        }
        
        return Response({
            'metrics': UserMetricSerializer(metrics).data,
            'stats': stats,
        })

