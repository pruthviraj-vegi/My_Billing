# ------------------------------------------------------------------
# File: accounts/forms.py
# ------------------------------------------------------------------
from django import forms
from .models import CustomUser


class CustomUserForm(forms.ModelForm):
    """Unified form for creating and editing users."""

    class Meta:
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "role",
            "is_active",
            "address",
        )
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter first name",
                    "autofocus": True,
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter last name",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter phone number",
                    "maxlength": "15",
                }
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "Enter email address"}
            ),
            "role": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "address": forms.Textarea(
                attrs={"class": "form-textarea", "placeholder": "Enter address"}
            ),
        }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            raise forms.ValidationError("Phone number is required.")

        # Check for duplicate phone number, excluding current instance
        existing_user = CustomUser.objects.filter(phone_number=phone_number)
        if self.instance and self.instance.pk:
            existing_user = existing_user.exclude(pk=self.instance.pk)

        if existing_user.exists():
            raise forms.ValidationError(
                "This phone number is already in use by another user."
            )

        return phone_number

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if not full_name or not full_name.strip():
            raise forms.ValidationError("Full name is required.")
        return full_name.strip()

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            # Check for duplicate email, excluding current instance
            existing_user = CustomUser.objects.filter(email=email)
            if self.instance and self.instance.pk:
                existing_user = existing_user.exclude(pk=self.instance.pk)

            if existing_user.exists():
                raise forms.ValidationError(
                    "This email address is already in use by another user."
                )
        return email or None  # Convert empty string to None


class PasswordResetForm(forms.Form):
    """Simple password reset form with minimal validation."""

    new_password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter new password",
                "autofocus": True,
            }
        ),
        label="New Password",
    )

    confirm_password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Confirm new password",
            }
        ),
        label="Confirm Password",
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def clean_new_password(self):
        new_password = self.cleaned_data.get("new_password")
        if not new_password:
            raise forms.ValidationError("Password is required.")
        return new_password
