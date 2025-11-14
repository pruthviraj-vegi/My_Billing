from django import forms
from .models import Customer, Payment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone_number", "email", "address", "referred_by"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter full name",
                    "autofocus": True,
                }
            ),
            "phone_number": forms.NumberInput(
                attrs={
                    "placeholder": "Enter 10-digit phone number",
                    "maxlength": "10",
                    "pattern": "[0-9]{10}",
                }
            ),
            "email": forms.EmailInput(
                attrs={ "placeholder": "Enter email address"}
            ),
            "address": forms.Textarea(
                attrs={
                    "placeholder": "Enter complete address",
                    "rows": "4",
                }
            ),
            "referred_by": forms.Select(
                attrs={
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        # Add required field indicators
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

        # Adding form-control class to all fields
        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-input"

        # Referred by is optional; exclude self from choices if editing
        self.fields["referred_by"].required = False
        if self.instance and getattr(self.instance, "pk", None):
            self.fields["referred_by"].queryset = Customer.objects.exclude(pk=self.instance.pk)
        else:
            self.fields["referred_by"].queryset = Customer.objects.all()

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            raise forms.ValidationError("Phone number is required.")

        # Check if phone number is exactly 10 digits
        if not phone_number.isdigit() or len(phone_number) != 10:
            raise forms.ValidationError(
                "Phone number must be exactly 10 digits (e.g., 9876543210)."
            )

        # Check for duplicate phone number, excluding current instance
        existing_customer = Customer.objects.filter(phone_number=phone_number)
        if self.instance:
            existing_customer = existing_customer.exclude(pk=self.instance.pk)

        if existing_customer.exists():
            raise forms.ValidationError(
                "This phone number is already in use by another customer."
            )

        return phone_number


    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and not "@" in email:
            raise forms.ValidationError("Please enter a valid email address.")
        return email.lower() if email else email


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["customer", "payment_type", "amount", "method", "transaction_id", "payment_date", "notes"]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "payment_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "method": forms.Select(attrs={"class": "form-select"}),
            "transaction_id": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Transaction reference (optional)",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": "3", "placeholder": "Payment notes"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)
        
        if self.customer:
            self.fields["customer"].initial = self.customer
            # Create a custom widget that shows customer name but is read-only
            self.fields["customer"].widget.attrs['readonly'] = True

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


