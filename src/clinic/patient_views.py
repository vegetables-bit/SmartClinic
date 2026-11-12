from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from clinic.authentication import roles_required
from clinic.audit import record_audit_event
from clinic.models import Patient, StaffProfile
from clinic.patient_forms import (
    PatientForm,
    PatientIdentifierGenerationError,
    PatientSearchForm,
    save_patient_with_generated_identifier,
)
from clinic.navigation import safe_return_url

PATIENT_READ_ROLES = (
    StaffProfile.Role.ADMINISTRATOR,
    StaffProfile.Role.RECEPTIONIST,
    StaffProfile.Role.NURSE,
)
PATIENT_MANAGEMENT_ROLES = (
    StaffProfile.Role.ADMINISTRATOR,
    StaffProfile.Role.RECEPTIONIST,
)
PATIENTS_PER_PAGE = 25


@roles_required(*PATIENT_READ_ROLES)
def patient_list(request):
    role = request.user.staff_profile.role
    can_manage_demographics = role in PATIENT_MANAGEMENT_ROLES
    search_form = PatientSearchForm(
        request.GET,
        can_view_archived=role != StaffProfile.Role.NURSE,
    )
    if not search_form.is_valid():
        return render(
            request,
            "clinic/patients/patient_list.html",
            {
                "search_form": search_form,
                "patients": Paginator(Patient.objects.none(), PATIENTS_PER_PAGE).page(1),
                "can_manage_demographics": can_manage_demographics,
            },
            status=400,
        )

    cleaned = search_form.cleaned_data
    patients = Patient.objects.all()
    if role == StaffProfile.Role.NURSE or cleaned["status"] == "active":
        patients = patients.filter(is_archived=False)
    elif cleaned["status"] == "archived":
        patients = patients.filter(is_archived=True)

    query = cleaned["query"]
    if query:
        search_filter = (
            Q(patient_identifier__icontains=query)
            | Q(full_name__icontains=query)
        )
        if can_manage_demographics:
            search_filter |= Q(phone_number__icontains=query)
        patients = patients.filter(search_filter)

    page = Paginator(
        patients.only(
            "patient_identifier",
            "full_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "is_archived",
        ),
        PATIENTS_PER_PAGE,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "clinic/patients/patient_list.html",
        {
            "search_form": search_form,
            "patients": page,
            "can_manage_demographics": can_manage_demographics,
            "can_view_contact_details": can_manage_demographics,
        },
    )


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_create(request):
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                patient = save_patient_with_generated_identifier(form)
                record_audit_event(
                    actor=request.user,
                    action="patient.created",
                    target=patient,
                    metadata={
                        "patient_identifier": patient.patient_identifier,
                        "record_id": patient.pk,
                    },
                )
        except PatientIdentifierGenerationError:
            form.add_error(
                None,
                "A unique patient identifier could not be generated. Please try again.",
            )
            return render(
                request,
                "clinic/patients/patient_form.html",
                {"form": form, "page_title": "Register patient"},
                status=503,
            )

        messages.success(request, "Patient record created.")
        return redirect(
            "clinic_patients:patient_profile",
            patient_identifier=patient.patient_identifier,
        )

    return render(
        request,
        "clinic/patients/patient_form.html",
        {"form": form, "page_title": "Register patient"},
    )


@roles_required(*PATIENT_READ_ROLES)
def patient_profile(request, patient_identifier):
    role = request.user.staff_profile.role
    patients = Patient.objects
    if role == StaffProfile.Role.NURSE:
        patients = patients.filter(is_archived=False)
    patient = get_object_or_404(patients, patient_identifier=patient_identifier)
    return_url = safe_return_url(
        request,
        "return_to",
        {reverse("clinic_patients:patient_list")},
    )
    return render(
        request,
        "clinic/patients/patient_profile.html",
        {
            "patient": patient,
            "return_url": return_url,
            "can_manage_demographics": role in PATIENT_MANAGEMENT_ROLES,
            "can_view_contact_details": role in PATIENT_MANAGEMENT_ROLES,
        },
    )


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_edit(request, patient_identifier):
    patient = get_object_or_404(
        Patient.objects,
        patient_identifier=patient_identifier,
    )
    original_values = {
        field: getattr(patient, field)
        for field in PatientForm.Meta.fields
    }
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == "POST" and form.is_valid():
        changed_fields = [
            field
            for field in PatientForm.Meta.fields
            if form.cleaned_data[field] != original_values[field]
        ]
        try:
            with transaction.atomic():
                form.save()
                if changed_fields:
                    record_audit_event(
                        actor=request.user,
                        action="patient.demographics_updated",
                        target=patient,
                        metadata={
                            "patient_identifier": patient.patient_identifier,
                            "record_id": patient.pk,
                            "changed_fields": changed_fields,
                        },
                    )
        except ValidationError:
            form.add_error(
                None,
                "The patient details could not be saved. Check the submitted values.",
            )
        else:
            messages.success(request, "Patient details updated.")
            return redirect(
                "clinic_patients:patient_profile",
                patient_identifier=patient.patient_identifier,
            )

    return render(
        request,
        "clinic/patients/patient_form.html",
        {"form": form, "page_title": "Edit patient", "patient": patient},
    )


@require_POST
@roles_required(StaffProfile.Role.ADMINISTRATOR)
def patient_archive(request, patient_identifier):
    patient = get_object_or_404(
        Patient.objects,
        patient_identifier=patient_identifier,
    )
    if not patient.is_archived:
        with transaction.atomic():
            patient.is_archived = True
            patient.save(update_fields=("is_archived", "updated_at"))
            record_audit_event(
                actor=request.user,
                action="patient.archived",
                target=patient,
                metadata={
                    "patient_identifier": patient.patient_identifier,
                    "record_id": patient.pk,
                    "previous_is_archived": False,
                    "is_archived": True,
                },
            )
        messages.success(request, "Patient record archived.")
    else:
        messages.info(request, "Patient record is already archived.")
    return redirect(
        "clinic_patients:patient_profile",
        patient_identifier=patient.patient_identifier,
    )


@require_POST
@roles_required(StaffProfile.Role.ADMINISTRATOR)
def patient_restore(request, patient_identifier):
    patient = get_object_or_404(
        Patient.objects,
        patient_identifier=patient_identifier,
    )
    if patient.is_archived:
        with transaction.atomic():
            patient.is_archived = False
            patient.save(update_fields=("is_archived", "updated_at"))
            record_audit_event(
                actor=request.user,
                action="patient.restored",
                target=patient,
                metadata={
                    "patient_identifier": patient.patient_identifier,
                    "record_id": patient.pk,
                    "previous_is_archived": True,
                    "is_archived": False,
                },
            )
        messages.success(request, "Patient record restored.")
    else:
        messages.info(request, "Patient record is already active.")
    return redirect(
        "clinic_patients:patient_profile",
        patient_identifier=patient.patient_identifier,
    )
