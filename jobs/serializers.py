from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (Application, CandidateProfile, EmployerProfile, Job,
                     Notification)

MAX_RESUME_MB = 5


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=["employer", "candidate"],
                                   write_only=True)
    company_name = serializers.CharField(write_only=True, required=False,
                                         allow_blank=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "role", "company_name")

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["role"] == "employer" and not attrs.get("company_name"):
            raise serializers.ValidationError(
                {"company_name": "Company name is required for employers."})
        return attrs

    def create(self, validated_data):
        role = validated_data.pop("role")
        company_name = validated_data.pop("company_name", "")
        user = User.objects.create_user(**validated_data)
        if role == "employer":
            EmployerProfile.objects.create(user=user, company_name=company_name)
        else:
            CandidateProfile.objects.create(user=user)
        return user


class EmployerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = ("id", "company_name", "website", "description")


class CandidateProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = ("id", "username", "headline", "phone", "resume")

    def validate_resume(self, value):
        if value.size > MAX_RESUME_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"Resume must be smaller than {MAX_RESUME_MB} MB.")
        return value


class JobSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source="employer.company_name", read_only=True)
    applications_count = serializers.IntegerField(
        source="applications.count", read_only=True)

    class Meta:
        model = Job
        fields = ("id", "title", "description", "company", "location",
                  "job_type", "salary_min", "salary_max", "is_active",
                  "applications_count", "created_at")
        read_only_fields = ("is_active",)

    def validate(self, attrs):
        low = attrs.get("salary_min")
        high = attrs.get("salary_max")
        if low is not None and high is not None and high < low:
            raise serializers.ValidationError(
                "salary_max cannot be smaller than salary_min.")
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    company = serializers.CharField(
        source="job.employer.company_name", read_only=True)
    candidate_name = serializers.CharField(
        source="candidate.user.username", read_only=True)
    candidate_resume = serializers.FileField(
        source="candidate.resume", read_only=True)

    class Meta:
        model = Application
        fields = ("id", "job", "job_title", "company", "candidate_name",
                  "candidate_resume", "cover_letter", "status",
                  "applied_at", "updated_at")
        read_only_fields = ("status", "applied_at", "updated_at")


class ApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ("status",)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "message", "is_read", "created_at")
        read_only_fields = ("message", "created_at")