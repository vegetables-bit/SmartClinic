from django.db.models import Q

from clinic.models import Appointment, Patient


def patients_in_clinician_care(clinician):
    care_appointment_statuses = tuple(
        status
        for status, _ in Appointment.Status.choices
        if status != Appointment.Status.CANCELLED
    )
    return Patient.objects.filter(
        Q(
            appointments__clinician=clinician,
            appointments__status__in=care_appointment_statuses,
        )
        | Q(consultations__clinician=clinician)
        | Q(medical_history_entries__author=clinician)
    ).distinct()


def clinician_has_patient_care_scope(clinician, patient):
    return patients_in_clinician_care(clinician).filter(pk=patient.pk).exists()
