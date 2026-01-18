from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db.models import Avg, Count, Q

from marketing.models import (
    FeatureBlock,
    PolicyPage,
    SecurityHighlight,
    SupportedAsset,
    Testimonial,
    UserReview,
)
from marketing.serializers import (
    FeatureBlockSerializer,
    PolicyPageSerializer,
    SecurityHighlightSerializer,
    SupportedAssetSerializer,
    TestimonialSerializer,
    UserReviewSerializer,
    UserReviewCreateSerializer,
)
from authentication.permissions import IsAdminUser


class LandingContentView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        features = FeatureBlockSerializer(
            FeatureBlock.objects.filter(is_active=True), many=True
        ).data
        security = SecurityHighlightSerializer(
            SecurityHighlight.objects.filter(is_active=True), many=True
        ).data
        assets = SupportedAssetSerializer(
            SupportedAsset.objects.filter(is_featured=True)[:24], many=True
        ).data
        testimonials = TestimonialSerializer(
            Testimonial.objects.filter(is_featured=True), many=True
        ).data

        return Response(
            {
                "features": features,
                "security": security,
                "assets": assets,
                "testimonials": testimonials,
            }
        )


class PolicyDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get_object(self, slug: str) -> PolicyPage:
        return PolicyPage.objects.get(slug=slug)

    def get(self, request, slug: str):
        policy = self.get_object(slug)
        data = PolicyPageSerializer(policy).data
        return Response(data)


class UserReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Reviews/Testimonials
    - List: Get all approved reviews (public)
    - Create: Submit a new review (authenticated or anonymous)
    - Retrieve: Get single review
    - Admin actions: Approve, reject, feature reviews
    """
    queryset = UserReview.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'rating', 'is_featured']
    search_fields = ['author_name', 'email', 'title', 'comment']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserReviewCreateSerializer
        return UserReviewSerializer

    def get_permissions(self):
        """Allow public access for list/retrieve, authenticated for create, admin for modify"""
        if self.action in ['list', 'retrieve', 'statistics', 'featured']:
            return [AllowAny()]
        elif self.action == 'create':
            return [IsAuthenticated()]  # Only authenticated users can post reviews
        elif self.action in ['approve', 'reject', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Show approved reviews to public, all to admins"""
        queryset = UserReview.objects.all()
        
        if self.action in ['list', 'retrieve', 'featured']:
            # Public: only show approved reviews
            if not (self.request.user.is_authenticated and (self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin')):
                queryset = queryset.filter(status='approved')
        
        # Filter featured if requested
        if self.request.query_params.get('featured') == 'true':
            queryset = queryset.filter(is_featured=True)
            
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new review"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set user if authenticated
        review = serializer.save()
        if request.user.is_authenticated:
            review.user = request.user
            review.save()
        
        return Response(
            UserReviewSerializer(review).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve a review"""
        review = self.get_object()
        review.status = 'approved'
        review.save()
        return Response({
            'message': 'Review approved successfully',
            'review': UserReviewSerializer(review).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject a review"""
        review = self.get_object()
        review.status = 'rejected'
        review.save()
        return Response({
            'message': 'Review rejected successfully',
            'review': UserReviewSerializer(review).data
        })

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured reviews"""
        featured_reviews = self.get_queryset().filter(is_featured=True, status='approved')[:10]
        serializer = self.get_serializer(featured_reviews, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get review statistics (average rating, total reviews, distribution)"""
        approved_reviews = UserReview.objects.filter(status='approved')
        
        total_reviews = approved_reviews.count()
        average_rating = approved_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        rating_distribution = approved_reviews.values('rating').annotate(
            count=Count('rating')
        ).order_by('rating')
        
        # Calculate average ratings for breakdown if available
        avg_service = approved_reviews.exclude(service_rating__isnull=True).aggregate(
            Avg('service_rating')
        )['service_rating__avg'] or 0
        avg_speed = approved_reviews.exclude(speed_rating__isnull=True).aggregate(
            Avg('speed_rating')
        )['speed_rating__avg'] or 0
        avg_support = approved_reviews.exclude(support_rating__isnull=True).aggregate(
            Avg('support_rating')
        )['support_rating__avg'] or 0
        
        return Response({
            'total_reviews': total_reviews,
            'average_rating': round(float(average_rating), 2),
            'rating_distribution': list(rating_distribution),
            'average_breakdown': {
                'service': round(float(avg_service), 2) if avg_service else None,
                'speed': round(float(avg_speed), 2) if avg_speed else None,
                'support': round(float(avg_support), 2) if avg_support else None,
            }
        })

