"""
Security middleware for IP banning and device tracking
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from .models import BannedIP
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


class JWTAuthenticationFromCookie(JWTAuthentication):
    """
    JWT Authentication that reads token from cookies instead of Authorization header
    """
    def authenticate(self, request):
        # Try to get token from cookie
        access_token = request.COOKIES.get('access_token')
        
        if not access_token:
            # Fall back to Authorization header if no cookie
            return super().authenticate(request)
        
        # Validate token
        try:
            validated_token = self.get_validated_token(access_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except (InvalidToken, AuthenticationFailed):
            return None


class IPBanMiddleware(MiddlewareMixin):
    """
    Middleware to check if client IP is banned before processing request
    """
    def process_request(self, request):
        try:
            # Skip IP check for admin panel (admins can access even if their IP is banned)
            if request.path.startswith('/admin/'):
                return None
            
            client_ip = get_client_ip(request)
            
            # Check if IP is banned
            try:
                if BannedIP.is_ip_banned(client_ip):
                    logger.warning(f"Blocked request from banned IP: {client_ip} to {request.path}")
                    return JsonResponse(
                        {
                            'error': 'Access denied. Your IP address has been banned.',
                            'detail': 'Please contact support if you believe this is an error.'
                        },
                        status=403
                    )
            except Exception as e:
                # Don't block requests if IP check fails
                logger.error(f"Error checking IP ban: {str(e)}", exc_info=True)
            
            return None
        except Exception as e:
            # Don't block requests if middleware fails
            logger.error(f"Error in IPBanMiddleware: {str(e)}", exc_info=True)
            return None


class UpdateLastSeenMiddleware(MiddlewareMixin):
    """
    Middleware to update user's last_seen timestamp on API requests
    Only updates once per minute to reduce database writes
    """
    def process_request(self, request):
        """Update user's last_seen if authenticated"""
        try:
            # Only process API requests (not admin or static files)
            if not request.path.startswith('/api/'):
                return None
            
            # Skip for non-authenticated users
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return None
            
            # Update last_seen using cache to throttle updates (max once per minute)
            from django.core.cache import cache
            from django.utils import timezone
            from datetime import timedelta
            
            cache_key = f'last_seen_update_{request.user.id}'
            last_update = cache.get(cache_key)
            
            # Update more frequently (every 10 seconds) for better real-time status
            update_interval = timedelta(seconds=10)
            
            # Always update if no cached update or if enough time has passed
            now = timezone.now()
            if not last_update or (now - last_update) > update_interval:
                try:
                    # Refresh user from database to get latest last_seen value
                    request.user.refresh_from_db(fields=['last_seen'])
                    
                    # If last_seen is None, user has explicitly logged out - don't update
                    # This ensures logged-out users stay offline
                    if request.user.last_seen is None:
                        return None
                    
                    # Update last_seen for authenticated users making API calls
                    request.user.last_seen = now
                    request.user.save(update_fields=['last_seen'])
                    
                    # Cache the update time for 15 seconds (longer than update interval for reliability)
                    cache.set(cache_key, now, 15)
                except Exception as e:
                    # Don't break requests if update fails
                    logger.error(f"Error updating last_seen for user {request.user.id}: {str(e)}", exc_info=True)
            
            return None
        except Exception as e:
            # Don't break requests if middleware fails
            logger.error(f"Error in UpdateLastSeenMiddleware: {str(e)}", exc_info=True)
            return None
