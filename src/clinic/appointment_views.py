from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinic.appointment_reminders import (
    REMINDER_NOTIFICATION_TYPE,
    sync_appointment_reminder as _sync_appointment_reminder,
)
from clinic.appointment_forms import AppointmentForm, AppointmentSearchForm
from clinic.authentication import roles_required
from clinic.models import Appointment, AppointmentNotification, AuditEvent, StaffProfile

APPOINTMENT_MANAGER_ROLES = (
    StaffProfile.Role.ADMINISTRATOR,
    StaffProfile.Role.RECEPTIONIST,
)
APPOINTMENT_READ_ROLES = (
    *APPOINTMENT_MANAGER_ROLES,
    StaffProfile.Role.CLINICIAN,
)
APPOINTMENTS_PER_PAGE = 25
EDITABLE_STATUSES = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
)


def _appointment_queryset_for(user):
    appointments = Appointment.objects.select_related(
        "patient",
        "clinician__account",
    ).order_by("appointment_at", "pk")
    if user.staff_profile.role == StaffProfile.Role.CLINICIAN:
        appointments = appointments.filter(clinician=user.staff_profile)
    return appointments


def _appointment_identifier(appointment):
    return appointment.appointment_identifier


def _record_appointment_event(appointment, actor, action, metadata):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        content_object=appointment,
        metadata=metadata,
    )


@roles_required(*APPOINTMENT_READ_ROLES)
def appointment_list(request):
    search_form = AppointmentSearchForm(request.GET)
    if not search_form.is_valid():
        return render(
            request,
            "clinic/appointments/appointment_list.html",
            {
                "search_form": search_form,
                "appointments": Paginator(
                    Appointment.objects.none(),
                    APPOINTMENTS_PER_PAGE,
                ).page(1),
                "query_string": "",
                "can_manage_appointments": request.user.staff_profile.role
                in APPOINTMENT_MANAGER_ROLES,
                "appointment_duration_minutes": settings.APPOINTMENT_DEFAULT_DURATION_MINUTES,
            },
            status=400,
        )

    appointments = _appointment_queryset_for(request.user)
    cleaned = search_form.cleaned_data
    query = cleaned["query"]
    if query:
        search_filter = (
            Q(patient__patient_identifier__icontains=query)
            | Q(patient__full_name__icontains=query)
        )
        appointment_pk = search_form.appointment_pk_from_query()
        if appointment_pk is not None:
            search_filter |= Q(pk=appointment_pk)
        appointments = appointments.filter(search_filter)
    if cleaned["appointment_date"]:
        appointments = appointments.filter(
            appointment_at__date=cleaned["appointment_date"]
        )
    if cleaned["category"] == "upcoming":
        appointments = appointments.filter(
            status__in=(Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED),
            appointment_at__gte=timezone.now(),
        )
    elif cleaned["category"] == "completed":
        appointments = appointments.filter(status=Appointment.Status.COMPLETED)
    elif cleaned["category"] == "cancelled":
        appointments = appointments.filter(status=Appointment.Status.CANCELLED)
    elif cleaned["category"] == "missed":
        appointments = appointments.filter(status=Appointment.Status.MISSED)
    if cleaned["status"]:
        appointments = appointments.filter(status=cleaned["status"])
    if cleaned["clinician"]:
        appointments = appointments.filter(clinician=cleaned["clinician"])

    query_params = request.GET.copy()
    query_params.pop("page", None)
    page = Paginator(
        appointments,
        APPOINTMENTS_PER_PAGE,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "clinic/appointments/appointment_list.html",
        {
            "search_form": search_form,
            "appointments": page,
            "query_string": query_params.urlencode(),
            "can_manage_appointments": request.user.staff_profile.role
            in APPOINTMENT_MANAGER_ROLES,
            "appointment_duration_minutes": settings.APPOINTMENT_DEFAULT_DURATION_MINUTES,
        },
    )


@roles_required(*APPOINTMENT_MANAGER_ROLES)
def appointment_create(request):
    if request.method == "POST":
        with transaction.atomic():
            form = AppointmentForm(request.POST)
            if form.is_valid():
                appointment = form.save(commit=False)
                appointment.status = Appointment.Status.SCHEDULED
                appointment.save()
                _record_appointment_event(
                    appointment,
                    request.user,
                    "appointment.created",
                    {
                        "appointment_identifier": _appointment_identifier(appointment),
                        "status": Appointment.Status.SCHEDULED,
                    },
                )
                _sync_appointment_reminder(appointment)
                messages.success(request, "Appointment scheduled.")
                return redirect(
                    "clinic_appointments:appointment_detail",
                    appointment_id=appointment.pk,
                )
    else:
        form = AppointmentForm()
    return render(
        request,
        "clinic/appointments/appointment_form.html",
        {
            "form": form,
            "page_title": "Schedule appointment",
            "appointment_duration_minutes": settings.APPOINTMENT_DEFAULT_DURATION_MINUTES,
        },
    )


@roles_required(*APPOINTMENT_READ_ROLES)
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        _appointment_queryset_for(request.user),
        pk=appointment_id,
    )
    can_manage = request.user.staff_profile.role in APPOINTMENT_MANAGER_ROLES
    return render(
        request,
        "clinic/appointments/appointment_detail.html",
        {
            "appointment": appointment,
            "appointment_identifier": _appointment_identifier(appointment),
            "can_manage_appointments": can_manage,
            "can_edit_appointment": can_manage
            and appointment.status in EDITABLE_STATUSES,
            "can_cancel_appointment": can_manage
            and appointment.status in EDITABLE_STATUSES,
        },
    )


