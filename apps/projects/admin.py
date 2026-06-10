"""
Django Admin configuration for the IT Automation SDLC Platform.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Project, AgentOutput, ProjectAsset, BRDVersion, TOCSection


# ─── Agent Output Inline ──────────────────────────────────────────────────────

class AgentOutputInline(admin.TabularInline):
    model = AgentOutput
    extra = 0
    readonly_fields = ['id', 'agent_type', 'status', 'error_message', 'created_at', 'updated_at']
    fields = ['agent_type', 'status', 'error_message', 'updated_at']
    can_delete = False
    show_change_link = True


class ProjectAssetInline(admin.TabularInline):
    model = ProjectAsset
    extra = 0
    readonly_fields = ['id', 'connector_type', 'extraction_status', 'is_active', 'created_at']
    fields = ['connector_type', 'title', 'extraction_status', 'is_active']
    can_delete = True
    show_change_link = True


class BRDVersionInline(admin.TabularInline):
    model = BRDVersion
    extra = 0
    readonly_fields = ['id', 'version_number', 'notes', 'created_at']
    fields = ['version_number', 'notes', 'created_at']
    can_delete = False
    show_change_link = True


# ─── Project Admin ────────────────────────────────────────────────────────────

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'id_short', 'name', 'line_of_business', 'application_type',
        'status_badge', 'brd_approved', 'asset_count', 'version_count', 'created_at',
    ]
    list_filter = ['status', 'brd_approved', 'application_type', 'created_at']
    search_fields = ['id', 'name', 'line_of_business', 'department', 'raw_input']
    readonly_fields = [
        'id', 'extracted_text', 'clarification_questions',
        'clarification_answers', 'created_at', 'updated_at',
    ]
    ordering = ['-created_at']

    fieldsets = [
        ('Project Identity', {
            'fields': ['id', 'name', 'line_of_business', 'application_type', 'department'],
        }),
        ('Input Content', {
            'fields': ['raw_input', 'uploaded_file', 'extracted_text'],
            'classes': ['collapse'],
        }),
        ('Clarification Q&A', {
            'fields': ['clarification_questions', 'clarification_answers'],
            'classes': ['collapse'],
        }),
        ('Pipeline State', {
            'fields': ['status', 'brd_approved', 'revision_notes', 'error_message'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    inlines = [AgentOutputInline, ProjectAssetInline, BRDVersionInline]

    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'

    def status_badge(self, obj):
        colours = {
            'new': '#6c757d',
            'clarifying': '#17a2b8',
            'awaiting_answers': '#ffc107',
            'generating_brd': '#007bff',
            'awaiting_approval': '#fd7e14',
            'approved': '#28a745',
            'complete': '#155724',
            'failed': '#dc3545',
        }
        colour = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            colour, obj.status.replace('_', ' ').title()
        )
    status_badge.short_description = 'Status'

    def asset_count(self, obj):
        total = obj.assets.count()
        active = obj.assets.filter(is_active=True).count()
        return f'{active}/{total} active'
    asset_count.short_description = 'Assets'

    def version_count(self, obj):
        return obj.brd_versions.count()
    version_count.short_description = 'BRD Versions'


# ─── AgentOutput Admin ────────────────────────────────────────────────────────

@admin.register(AgentOutput)
class AgentOutputAdmin(admin.ModelAdmin):
    list_display = ['project', 'agent_type', 'status', 'error_message', 'updated_at']
    list_filter = ['agent_type', 'status']
    search_fields = ['project__id', 'project__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


# ─── ProjectAsset Admin ───────────────────────────────────────────────────────

@admin.register(ProjectAsset)
class ProjectAssetAdmin(admin.ModelAdmin):
    list_display = [
        'id_short', 'project', 'connector_type', 'title',
        'extraction_status', 'is_active', 'created_at',
    ]
    list_filter = ['connector_type', 'extraction_status', 'is_active']
    search_fields = ['project__name', 'title', 'url']
    readonly_fields = ['id', 'extracted_text', 'summary', 'extraction_error', 'created_at', 'updated_at']

    fieldsets = [
        ('Asset Identity', {
            'fields': ['id', 'project', 'connector_type', 'title'],
        }),
        ('Source', {
            'fields': ['file', 'url'],
        }),
        ('Extraction Results', {
            'fields': ['extraction_status', 'extraction_error', 'summary', 'extracted_text'],
            'classes': ['collapse'],
        }),
        ('Context Toggle', {
            'fields': ['is_active'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'


# ─── BRDVersion Admin ─────────────────────────────────────────────────────────

@admin.register(BRDVersion)
class BRDVersionAdmin(admin.ModelAdmin):
    list_display = ['project', 'version_number', 'notes', 'created_at']
    list_filter = ['created_at']
    search_fields = ['project__name', 'project__id', 'notes']
    readonly_fields = ['id', 'project', 'version_number', 'structured_output', 'created_at']

    def has_change_permission(self, request, obj=None):
        return False  # BRD versions are immutable — no editing in admin


# ─── TOCSection Admin ─────────────────────────────────────────────────────────

@admin.register(TOCSection)
class TOCSectionAdmin(admin.ModelAdmin):
    list_display = ['project', 'order', 'label', 'key', 'is_enabled', 'is_custom']
    list_filter = ['is_enabled', 'is_custom']
    search_fields = ['project__name', 'label', 'key']
    ordering = ['project', 'order']
