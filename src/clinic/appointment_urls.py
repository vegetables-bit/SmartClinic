from django.urls import path

from clinic import appointment_views

app_name = "clinic_appointments"

urlpatterns = [
    path("", appointment_views.appointment_list, name="appointment_list"),
    path("reminders/", appointment_views.appointment_reminders, name="appointment_reminders"),
    path(
        "reminders/<int:notification_id>/read/",
        appointment_views.appointment_reminder_mark_read,
        name="appointment_reminder_mark_read",
    ),
    path("create/", appointment_views.appointment_create, name="appointment_create"),
    path(
        "<int:appointment_id>/",
        appointment_views.appointment_detail,
        name="appointment_detail",
    ),
    path(
        "<int:appointment_id>/edit/",
        appointment_views.appointment_edit,
        name="appointment_edit",
    ),
    path(
        "<int:appointment_id>/cancel/",
        appointment_views.appointment_cancel,
        name="appointment_cancel",
    ),
]
