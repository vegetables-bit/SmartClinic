import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from clinic.models import Department, StaffProfile

User = get_user_model()
STAFF_IDENTIFIER_ATTEMPTS = 5


def generate_unique_staff_identifier(*, exclude_profile_id=None):
    for _ in range(STAFF_IDENTIFIER_ATTEMPTS):
        identifier = f"ST-{uuid.uuid4().hex.upper()}"
        existing = StaffProfile.objects.filter(
            staff_identifier__iexact=identifier
        )
        if exclude_profile_id is not None:
            existing = existing.exclude(pk=exclude_profile_id)
        if not existing.exists():
            return identifier
    raise ValidationError(
        "A unique staff identifier could not be generated. Please try again."
    )


def validate_staff_identifier(value, *, exclude_profile_id=None):
    if not value:
        return value
    existing = StaffProfile.objects.filter(staff_identifier__iexact=value)
    if exclude_profile_id is not None:
        existing = existing.exclude(pk=exclude_profile_id)
    if existing.exists():
        raise ValidationError("A staff account with this identifier already exists.")
    return value


class StaffAuthenticationForm(AuthenticationForm):
    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            return ""

        user = (
            User.objects.filter(
                Q(username__iexact=username)
                | Q(email__iexact=username)
                | Q(staff_profile__staff_identifier__iexact=username)
            )
            .select_related("staff_profile")
            .order_by("pk")
            .first()
        )
        if user is not None:
            return user.get_username()
        return username

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        profile = getattr(user, "staff_profile", None)
        if profile is None or not profile.is_active:
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )


class StaffPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        for user in super().get_users(email):
            profile = getattr(user, "staff_profile", None)
            if user.is_active and profile is not None and profile.is_active:
                yield user


class StaffAccountCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=StaffProfile.Role.choices)
    staff_identifier = forms.CharField(
        max_length=50,
        required=False,
        help_text="Leave blank to assign a unique staff identifier automatically.",
    )
    phone_number = forms.CharField(max_length=30, required=False)
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
    )
    password1 = forms.CharField(
        label="Temporary password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm temporary password",
        strip=False,
        widget=forms.PasswordInput,
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("An account with this username already exists.")
        return username

    def clean_staff_identifier(self):
        value = self.cleaned_data.get("staff_identifier", "")
        if not value:
            value = generate_unique_staff_identifier()
        return validate_staff_identifier(value)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        if password:
            user = User(
                username=cleaned_data.get("username", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                validate_password(password, user=user)
            except ValidationError as error:
                self.add_error("password1", error)

        if (
            cleaned_data.get("password1")
            and cleaned_data.get("password2")
            and cleaned_data["password1"] != cleaned_data["password2"]
        ):
            self.add_error("password2", "The passwords do not match.")
        return cleaned_data

    def save(self):
        if not self.is_valid():
            raise ValueError("Staff account form must be valid before saving.")

        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        profile = StaffProfile.objects.create(
            account=user,
            role=self.cleaned_data["role"],
            staff_identifier=self.cleaned_data["staff_identifier"],
            phone_number=self.cleaned_data["phone_number"],
            is_active=True,
        )
        profile.departments.set(self.cleaned_data["departments"])
        return profile


class StaffAccountUpdateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=StaffProfile.Role.choices)
    staff_identifier = forms.CharField(
        max_length=50,
        required=False,
        help_text="Leave blank to keep the current identifier or assign one if missing.",
    )
    phone_number = forms.CharField(max_length=30, required=False)
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
    )

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update(
                {
                    "username": profile.account.username,
                    "first_name": profile.account.first_name,
                    "last_name": profile.account.last_name,
                    "email": profile.account.email,
                    "role": profile.role,
                    "staff_identifier": profile.staff_identifier or "",
                    "phone_number": profile.phone_number,
                    "departments": profile.departments.values_list("pk", flat=True),
                }
            )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(
            Q(username__iexact=username) & ~Q(pk=self.profile.account_id)
        ).exists():
            raise ValidationError("An account with this username already exists.")
        return username

    def clean_staff_identifier(self):
        value = self.cleaned_data.get("staff_identifier", "")
        if not value:
            value = self.profile.staff_identifier or generate_unique_staff_identifier(
                exclude_profile_id=self.profile.pk
            )
        return validate_staff_identifier(value, exclude_profile_id=self.profile.pk)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exclude(
            pk=self.profile.account_id
        ).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        new_role = cleaned_data.get("role")
        if (
            self.profile.role == StaffProfile.Role.ADMINISTRATOR
            and self.profile.is_active
            and self.profile.account.is_active
            and new_role != StaffProfile.Role.ADMINISTRATOR
        ):
            another_active_admin = (
                StaffProfile.objects.filter(
                    role=StaffProfile.Role.ADMINISTRATOR,
                    is_active=True,
                    account__is_active=True,
                )
                .exclude(pk=self.profile.pk)
                .exists()
            )
            if not another_active_admin:
                self.add_error(
                    None,
                    "The last active administrator cannot be demoted.",
                )
        return cleaned_data

    def save(self):
        if not self.is_valid():
            raise ValueError("Staff account form must be valid before saving.")

        user = self.profile.account
        user.username = self.cleaned_data["username"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save(
            update_fields=[
                "username",
                "first_name",
                "last_name",
                "email",
            ]
        )

        self.profile.role = self.cleaned_data["role"]
        self.profile.staff_identifier = (
            self.cleaned_data["staff_identifier"]
        )
        self.profile.phone_number = self.cleaned_data["phone_number"]
        self.profile.save(
            update_fields=[
                "role",
                "staff_identifier",
                "phone_number",
                "updated_at",
            ]
        )
        self.profile.departments.set(self.cleaned_data["departments"])
        return self.profile


class StaffSearchForm(forms.Form):
    query = forms.CharField(
        label="Search staff",
        max_length=100,
        required=False,
    )
    role = forms.ChoiceField(
        choices=(("", "All roles"), *StaffProfile.Role.choices),
        required=False,
    )
    status = forms.ChoiceField(
        choices=(("", "All statuses"), ("active", "Active"), ("inactive", "Inactive")),
        required=False,
    )

    def clean_query(self):
        query = self.cleaned_data.get("query", "").strip()
        if any(ord(character) < 32 or ord(character) == 127 for character in query):
            raise ValidationError("Search must not contain control characters.")
        return query
