from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinic.models import (
    Appointment,
    AuditEvent,
    Consultation,
    ConsultationRevision,
    Department,
    MedicalHistoryEntry,
    Patient,
    StaffProfile,
)

User = get_user_model()


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class ClinicalWorkflowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.admin = self.create_staff("clinical-admin", StaffProfile.Role.ADMINISTRATOR)
        self.receptionist = self.create_staff(
            "clinical-reception",
            StaffProfile.Role.RECEPTIONIST,
        )
        self.clinician = self.create_staff(
            "clinical-doctor",
            StaffProfile.Role.CLINICIAN,
        )
        self.other_clinician = self.create_staff(
            "clinical-other-doctor",
            StaffProfile.Role.CLINICIAN,
        )
        self.nurse = self.create_staff("clinical-nurse", StaffProfile.Role.NURSE)
        self.patient = Patient.objects.create(
            full_name="Fictional Clinical Patient",
        )
        self.other_patient = Patient.objects.create(
            full_name="Another Fictional Clinical Patient",
        )
        starts_at = timezone.now() - timedelta(hours=1)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            status=Appointment.Status.CONFIRMED,
        )
        self.other_appointment = Appointment.objects.create(
            patient=self.other_patient,
            clinician=self.other_clinician,
            appointment_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
        )

    def create_staff(self, username, role):
        account = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
        )
        profile = StaffProfile.objects.create(account=account, role=role)
        profile.departments.add(self.department)
        return profile

    def login_as(self, profile):
        self.client.force_login(profile.account)

    def history_url(self, patient=None):
        patient = patient or self.patient
        return reverse(
            "clinic_clinical:patient_history",
            args=[patient.patient_identifier],
        )

    def clinical_index_url(self):
        return reverse("clinic_clinical:patient_index")

    def consultation_form_url(self, patient=None):
        patient = patient or self.patient
        return reverse(
            "clinic_clinical:consultation_create",
            args=[patient.patient_identifier],
        )

    def consultation_data(self, **overrides):
        data = {
            "consultation_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "appointment": str(self.appointment.pk),
            "symptoms": "Fictional symptoms",
            "diagnosis": "Fictional diagnosis",
            "treatment": "Fictional care plan",
            "clinician_notes": "Fictional clinician note",
        }
        data.update(overrides)
        return data

    def create_consultation(self, **overrides):
        fields = {
            "patient": self.patient,
            "appointment": self.appointment,
            "clinician": self.clinician,
            "consultation_at": timezone.now(),
            "symptoms": "Fictional symptom",
        }
        fields.update(overrides)
        return Consultation.objects.create(**fields)

    def test_assigned_clinician_can_create_consultation_and_audit_metadata(self):
        self.login_as(self.clinician)

        response = self.client.post(
            self.consultation_form_url(),
            self.consultation_data(),
        )

        consultation = Consultation.objects.get()
        self.assertRedirects(
            response,
            reverse(
                "clinic_clinical:consultation_detail",
                args=[consultation.pk],
            ),
        )
        self.assertEqual(consultation.patient, self.patient)
        self.assertEqual(consultation.appointment, self.appointment)
        self.assertEqual(consultation.clinician, self.clinician)
        self.assertEqual(consultation.diagnosis, "Fictional diagnosis")
        event = AuditEvent.objects.get(
            action="consultation.created",
            object_id=str(consultation.pk),
        )
        self.assertEqual(event.actor, self.clinician.account)
        self.assertEqual(
            event.metadata,
            {
                "patient_identifier": self.patient.patient_identifier,
                "record_id": consultation.pk,
            },
        )

    def test_consultation_can_be_recorded_without_an_appointment(self):
        self.login_as(self.clinician)

        response = self.client.post(
            self.consultation_form_url(),
            self.consultation_data(appointment=""),
        )

        self.assertEqual(response.status_code, 302)
        consultation = Consultation.objects.get()
        self.assertIsNone(consultation.appointment)
        self.assertEqual(consultation.patient, self.patient)

    def test_consultation_amendment_preserves_previous_content_and_audits_changed_fields(self):
        consultation = self.create_consultation(
            symptoms="Original fictional symptoms",
            diagnosis="Original fictional diagnosis",
            treatment="Original fictional care plan",
            clinician_notes="Original fictional note",
        )
        self.login_as(self.clinician)
        response = self.client.post(
            reverse(
                "clinic_clinical:consultation_edit",
                args=[consultation.pk],
            ),
            {
                "consultation_at": timezone.localtime(
                    consultation.consultation_at,
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "appointment": str(self.appointment.pk),
                "symptoms": "Amended fictional symptoms",
                "diagnosis": "Original fictional diagnosis",
                "treatment": "Original fictional care plan",
                "clinician_notes": "Original fictional note",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "clinic_clinical:consultation_detail",
                args=[consultation.pk],
            ),
        )
        consultation.refresh_from_db()
        self.assertEqual(consultation.symptoms, "Amended fictional symptoms")
        revision = ConsultationRevision.objects.get(consultation=consultation)
        self.assertEqual(revision.revised_by, self.clinician)
        self.assertEqual(revision.previous_symptoms, "Original fictional symptoms")
        self.assertEqual(revision.previous_diagnosis, "Original fictional diagnosis")
        event = AuditEvent.objects.get(
            action="consultation.amended",
            object_id=str(consultation.pk),
        )
        self.assertEqual(event.actor, self.clinician.account)
        self.assertEqual(event.metadata["changed_fields"], ["symptoms"])
        self.assertNotIn("Original fictional symptoms", str(event.metadata))

        detail = self.client.get(
            reverse(
                "clinic_clinical:consultation_detail",
                args=[consultation.pk],
            )
        )
        self.assertContains(detail, "Amended fictional symptoms")
        self.assertContains(detail, "Original fictional symptoms")

    def test_unchanged_consultation_submission_does_not_create_revision(self):
        consultation = self.create_consultation(
            symptoms="Existing fictional symptoms",
        )
        self.login_as(self.clinician)
        response = self.client.post(
            reverse(
                "clinic_clinical:consultation_edit",
                args=[consultation.pk],
            ),
            {
                "consultation_at": timezone.localtime(
                    consultation.consultation_at,
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "appointment": str(self.appointment.pk),
                "symptoms": consultation.symptoms,
                "diagnosis": consultation.diagnosis,
                "treatment": consultation.treatment,
                "clinician_notes": consultation.clinician_notes,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ConsultationRevision.objects.exists())
        self.assertFalse(
            AuditEvent.objects.filter(
                action="consultation.amended",
                object_id=str(consultation.pk),
            ).exists()
        )

    def test_consultation_datetime_is_required(self):
        self.login_as(self.clinician)

        response = self.client.post(
            self.consultation_form_url(),
            self.consultation_data(consultation_at=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("consultation_at", response.context["form"].errors)
        self.assertFalse(Consultation.objects.exists())

    def test_consultation_creation_rejects_non_form_http_methods(self):
        self.login_as(self.clinician)

        response = self.client.put(
            self.consultation_form_url(),
            self.consultation_data(),
        )

        self.assertEqual(response.status_code, 405)
        self.assertFalse(Consultation.objects.exists())

    def test_unrelated_appointment_is_not_a_valid_consultation_choice(self):
        self.login_as(self.clinician)

        response = self.client.post(
            self.consultation_form_url(),
            self.consultation_data(appointment=str(self.other_appointment.pk)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("appointment", response.context["form"].errors)
        self.assertFalse(Consultation.objects.exists())

    def test_archived_patient_cannot_receive_new_consultations(self):
        self.patient.is_archived = True
        self.patient.save(update_fields=("is_archived", "updated_at"))
        self.login_as(self.clinician)

        response = self.client.get(self.consultation_form_url())

        self.assertRedirects(response, self.history_url())
        self.assertFalse(Consultation.objects.exists())

    def test_patient_history_returns_only_assigned_patient_records_in_reverse_chronology(self):
        older = self.create_consultation(
            consultation_at=timezone.now() - timedelta(days=2),
        )
        newer = self.create_consultation(
            consultation_at=timezone.now() - timedelta(days=1),
            symptoms="Newer fictional symptoms",
        )
        unrelated = self.create_consultation(
            patient=self.other_patient,
            appointment=self.other_appointment,
            clinician=self.other_clinician,
        )
        MedicalHistoryEntry.objects.create(
            patient=self.patient,
            author=self.clinician,
            entry_text="Fictional longitudinal note.",
        )
        self.login_as(self.clinician)

        response = self.client.get(self.history_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["consultations"]),
            [newer, older],
        )
        self.assertEqual(
            [entry.patient_id for entry in response.context["history_entries"]],
            [self.patient.pk],
        )
        self.assertContains(response, "Fictional longitudinal note.")
        self.assertNotContains(response, "Another Fictional Clinical Patient")
        self.assertNotIn(unrelated.pk, [item.pk for item in response.context["consultations"]])

    def test_empty_history_has_an_explicit_empty_state(self):
        self.login_as(self.clinician)

        response = self.client.get(self.history_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No consultations have been recorded")
        self.assertContains(response, "No separate medical history entries")

    def test_clinician_can_add_append_only_medical_history_entry(self):
        self.login_as(self.clinician)

        response = self.client.post(
            reverse(
                "clinic_clinical:medical_history_entry_create",
                args=[self.patient.patient_identifier],
            ),
            {
                "entry_text": "Fictional history entry.",
                "effective_date": "",
            },
        )

        self.assertRedirects(response, self.history_url())
        entry = MedicalHistoryEntry.objects.get()
        self.assertEqual(entry.patient, self.patient)
        self.assertEqual(entry.author, self.clinician)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="medical_history.created",
                actor=self.clinician.account,
                object_id=str(entry.pk),
            ).exists()
        )

    def test_medical_history_entry_requires_text(self):
        self.login_as(self.clinician)
        response = self.client.post(
            reverse(
                "clinic_clinical:medical_history_entry_create",
                args=[self.patient.patient_identifier],
            ),
            {"entry_text": "", "effective_date": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("entry_text", response.context["form"].errors)
        self.assertFalse(MedicalHistoryEntry.objects.exists())

    def test_history_and_consultation_detail_are_limited_to_clinical_role_and_scope(self):
        consultation = self.create_consultation()
        detail_url = reverse(
            "clinic_clinical:consultation_detail",
            args=[consultation.pk],
        )

        for profile in (self.admin, self.receptionist, self.nurse):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                self.assertEqual(self.client.get(self.history_url()).status_code, 403)
                self.assertEqual(self.client.get(detail_url).status_code, 403)
                self.assertEqual(
                    self.client.get(
                        reverse(
                            "clinic_clinical:consultation_edit",
                            args=[consultation.pk],
                        )
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(self.consultation_form_url()).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(self.clinical_index_url()).status_code,
                    403,
                )

        self.login_as(self.other_clinician)
        self.assertEqual(self.client.get(self.clinical_index_url()).status_code, 200)
        self.assertNotContains(
            self.client.get(self.clinical_index_url()),
            f"<h3>{self.patient.full_name}</h3>",
        )
        self.assertEqual(self.client.get(self.history_url()).status_code, 404)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse(
                    "clinic_clinical:consultation_edit",
                    args=[consultation.pk],
                )
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.consultation_form_url()).status_code,
            404,
        )

    def test_clinical_navigation_and_dashboard_action_are_clinician_only(self):
        clinical_index_url = self.clinical_index_url()
        for profile in (self.clinician,):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                response = self.client.get(reverse("clinic_auth:staff_home"))
                self.assertContains(response, f'href="{clinical_index_url}"')
                self.assertContains(response, "Clinical Records")
                nav = response.content.decode().split(
                    '<nav class="app-nav"',
                    1,
                )[1].split("</nav>", 1)[0]
                self.assertIn(clinical_index_url, nav)
                self.assertNotIn(
                    reverse("clinic_auth:password_change"),
                    nav,
                )
                self.assertEqual(
                    self.client.get(reverse("clinic_auth:settings")).status_code,
                    200,
                )

        for profile in (self.admin, self.receptionist, self.nurse):
            with self.subTest(role=profile.role):
                self.login_as(profile)
                response = self.client.get(reverse("clinic_auth:staff_home"))
                self.assertNotContains(response, clinical_index_url)
                self.assertNotContains(response, "Clinical Records")

    def test_clinical_index_lists_only_care_scope_and_links_to_existing_workflows(self):
        self.login_as(self.clinician)

        response = self.client.get(self.clinical_index_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.full_name)
        self.assertNotContains(
            response,
            f"<h3>{self.other_patient.full_name}</h3>",
        )
        self.assertContains(response, self.history_url())
        self.assertContains(response, self.consultation_form_url())
        self.assertEqual(self.client.get(self.history_url()).status_code, 200)
        self.assertEqual(
            self.client.get(self.consultation_form_url()).status_code,
            200,
        )

    def test_cancelled_appointment_only_does_not_show_history_link(self):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=("status", "updated_at"))
        self.login_as(self.clinician)

        response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.history_url())
        self.assertNotContains(response, "Patient medical history")
        self.assertNotContains(response, "Record consultation")
        self.assertEqual(self.client.get(self.history_url()).status_code, 404)

    def test_other_qualifying_appointment_preserves_history_link_for_cancelled_detail(self):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=("status", "updated_at"))
        later_start = self.appointment.appointment_at + timedelta(days=1)
        Appointment.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            appointment_at=later_start,
            ends_at=later_start + timedelta(minutes=30),
            status=Appointment.Status.CONFIRMED,
        )
        self.login_as(self.clinician)

        response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )

        self.assertContains(response, self.history_url())
        self.assertEqual(self.client.get(self.history_url()).status_code, 200)

    def test_authored_clinical_record_preserves_history_link_for_cancelled_detail(self):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=("status", "updated_at"))
        self.create_consultation()
        self.login_as(self.clinician)

        response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )

        self.assertContains(response, self.history_url())
        self.assertEqual(self.client.get(self.history_url()).status_code, 200)

    def test_unauthenticated_and_missing_records_are_handled_safely(self):
        self.assertEqual(self.client.get(self.history_url()).status_code, 302)

        self.login_as(self.clinician)
        self.assertEqual(
            self.client.get(
                reverse(
                    "clinic_clinical:patient_history",
                    args=["PT-NOT-A-REAL-ID"],
                )
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("clinic_clinical:consultation_detail", args=[999999])
            ).status_code,
            404,
        )

    def test_consultation_detail_is_visible_to_clinician_with_care_scope(self):
        consultation = self.create_consultation()
        self.login_as(self.clinician)

        response = self.client.get(
            reverse(
                "clinic_clinical:consultation_detail",
                args=[consultation.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fictional symptom")

    def test_assigned_clinician_can_open_existing_consultation_details(self):
        consultation = self.create_consultation()
        Appointment.objects.create(
            patient=self.patient,
            clinician=self.other_clinician,
            appointment_at=self.appointment.appointment_at + timedelta(days=1),
            ends_at=self.appointment.ends_at + timedelta(days=1),
        )
        self.login_as(self.other_clinician)

        response = self.client.get(
            reverse(
                "clinic_clinical:consultation_detail",
                args=[consultation.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fictional symptom")

    def test_consultation_creation_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.clinician.account)
        url = self.consultation_form_url()
        response = client.get(url)
        csrf_token = response.cookies["csrftoken"].value

        rejected = client.post(url, self.consultation_data())
        self.assertEqual(rejected.status_code, 403)
        self.assertFalse(Consultation.objects.exists())

        accepted = client.post(
            url,
            self.consultation_data(),
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(Consultation.objects.count(), 1)

    def test_appointment_detail_links_to_clinical_workflow_for_assigned_clinician(self):
        self.login_as(self.clinician)

        response = self.client.get(
            reverse(
                "clinic_appointments:appointment_detail",
                args=[self.appointment.pk],
            )
        )

        self.assertContains(
            response,
            reverse(
                "clinic_clinical:patient_history",
                args=[self.patient.patient_identifier],
            ),
        )
        self.assertContains(
            response,
            f'{reverse("clinic_clinical:consultation_create", args=[self.patient.patient_identifier])}?appointment={self.appointment.pk}',
        )
        create_response = self.client.get(
            reverse(
                "clinic_clinical:consultation_create",
                args=[self.patient.patient_identifier],
            ),
            {"appointment": self.appointment.pk},
        )
        self.assertEqual(
            create_response.context["form"]["appointment"].value(),
            str(self.appointment.pk),
        )
