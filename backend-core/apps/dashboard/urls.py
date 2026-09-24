"""Dashboard URLs"""
from django.urls import path
from apps.uploads.presentation.dashboard_views import DashboardStatsView, RecentActivitiesView

app_name = 'dashboard'

urlpatterns = [
    path('stats/', DashboardStatsView.as_view(), name='stats'),
    path('activities/', RecentActivitiesView.as_view(), name='activities'),
]
