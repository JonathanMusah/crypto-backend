from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SettingsViewSet, AnalyticsEventViewSet, UserMetricViewSet

router = DefaultRouter()
router.register(r'settings', SettingsViewSet, basename='settings')
router.register(r'events', AnalyticsEventViewSet, basename='analytics-event')
router.register(r'metrics', UserMetricViewSet, basename='user-metric')

urlpatterns = [
    path('', include(router.urls)),
]

