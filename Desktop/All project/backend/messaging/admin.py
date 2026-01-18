"""
Admin interface for messaging system
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Conversation, Message, MessageReport


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user1_email', 'user2_email', 'listing_reference',
        'scam_score_display', 'is_locked', 'message_count', 'created_at', 'last_message_at'
    ]
    list_filter = ['is_locked', 'created_at', 'last_message_at', 'scam_score']
    search_fields = ['user1__email', 'user2__email', 'listing__reference']
    readonly_fields = ['created_at', 'last_message_at', 'scam_score']
    raw_id_fields = ['user1', 'user2', 'listing', 'transaction', 'locked_by']

    fieldsets = (
        ('Participants', {
            'fields': ('user1', 'user2')
        }),
        ('Context', {
            'fields': ('listing', 'transaction')
        }),
        ('Status', {
            'fields': ('is_locked', 'locked_by', 'locked_reason', 'scam_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_message_at')
        }),
        ('Archived', {
            'fields': ('is_archived_user1', 'is_archived_user2')
        }),
    )

    def user1_email(self, obj):
        return obj.user1.email
    user1_email.short_description = 'User 1'

    def user2_email(self, obj):
        return obj.user2.email
    user2_email.short_description = 'User 2'

    def listing_reference(self, obj):
        return obj.listing.reference if obj.listing else '-'
    listing_reference.short_description = 'Listing'

    def scam_score_display(self, obj):
        if obj.scam_score >= 50:
            color = 'red'
        elif obj.scam_score >= 20:
            color = 'orange'
        else:
            color = 'green'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.scam_score
        )
    scam_score_display.short_description = 'Scam Score'

    def message_count(self, obj):
        return obj.messages.filter(is_deleted=False).count()
    message_count.short_description = 'Messages'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            message_count=Count('messages', filter=Q(messages__is_deleted=False))
        )

    actions = ['lock_conversations', 'unlock_conversations']

    def lock_conversations(self, request, queryset):
        for conversation in queryset:
            conversation.is_locked = True
            conversation.locked_by = request.user
            # Auto-archive when locked
            conversation.is_archived_user1 = True
            conversation.is_archived_user2 = True
            conversation.save(update_fields=['is_locked', 'locked_by', 'is_archived_user1', 'is_archived_user2'])
        self.message_user(request, f'{queryset.count()} conversations locked and archived.')
    lock_conversations.short_description = 'Lock and archive selected conversations'

    def unlock_conversations(self, request, queryset):
        queryset.update(is_locked=False, locked_by=None)
        self.message_user(request, f'{queryset.count()} conversations unlocked.')
    unlock_conversations.short_description = 'Unlock selected conversations'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'conversation_link', 'sender_email', 'content_preview',
        'message_type', 'flagged', 'scam_detected', 'created_at'
    ]
    list_filter = [
        'message_type', 'flagged', 'scam_detected', 'created_at', 'read'
    ]
    search_fields = ['content', 'sender__email', 'conversation__id']
    readonly_fields = [
        'created_at', 'read', 'read_at', 'flagged', 'scam_detected',
        'scam_patterns', 'original_content_display'
    ]
    raw_id_fields = ['conversation', 'sender']

    fieldsets = (
        ('Message', {
            'fields': ('conversation', 'sender', 'content', 'original_content_display', 'message_type')
        }),
        ('Status', {
            'fields': ('read', 'read_at', 'flagged', 'flagged_reason', 'scam_detected', 'scam_patterns')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at')
        }),
    )

    def conversation_link(self, obj):
        return format_html(
            '<a href="/admin/messaging/conversation/{}/change/">{}</a>',
            obj.conversation.id, obj.conversation.id
        )
    conversation_link.short_description = 'Conversation'

    def sender_email(self, obj):
        return obj.sender.email
    sender_email.short_description = 'Sender'

    def content_preview(self, obj):
        preview = obj.content[:100]
        if len(obj.content) > 100:
            preview += '...'
        return preview
    content_preview.short_description = 'Content'

    def original_content_display(self, obj):
        if obj.original_content:
            return format_html(
                '<div style="background: #f0f0f0; padding: 10px; border-radius: 5px;">'
                '<strong>Original (blocked):</strong><br/>{}'
                '</div>',
                obj.original_content
            )
        return '-'
    original_content_display.short_description = 'Original Content'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('conversation', 'sender')

    actions = ['flag_messages', 'unflag_messages', 'mark_as_scam', 'unmark_as_scam']

    def flag_messages(self, request, queryset):
        queryset.update(flagged=True)
        self.message_user(request, f'{queryset.count()} messages flagged.')
    flag_messages.short_description = 'Flag selected messages'

    def unflag_messages(self, request, queryset):
        queryset.update(flagged=False)
        self.message_user(request, f'{queryset.count()} messages unflagged.')
    unflag_messages.short_description = 'Unflag selected messages'

    def mark_as_scam(self, request, queryset):
        queryset.update(scam_detected=True, flagged=True)
        self.message_user(request, f'{queryset.count()} messages marked as scam.')
    mark_as_scam.short_description = 'Mark as scam'

    def unmark_as_scam(self, request, queryset):
        queryset.update(scam_detected=False)
        self.message_user(request, f'{queryset.count()} messages unmarked as scam.')
    unmark_as_scam.short_description = 'Unmark as scam'


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'message_link', 'reported_by_email', 'reason_preview',
        'reviewed', 'reviewed_by_email', 'created_at'
    ]
    list_filter = ['reviewed', 'created_at', 'reviewed_at']
    search_fields = ['reason', 'reported_by__email', 'message__id']
    readonly_fields = ['created_at', 'reviewed_at']
    raw_id_fields = ['message', 'reported_by', 'reviewed_by']

    fieldsets = (
        ('Report', {
            'fields': ('message', 'reported_by', 'reason', 'created_at')
        }),
        ('Review', {
            'fields': ('reviewed', 'reviewed_by', 'reviewed_at', 'admin_notes')
        }),
    )

    def message_link(self, obj):
        return format_html(
            '<a href="/admin/messaging/message/{}/change/">{}</a>',
            obj.message.id, obj.message.id
        )
    message_link.short_description = 'Message'

    def reported_by_email(self, obj):
        return obj.reported_by.email
    reported_by_email.short_description = 'Reported By'

    def reason_preview(self, obj):
        preview = obj.reason[:100]
        if len(obj.reason) > 100:
            preview += '...'
        return preview
    reason_preview.short_description = 'Reason'

    def reviewed_by_email(self, obj):
        return obj.reviewed_by.email if obj.reviewed_by else '-'
    reviewed_by_email.short_description = 'Reviewed By'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'message', 'reported_by', 'reviewed_by'
        )

    actions = ['mark_as_reviewed']

    def mark_as_reviewed(self, request, queryset):
        for report in queryset:
            report.reviewed = True
            report.reviewed_by = request.user
            report.save(update_fields=['reviewed', 'reviewed_by'])
        self.message_user(request, f'{queryset.count()} reports marked as reviewed.')
    mark_as_reviewed.short_description = 'Mark as reviewed'

