# ------------------------------------------------------------------
# File: accounts/forms.py
# ------------------------------------------------------------------
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter your phone number",
                "type": "tel",
            }
        ),
        label="Phone Number",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-input", "placeholder": "Enter your password"}
        ),
        label="Password",
    )
    remember = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "checkbox-input"}),
        label="Remember me",
    )

    def clean(self):
        # Get the phone number from the username field (which is actually phone_number)
        phone_number = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if phone_number and password:
            # Try to authenticate with phone number
            user = authenticate(username=phone_number, password=password)
            if user is None:
                raise forms.ValidationError(
                    "Invalid phone number or password. Please try again."
                )
            if not user.is_active:
                raise forms.ValidationError(
                    "This account is inactive. Please contact administrator."
                )
            self.user_cache = user
        return self.cleaned_data