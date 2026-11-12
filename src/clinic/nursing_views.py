import logging

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from clinic.authentication import roles_required
from clinic.audit import record_audit_event
from clinic.clinical_forms import NursingObservationForm
from clinic.models import Appointment, NursingObservation, StaffProfile

logger = logging.getLogger(__name__)


@roles_required(StaffProfile.Role.NURSE)
@require_http_methods(["GET", "POST"])
def nursing_observation_create(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "clinician__account"),
        pk=appointment_id,
    )
    nurse = request.user.staff_profile
    form = NursingObservationForm(
        request.POST or None,
        appointment=appointment,
        recorded_by=nurse,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                observation = form.save(commit=False)
                observation.appointment = appointment
                observation.recorded_by = nurse
                observation.full_clean()
                observation.save()
                record_audit_event(
                    actor=request.user,
                    action="nursing_observation.created",
                    target=observation,
                    metadata={
                        "patient_identifier": appointment.patient.patient_identifier,
                        "record_id": observation.pk,
                    },
                )
        except DatabaseError:
            logger.error("Persistence failed for nursing_observation.created.")
            form.add_error(
                None,
                "The observation could not be saved. Please try again.",
            )
            return render(
                request,
                "clinic/nursing/nursing_observation_form.html",
                {"form": form, "appointment": appointment},
                status=503,
            )

        messages.success(request, "Nursing observation recorded.")
        return redirect(
            "clinic_appointments:appointment_detail",
            appointment_id=appointment.pk,
        )

    return render(
        request,
        "clinic/nursing/nursing_observation_form.html",
        {"form": form, "appointment": appointment},
    )


def observations_for_appointment(appointment):
    return (
        NursingObservation.objects.filter(appointment=appointment)
        .select_related("recorded_by__account")
        .order_by("-observed_at", "-pk")
    )
