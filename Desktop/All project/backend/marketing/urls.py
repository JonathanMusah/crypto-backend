from django.urls import path, include
from rest_framework.routers import DefaultRouter
from marketing.views import LandingContentView, PolicyDetailView, UserReviewViewSet

router = DefaultRouter()
router.register(r'reviews', UserReviewViewSet, basename='review')

urlpatterns = [
    path("landing/", LandingContentView.as_view(), name="marketing-landing-content"),
    path("policies/<slug:slug>/", PolicyDetailView.as_view(), name="marketing-policy"),
    path("", include(router.urls)),
]

