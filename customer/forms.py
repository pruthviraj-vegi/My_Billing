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
            "phone_number": forms.TextInput(
                attrs={
                    "type": "tel",
                    "placeholder": "Enter 10-digit phone number",
                    "maxlength": "10",
                    "pattern": "[0-9]{10}",
                    "inputmode": "numeric",
                }
            ),
            "email": forms.EmailInput(attrs={"placeholder": "Enter email address"}),
            "address": forms.Textarea(
                attrs={
                    "placeholder": "Enter complete address",
                    "rows": "4",
                }
            ),
            "referred_by": forms.Select(attrs={}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required field indicators
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

        # Adding form-control class to all fields
        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-input"

        # Override maxlength for phone_number to enforce 10 digits
        self.fields["phone_number"].widget.attrs["maxlength"] = "10"

        # Referred by is optional; exclude self from choices if editing
        self.fields["referred_by"].required = False
        if self.instance.pk:
            self.fields["referred_by"].queryset = Customer.objects.exclude(
                pk=self.instance.pk
            )
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
        if self.instance.pk:
            existing_customer = existing_customer.exclude(pk=self.instance.pk)

        if existing_customer.exists():
            raise forms.ValidationError(
                "This phone number is already in use by another customer."
            )

        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            # Additional validation (Django's EmailField already validates basic format)
            if "@" not in email:
                raise forms.ValidationError("Please enter a valid email address.")
            return email.lower()
        return email


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "customer",
            "payment_type",
            "amount",
            "method",
            "transaction_id",
            "payment_date",
            "notes",
        ]
        widgets = {
            "customer": forms.Select(
                attrs={
                    "placeholder": "Select customer",
                    "help_text": "Select the customer for the payment",
                }
            ),
            "payment_type": forms.Select(
                attrs={
                    "placeholder": "Select payment type",
                    "help_text": "Select the payment type for the payment",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "placeholder": "Enter amount",
                    "autofocus": True,
                    "help_text": "Enter the amount for the payment",
                }
            ),
            "method": forms.Select(attrs={}),
            "transaction_id": forms.TextInput(
                attrs={
                    "placeholder": "Transaction reference (optional)",
                    "help_text": "Enter the transaction reference for the payment",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "help_text": "Select the date and time for the payment",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Enter payment notes",
                    "rows": "2",
                    "help_text": "Enter the notes for the payment",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)

        # Add required field indicators
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

        # Apply appropriate classes to fields
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "form-textarea"
            else:
                widget.attrs["class"] = "form-input"

        # Handle customer field if provided
        if self.customer:
            self.fields["customer"].initial = self.customer
            # Disable the field to prevent selection (readonly doesn't work on select elements)
            self.fields["customer"].widget.attrs["readonly"] = True

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount
