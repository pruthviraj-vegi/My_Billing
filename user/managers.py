# ------------------------------------------------------------------
# File: accounts/managers.py
# ------------------------------------------------------------------
from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    def email_validator(self, email):
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("Please provide a valid email address"))

    def create_user(
        self, full_name, phone_number, password, email=None, **extra_fields
    ):
        if not full_name:
            raise ValueError(_("Users must submit a full name"))
        if not phone_number:
            raise ValueError(_("Users must submit a phone number"))

        if email:
            email = self.normalize_email(email)
            self.email_validator(email)

        user = self.model(
            full_name=full_name, phone_number=phone_number, email=email, **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, full_name, phone_number, password, email=None, **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "OWNER")

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superusers must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superusers must have is_superuser=True"))

        return self.create_user(
            full_name, phone_number, password, email, **extra_fields
        )
