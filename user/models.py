# ------------------------------------------------------------------
# File: accounts/models.py
# ------------------------------------------------------------------
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager
from base.utility import StringProcessor
from decimal import Decimal
from django.conf import settings

User = settings.AUTH_USER_MODEL


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MANAGER = "MANAGER", "Manager"
        CASHIER = "CASHIER", "Cashier"
        STAFF = "STAFF", "Staff"
        SALESPERSON = "SALESPERSON", "Salesperson"

    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)

    profile_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    email = models.EmailField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("Email Address (Optional)"),
        help_text=_("Optional email address. Leave blank if not needed."),
    )
    phone_number = models.CharField(
        max_length=15, unique=True, verbose_name=_("Phone Number")
    )
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CASHIER)
    address = models.TextField(max_length=255, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    # --- ADDED TO FIX MIGRATION ERROR ---
    # These fields are required to avoid clashes with the default User model's
    # reverse accessors when you have a custom user model.
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions "
            "granted to each of their groups."
        ),
        related_name="customuser_set",  # Unique related_name
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="customuser_permissions_set",  # Unique related_name
        related_query_name="user",
    )

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name"]
    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        # Convert empty email strings to None to avoid unique constraint violations
        if self.email == "":
            self.email = None

        self.first_name = StringProcessor(self.first_name).toTitle()
        self.last_name = StringProcessor(self.last_name).toTitle()
        if self.email:
            self.email = StringProcessor(self.email).toLowercase()
        self.address = StringProcessor(self.address).toTitle()

        self.profile_id = StringProcessor(self.first_name + self.last_name).toTitle()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone_number})"

    @property
    def is_owner(self):
        return self.role == self.Roles.OWNER

    @property
    def is_manager(self):
        return self.role in [self.Roles.OWNER, self.Roles.MANAGER]

    @property
    def username(self):
        return self.first_name

    @property
    def full_name(self):
        return str(self.first_name) + " " + str(self.last_name)


class Salary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="salaries")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)  # null = current salary
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_salaries",
    )

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.user.full_name} - {self.amount} ({self.effective_from})"


class LoginEvent(models.Model):
    """Audit log of user login/logout events."""

    class EventType(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="login_events"
    )
    event_type = models.CharField(max_length=10, choices=EventType.choices)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = [
            models.Index(fields=["user", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.event_type} {self.occurred_at.isoformat()}"
