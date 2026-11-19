from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Application, Job, Notification
from .serializers import (ApplicationSerializer, ApplicationStatusSerializer,
                          CandidateProfileSerializer,
                          EmployerProfileSerializer, JobSerializer,
                          NotificationSerializer, SignupSerializer)


# ---------- Permissions ----------
class IsEmployer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(
            request.user, "employer_profile")


class IsCandidate(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(
            request.user, "candidate_profile")


# ---------- Accounts and profiles ----------
class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]


class CandidateProfileView(generics.RetrieveUpdateAPIView):
    """Candidates view and update their profile, and upload a resume."""
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsCandidate]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user.candidate_profile


class EmployerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = EmployerProfileSerializer
    permission_classes = [IsEmployer]

    def get_object(self):
        return self.request.user.employer_profile


# ---------- Jobs ----------
class JobListCreateView(generics.ListCreateAPIView):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsEmployer()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = Job.objects.filter(is_active=True).select_related("employer")
        params = self.request.query_params

        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search))

        location = params.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        job_type = params.get("job_type")
        if job_type:
            queryset = queryset.filter(job_type=job_type)

        company = params.get("company")
        if company:
            queryset = queryset.filter(employer__company_name__icontains=company)

        min_salary = params.get("min_salary")
        if min_salary:
            try:
                queryset = queryset.filter(salary_max__gte=int(min_salary))
            except ValueError:
                raise ValidationError({"min_salary": "Must be a whole number."})

        return queryset

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user.employer_profile)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsEmployer()]

    def get_queryset(self):
        if self.request.method in permissions.SAFE_METHODS:
            return Job.objects.select_related("employer")
        # Employers can only change their own jobs (others get 404)
        return Job.objects.filter(employer=self.request.user.employer_profile)


# ---------- Applications ----------
class ApplyView(APIView):
    permission_classes = [IsCandidate]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, is_active=True)
        candidate = request.user.candidate_profile

        if not candidate.resume:
            return Response({"error": "Upload your resume before applying."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                application = Application.objects.create(
                    job=job, candidate=candidate,
                    cover_letter=request.data.get("cover_letter", ""))
        except IntegrityError:
            return Response({"error": "You already applied for this job."},
                            status=status.HTTP_409_CONFLICT)

        Notification.objects.create(
            recipient=job.employer.user,
            message=f"{request.user.username} applied for {job.title}")

        data = ApplicationSerializer(application, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class MyApplicationsView(generics.ListAPIView):
    """Candidates track their own applications."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsCandidate]

    def get_queryset(self):
        return Application.objects.filter(
            candidate=self.request.user.candidate_profile
        ).select_related("job__employer", "candidate__user")


class JobApplicationsView(generics.ListAPIView):
    """Employers see applications for their own job. Optional ?status=..."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsEmployer]

    def get_queryset(self):
        job = get_object_or_404(
            Job, pk=self.kwargs["pk"],
            employer=self.request.user.employer_profile)
        queryset = job.applications.select_related(
            "job__employer", "candidate__user")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class ApplicationStatusView(APIView):
    """Employers update the status of an application to their own job."""
    permission_classes = [IsEmployer]

    def patch(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related("job", "candidate__user"),
            pk=pk, job__employer=request.user.employer_profile)
        serializer = ApplicationStatusSerializer(application, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        Notification.objects.create(
            recipient=application.candidate.user,
            message=(f"Your application for {application.job.title} "
                     f"is now: {application.status}"))
        return Response(serializer.data)


# ---------- Notifications and reports ----------
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()
        return Response({"detail": "Marked as read."})


class EmployerStatsView(APIView):
    """Reporting: application statistics for an employer."""
    permission_classes = [IsEmployer]

    def get(self, request):
        employer = request.user.employer_profile
        applications = Application.objects.filter(job__employer=employer)
        return Response({
            "jobs_posted": employer.jobs.count(),
            "total_applications": applications.count(),
            "by_status": {
                value: applications.filter(status=value).count()
                for value, _ in Application.STATUS_CHOICES
            },
        })
