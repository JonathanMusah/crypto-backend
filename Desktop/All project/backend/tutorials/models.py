from django.db import models
from django.conf import settings


class Tutorial(models.Model):
    CATEGORY_CHOICES = [
        ('beginner', 'Beginner'),
        ('trading', 'Trading'),
        ('wallets', 'Wallets'),
        ('security', 'Security'),
    ]

    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    video_url = models.URLField(blank=True, null=True)
    slug = models.SlugField(unique=True)
    excerpt = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='tutorials/thumbnails/', blank=True, null=True)
    order = models.IntegerField(default=0)
    is_published = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='tutorials')
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tutorials'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title


class TutorialProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tutorial_progress')
    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tutorial_progress'
        unique_together = ('user', 'tutorial')

    def __str__(self):
        return f"{self.user.email} - {self.tutorial.title}"

