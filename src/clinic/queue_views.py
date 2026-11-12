from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinic.audit import record_audit_event
from clinic.authentication import roles_required
from clinic.models import Appointment, QueueEntry, StaffProfile

ALL_QUEUE_ROLES = tuple(StaffProfile.Role.values)
FRONT_DESK_ROLES = {
    StaffProfile.Role.ADMINISTRATOR,
    StaffProfile.Role.RECEPTIONIST,
    StaffProfile.Role.NURSE,
}


def _appointments_for_user(user):
    appointments = Appointment.objects.select_related(
        "patient", "clinician__account", "queue_entry"
    ).filter(
        appointment_at__date=timezone.localdate(),
        status__in=(
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
            Appointment.Status.ATTENDED,
            Appointment.Status.COMPLETED,
        ),
    )
    if user.staff_profile.role == StaffProfile.Role.CLINICIAN:
        appointments = appointments.filter(clinician=user.staff_profile)
    return appointments.order_by(
        F("queue_entry__checked_in_at").asc(nulls_last=True),
        "appointment_at",
        "pk",
    )


@roles_required(*ALL_QUEUE_ROLES)
def queue_board(request):
    return render(
        request,
        "clinic/queue/queue_board.html",
        {
            "appointments": _appointments_for_user(request.user),
            "can_check_in": request.user.staff_profile.role in FRONT_DESK_ROLES,
            "today": timezone.localdate(),
        },
    )


def _audit_transition(entry, actor, previous_status):
    record_audit_event(
        actor=actor,
        action="queue.status_changed",
        target=entry,
        metadata={
            "appointment_identifier": entry.appointment.appointment_identifier,
            "previous_status": previous_status,
            "status": entry.status,
        },
    )


@require_POST
@roles_required(*FRONT_DESK_ROLES)
def queue_check_in(request, appointment_id):
    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update().select_related("patient"),
            pk=appointment_id,
        )
        if timezone.localtime(appointment.appointment_at).date() != timezone.localdate():
            messages.error(request, "Only today's appointments can be checked in.")
        elif appointment.status not in (
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
        ):
            messages.error(request, "This appointment cannot be checked in.")
        elif QueueEntry.objects.filter(appointment=appointment).exists():
            messages.info(request, "This appointment is already on the clinic queue.")
        else:
            entry = QueueEntry.objects.create(
                appointment=appointment,
                status=QueueEntry.Status.WAITING,
                checked_in_at=timezone.now(),
                changed_by=request.user.staff_profile,
            )
            appointment.status = Appointment.Status.ATTENDED
            appointment.save(update_fields=("status", "updated_at"))
            _audit_transition(entry, request.user, "not_checked_in")
            messages.success(request, "Patient checked in and added to the queue.")
    return redirect("clinic_queue:board")


@require_POST
@roles_required(*ALL_QUEUE_ROLES)
def queue_transition(request, entry_id, action):
    role = request.user.staff_profile.role
    if action == "call" and role not in FRONT_DESK_ROLES:
        messages.error(request, "Your role cannot call patients from the queue.")
        return redirect("clinic_queue:board")

    with transaction.atomic():
        entry = get_object_or_404(
            QueueEntry.objects.select_for_update().select_related(
                "appointment__clinician", "appointment__patient"
            ),
            pk=entry_id,
        )
        if role == StaffProfile.Role.CLINICIAN and (
            entry.appointment.clinician_id != request.user.staff_profile.pk
        ):
            messages.error(request, "You can only update your assigned appointments.")
            return redirect("clinic_queue:board")

        previous_status = entry.status
        now = timezone.now()
        if action == "call" and entry.status == QueueEntry.Status.WAITING:
            entry.status = QueueEntry.Status.CALLED
            entry.called_at = now
        elif action == "start" and role in {
            StaffProfile.Role.ADMINISTRATOR,
            StaffProfile.Role.CLINICIAN,
        } and entry.status in {QueueEntry.Status.WAITING, QueueEntry.Status.CALLED}:
            entry.status = QueueEntry.Status.IN_CONSULTATION
            entry.consultation_started_at = now
        elif action == "complete" and role in {
            StaffProfile.Role.ADMINISTRATOR,
            StaffProfile.Role.CLINICIAN,
        } and entry.status == QueueEntry.Status.IN_CONSULTATION:
            entry.status = QueueEntry.Status.COMPLETED
            entry.completed_at = now
            appointment = entry.appointment
            appointment.status = Appointment.Status.COMPLETED
            appointment.save(update_fields=("status", "updated_at"))
        else:
            messages.error(request, "That queue transition is not available.")
            return redirect("clinic_queue:board")

        entry.changed_by = request.user.staff_profile
        entry.save(
            update_fields=(
                "status",
                "called_at",
                "consultation_started_at",
                "completed_at",
                "changed_by",
                "updated_at",
            )
        )
        _audit_transition(entry, request.user, previous_status)
        messages.success(request, "Queue status updated.")

    return redirect("clinic_queue:board")
