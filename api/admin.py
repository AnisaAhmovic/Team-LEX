from django.contrib import admin

from api.models import AuditChunk, AuditLog


class AuditChunkInline(admin.TabularInline):
    """Shows the chunks underneath the question they came from."""
    model = AuditChunk
    extra = 0


class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "source", "test_id", "question", "outcome", "top_score"]
    list_filter = ["outcome", "source", "config_summary"]
    search_fields = ["question", "test_id"]
    inlines = [AuditChunkInline]


admin.site.register(AuditLog, AuditLogAdmin)
