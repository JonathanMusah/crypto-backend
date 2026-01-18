from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class FeatureBlock(TimeStampedModel):
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    icon = models.CharField(max_length=80, default="Sparkles")
    accent_color = models.CharField(max_length=30, default="#38bdf8")
    emphasis = models.CharField(max_length=120, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Feature highlight"
        verbose_name_plural = "Feature highlights"

    def __str__(self) -> str:
        return self.title


class SecurityHighlight(TimeStampedModel):
    title = models.CharField(max_length=150)
    description = models.TextField()
    badge = models.CharField(max_length=60, blank=True)
    icon = models.CharField(max_length=80, default="Shield")
    status = models.CharField(max_length=60, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Security highlight"
        verbose_name_plural = "Security highlights"

    def __str__(self) -> str:
        return self.title


class SupportedAsset(TimeStampedModel):
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=20)
    network = models.CharField(max_length=80, blank=True)
    segment = models.CharField(max_length=80, blank=True)
    liquidity_rank = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "liquidity_rank", "symbol"]
        verbose_name = "Supported asset"
        verbose_name_plural = "Supported assets"
        constraints = [
            models.UniqueConstraint(
                fields=("symbol", "network"),
                name="marketing_supportedasset_symbol_network_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})"


class Testimonial(TimeStampedModel):
    author_name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True)
    company = models.CharField(max_length=120, blank=True)
    quote = models.TextField()
    avatar_url = models.URLField(blank=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=5.0)
    highlight = models.CharField(max_length=120, blank=True)
    is_featured = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-rating", "author_name"]
        verbose_name = "Customer testimonial"
        verbose_name_plural = "Customer testimonials"

    def __str__(self) -> str:
        return self.author_name


class UserReview(TimeStampedModel):
    """User-submitted testimonials and ratings"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='reviews',
        null=True,
        blank=True
    )
    author_name = models.CharField(max_length=120, help_text="Display name for the review")
    email = models.EmailField(blank=True, help_text="Email (optional, used for verification)")
    rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=200, blank=True, help_text="Review title/summary")
    comment = models.TextField(help_text="Detailed review comment")
    
    # Rating breakdown (optional)
    service_rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Service quality rating"
    )
    speed_rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Transaction speed rating"
    )
    support_rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Customer support rating"
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_featured = models.BooleanField(default=False, help_text="Feature on homepage")
    admin_note = models.TextField(blank=True, help_text="Admin internal notes")
    
    # Optional fields for display
    role = models.CharField(max_length=120, blank=True)
    company = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User Review"
        verbose_name_plural = "User Reviews"
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['rating', '-created_at']),
            models.Index(fields=['is_featured', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.author_name} - {self.rating}★ - {self.status}"

    @property
    def overall_rating(self):
        """Calculate overall rating from individual ratings if available"""
        ratings = [r for r in [self.service_rating, self.speed_rating, self.support_rating] if r]
        if ratings:
            return sum(ratings) / len(ratings)
        return float(self.rating)

    @classmethod
    def get_average_rating(cls, status='approved'):
        """Get average rating for approved reviews"""
        from django.db.models import Avg
        return cls.objects.filter(status=status).aggregate(Avg('rating'))['rating__avg'] or 0

    @classmethod
    def get_rating_distribution(cls, status='approved'):
        """Get distribution of ratings (1-5 stars)"""
        from django.db.models import Count
        return cls.objects.filter(status=status).values('rating').annotate(count=Count('rating')).order_by('rating')

    @classmethod
    def get_total_reviews(cls, status='approved'):
        """Get total number of approved reviews"""
        return cls.objects.filter(status=status).count()


class PolicyPage(TimeStampedModel):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150)
    summary = models.TextField()
    sections = models.JSONField(default=list, blank=True)
    last_updated = models.DateField()
    hero_badge = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Policy page"
        verbose_name_plural = "Policy pages"

    def __str__(self) -> str:
        return self.title

