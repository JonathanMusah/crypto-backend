from django.contrib import admin
from .models import KYCVerification


@admin.register(KYCVerification)
class KYCVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'document_type', 'first_name', 'last_name', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'document_type', 'submitted_at')
    search_fields = ('user__email', 'document_number', 'first_name', 'last_name')
    readonly_fields = ('submitted_at', 'reviewed_at', 'reviewed_by')

