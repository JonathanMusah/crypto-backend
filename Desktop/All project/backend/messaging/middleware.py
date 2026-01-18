"""
Custom WebSocket authentication middleware for JWT token from cookies.
"""
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from channels.auth import AuthMiddlewareStack
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser

User = get_user_model()
jwt_auth = JWTAuthentication()


@database_sync_to_async
def get_user_from_token(token):
    """Get user from JWT token"""
    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        return user
    except (InvalidToken, TokenError, Exception):
        pass
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom JWT authentication middleware for WebSocket connections.
    Reads JWT token from cookies.
    """
    
    async def __call__(self, scope, receive, send):
        # Get cookies from scope
        cookies = {}
        if 'headers' in scope:
            for header_name, header_value in scope.get('headers', []):
                if header_name == b'cookie':
                    cookie_string = header_value.decode('utf-8')
                    for cookie in cookie_string.split(';'):
                        if '=' in cookie:
                            key, value = cookie.strip().split('=', 1)
                            cookies[key] = value
        
        # Try to get access_token from cookies
        access_token = cookies.get('access_token')
        
        if access_token:
            scope['user'] = await get_user_from_token(access_token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Stack JWT auth middleware with URL router"""
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))

