from django.urls import path
from . import views

urlpatterns = [
    # Project lifecycle
    path('', views.ProjectCreateView.as_view(), name='project-create'),
    path('<uuid:pk>/status/', views.ProjectStatusView.as_view(), name='project-status'),

    # Clarification Q&A
    path('<uuid:pk>/clarification-questions/', views.ClarificationQuestionsView.as_view(), name='clarification-questions'),
    path('<uuid:pk>/answer-questions/', views.AnswerQuestionsView.as_view(), name='answer-questions'),

    # BRD
    path('<uuid:pk>/brd/', views.BRDOutputView.as_view(), name='brd-output'),
    path('<uuid:pk>/approve-brd/', views.ApproveBRDView.as_view(), name='approve-brd'),
    path('<uuid:pk>/revise-brd/', views.ReviseBRDView.as_view(), name='revise-brd'),

    # Other agent outputs
    path('<uuid:pk>/plan/', views.PlanOutputView.as_view(), name='plan-output'),
    path('<uuid:pk>/testcases/', views.TestCasesOutputView.as_view(), name='testcases-output'),
    path('<uuid:pk>/effort/', views.EffortOutputView.as_view(), name='effort-output'),

    # Downloads
    path('<uuid:pk>/download/<str:output_type>/', views.DownloadOutputView.as_view(), name='download-output'),
]
