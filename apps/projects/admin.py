from django.contrib import admin
from .models import Project, AgentOutput


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'brd_approved', 'created_at', 'updated_at']
    list_filter = ['status', 'brd_approved']
    search_fields = ['id', 'raw_input', 'extracted_text']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(AgentOutput)
class AgentOutputAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'agent_type', 'status', 'updated_at']
    list_filter = ['agent_type', 'status']
    search_fields = ['project__id']
    readonly_fields = ['id', 'created_at', 'updated_at']
