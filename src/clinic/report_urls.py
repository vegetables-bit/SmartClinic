from django.urls import path

from clinic import report_views

app_name = "clinic_reports"

urlpatterns = [
    path("operations/", report_views.operational_report, name="operations"),
]
