from django.urls import path
from apps.jobs.api.views.views import StartProcessingView, JobListView
from apps.jobs.api.views.ai_callback import AICallbackView
from apps.jobs.api.views.job_management_views import (
    JobListView as JobManagementListView,
    JobDetailView,
    JobDeleteView
)
from apps.jobs.api.views.job_rerun_view import JobRerunView
from apps.jobs.api.views.job_cancel_view import JobCancelView

urlpatterns = [
    path('start-job/', StartProcessingView.as_view(), name='start-processing'),
    path('list/', JobListView.as_view(), name='job-list'),  # Old list view (AI uses this)
    path('ai-callback/', AICallbackView.as_view(), name='ai-callback'),
    
    # Job Management (Frontend UI)
    path('', JobManagementListView.as_view(), name='job-management-list'),
    path('<uuid:job_id>/', JobDetailView.as_view(), name='job-detail'),
    path('<uuid:job_id>/delete/', JobDeleteView.as_view(), name='job-delete'),
    path('<uuid:job_id>/cancel/', JobCancelView.as_view(), name='job-cancel'),
    path('<uuid:job_id>/rerun/', JobRerunView.as_view(), name='job-rerun'),
    
    # Note: To get products for a job, use /v1/api/products/?job_id={job_id}
]
