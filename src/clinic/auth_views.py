import logging
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    LoginView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    LogoutView,
)
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinic.auth_forms import (
    StaffAccountCreateForm,
    StaffAccountUpdateForm,
    StaffAuthenticationForm,
    MyProfileForm,
    StaffPasswordResetForm,
    StaffSearchForm,
)
from clinic.authentication import active_staff_required, administrator_required
from clinic.appointment_reminders import REMINDER_NOTIFICATION_TYPE
from clinic.appointment_views import (
    APPOINTMENT_READ_ROLES,
    appointment_queryset_for,
)
from clinic.audit import record_audit_event
from clinic.models import Appointment, AppointmentNotification, Patient, StaffProfile

STAFF_PER_PAGE = 25
logger = logging.getLogger(__name__)


class StaffLoginView(LoginView):
    template_name = "clinic/auth/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        response = super().form_valid(form)
        try:
            record_audit_event(
                actor=user,
                action="auth.login.succeeded",
                target=user,
                metadata={},
            )
        except DatabaseError:
            logout(self.request)
            logger.error("Audit persistence failed for auth.login.succeeded.")
            form.add_error(
                None,
                "Sign-in could not be completed. Please try again.",
            )
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 503
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        invalid_credentials = any(
            error.code == "invalid_login"
            for error in form.errors.as_data().get("__all__", [])
        )
        if invalid_credentials:
            try:
                record_audit_event(
                    actor=None,
                    action="auth.login.failed",
                    target=None,
                    metadata={},
                )
            except DatabaseError:
                logger.error("Audit persistence failed for auth.login.failed.")
        return response

    def get_success_url(self):
        success_url = super().get_success_url()
        try:
            namespace = resolve(urlsplit(success_url).path).namespace
        except Resolver404:
            return success_url

        if namespace == "admin" and not (
            self.request.user.is_active and self.request.user.is_staff
        ):
            return str(reverse_lazy("clinic_auth:staff_home"))
        return success_url

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, "staff_profile", None)
            if (
                not request.user.is_active
                or profile is None
                or not profile.is_active
            ):
                logout(request)
        return super().dispatch(request, *args, **kwargs)


class StaffLogoutView(LogoutView):
    next_page = reverse_lazy("clinic_auth:login")
    template_name = "clinic/auth/logout.html"

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.pk is not None:
            try:
                record_audit_event(
                    actor=user,
                    action="auth.logout",
                    target=user,
                    metadata={},
                )
            except DatabaseError:
                logger.error("Audit persistence failed for auth.logout.")
        return super().post(request, *args, **kwargs)


@method_decorator(active_staff_required, name="dispatch")
class StaffPasswordChangeView(PasswordChangeView):
    template_name = "clinic/auth/password_change.html"
    success_url = reverse_lazy("clinic_auth:password_change_done")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
                record_audit_event(
                    actor=user,
                    action="auth.password.changed",
                    target=user,
                    metadata={},
                )
        except DatabaseError:
            logger.error("Audit persistence failed for auth.password.changed.")
            form.add_error(
                None,
                "Password change could not be completed. Please try again.",
            )
            return self.form_invalid(form)
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Your password was changed.")
        return HttpResponseRedirect(self.get_success_url())


class StaffPasswordResetView(PasswordResetView):
    form_class = StaffPasswordResetForm
    template_name = "clinic/auth/password_reset_form.html"
    email_template_name = "clinic/auth/password_reset_email.txt"
    subject_template_name = "clinic/auth/password_reset_subject.txt"
    success_url = reverse_lazy("clinic_auth:password_reset_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            record_audit_event(
                actor=None,
                action="auth.password_reset.requested",
                target=None,
                metadata={},
            )
        except DatabaseError:
            logger.error(
                "Audit persistence failed for auth.password_reset.requested."
            )
        return response


class StaffPasswordResetDoneView(PasswordResetDoneView):
    template_name = "clinic/auth/password_reset_done.html"


class StaffPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "clinic/auth/password_reset_confirm.html"
    success_url = reverse_lazy("clinic_auth:password_reset_complete")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
                record_audit_event(
                    actor=None,
                    action="auth.password_reset.completed",
                    target=user,
                    metadata={},
                )
        except DatabaseError:
            logger.error(
                "Audit persistence failed for auth.password_reset.completed."
            )
            form.add_error(
                None,
                "Password reset could not be completed. Please try again.",
            )
            return self.form_invalid(form)

        del self.request.session[INTERNAL_RESET_SESSION_TOKEN]
        if self.post_reset_login:
            auth_login(self.request, user, self.post_reset_login_backend)
        return HttpResponseRedirect(self.get_success_url())


class StaffPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "clinic/auth/password_reset_complete.html"


