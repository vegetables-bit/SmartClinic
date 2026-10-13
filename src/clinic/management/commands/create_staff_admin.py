from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from clinic.models import StaffProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create the first Smart Clinic staff administrator account."

    def handle(self, *args, **options):
        username = input("Username: ").strip()
        email = input("Email address: ").strip()
        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()

        if not username:
            raise CommandError("A username is required.")
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError("An account with this username already exists.")

        password = getpass("Password (input hidden): ")
        confirmation = getpass("Confirm password (input hidden): ")
        if password != confirmation:
            raise CommandError("The passwords do not match.")

        candidate = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                StaffProfile.objects.create(
                    account=user,
                    role=StaffProfile.Role.ADMINISTRATOR,
                    is_active=True,
                )
        except IntegrityError as error:
            raise CommandError(
                "The administrator account could not be created because a "
                "unique account or staff identifier conflicted."
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Staff administrator account {user.username!r} created."
            )
        )
