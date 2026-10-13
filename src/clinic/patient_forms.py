import logging

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from clinic.models import Patient
from clinic.models.patients import generate_patient_identifier

logger = logging.getLogger(__name__)

PATIENT_IDENTIFIER_ATTEMPTS = 5


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = (
            "full_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "address",
            "emergency_contact_name",
            "emergency_contact_phone",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")
        return date_of_birth


class PatientSearchForm(forms.Form):
    query = forms.CharField(
        label="Search patients",
        required=False,
        max_length=100,
    )
    status = forms.ChoiceField(
        choices=(
            ("active", "Active patients"),
            ("archived", "Archived patients"),
            ("all", "All patients"),
        ),
        required=False,
        initial="active",
    )

    def clean_query(self):
        query = self.cleaned_data.get("query", "").strip()
        if any(ord(character) < 32 or ord(character) == 127 for character in query):
            raise ValidationError("Search must not contain control characters.")
        return query

    def clean_status(self):
        return self.cleaned_data.get("status") or "active"


class PatientIdentifierGenerationError(Exception):
    """Raised when a unique generated patient identifier cannot be reserved."""


def save_patient_with_generated_identifier(form):
    patient = form.save(commit=False)

    for _ in range(PATIENT_IDENTIFIER_ATTEMPTS):
        identifier = generate_patient_identifier()
        if Patient.objects.filter(patient_identifier=identifier).exists():
            continue

        patient.patient_identifier = identifier
        try:
            patient.full_clean()
        except ValidationError as error:
            identifier_errors = error.error_dict.get("patient_identifier", ())
            if (
                identifier_errors
                and Patient.objects.filter(patient_identifier=identifier).exists()
            ):
                continue
            raise

        try:
            with transaction.atomic():
                patient.save()
                form.save_m2m()
            return patient
        except IntegrityError:
            if Patient.objects.filter(patient_identifier=identifier).exists():
                continue
            raise

    logger.error(
        "Could not generate a unique patient identifier after %s attempts.",
        PATIENT_IDENTIFIER_ATTEMPTS,
    )
    raise PatientIdentifierGenerationError
