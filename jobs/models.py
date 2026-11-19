from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


class EmployerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="employer_profile")
    company_name = models.CharField(max_length=200)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.company_name


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="candidate_profile")
    headline = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    resume = models.FileField(
        upload_to="resumes/", blank=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx"])])

    def __str__(self):
        return self.user.username


class Job(models.Model):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"
    TYPE_CHOICES = [
        (FULL_TIME, "Full time"),
        (PART_TIME, "Part time"),
        (INTERNSHIP, "Internship"),
        (CONTRACT, "Contract"),
    ]

    employer = models.ForeignKey(
        EmployerProfile, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    job_type = models.CharField(max_length=20, choices=TYPE_CHOICES,
                                default=FULL_TIME)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} at {self.employer}"


class Application(models.Model):
    APPLIED = "applied"
    REVIEWING = "reviewing"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    HIRED = "hired"
    STATUS_CHOICES = [
        (APPLIED, "Applied"),
        (REVIEWING, "Reviewing"),
        (SHORTLISTED, "Shortlisted"),
        (REJECTED, "Rejected"),
        (HIRED, "Hired"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE,
                            related_name="applications")
    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE,
        related_name="applications")
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES,
                              default=APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "candidate"],
                                    name="unique_candidate_job")
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job} ({self.status})"


class Notification(models.Model):
    """A simple in-app message, used to notify employers about new applications."""
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications")
    message = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.recipient}: {self.message}"