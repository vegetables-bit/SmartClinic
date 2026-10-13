from functools import wraps

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from clinic.models import StaffProfile


def active_staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "staff_profile", None)
        if (
            not request.user.is_active
            or profile is None
            or not profile.is_active
        ):
            logout(request)
            return redirect("clinic_auth:login")
        return view_func(request, *args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @active_staff_required
        def wrapped(request, *args, **kwargs):
            if request.user.staff_profile.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


administrator_required = roles_required(StaffProfile.Role.ADMINISTRATOR)
