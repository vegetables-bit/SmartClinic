from django.urls import path

from clinic import clinical_views

app_name = "clinic_clinical"

urlpatterns = [
    path("", clinical_views.patient_index, name="patient_index"),
    path(
        "patients/<str:patient_identifier>/history/",
        clinical_views.patient_history,
        name="patient_history",
    ),
    path(
        "patients/<str:patient_identifier>/consultations/new/",
        clinical_views.consultation_create,
        name="consultation_create",
    ),
    path(
        "patients/<str:patient_identifier>/history/new/",
        clinical_views.medical_history_entry_create,
        name="medical_history_entry_create",
    ),
    path(
        "consultations/<int:consultation_id>/",
        clinical_views.consultation_detail,
        name="consultation_detail",
    ),
    path(
        "consultations/<int:consultation_id>/edit/",
        clinical_views.consultation_edit,
        name="consultation_edit",
    ),
]
