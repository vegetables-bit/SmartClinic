from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clinic.authentication import roles_required
from clinic.models import Patient, StaffProfile
from clinic.patient_forms import (
    PatientForm,
    PatientIdentifierGenerationError,
    PatientSearchForm,
    save_patient_with_generated_identifier,
)

PATIENT_MANAGEMENT_ROLES = (
    StaffProfile.Role.ADMINISTRATOR,
    StaffProfile.Role.RECEPTIONIST,
)
PATIENTS_PER_PAGE = 25


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_list(request):
    search_form = PatientSearchForm(request.GET)
    if not search_form.is_valid():
        return render(
            request,
            "clinic/patients/patient_list.html",
            {
                "search_form": search_form,
                "patients": Paginator(Patient.objects.none(), PATIENTS_PER_PAGE).page(1),
            },
            status=400,
        )

    cleaned = search_form.cleaned_data
    patients = Patient.objects.all()
    if cleaned["status"] == "active":
        patients = patients.filter(is_archived=False)
    elif cleaned["status"] == "archived":
        patients = patients.filter(is_archived=True)

    query = cleaned["query"]
    if query:
        patients = patients.filter(
            Q(patient_identifier__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone_number__icontains=query)
        )

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
        {"search_form": search_form, "patients": page},
    )


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_create(request):
    form = PatientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            patient = save_patient_with_generated_identifier(form)
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


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_profile(request, patient_identifier):
    patient = get_object_or_404(
        Patient.objects,
        patient_identifier=patient_identifier,
    )
    return render(
        request,
        "clinic/patients/patient_profile.html",
        {"patient": patient},
    )


@roles_required(*PATIENT_MANAGEMENT_ROLES)
def patient_edit(request, patient_identifier):
    patient = get_object_or_404(
        Patient.objects,
        patient_identifier=patient_identifier,
    )
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
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
        patient.is_archived = True
        patient.save(update_fields=("is_archived", "updated_at"))
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
        patient.is_archived = False
        patient.save(update_fields=("is_archived", "updated_at"))
        messages.success(request, "Patient record restored.")
    else:
        messages.info(request, "Patient record is already active.")
    return redirect(
        "clinic_patients:patient_profile",
        patient_identifier=patient.patient_identifier,
    )
