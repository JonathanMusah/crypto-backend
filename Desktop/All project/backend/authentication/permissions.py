from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'


class IsAdminOrReadOnly(BasePermission):
    """
    Allows read-only access to all users, but write access only to admin users.
    """
    def has_permission(self, request, view):
        # Allow read-only methods for all users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        # Allow write methods only for admin users
        return request.user and request.user.role == 'admin'