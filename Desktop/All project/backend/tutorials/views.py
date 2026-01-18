from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from .models import Tutorial, TutorialProgress
from .serializers import TutorialSerializer, TutorialProgressSerializer


class TutorialViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tutorial CRUD operations.
    - List: Public (only published tutorials for non-admin)
    - Detail: Public
    - Create/Update/Delete: Admin only
    """
    serializer_class = TutorialSerializer
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_published']
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['created_at', 'order', 'views']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Return published tutorials for non-admin, all for admin"""
        if self.request.user.is_staff:
            return Tutorial.objects.all().select_related('author')
        return Tutorial.objects.filter(is_published=True).select_related('author')

    def get_permissions(self):
        """Admin only for create, update, delete"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_context(self):
        """Add request to context for image URL generation and progress tracking"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['get'], lookup_field='slug')
    def detail(self, request, slug=None):
        """
        Get tutorial detail.
        Endpoint: /api/tutorials/tutorials/{slug}/
        For frontend: /tutorials/detail/{slug}
        """
        tutorial = self.get_object()
        # Increment views
        tutorial.views += 1
        tutorial.save(update_fields=['views'])
        serializer = self.get_serializer(tutorial)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def mark_complete(self, request, slug=None):
        """Mark tutorial as complete for the current user"""
        tutorial = self.get_object()
        progress, created = TutorialProgress.objects.get_or_create(
            user=request.user,
            tutorial=tutorial
        )
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()
        return Response({
            'message': 'Tutorial marked as complete',
            'progress': TutorialProgressSerializer(progress).data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def mark_incomplete(self, request, slug=None):
        """Mark tutorial as incomplete for the current user"""
        tutorial = self.get_object()
        try:
            progress = TutorialProgress.objects.get(user=request.user, tutorial=tutorial)
            progress.is_completed = False
            progress.completed_at = None
            progress.save()
            return Response({
                'message': 'Tutorial marked as incomplete',
                'progress': TutorialProgressSerializer(progress).data
            })
        except TutorialProgress.DoesNotExist:
            return Response(
                {'error': 'Progress record not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TutorialProgressViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tutorial Progress tracking.
    - List: User's own progress
    - Create/Update: User's own progress
    """
    serializer_class = TutorialProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users can only see their own progress"""
        return TutorialProgress.objects.filter(user=self.request.user).select_related('tutorial', 'user')

    def perform_create(self, serializer):
        """Create progress record for current user"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def progress(self, request):
        """
        Get user's tutorial progress.
        Endpoint: /api/tutorials/progress/progress/
        For frontend: /tutorials/progress
        """
        progress_records = self.get_queryset()
        serializer = self.get_serializer(progress_records, many=True)
        
        # Calculate statistics
        total_tutorials = Tutorial.objects.filter(is_published=True).count()
        completed_count = progress_records.filter(is_completed=True).count()
        
        return Response({
            'progress': serializer.data,
            'statistics': {
                'total_tutorials': total_tutorials,
                'completed_count': completed_count,
                'in_progress_count': progress_records.filter(is_completed=False).count(),
                'completion_percentage': round((completed_count / total_tutorials * 100) if total_tutorials > 0 else 0, 2)
            }
        })

