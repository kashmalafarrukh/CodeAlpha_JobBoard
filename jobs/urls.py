from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

urlpatterns = [
    path("auth/signup/", views.SignupView.as_view()),
    path("auth/login/", obtain_auth_token),
    path("candidate/profile/", views.CandidateProfileView.as_view()),
    path("employer/profile/", views.EmployerProfileView.as_view()),
    path("employer/stats/", views.EmployerStatsView.as_view()),
    path("jobs/", views.JobListCreateView.as_view()),
    path("jobs/<int:pk>/", views.JobDetailView.as_view()),
    path("jobs/<int:pk>/apply/", views.ApplyView.as_view()),
    path("jobs/<int:pk>/applications/", views.JobApplicationsView.as_view()),
    path("applications/", views.MyApplicationsView.as_view()),
    path("applications/<int:pk>/status/", views.ApplicationStatusView.as_view()),
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/<int:pk>/read/", views.NotificationReadView.as_view()),
]