from django.urls import path

from clinic import queue_views

app_name = "clinic_queue"

urlpatterns = [
    path("", queue_views.queue_board, name="board"),
    path(
        "appointments/<int:appointment_id>/check-in/",
        queue_views.queue_check_in,
        name="check_in",
    ),
    path(
        "entries/<int:entry_id>/<str:action>/",
        queue_views.queue_transition,
        name="transition",
    ),
]
