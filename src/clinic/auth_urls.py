from django.contrib.auth.views import PasswordChangeDoneView
from django.urls import path, reverse_lazy

from clinic.auth_views import (
    StaffLoginView,
    StaffLogoutView,
    StaffPasswordChangeView,
    StaffPasswordResetCompleteView,
    StaffPasswordResetConfirmView,
    StaffPasswordResetDoneView,
    StaffPasswordResetView,
    staff_account_create,
    staff_account_edit,
    staff_account_list,
    staff_account_profile,
    staff_account_status,
    staff_home,
)

app_name = "clinic_auth"

urlpatterns = [
    path("login/", StaffLoginView.as_view(), name="login"),
    path("logout/", StaffLogoutView.as_view(), name="logout"),
    path("home/", staff_home, name="staff_home"),
    path("password/change/", StaffPasswordChangeView.as_view(), name="password_change"),
    path(
        "password/change/done/",
        PasswordChangeDoneView.as_view(
            template_name="clinic/auth/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path("password/reset/", StaffPasswordResetView.as_view(), name="password_reset"),
    path(
        "password/reset/done/",
        StaffPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        StaffPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        StaffPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("staff/", staff_account_list, name="staff_account_list"),
    path("staff/create/", staff_account_create, name="staff_account_create"),
    path(
        "staff/<int:profile_id>/",
        staff_account_profile,
        name="staff_account_profile",
    ),
    path("staff/<int:profile_id>/edit/", staff_account_edit, name="staff_account_edit"),
    path(
        "staff/<int:profile_id>/status/",
        staff_account_status,
        name="staff_account_status",
    ),
]
