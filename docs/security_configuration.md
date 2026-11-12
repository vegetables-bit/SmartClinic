# Environment-specific Django security configuration

The application requires an explicit `DJANGO_ENV` value:

- `development` selects local HTTP settings, localhost and `testserver`
  hosts, debug mode, and Django's console email backend.
- `production` selects `DEBUG=False`, requires an explicit host allow-list and
  strong secret, enables secure session and CSRF cookies, and requires explicit
  HTTPS, HSTS, and email-backend configuration.
- Missing or unknown environment names fail during settings loading.

## Local development and tests

From the repository root in PowerShell:

```powershell
$env:DJANGO_ENV = 'development'
$env:DJANGO_SECRET_KEY = (& .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
.\.venv\Scripts\python.exe .\src\manage.py runserver
```

Development allows `localhost`, `127.0.0.1`, and Django's `testserver` host,
does not force HTTPS, and leaves secure-only cookies disabled so local HTTP
and the existing test client continue to work. Tests may continue to override
`MAILERS` with Django's in-memory email backend.

## Production environment

Production requires all of the following values to be supplied externally.
Values below describe format only; do not copy example hostnames or secrets
into a real deployment:

| Variable | Requirement |
|---|---|
| `DJANGO_ENV` | Must be exactly `production`. |
| `DJANGO_SECRET_KEY` | At least 50 characters, at least 5 distinct characters, not prefixed with `django-insecure-`; keep secret and rotate through an approved procedure. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated explicit hostnames; no empty entries, wildcards, URL schemes, paths, or embedded spaces. |
| `DJANGO_HTTPS_REDIRECT` | Required strict `true` or `false`. `true` enables Django HTTPS redirect; `false` explicitly disables it. |
| `DJANGO_HSTS_SECONDS` | Required non-negative integer. `0` disables HSTS; positive values enable HSTS and require `DJANGO_HTTPS_REDIRECT=true`. Choose duration only after deployment review. |
| `DJANGO_EMAIL_BACKEND` | Required explicit Django email backend path; the development console backend is rejected. Configure provider/SMTP details using the selected backend's approved settings and secret store. |

`EMAIL_BACKEND` routes Django mail through the backend selected in
`MAILERS["default"]["BACKEND"]`, so the development console backend and
test-time mailer overrides are honored. Optional SMTP settings are read from
`DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`,
`DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_USE_TLS`, and
`DJANGO_EMAIL_USE_SSL`. Set
`DJANGO_DEFAULT_FROM_EMAIL` to the approved sender address. Keep provider
credentials in the deployment secret store. The reminder email command is
manual/externally scheduled and is not started by the web application.

Production settings always enable secure-only session and CSRF cookies and
disable debug mode. No reverse-proxy SSL header is configured or trusted.
`DJANGO_HTTPS_REDIRECT=true` assumes Django receives requests with a scheme it
can recognize as HTTPS. If TLS terminates at a reverse proxy, the proxy and
trusted-scheme design must be explicitly reviewed before enabling this option;
do not set `SECURE_PROXY_SSL_HEADER` merely to suppress redirect loops.

Hostnames, TLS termination and proxy design, HTTPS redirect policy, HSTS
duration and scope, and the production email provider remain deployment
decisions requiring approval. The settings do not invent those values or
credentials. Production startup fails if required inputs are missing or
malformed; error messages identify setting names, not secret contents.

Before deployment, run the Django deployment checks with the production
environment and approved values:

```powershell
.\.venv\Scripts\python.exe .\src\manage.py check --deploy
```

Resolve or explicitly document each remaining warning against the actual
hosting and TLS configuration. This project does not define a production
server, reverse proxy, domain, certificate, or email provider.
