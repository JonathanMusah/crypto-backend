from rest_framework import serializers

from marketing.models import (
    FeatureBlock,
    PolicyPage,
    SecurityHighlight,
    SupportedAsset,
    Testimonial,
    UserReview,
)


class FeatureBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureBlock
        fields = [
            "id",
            "title",
            "subtitle",
            "description",
            "icon",
            "accent_color",
            "emphasis",
        ]


class SecurityHighlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityHighlight
        fields = [
            "id",
            "title",
            "description",
            "badge",
            "icon",
            "status",
        ]


class SupportedAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportedAsset
        fields = [
            "id",
            "name",
            "symbol",
            "network",
            "segment",
            "liquidity_rank",
            "is_featured",
            "description",
        ]


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = [
            "id",
            "author_name",
            "role",
            "company",
            "quote",
            "avatar_url",
            "rating",
            "highlight",
        ]


class PolicyPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyPage
        fields = [
            "slug",
            "title",
            "summary",
            "sections",
            "last_updated",
            "hero_badge",
        ]


class UserReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    overall_rating = serializers.FloatField(read_only=True)
    
    class Meta:
        model = UserReview
        fields = [
            "id",
            "user",
            "user_email",
            "author_name",
            "email",
            "rating",
            "title",
            "comment",
            "service_rating",
            "speed_rating",
            "support_rating",
            "status",
            "is_featured",
            "role",
            "company",
            "avatar_url",
            "overall_rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "status", "created_at", "updated_at")

    def validate_rating(self, value):
        """Ensure rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def create(self, validated_data):
        """Set user from request if authenticated"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
            # Auto-populate author_name and email if not provided
            if not validated_data.get('author_name'):
                validated_data['author_name'] = request.user.get_full_name() or request.user.email.split('@')[0]
            if not validated_data.get('email'):
                validated_data['email'] = request.user.email
        return super().create(validated_data)


class UserReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews (allows anonymous users)"""
    class Meta:
        model = UserReview
        fields = [
            "author_name",
            "email",
            "rating",
            "title",
            "comment",
            "service_rating",
            "speed_rating",
            "support_rating",
            "role",
            "company",
        ]

    def validate_rating(self, value):
        """Ensure rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

