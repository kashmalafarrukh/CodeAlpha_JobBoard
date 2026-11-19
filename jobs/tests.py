import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import (Application, CandidateProfile, EmployerProfile, Job,
                     Notification)

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class JobBoardTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.boss = User.objects.create_user("boss", password="Pass12345!")
        EmployerProfile.objects.create(user=self.boss, company_name="Acme")
        self.rival = User.objects.create_user("rival", password="Pass12345!")
        EmployerProfile.objects.create(user=self.rival, company_name="Rival Co")
        self.ali = User.objects.create_user("ali", password="Pass12345!")
        CandidateProfile.objects.create(user=self.ali)
        self.sara = User.objects.create_user("sara", password="Pass12345!")
        CandidateProfile.objects.create(user=self.sara)

        self.job = Job.objects.create(
            employer=self.boss.employer_profile, title="Python Developer",
            description="Build APIs", location="Lahore",
            job_type=Job.FULL_TIME, salary_min=100, salary_max=200)

    # ----- helpers -----
    def login(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def upload_resume(self, user, name="cv.pdf"):
        self.login(user)
        file = SimpleUploadedFile(name, b"resume text")
        return self.client.patch("/api/candidate/profile/", {"resume": file},
                                 format="multipart")

    def apply(self, user, job=None):
        job = job or self.job
        self.upload_resume(user)
        return self.client.post(f"/api/jobs/{job.id}/apply/",
                                {"cover_letter": "Hire me"})

    # ----- signup -----
    def test_employer_signup_needs_company_name(self):
        response = self.client.post("/api/auth/signup/", {
            "username": "newboss", "password": "StrongPass123",
            "role": "employer"})
        self.assertEqual(response.status_code, 400)

    def test_candidate_signup_creates_profile(self):
        response = self.client.post("/api/auth/signup/", {
            "username": "newguy", "password": "StrongPass123",
            "role": "candidate"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(CandidateProfile.objects.filter(
            user__username="newguy").exists())

    # ----- jobs -----
    def test_job_list_is_public_and_hides_inactive(self):
        Job.objects.create(employer=self.boss.employer_profile, title="Old",
                           description="x", location="Lahore", is_active=False)
        response = self.client.get("/api/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_candidate_cannot_post_job(self):
        self.login(self.ali)
        response = self.client.post("/api/jobs/", {
            "title": "X", "description": "Y", "location": "Z"})
        self.assertEqual(response.status_code, 403)

    def test_employer_can_post_job(self):
        self.login(self.boss)
        response = self.client.post("/api/jobs/", {
            "title": "Designer", "description": "Design things",
            "location": "Karachi", "job_type": "contract"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["company"], "Acme")

    def test_salary_range_is_validated(self):
        self.login(self.boss)
        response = self.client.post("/api/jobs/", {
            "title": "Designer", "description": "Design things",
            "location": "Karachi", "salary_min": 500, "salary_max": 100})
        self.assertEqual(response.status_code, 400)

    def test_other_employer_cannot_edit_job(self):
        self.login(self.rival)
        response = self.client.patch(f"/api/jobs/{self.job.id}/",
                                     {"title": "Hacked"})
        self.assertEqual(response.status_code, 404)

    def test_search_and_filters(self):
        Job.objects.create(employer=self.rival.employer_profile,
                           title="Chef", description="Cook food",
                           location="Islamabad", job_type=Job.PART_TIME,
                           salary_max=50)
        by_search = self.client.get("/api/jobs/?search=python")
        self.assertEqual(len(by_search.data["results"]), 1)
        by_location = self.client.get("/api/jobs/?location=islamabad")
        self.assertEqual(by_location.data["results"][0]["title"], "Chef")
        by_type = self.client.get("/api/jobs/?job_type=part_time")
        self.assertEqual(len(by_type.data["results"]), 1)
        by_company = self.client.get("/api/jobs/?company=acme")
        self.assertEqual(by_company.data["results"][0]["title"],
                         "Python Developer")
        by_salary = self.client.get("/api/jobs/?min_salary=150")
        self.assertEqual(len(by_salary.data["results"]), 1)

    # ----- resume upload and applying -----
    def test_cannot_apply_without_resume(self):
        self.login(self.ali)
        response = self.client.post(f"/api/jobs/{self.job.id}/apply/")
        self.assertEqual(response.status_code, 400)

    def test_wrong_resume_type_is_rejected(self):
        response = self.upload_resume(self.ali, name="virus.exe")
        self.assertEqual(response.status_code, 400)

    def test_candidate_can_apply_and_employer_is_notified(self):
        response = self.apply(self.ali)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "applied")
        self.assertTrue(Notification.objects.filter(
            recipient=self.boss).exists())

    def test_duplicate_application_is_rejected(self):
        self.apply(self.ali)
        response = self.apply(self.ali)
        self.assertEqual(response.status_code, 409)

    def test_employer_cannot_apply(self):
        self.login(self.boss)
        response = self.client.post(f"/api/jobs/{self.job.id}/apply/")
        self.assertEqual(response.status_code, 403)

    # ----- tracking and status updates -----
    def test_employer_updates_status_and_candidate_is_notified(self):
        application_id = self.apply(self.ali).data["id"]
        self.login(self.boss)
        response = self.client.patch(
            f"/api/applications/{application_id}/status/",
            {"status": "shortlisted"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.get(pk=application_id).status,
                         "shortlisted")
        self.assertTrue(Notification.objects.filter(
            recipient=self.ali).exists())

    def test_other_employer_cannot_update_status(self):
        application_id = self.apply(self.ali).data["id"]
        self.login(self.rival)
        response = self.client.patch(
            f"/api/applications/{application_id}/status/",
            {"status": "hired"})
        self.assertEqual(response.status_code, 404)

    def test_candidate_cannot_update_status(self):
        application_id = self.apply(self.ali).data["id"]
        self.login(self.ali)
        response = self.client.patch(
            f"/api/applications/{application_id}/status/",
            {"status": "hired"})
        self.assertEqual(response.status_code, 403)

    def test_my_applications_shows_only_my_own(self):
        self.apply(self.ali)
        self.login(self.sara)
        response = self.client.get("/api/applications/")
        self.assertEqual(len(response.data["results"]), 0)

    # ----- reporting -----
    def test_employer_stats(self):
        self.apply(self.ali)
        self.login(self.boss)
        response = self.client.get("/api/employer/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["jobs_posted"], 1)
        self.assertEqual(response.data["total_applications"], 1)
        self.assertEqual(response.data["by_status"]["applied"], 1)