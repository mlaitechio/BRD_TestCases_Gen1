from django.urls import path
from . import views

urlpatterns = [
    # ── Project Lifecycle ──────────────────────────────────────────────────────
    path('', views.ProjectListCreateView.as_view(), name='project-list-create'),
    path('<uuid:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('<uuid:pk>/status/', views.ProjectStatusView.as_view(), name='project-status'),

    # ── BRD Core ──────────────────────────────────────────────────────────────
    path('<uuid:pk>/brd/', views.BRDOutputView.as_view(), name='brd-output'),
    path('<uuid:pk>/generate-brd/', views.GenerateBRDView.as_view(), name='generate-brd'),
    path('<uuid:pk>/approve-brd/', views.ApproveBRDView.as_view(), name='approve-brd'),
    path('<uuid:pk>/revise-brd/', views.ReviseBRDView.as_view(), name='revise-brd'),

    # ── BRD Versioning ────────────────────────────────────────────────────────
    path('<uuid:pk>/brd/versions/', views.BRDVersionListView.as_view(), name='brd-versions'),
    path('<uuid:pk>/brd/save-version/', views.SaveBRDVersionView.as_view(), name='brd-save-version'),
    path('<uuid:pk>/brd/restore/<int:vn>/', views.RestoreBRDVersionView.as_view(), name='brd-restore-version'),
    path('<uuid:pk>/brd/edit-section/', views.BRDSectionEditView.as_view(), name='brd-edit-section'),
    path('<uuid:pk>/brd/chat-edit/', views.BRDChatEditView.as_view(), name='brd-chat-edit'),
    path('<uuid:pk>/brd/chat-edit/<str:task_id>/', views.BRDChatEditStatusView.as_view(), name='brd-chat-edit-status'),

    # ── TestCase Versioning ───────────────────────────────────────────────────
    path('<uuid:pk>/testcases/versions/', views.TestCaseVersionListView.as_view(), name='testcase-versions'),
    path('<uuid:pk>/testcases/save-version/', views.SaveTestCaseVersionView.as_view(), name='testcase-save-version'),
    path('<uuid:pk>/testcases/restore/<int:vn>/', views.RestoreTestCaseVersionView.as_view(), name='testcase-restore-version'),

    # ── Project Plan Versioning ───────────────────────────────────────────────
    path('<uuid:pk>/plan/versions/', views.ProjectPlanVersionListView.as_view(), name='plan-versions'),
    path('<uuid:pk>/plan/save-version/', views.SaveProjectPlanVersionView.as_view(), name='plan-save-version'),
    path('<uuid:pk>/plan/restore/<int:vn>/', views.RestoreProjectPlanVersionView.as_view(), name='plan-restore-version'),

    # ── Table of Contents ─────────────────────────────────────────────────────
    path('<uuid:pk>/toc/', views.TOCView.as_view(), name='toc'),

    # ── Source Connectors / Assets ────────────────────────────────────────────
    path('<uuid:pk>/assets/', views.ProjectAssetListCreateView.as_view(), name='asset-list-create'),
    path('<uuid:pk>/assets/search/', views.ProjectAssetSearchView.as_view(), name='asset-search'),
    path('<uuid:pk>/assets/<uuid:aid>/toggle/', views.ProjectAssetToggleView.as_view(), name='asset-toggle'),
    path('<uuid:pk>/assets/<uuid:aid>/', views.ProjectAssetDeleteView.as_view(), name='asset-delete'),

    # ── AI Chat & Multi-Document Chat Edit ────────────────────────────────────
    path('<uuid:pk>/chat/', views.AIChatView.as_view(), name='ai-chat'),
    path('<uuid:pk>/<str:document_type>/chat-edit/', views.DocumentChatEditView.as_view(), name='document-chat-edit'),
    path('<uuid:pk>/<str:document_type>/chat-edit/<str:task_id>/', views.DocumentChatEditStatusView.as_view(), name='document-chat-edit-status'),

    # ── Other Agent Outputs ───────────────────────────────────────────────────
    path('<uuid:pk>/generate-plan/', views.GeneratePlanView.as_view(), name='generate-plan'),
    path('<uuid:pk>/generate-testcases/', views.GenerateTestCasesView.as_view(), name='generate-testcases'),
    path('<uuid:pk>/generate-effort/', views.GenerateEffortView.as_view(), name='generate-effort'),
    path('<uuid:pk>/plan/', views.PlanOutputView.as_view(), name='plan-output'),
    path('<uuid:pk>/testcases/', views.TestCasesOutputView.as_view(), name='testcases-output'),
    path('<uuid:pk>/effort/', views.EffortOutputView.as_view(), name='effort-output'),

    # ── DOCX Downloads ────────────────────────────────────────────────────────
    path('<uuid:pk>/download/<str:output_type>/', views.DownloadOutputView.as_view(), name='download-output'),
]
