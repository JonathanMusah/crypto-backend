from rest_framework import serializers
from .models import Tutorial, TutorialProgress


class TutorialSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Tutorial
        fields = (
            'id', 'title', 'content', 'category', 'video_url', 'slug', 
            'excerpt', 'thumbnail', 'thumbnail_url', 'order', 'is_published', 
            'author', 'views', 'user_progress', 'is_completed', 
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'author', 'views', 'created_at', 'updated_at', 'user_progress', 'is_completed')

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def get_user_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                progress = TutorialProgress.objects.get(user=request.user, tutorial=obj)
                return {
                    'is_completed': progress.is_completed,
                    'completed_at': progress.completed_at,
                    'created_at': progress.created_at
                }
            except TutorialProgress.DoesNotExist:
                return None
        return None

    def get_is_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                progress = TutorialProgress.objects.get(user=request.user, tutorial=obj)
                return progress.is_completed
            except TutorialProgress.DoesNotExist:
                return False
        return False


class TutorialProgressSerializer(serializers.ModelSerializer):
    tutorial = TutorialSerializer(read_only=True)
    tutorial_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = TutorialProgress
        fields = ('id', 'user', 'tutorial', 'tutorial_id', 'is_completed', 'completed_at', 'created_at')
        read_only_fields = ('id', 'user', 'created_at')

    def create(self, validated_data):
        tutorial_id = validated_data.pop('tutorial_id', None)
        if tutorial_id:
            validated_data['tutorial_id'] = tutorial_id
        return super().create(validated_data)

