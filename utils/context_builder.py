"""
Context Builder Utility.

Assembles a clean, token-capped context string from all active
ProjectAsset summaries for a given project. This context is injected
into agent system prompts before BRD, Plan, TestCase, and Effort generation.

Usage:
    from utils.context_builder import build_context_for_project
    context = build_context_for_project(project)
    # Pass `context` to agent generate_* functions as context_summary
"""

import logging

logger = logging.getLogger(__name__)

# Maximum characters of context to inject into prompts.
# ~4000 chars ≈ ~1000 tokens — leaves ample room for structured BRD output.
MAX_CONTEXT_CHARS = 4000

# Maximum characters per individual asset summary
MAX_SUMMARY_CHARS = 600


def build_context_for_project(project) -> str:
    """
    Build a combined context string from all active project assets.

    Args:
        project: A Project model instance.

    Returns:
        str: Formatted context block for injection into AI prompts.
             Returns empty string if no active assets or no summaries available.
    """
    from apps.projects.models import ProjectAsset  # Avoid circular import

    active_assets = project.assets.filter(
        is_active=True,
        extraction_status='complete',
    ).exclude(summary=None).exclude(summary='')

    if not active_assets.exists():
        logger.debug(f'[ContextBuilder] No active assets for project {project.id}')
        return ''

    parts = []
    total_chars = 0

    for asset in active_assets:
        connector_label = dict(ProjectAsset.CONNECTOR_TYPE_CHOICES).get(
            asset.connector_type, asset.connector_type.title()
        )
        title = asset.title or asset.url or 'Untitled'
        summary = (asset.summary or '')[:MAX_SUMMARY_CHARS]

        block = f'[{connector_label}] {title}:\n{summary}'

        if total_chars + len(block) > MAX_CONTEXT_CHARS:
            logger.debug(
                f'[ContextBuilder] Context cap reached at {total_chars} chars '
                f'after {len(parts)} assets — stopping early.'
            )
            break

        parts.append(block)
        total_chars += len(block)

    if not parts:
        return ''

    header = (
        '=== PROJECT CONTEXT (from attached source documents) ===\n'
        'Use the following context to ensure the generated document aligns '
        'with the project\'s actual meetings, decisions, and references:\n\n'
    )
    footer = '\n=== END OF PROJECT CONTEXT ==='

    context = header + '\n\n---\n\n'.join(parts) + footer
    logger.info(
        f'[ContextBuilder] Built context for project {project.id}: '
        f'{len(parts)} assets, {len(context)} chars'
    )
    return context


def build_project_metadata_block(project) -> str:
    """
    Build a short metadata block with project name, LOB, app type, department.
    Prepended to extracted_text before passing to agents.

    Args:
        project: A Project model instance.

    Returns:
        str: Metadata header string (empty if all fields are blank).
    """
    lines = []
    if project.name:
        lines.append(f'Project Name: {project.name}')
    if project.line_of_business:
        lines.append(f'Line of Business: {project.line_of_business}')
    if project.application_type:
        app_label = dict(project.APPLICATION_TYPE_CHOICES).get(
            project.application_type, project.application_type
        )
        lines.append(f'Application Type: {app_label}')
    if project.department:
        lines.append(f'Department: {project.department}')

    if not lines:
        return ''

    return 'PROJECT METADATA:\n' + '\n'.join(lines) + '\n\n'
