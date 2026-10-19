from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from clinic.authentication import roles_required
from clinic.clinical_access import patients_in_clinician_care
from clinic.clinical_forms import ConsultationForm, MedicalHistoryEntryForm
from clinic.models import (
    AuditEvent,
    Consultation,
    ConsultationRevision,
    MedicalHistoryEntry,
    StaffProfile,
)


def _get_patient_in_clinician_care(request, patient_identifier):
    return get_object_or_404(
        patients_in_clinician_care(request.user.staff_profile),
        patient_identifier=patient_identifier,
    )


def _record_clinical_event(actor, action, instance, patient, **metadata):
    event_metadata = {
        "patient_identifier": patient.patient_identifier,
        "record_id": instance.pk,
        **metadata,
    }
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        content_object=instance,
        metadata=event_metadata,
    )


@roles_required(StaffProfile.Role.CLINICIAN)
def patient_index(request):
    patients = patients_in_clinician_care(request.user.staff_profile).order_by(
        "full_name",
        "patient_identifier",
    )
    return render(
        request,
        "clinic/clinical/patient_index.html",
        {"patients": patients},
    )


@roles_required(StaffProfile.Role.CLINICIAN)
def patient_history(request, patient_identifier):
    patient = _get_patient_in_clinician_care(request, patient_identifier)
    consultations = (
        Consultation.objects.filter(patient=patient)
        .select_related("clinician__account", "appointment")
        .order_by("-consultation_at", "-pk")
    )
    history_entries = (
        MedicalHistoryEntry.objects.filter(patient=patient)
        .select_related("author__account")
        .order_by("-recorded_at", "-pk")
    )
    return render(
        request,
        "clinic/clinical/patient_history.html",
        {
            "patient": patient,
            "consultations": consultations,
            "history_entries": history_entries,
        },
    )


