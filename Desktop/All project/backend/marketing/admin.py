from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from marketing.models import (
    FeatureBlock,
    PolicyPage,
    SecurityHighlight,
    SupportedAsset,
    Testimonial,
    UserReview,
)


@admin.register(FeatureBlock)
class FeatureBlockAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "accent_color", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("title", "subtitle", "description")


@admin.register(SecurityHighlight)
class SecurityHighlightAdmin(admin.ModelAdmin):
    list_display = ("title", "badge", "status", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("title", "description", "badge")


@admin.register(SupportedAsset)
class SupportedAssetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "symbol",
        "network",
        "segment",
        "liquidity_rank",
        "is_featured",
    )
    list_editable = ("liquidity_rank", "is_featured")
    list_filter = ("is_featured", "segment", "network")
    search_fields = ("name", "symbol")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("author_name", "company", "rating", "highlight", "is_featured")
    list_editable = ("is_featured",)
    search_fields = ("author_name", "company", "quote")


@admin.register(PolicyPage)
class PolicyPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "last_updated")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "summary")


class UserReviewAdmin(admin.ModelAdmin):
    list_display = ("author_name", "email", "rating_display", "status_display", "is_featured", "is_featured_display", "created_at", "quick_actions")
    list_filter = ("status", "rating", "is_featured", "created_at")
    list_editable = ("is_featured",)
    search_fields = ("author_name", "email", "comment", "title")
    readonly_fields = ("created_at", "updated_at", "overall_rating")
    fieldsets = (
        ("Review Information", {
            "fields": ("user", "author_name", "email", "rating", "title", "comment")
        }),
        ("Detailed Ratings (Optional)", {
            "fields": ("service_rating", "speed_rating", "support_rating"),
            "classes": ("collapse",)
        }),
        ("Display Settings", {
            "fields": ("status", "is_featured", "role", "company", "avatar_url")
        }),
        ("Admin Notes", {
            "fields": ("admin_note",),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "overall_rating"),
            "classes": ("collapse",)
        }),
    )
    
    actions = ["approve_reviews", "reject_reviews", "feature_reviews", "unfeature_reviews"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:review_id>/approve/',
                self.admin_site.admin_view(self.approve_review_view),
                name='marketing_userreview_approve',
            ),
            path(
                '<int:review_id>/reject/',
                self.admin_site.admin_view(self.reject_review_view),
                name='marketing_userreview_reject',
            ),
        ]
        return custom_urls + urls

    def approve_review_view(self, request, review_id):
        """View to approve a single review"""
        review = get_object_or_404(UserReview, pk=review_id)
        review.status = 'approved'
        review.save()
        messages.success(request, f'Review by {review.author_name} has been approved.')
        return redirect('admin:marketing_userreview_changelist')

    def reject_review_view(self, request, review_id):
        """View to reject a single review"""
        review = get_object_or_404(UserReview, pk=review_id)
        review.status = 'rejected'
        review.save()
        messages.success(request, f'Review by {review.author_name} has been rejected.')
        return redirect('admin:marketing_userreview_changelist')

    def rating_display(self, obj):
        """Display rating with stars"""
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: #f59e0b; font-size: 14px;">{}</span> <span style="color: #64748b;">({})</span>',
            stars, obj.rating
        )
    rating_display.short_description = "Rating"

    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': '#f59e0b',
            'approved': '#10b981',
            'rejected': '#ef4444',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-transform: uppercase;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Status"

    def is_featured_display(self, obj):
        """Display featured status with icon"""
        if obj.is_featured:
            return format_html(
                '<span style="color: #f59e0b;">⭐ Featured</span>'
            )
        return '-'
    is_featured_display.short_description = "Featured"

    def quick_actions(self, obj):
        """Quick action buttons for approve/reject"""
        if obj.status == 'pending':
            approve_url = f'/admin/marketing/userreview/{obj.id}/approve/'
            reject_url = f'/admin/marketing/userreview/{obj.id}/reject/'
            return format_html(
                '<a href="{}" class="button" style="background: #10b981; color: white; padding: 6px 14px; border-radius: 4px; text-decoration: none; margin-right: 6px; font-size: 12px; font-weight: 500; display: inline-block;">✓ Approve</a>'
                '<a href="{}" class="button" style="background: #ef4444; color: white; padding: 6px 14px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: 500; display: inline-block;">✗ Reject</a>',
                approve_url,
                reject_url
            )
        return format_html('<span style="color: #94a3b8;">-</span>')
    quick_actions.short_description = "Quick Actions"

    def approve_reviews(self, request, queryset):
        """Approve selected reviews"""
        updated = queryset.update(status='approved')
        self.message_user(request, f"{updated} review(s) approved.")
    approve_reviews.short_description = "Approve selected reviews"

    def reject_reviews(self, request, queryset):
        """Reject selected reviews"""
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} review(s) rejected.")
    reject_reviews.short_description = "Reject selected reviews"

    def feature_reviews(self, request, queryset):
        """Feature selected reviews"""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated} review(s) featured.")
    feature_reviews.short_description = "Feature selected reviews"

    def unfeature_reviews(self, request, queryset):
        """Unfeature selected reviews"""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f"{updated} review(s) unfeatured.")
    unfeature_reviews.short_description = "Unfeature selected reviews"

