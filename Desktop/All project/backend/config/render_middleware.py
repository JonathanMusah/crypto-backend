"""
Middleware to handle ALLOWED_HOSTS for Render deployment
"""
from django.http import HttpResponse


class AllowRenderHostMiddleware:
    """Allow all hosts on Render without ALLOWED_HOSTS validation"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Allow the request to pass through without ALLOWED_HOSTS check
        return self.get_response(request)
