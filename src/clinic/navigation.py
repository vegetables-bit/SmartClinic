from urllib.parse import urlsplit

from django.utils.http import url_has_allowed_host_and_scheme


def safe_return_url(request, parameter, allowed_paths):
    return_url = request.GET.get(parameter, "")
    if not return_url:
        return ""

    try:
        parsed_url = urlsplit(return_url)
    except ValueError:
        return ""
    if (
        parsed_url.scheme
        or parsed_url.netloc
        or parsed_url.path not in allowed_paths
        or not url_has_allowed_host_and_scheme(
            return_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    ):
        return ""
    return return_url
