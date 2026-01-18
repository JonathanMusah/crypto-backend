from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Notification
        fields = (
            'id', 'user', 'user_email', 'message', 'read', 'notification_type', 
            'title', 'related_object_type', 'related_object_id',
            'created_at', 'time_ago'
        )
        read_only_fields = ('id', 'created_at', 'time_ago', 'user_email')
    
    def create(self, validated_data):
        """Create notification - user field is required"""
        # User must be provided in validated_data
        if 'user' not in validated_data or validated_data['user'] is None:
            raise serializers.ValidationError({'user': 'User field is required'})
        return super().create(validated_data)

    def get_time_ago(self, obj):
        """Return human-readable time ago"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return 'Just now'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        elif diff < timedelta(days=7):
            days = diff.days
            return f'{days} day{"s" if days > 1 else ""} ago'
        else:
            return obj.created_at.strftime('%b %d, %Y')

