from django.contrib import admin

from .models import (Application, CandidateProfile, EmployerProfile, Job,
                     Notification)


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    readonly_fields = ("applied_at",)


@admin.register(EmployerProfile)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website")
    search_fields = ("company_name",)


@admin.register(CandidateProfile)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("user", "headline", "phone")
    search_fields = ("user__username", "headline")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "location", "job_type", "is_active", "created_at")
    list_filter = ("job_type", "is_active", "location")
    search_fields = ("title", "description")
    inlines = [ApplicationInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "applied_at")
    list_filter = ("status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "message", "is_read", "created_at")
    list_filter = ("is_read",)