@roles_required(StaffProfile.Role.CLINICIAN)
@require_http_methods(["GET", "POST"])
def consultation_create(request, patient_identifier):
    patient = _get_patient_in_clinician_care(request, patient_identifier)
    if patient.is_archived:
        messages.error(request, "A consultation cannot be added to an archived patient.")
        return redirect(
            "clinic_clinical:patient_history",
            patient_identifier=patient.patient_identifier,
        )

    clinician = request.user.staff_profile
    initial = {}
    appointment_id = request.GET.get("appointment")
    if request.method == "GET" and appointment_id:
        initial["appointment"] = appointment_id
    form = ConsultationForm(
        request.POST or None,
        patient=patient,
        clinician=clinician,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            consultation = form.save(commit=False)
            consultation.save()
            _record_clinical_event(
                request.user,
                "consultation.created",
                consultation,
                patient,
            )
        messages.success(request, "Consultation recorded.")
        return redirect(
            "clinic_clinical:consultation_detail",
            consultation_id=consultation.pk,
        )

    return render(
        request,
        "clinic/clinical/consultation_form.html",
        {"patient": patient, "form": form},
    )


@roles_required(StaffProfile.Role.CLINICIAN)
def consultation_detail(request, consultation_id):
    consultation = get_object_or_404(
        Consultation.objects.select_related(
            "patient",
            "appointment",
            "clinician__account",
        ).prefetch_related(
            "revisions__revised_by__account",
            "revisions__previous_appointment",
        ),
        pk=consultation_id,
        patient__in=patients_in_clinician_care(request.user.staff_profile),
    )
    return render(
        request,
        "clinic/clinical/consultation_detail.html",
        {"consultation": consultation},
    )


@roles_required(StaffProfile.Role.CLINICIAN)
@require_http_methods(["GET", "POST"])
def consultation_edit(request, consultation_id):
    consultation = get_object_or_404(
        Consultation.objects.select_related("patient", "appointment"),
        pk=consultation_id,
        clinician=request.user.staff_profile,
        patient__in=patients_in_clinician_care(request.user.staff_profile),
    )
    clinician = request.user.staff_profile
    if request.method == "POST":
        with transaction.atomic():
            consultation = get_object_or_404(
                Consultation.objects.select_for_update().select_related(
                    "patient",
                    "appointment",
                ),
                pk=consultation_id,
                clinician=clinician,
                patient__in=patients_in_clinician_care(clinician),
            )
            previous_values = {
                "consultation_at": consultation.consultation_at,
                "appointment": consultation.appointment_id,
                "symptoms": consultation.symptoms,
                "diagnosis": consultation.diagnosis,
                "treatment": consultation.treatment,
                "clinician_notes": consultation.clinician_notes,
            }
            previous_appointment = consultation.appointment
            form = ConsultationForm(
                request.POST,
                patient=consultation.patient,
                clinician=clinician,
                instance=consultation,
            )
            if form.is_valid():
                changed_fields = []
                for field in (
                    "consultation_at",
                    "appointment",
                    "symptoms",
                    "diagnosis",
                    "treatment",
                    "clinician_notes",
                ):
                    submitted_value = form.cleaned_data[field]
                    current_value = previous_values[field]
                    if field == "appointment":
                        submitted_value = (
                            submitted_value.pk if submitted_value else None
                        )
                    elif field == "consultation_at":
                        submitted_value = submitted_value.replace(microsecond=0)
                        current_value = current_value.replace(microsecond=0)
                    if submitted_value != current_value:
                        changed_fields.append(field)
                if changed_fields:
                    ConsultationRevision.objects.create(
                        consultation=consultation,
                        revised_by=clinician,
                        previous_appointment=previous_appointment,
                        previous_consultation_at=previous_values["consultation_at"],
                        previous_symptoms=previous_values["symptoms"],
                        previous_diagnosis=previous_values["diagnosis"],
                        previous_treatment=previous_values["treatment"],
                        previous_clinician_notes=previous_values["clinician_notes"],
                    )
                    updated_consultation = form.save(commit=False)
                    updated_consultation.save()
                    _record_clinical_event(
                        request.user,
                        "consultation.amended",
                        updated_consultation,
                        consultation.patient,
                        changed_fields=changed_fields,
                    )
        if form.is_valid():
            if changed_fields:
                messages.success(
                    request,
                    "Consultation amended; the prior version was preserved.",
                )
            else:
                messages.info(request, "No consultation changes were submitted.")
            return redirect(
                "clinic_clinical:consultation_detail",
                consultation_id=consultation.pk,
            )
    else:
        form = ConsultationForm(
            patient=consultation.patient,
            clinician=clinician,
            instance=consultation,
        )

    return render(
        request,
        "clinic/clinical/consultation_form.html",
        {
            "patient": consultation.patient,
            "form": form,
            "page_title": "Edit consultation",
            "submit_label": "Save amendment",
        },
    )


@roles_required(StaffProfile.Role.CLINICIAN)
@require_http_methods(["GET", "POST"])
def medical_history_entry_create(request, patient_identifier):
    patient = _get_patient_in_clinician_care(request, patient_identifier)
    if patient.is_archived:
        messages.error(request, "A history entry cannot be added to an archived patient.")
        return redirect(
            "clinic_clinical:patient_history",
            patient_identifier=patient.patient_identifier,
        )

    form = MedicalHistoryEntryForm(
        request.POST or None,
        patient=patient,
        author=request.user.staff_profile,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            entry = form.save(commit=False)
            entry.save()
            _record_clinical_event(
                request.user,
                "medical_history.created",
                entry,
                patient,
            )
        messages.success(request, "Medical history entry recorded.")
        return redirect(
            "clinic_clinical:patient_history",
            patient_identifier=patient.patient_identifier,
        )

    return render(
        request,
        "clinic/clinical/medical_history_entry_form.html",
        {"patient": patient, "form": form},
    )