@roles_required(*APPOINTMENT_MANAGER_ROLES)
def appointment_edit(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    if appointment.status not in EDITABLE_STATUSES:
        messages.error(
            request,
            "Only Scheduled or Confirmed appointments can be edited or rescheduled.",
        )
        return redirect(
            "clinic_appointments:appointment_detail",
            appointment_id=appointment.pk,
        )

    old_start = appointment.appointment_at
    old_end = appointment.ends_at
    old_patient_id = appointment.patient_id
    old_clinician_id = appointment.clinician_id
    old_reason = appointment.reason_for_visit
    if request.method == "POST":
        with transaction.atomic():
            form = AppointmentForm(request.POST, instance=appointment)
            if form.is_valid():
                appointment = form.save()
                changed_fields = []
                if old_patient_id != appointment.patient_id:
                    changed_fields.append("patient")
                if old_clinician_id != appointment.clinician_id:
                    changed_fields.append("clinician")
                if old_reason != appointment.reason_for_visit:
                    changed_fields.append("reason_for_visit")
                schedule_changed = (
                    old_start != appointment.appointment_at
                    or old_end != appointment.ends_at
                )
                if schedule_changed:
                    changed_fields.append("schedule")
                if changed_fields:
                    action = (
                        "appointment.rescheduled"
                        if schedule_changed
                        else "appointment.updated"
                    )
                    event_metadata = {"changed_fields": changed_fields}
                    if schedule_changed:
                        event_metadata.update(
                            {
                                "previous_start": old_start.isoformat(),
                                "previous_end": old_end.isoformat(),
                                "new_start": appointment.appointment_at.isoformat(),
                                "new_end": appointment.ends_at.isoformat(),
                            }
                        )
                    _record_appointment_event(
                        appointment,
                        request.user,
                        action,
                        event_metadata,
                    )
                _sync_appointment_reminder(appointment)
                messages.success(request, "Appointment details updated.")
                return redirect(
                    "clinic_appointments:appointment_detail",
                    appointment_id=appointment.pk,
                )
    else:
        form = AppointmentForm(instance=appointment)
    return render(
        request,
        "clinic/appointments/appointment_form.html",
        {
            "form": form,
            "page_title": "Edit or reschedule appointment",
            "appointment": appointment,
            "appointment_duration_minutes": int(
                (appointment.ends_at - appointment.appointment_at).total_seconds()
                // 60
            ),
        },
    )


@require_POST
@roles_required(*APPOINTMENT_MANAGER_ROLES)
def appointment_cancel(request, appointment_id):
    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update(),
            pk=appointment_id,
        )
        if appointment.status == Appointment.Status.CANCELLED:
            messages.info(request, "This appointment is already cancelled.")
        elif appointment.status not in EDITABLE_STATUSES:
            messages.error(
                request,
                "Only Scheduled or Confirmed appointments can be cancelled.",
            )
        else:
            previous_status = appointment.status
            appointment.status = Appointment.Status.CANCELLED
            appointment.cancellation_reason = request.POST.get(
                "cancellation_reason",
                "",
            ).strip()
            appointment.save(
                update_fields=(
                    "status",
                    "cancellation_reason",
                    "updated_at",
                )
            )
            _record_appointment_event(
                appointment,
                request.user,
                "appointment.cancelled",
                {
                    "appointment_identifier": _appointment_identifier(appointment),
                    "previous_status": previous_status,
                    "status": Appointment.Status.CANCELLED,
                },
            )
            _sync_appointment_reminder(appointment)
            messages.success(request, "Appointment cancelled.")
    return redirect(
        "clinic_appointments:appointment_detail",
        appointment_id=appointment.pk,
    )


@roles_required(StaffProfile.Role.CLINICIAN)
def appointment_reminders(request):
    notifications = (
        AppointmentNotification.objects.filter(
            recipient=request.user,
            notification_type=REMINDER_NOTIFICATION_TYPE,
            scheduled_for__lte=timezone.now(),
            appointment__appointment_at__gt=timezone.now(),
            appointment__status__in=(
                Appointment.Status.SCHEDULED,
                Appointment.Status.CONFIRMED,
            ),
            appointment__clinician__account=request.user,
            appointment__clinician__is_active=True,
            appointment__clinician__account__is_active=True,
        )
        .select_related(
            "appointment",
            "appointment__patient",
            "appointment__clinician",
            "appointment__clinician__account",
        )
        .order_by("scheduled_for", "-created_at")
    )
    return render(
        request,
        "clinic/appointments/appointment_reminders.html",
        {
            "notifications": notifications,
            "unread_notifications": notifications.filter(read_at__isnull=True),
        },
    )


@require_POST
@roles_required(StaffProfile.Role.CLINICIAN)
def appointment_reminder_mark_read(request, notification_id):
    notification = get_object_or_404(
        AppointmentNotification.objects.select_related(
            "appointment",
            "appointment__patient",
            "appointment__clinician",
            "appointment__clinician__account",
        ),
        pk=notification_id,
        recipient=request.user,
        notification_type=REMINDER_NOTIFICATION_TYPE,
        scheduled_for__lte=timezone.now(),
        appointment__appointment_at__gt=timezone.now(),
        appointment__status__in=(
            Appointment.Status.SCHEDULED,
            Appointment.Status.CONFIRMED,
        ),
        appointment__clinician__account=request.user,
        appointment__clinician__is_active=True,
        appointment__clinician__account__is_active=True,
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
        messages.success(request, "Reminder marked as read.")
    else:
        messages.info(request, "This reminder was already read.")
    return redirect("clinic_appointments:appointment_reminders")
