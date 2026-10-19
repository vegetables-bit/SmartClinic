from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    LogoutView,
)
from django.core.paginator import Paginator
from django.db import transaction
from django.db import IntegrityError
from django.db.models import Q
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
from clinic.models import AppointmentNotification, StaffProfile

STAFF_PER_PAGE = 25


class StaffLoginView(LoginView):
    template_name = "clinic/auth/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True

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


@method_decorator(active_staff_required, name="dispatch")
class StaffPasswordChangeView(PasswordChangeView):
    template_name = "clinic/auth/password_change.html"
    success_url = reverse_lazy("clinic_auth:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your password was changed.")
        return response


class StaffPasswordResetView(PasswordResetView):
    form_class = StaffPasswordResetForm
    template_name = "clinic/auth/password_reset_form.html"
    email_template_name = "clinic/auth/password_reset_email.txt"
    subject_template_name = "clinic/auth/password_reset_subject.txt"
    success_url = reverse_lazy("clinic_auth:password_reset_done")


class StaffPasswordResetDoneView(PasswordResetDoneView):
    template_name = "clinic/auth/password_reset_done.html"


class StaffPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "clinic/auth/password_reset_confirm.html"
    success_url = reverse_lazy("clinic_auth:password_reset_complete")


class StaffPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "clinic/auth/password_reset_complete.html"


@active_staff_required
def staff_home(request):
    profile = request.user.staff_profile
    upcoming_reminders = (
        AppointmentNotification.objects.filter(
            recipient=request.user,
            notification_type=REMINDER_NOTIFICATION_TYPE,
            read_at__isnull=True,
            scheduled_for__lte=timezone.now(),
            appointment__appointment_at__gt=timezone.now(),
            appointment__status__in=("scheduled", "confirmed"),
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
    return render(
        request,
        "clinic/auth/staff_home.html",
        {
            "dashboard_title": f"{profile.get_role_display()} dashboard",
            "upcoming_reminders": upcoming_reminders,
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
        try:
            with transaction.atomic():
                profile = form.save()
        except IntegrityError:
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
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
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
