from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TutorialViewSet, TutorialProgressViewSet

router = DefaultRouter()
router.register(r'tutorials', TutorialViewSet, basename='tutorial')
router.register(r'progress', TutorialProgressViewSet, basename='tutorial-progress')

urlpatterns = [
    # Frontend API structure endpoints
    path('tutorials/list/', TutorialViewSet.as_view({'get': 'list'}), name='tutorials-list'),
    path('tutorials/detail/<slug:slug>/', TutorialViewSet.as_view({'get': 'retrieve'}), name='tutorials-detail'),
    path('tutorials/progress/', TutorialProgressViewSet.as_view({'get': 'progress'}), name='tutorials-progress'),
    # Include router URLs for full CRUD
    path('', include(router.urls)),
]

