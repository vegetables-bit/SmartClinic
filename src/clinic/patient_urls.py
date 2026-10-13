from django.urls import path

from clinic import patient_views

app_name = "clinic_patients"

urlpatterns = [
    path("", patient_views.patient_list, name="patient_list"),
    path("register/", patient_views.patient_create, name="patient_create"),
    path(
        "<str:patient_identifier>/",
        patient_views.patient_profile,
        name="patient_profile",
    ),
    path(
        "<str:patient_identifier>/edit/",
        patient_views.patient_edit,
        name="patient_edit",
    ),
    path(
        "<str:patient_identifier>/archive/",
        patient_views.patient_archive,
        name="patient_archive",
    ),
    path(
        "<str:patient_identifier>/restore/",
        patient_views.patient_restore,
        name="patient_restore",
    ),
]
