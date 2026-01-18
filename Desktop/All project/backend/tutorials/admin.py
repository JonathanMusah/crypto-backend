from django.contrib import admin
from .models import Tutorial, TutorialProgress


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'order', 'views', 'author', 'created_at')
    list_filter = ('category', 'is_published', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views', 'created_at', 'updated_at')


@admin.register(TutorialProgress)
class TutorialProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'tutorial', 'is_completed', 'completed_at', 'created_at')
    list_filter = ('is_completed', 'created_at')
    search_fields = ('user__email', 'tutorial__title')

