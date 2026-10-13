from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from clinic.models import (
    Appointment,
    AppointmentNotification,
    AuditEvent,
    Consultation,
    Department,
    MedicalHistoryEntry,
    Patient,
    StaffProfile,
)

User = get_user_model()


class ClinicModelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="General Practice")
        self.user = User.objects.create_user(username="clinician")
        self.clinician = StaffProfile.objects.create(
            account=self.user,
            role=StaffProfile.Role.CLINICIAN,
            staff_identifier="ST-100",
        )
        self.clinician.departments.add(self.department)
        self.patient = Patient.objects.create(full_name="Fictional Patient")

    def create_appointment(self, **overrides):
        starts_at = timezone.now() + timedelta(days=1)
        fields = {
            "patient": self.patient,
            "clinician": self.clinician,
            "appointment_at": starts_at,
            "ends_at": starts_at + timedelta(minutes=30),
        }
        fields.update(overrides)
        return Appointment.objects.create(**fields)

    def test_department_and_staff_profile_relationship(self):
        self.assertEqual(
            list(self.department.staff_members.all()),
            [self.clinician],
        )
        self.assertEqual(self.user.staff_profile, self.clinician)
        self.assertEqual(self.clinician.role, StaffProfile.Role.CLINICIAN)

    def test_staff_role_has_database_constraint(self):
        user = User.objects.create_user(username="invalid-role-staff")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StaffProfile.objects.create(account=user, role="unknown")

    def test_department_name_is_case_insensitively_unique_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Department.objects.create(name="general practice")

    def test_staff_account_cannot_be_deleted_while_profile_exists(self):
        with self.assertRaises(ProtectedError):
            self.user.delete()
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_patient_identifier_is_generated_and_not_primary_key(self):
        another_patient = Patient.objects.create(full_name="Another Fictional Patient")

        self.assertTrue(self.patient.patient_identifier.startswith("PT-"))
        self.assertNotEqual(self.patient.patient_identifier, str(self.patient.pk))
        self.assertNotEqual(
            self.patient.patient_identifier,
            another_patient.patient_identifier,
        )

    def test_patient_identifier_is_unique_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Patient.objects.create(
                    patient_identifier=self.patient.patient_identifier,
                    full_name="Duplicate Identifier Patient",
                )

    def test_patient_name_is_required_by_model_validation(self):
        patient = Patient(full_name="")

        with self.assertRaises(ValidationError):
            patient.full_clean()

    def test_patient_name_cannot_be_empty_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Patient.objects.create(full_name="")

    def test_patient_can_be_archived_without_removing_appointments(self):
        appointment = self.create_appointment()

        self.patient.is_archived = True
        self.patient.save()

        appointment.refresh_from_db()
        self.assertTrue(appointment.patient.is_archived)
        self.assertTrue(Appointment.objects.filter(pk=appointment.pk).exists())

    def test_appointment_relationships_and_default_status(self):
        appointment = self.create_appointment()

        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.clinician, self.clinician)
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)

    def test_appointment_status_has_database_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_appointment(status="not-a-valid-status")

    def test_appointment_end_must_be_after_start_in_database(self):
        starts_at = timezone.now() + timedelta(days=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_appointment(
                    appointment_at=starts_at,
                    ends_at=starts_at,
                )

    def test_appointment_patient_delete_is_protected(self):
        self.create_appointment()

        with self.assertRaises(ProtectedError):
            self.patient.delete()
        self.assertTrue(Patient.objects.filter(pk=self.patient.pk).exists())

    def test_multiple_consultations_can_reference_the_same_patient(self):
        consultation_one = Consultation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            symptoms="Fictional symptom one",
        )
        consultation_two = Consultation.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            symptoms="Fictional symptom two",
        )

        self.assertEqual(self.patient.consultations.count(), 2)
        self.assertNotEqual(consultation_one.pk, consultation_two.pk)

    def test_consultation_can_link_to_appointment(self):
        appointment = self.create_appointment()
        consultation = Consultation.objects.create(
            patient=self.patient,
            appointment=appointment,
            clinician=self.clinician,
        )

        self.assertEqual(consultation.appointment, appointment)
        self.assertEqual(appointment.consultations.get(), consultation)

    def test_consultation_validation_rejects_mismatched_patient(self):
        appointment = self.create_appointment()
        other_patient = Patient.objects.create(full_name="Other Fictional Patient")
        consultation = Consultation(
            patient=other_patient,
            appointment=appointment,
            clinician=self.clinician,
        )

        with self.assertRaises(ValidationError):
            consultation.full_clean()

    def test_medical_history_entry_is_linked_to_patient_and_author(self):
        entry = MedicalHistoryEntry.objects.create(
            patient=self.patient,
            author=self.clinician,
            entry_text="Fictional longitudinal history note.",
        )

        self.assertEqual(self.patient.medical_history_entries.get(), entry)
        self.assertEqual(self.clinician.medical_history_entries.get(), entry)

    def test_patient_delete_is_protected_by_clinical_history(self):
        MedicalHistoryEntry.objects.create(
            patient=self.patient,
            author=self.clinician,
            entry_text="Fictional history note.",
        )

        with self.assertRaises(ProtectedError):
            self.patient.delete()

    def test_notification_links_appointment_and_recipient(self):
        appointment = self.create_appointment()
        recipient = User.objects.create_user(username="receptionist")
        notification = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=recipient,
        )

        self.assertEqual(appointment.notifications.get(), notification)
        self.assertEqual(recipient.appointment_notifications.get(), notification)

    def test_notification_preserves_record_when_recipient_account_is_deleted(self):
        appointment = self.create_appointment()
        recipient = User.objects.create_user(username="temporary-recipient")
        notification = AppointmentNotification.objects.create(
            appointment=appointment,
            recipient=recipient,
        )

        recipient.delete()

        notification.refresh_from_db()
        self.assertIsNone(notification.recipient)
        self.assertTrue(AppointmentNotification.objects.filter(pk=notification.pk).exists())

    def test_audit_event_resolves_target_without_copying_target_content(self):
        content_type = ContentType.objects.get_for_model(Patient)
        event = AuditEvent.objects.create(
            actor=self.user,
            action="patient.record_viewed",
            content_type=content_type,
            object_id=str(self.patient.pk),
            metadata={"request_id": "fictional-request-id"},
        )

        self.assertEqual(event.content_object, self.patient)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.metadata, {"request_id": "fictional-request-id"})

    def test_audit_event_survives_deletion_of_unprofiled_actor(self):
        actor = User.objects.create_user(username="temporary-audit-actor")
        event = AuditEvent.objects.create(actor=actor, action="session.failed")

        actor.delete()

        event.refresh_from_db()
        self.assertIsNone(event.actor)
        self.assertTrue(AuditEvent.objects.filter(pk=event.pk).exists())
