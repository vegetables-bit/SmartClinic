from django.urls import path

from clinic import nursing_views

app_name = "clinic_nursing"

urlpatterns = [
    path(
        "appointments/<int:appointment_id>/observations/new/",
        nursing_views.nursing_observation_create,
        name="observation_create",
    ),
]
