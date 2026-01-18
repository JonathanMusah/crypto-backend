from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KYCVerificationViewSet

router = DefaultRouter()
router.register(r'verifications', KYCVerificationViewSet, basename='kyc')

urlpatterns = [
    path('', include(router.urls)),
]

