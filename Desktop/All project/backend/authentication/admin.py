from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTP, UserDevice, SecurityLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'kyc_status', 'trust_score_display', 'successful_trades', 'is_staff', 'created_at')
    list_filter = ('role', 'kyc_status', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('email', 'username')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('phone', 'role', 'kyc_status')}),
        ('Trust Score & Reputation', {
            'fields': ('successful_trades', 'disputes_filed', 'disputes_against', 'trust_score', 'trust_score_override'),
            'description': 'Trust score is calculated automatically. Use override to manually set a score.'
        }),
    )
    readonly_fields = ('trust_score',)
    
    def trust_score_display(self, obj):
        """Display trust score with color coding"""
        score = obj.get_effective_trust_score()
        if score < 0:
            color = 'red'
            label = 'Blocked'
        elif score <= 3:
            color = 'orange'
            label = 'Low'
        elif score <= 10:
            color = 'blue'
            label = 'Medium'
        else:
            color = 'green'
            label = 'High'
        
        from django.utils.html import format_html
        override_note = f" (Override: {obj.trust_score_override})" if obj.trust_score_override is not None else ""
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} ({})</span>{}',
            color, score, label, override_note
        )
    trust_score_display.short_description = 'Trust Score'
    trust_score_display.admin_order_field = 'trust_score'


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'is_used', 'attempts')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('otp_hash', 'created_at', 'expires_at', 'attempts')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('OTP Information', {
            'fields': ('user', 'otp_hash', 'is_used', 'attempts')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'expires_at')
        }),
    )
    
    def has_add_permission(self, request):
        return False  # OTPs should only be created via API
    
    def has_change_permission(self, request, obj=None):
        return False  # OTPs should not be manually edited


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'device_fingerprint', 'is_active', 'first_seen', 'last_seen')
    list_filter = ('is_active', 'first_seen', 'last_seen')
    search_fields = ('user__email', 'ip_address', 'user_agent')
    readonly_fields = ('device_fingerprint', 'first_seen', 'last_seen', 'user_agent', 'ip_address')
    ordering = ('-last_seen',)
    
    fieldsets = (
        ('Device Information', {
            'fields': ('user', 'ip_address', 'user_agent', 'device_fingerprint', 'location')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('first_seen', 'last_seen')
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Devices should only be created via API


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('user__email', 'ip_address', 'user_agent')
    readonly_fields = ('user', 'event_type', 'ip_address', 'user_agent', 'details', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Event Information', {
            'fields': ('user', 'event_type', 'ip_address', 'user_agent')
        }),
        ('Details', {
            'fields': ('details',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Security logs should only be created via API
    
    def has_change_permission(self, request, obj=None):
        return False  # Security logs should not be manually edited