@active_staff_required
def staff_home(request):
    profile = request.user.staff_profile
    is_clinician = profile.role == StaffProfile.Role.CLINICIAN
    is_nurse = profile.role == StaffProfile.Role.NURSE
    can_view_appointments = (
        profile.role in APPOINTMENT_READ_ROLES and not is_nurse
    )
    can_view_patient_totals = profile.role in (
        StaffProfile.Role.ADMINISTRATOR,
        StaffProfile.Role.RECEPTIONIST,
    )
    upcoming_reminders = AppointmentNotification.objects.none()
    appointment_status_counts = []
    nurse_upcoming_appointments = ()
    today_appointment_count = None
    upcoming_appointment_count = None
    if is_nurse:
        now = timezone.now()
        nurse_upcoming_appointments = (
            Appointment.objects.filter(
                Q(appointment_at__date=timezone.localdate())
                | Q(appointment_at__gt=now),
                status__in=(
                    Appointment.Status.SCHEDULED,
                    Appointment.Status.CONFIRMED,
                ),
            )
            .select_related("patient", "clinician__account")
            .order_by("appointment_at", "pk")[:5]
        )
    if is_clinician:
        now = timezone.now()
        upcoming_reminders = (
            AppointmentNotification.objects.filter(
                recipient=request.user,
                notification_type=REMINDER_NOTIFICATION_TYPE,
                read_at__isnull=True,
                scheduled_for__lte=now,
                appointment__appointment_at__gt=now,
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
            .order_by("scheduled_for", "-created_at")[:5]
        )
    if can_view_appointments:
        now = timezone.now()
        appointments = appointment_queryset_for(request.user)
        appointment_metrics = appointments.aggregate(
            today=Count("pk", filter=Q(appointment_at__date=timezone.localdate())),
            upcoming=Count(
                "pk",
                filter=Q(
                    appointment_at__gt=now,
                    status__in=(
                        Appointment.Status.SCHEDULED,
                        Appointment.Status.CONFIRMED,
                    ),
                ),
            ),
        )
        today_appointment_count = appointment_metrics["today"]
        upcoming_appointment_count = appointment_metrics["upcoming"]
        grouped_status_counts = {
            row["status"]: row["total"]
            for row in appointments.order_by()
            .values("status")
            .annotate(total=Count("pk"))
        }
        appointment_status_counts = [
            {
                "value": status,
                "label": label,
                "total": grouped_status_counts.get(status, 0),
            }
            for status, label in Appointment.Status.choices
        ]
    registered_patient_count = (
        Patient.objects.count() if can_view_patient_totals else None
    )
    return render(
        request,
        (
            "clinic/auth/nurse_dashboard.html"
            if is_nurse
            else "clinic/auth/staff_home.html"
        ),
        {
            "dashboard_title": f"{profile.get_role_display()} dashboard",
            "upcoming_reminders": upcoming_reminders,
            "can_view_appointments": can_view_appointments,
            "can_view_patient_totals": can_view_patient_totals,
            "today_appointment_count": today_appointment_count,
            "upcoming_appointment_count": upcoming_appointment_count,
            "appointment_status_counts": appointment_status_counts,
            "registered_patient_count": registered_patient_count,
            "nurse_upcoming_appointments": nurse_upcoming_appointments,
        },
    )


@active_staff_required
def settings_page(request):
    return render(request, "clinic/auth/settings.html")


@active_staff_required
def my_profile(request):
    profile = request.user.staff_profile
    form = MyProfileForm(
        request.POST or None,
        account=request.user,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Your profile was updated.")
        return redirect("clinic_auth:my_profile")
    return render(
        request,
        "clinic/auth/my_profile.html",
        {"form": form, "profile": profile},
    )


@administrator_required
def staff_account_list(request):
    search_form = StaffSearchForm(request.GET)
    if not search_form.is_valid():
        return render(
            request,
            "clinic/auth/staff_account_list.html",
            {
                "search_form": search_form,
                "staff_profiles": Paginator(
                    StaffProfile.objects.none(),
                    STAFF_PER_PAGE,
                ).page(1),
            },
            status=400,
        )

    profiles = StaffProfile.objects.select_related("account").prefetch_related(
        "departments"
    )
    query = search_form.cleaned_data["query"]
    if query:
        profiles = profiles.filter(
            Q(staff_identifier__icontains=query)
            | Q(account__username__icontains=query)
            | Q(account__first_name__icontains=query)
            | Q(account__last_name__icontains=query)
            | Q(account__email__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(departments__name__icontains=query)
        ).distinct()
    if search_form.cleaned_data["role"]:
        profiles = profiles.filter(role=search_form.cleaned_data["role"])
    if search_form.cleaned_data["status"] == "active":
        profiles = profiles.filter(is_active=True, account__is_active=True)
    elif search_form.cleaned_data["status"] == "inactive":
        profiles = profiles.filter(
            Q(is_active=False) | Q(account__is_active=False)
        )

    page = Paginator(
        profiles.order_by("account__last_name", "account__first_name", "pk"),
        STAFF_PER_PAGE,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "clinic/auth/staff_account_list.html",
        {"staff_profiles": page, "search_form": search_form},
    )


@administrator_required
def staff_account_profile(request, profile_id):
    profile = get_object_or_404(
        StaffProfile.objects.select_related("account").prefetch_related(
            "departments"
        ),
        pk=profile_id,
    )
    return render(
        request,
        "clinic/auth/staff_account_profile.html",
        {"profile": profile},
    )


@administrator_required
def staff_account_create(request):
    form = StaffAccountCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        audit_write_started = False
        try:
            with transaction.atomic():
                profile = form.save()
                audit_write_started = True
                record_audit_event(
                    actor=request.user,
                    action="staff.account.created",
                    target=profile,
                    metadata={"account_id": profile.account_id},
                )
        except IntegrityError:
            if audit_write_started:
                raise
            form.add_error(
                None,
                "The account could not be saved because a unique value was "
                "claimed by another request. Review the username, email, and "
                "staff identifier, then try again.",
            )
        else:
            messages.success(
                request,
                f"Staff account {profile.account.username} was created.",
            )
            return redirect(
                "clinic_auth:staff_account_profile",
                profile_id=profile.pk,
            )
    return render(
        request,
        "clinic/auth/staff_account_form.html",
        {"form": form, "page_title": "Create staff account"},
    )


@administrator_required
def staff_account_edit(request, profile_id):
    profile = get_object_or_404(
        StaffProfile.objects.select_related("account").prefetch_related(
            "departments"
        ),
        pk=profile_id,
    )
    form = StaffAccountUpdateForm(
        request.POST or None,
        profile=profile,
    )
    if request.method == "POST" and form.is_valid():
        audit_write_started = False
        original_values = {
            "username": profile.account.username,
            "first_name": profile.account.first_name,
            "last_name": profile.account.last_name,
            "email": profile.account.email,
            "staff_identifier": profile.staff_identifier or "",
            "phone_number": profile.phone_number,
            "role": profile.role,
        }
        original_department_ids = set(
            profile.departments.values_list("pk", flat=True)
        )
        changed_account_fields = [
            field
            for field in (
                "username",
                "first_name",
                "last_name",
                "email",
                "staff_identifier",
                "phone_number",
            )
            if form.cleaned_data[field] != original_values[field]
        ]
        role_changed = form.cleaned_data["role"] != original_values["role"]
        departments_changed = set(
            form.cleaned_data["departments"].values_list("pk", flat=True)
        ) != original_department_ids
        try:
            with transaction.atomic():
                form.save()
                if changed_account_fields:
                    audit_write_started = True
                    record_audit_event(
                        actor=request.user,
                        action="staff.account.updated",
                        target=profile,
                        metadata={
                            "account_id": profile.account_id,
                            "changed_fields": changed_account_fields,
                        },
                    )
                if role_changed:
                    audit_write_started = True
                    record_audit_event(
                        actor=request.user,
                        action="staff.role.changed",
                        target=profile,
                        metadata={
                            "account_id": profile.account_id,
                            "changed_fields": ["role"],
                        },
                    )
                if departments_changed:
                    audit_write_started = True
                    record_audit_event(
                        actor=request.user,
                        action="staff.departments.changed",
                        target=profile,
                        metadata={
                            "account_id": profile.account_id,
                            "changed_fields": ["departments"],
                        },
                    )
        except IntegrityError:
            if audit_write_started:
                raise
            form.add_error(
                None,
                "The account could not be updated because a unique value was "
                "claimed by another request. Review the username, email, and "
                "staff identifier, then try again.",
            )
        else:
            messages.success(request, "Staff account was updated.")
            return redirect(
                "clinic_auth:staff_account_profile",
                profile_id=profile.pk,
            )
    return render(
        request,
        "clinic/auth/staff_account_form.html",
        {"form": form, "page_title": "Edit staff account"},
    )


@administrator_required
@require_POST
def staff_account_status(request, profile_id):
    with transaction.atomic():
        profile = get_object_or_404(
            StaffProfile.objects.select_for_update().select_related("account"),
            pk=profile_id,
        )
        activating = not (profile.is_active and profile.account.is_active)
        if not activating:
            if profile.account_id == request.user.pk:
                messages.error(request, "You cannot deactivate your own account.")
                return redirect(
                    "clinic_auth:staff_account_profile",
                    profile_id=profile.pk,
                )
            if profile.role == StaffProfile.Role.ADMINISTRATOR:
                another_active_admin = StaffProfile.objects.filter(
                    role=StaffProfile.Role.ADMINISTRATOR,
                    is_active=True,
                    account__is_active=True,
                ).exclude(pk=profile.pk).exists()
                if not another_active_admin:
                    messages.error(
                        request,
                        "The last active administrator cannot be deactivated.",
                    )
                    return redirect(
                        "clinic_auth:staff_account_profile",
                        profile_id=profile.pk,
                    )

        profile.is_active = activating
        profile.save(update_fields=("is_active", "updated_at"))
        profile.account.is_active = activating
        profile.account.save(update_fields=("is_active",))
        record_audit_event(
            actor=request.user,
            action=(
                "staff.account.activated"
                if activating
                else "staff.account.deactivated"
            ),
            target=profile,
            metadata={"account_id": profile.account_id},
        )

    messages.success(
        request,
        "Staff account activated." if activating else "Staff account deactivated.",
    )
    return redirect(
        "clinic_auth:staff_account_profile",
        profile_id=profile.pk,
    )


def forbidden(request, exception=None):
    return render(request, "403.html", status=403)
