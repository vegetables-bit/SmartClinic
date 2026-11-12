from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from clinic.appointment_forms import AppointmentReportForm
from clinic.authentication import roles_required
from clinic.models import (
    Appointment,
    Consultation,
    NursingObservation,
    QueueEntry,
    StaffProfile,
)

REPORT_ROLES = tuple(StaffProfile.Role.values)


@roles_required(*REPORT_ROLES)
def operational_report(request):
    form = AppointmentReportForm(request.GET or None)
    if not form.is_valid():
        return render(
            request,
            "clinic/reports/operational_report.html",
            {"form": form, "metrics": (), "status_rows": (), "queue_rows": ()},
            status=400,
        )

    role = request.user.staff_profile.role
    start_date = form.cleaned_data["start_date"]
    end_date = form.cleaned_data["end_date"]
    appointments = Appointment.objects.all()
    if role == StaffProfile.Role.CLINICIAN:
        appointments = appointments.filter(clinician=request.user.staff_profile)
    if start_date:
        appointments = appointments.filter(appointment_at__date__gte=start_date)
    if end_date:
        appointments = appointments.filter(appointment_at__date__lte=end_date)

    status_totals = {
        row["status"]: row["total"]
        for row in appointments.order_by().values("status").annotate(total=Count("pk"))
    }
    status_rows = [
        {"label": label, "total": status_totals.get(value, 0)}
        for value, label in Appointment.Status.choices
    ]
    queue = QueueEntry.objects.filter(appointment__in=appointments)
    queue_totals = {
        row["status"]: row["total"]
        for row in queue.order_by().values("status").annotate(total=Count("pk"))
    }
    queue_rows = [
        {"label": label, "total": queue_totals.get(value, 0)}
        for value, label in QueueEntry.Status.choices
    ]
    metrics = [
        {"label": "Appointments in period", "value": appointments.count()},
        {
            "label": "Queue entries waiting",
            "value": queue_totals.get(QueueEntry.Status.WAITING, 0),
        },
        {
            "label": "In consultation",
            "value": queue_totals.get(QueueEntry.Status.IN_CONSULTATION, 0),
        },
    ]
    if role == StaffProfile.Role.CLINICIAN:
        consultations = Consultation.objects.filter(clinician=request.user.staff_profile)
        if start_date:
            consultations = consultations.filter(consultation_at__date__gte=start_date)
        if end_date:
            consultations = consultations.filter(consultation_at__date__lte=end_date)
        metrics.append({"label": "Consultations recorded", "value": consultations.count()})
    elif role == StaffProfile.Role.NURSE:
        observations = NursingObservation.objects.filter(recorded_by=request.user.staff_profile)
        if start_date:
            observations = observations.filter(observed_at__date__gte=start_date)
        if end_date:
            observations = observations.filter(observed_at__date__lte=end_date)
        metrics.append({"label": "Your observations recorded", "value": observations.count()})
    elif role == StaffProfile.Role.ADMINISTRATOR:
        metrics.append(
            {
                "label": "Active staff accounts",
                "value": StaffProfile.objects.filter(
                    is_active=True,
                    account__is_active=True,
                ).count(),
            }
        )

    return render(
        request,
        "clinic/reports/operational_report.html",
        {
            "form": form,
            "metrics": metrics,
            "status_rows": status_rows,
            "queue_rows": queue_rows,
            "role_label": request.user.staff_profile.get_role_display(),
            "generated_at": timezone.localtime(),
        },
    )
