from django import forms
from .models import Invoice, AuditTable, InvoiceAudit, ReturnInvoice
from django.utils import timezone
from datetime import timedelta
from user.models import CustomUser
from customer.models import Customer


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "customer",
            "amount",
            "discount_amount",
            "payment_type",
            "advance_amount",
            "payment_method",
            "invoice_date",
            "due_date",
            "notes",
        ]
        widgets = {
            "customer": forms.Select(
                attrs={"class": "form-select", "placeholder": "Select customer"}
            ),
            "payment_type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "readonly": True,
                }
            ),
            "discount_amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                    "required": False,
                    "autofocus": True,
                }
            ),
            "advance_amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                    "readonly": True,
                    "required": False,
                }
            ),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "invoice_date": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "due_date": forms.DateTimeInput(
                attrs={
                    "class": "form-input",
                    "type": "datetime-local",
                    "default": timezone.now(),
                    "readonly": True,
                    "required": False,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "placeholder": "Enter any additional notes",
                    "rows": "3",
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

        # Make due_date not required by default (will be handled in clean method)
        self.fields["due_date"].required = False

        # Set initial HSN code - first active one if exists, else None
        if not self.instance.pk:  # Only for new products (not editing)
            customer = Customer.objects.first()
            if customer:
                self.fields["customer"].initial = customer

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")
        discount_amount = cleaned_data.get("discount_amount")
        advance_amount = cleaned_data.get("advance_amount")
        payment_type = cleaned_data.get("payment_type")
        due_date = cleaned_data.get("due_date")

        # Handle empty fields by setting them to 0
        if discount_amount is None or discount_amount == "":
            cleaned_data["discount_amount"] = 0
        if advance_amount is None or advance_amount == "":
            cleaned_data["advance_amount"] = 0

        # For cash invoices, set due_date to None, advance_amount to 0, and payment_status to PAID
        if payment_type == Invoice.PaymentType.CASH:
            cleaned_data["due_date"] = None
            cleaned_data["advance_amount"] = 0
            # Note: payment_status will be set in the model's save method
        # For credit invoices, due_date is required
        elif payment_type == Invoice.PaymentType.CREDIT and not due_date:
            raise forms.ValidationError("Due date is required for credit invoices")

        # Validate discount doesn't exceed amount
        if (
            amount
            and cleaned_data["discount_amount"]
            and cleaned_data["discount_amount"] > amount
        ):
            raise forms.ValidationError("Discount amount cannot exceed invoice amount")

        return cleaned_data

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount and amount < 0:
            raise forms.ValidationError("Amount cannot be negative")
        return amount

    def clean_discount_amount(self):
        discount_amount = self.cleaned_data.get("discount_amount")
        if discount_amount is None or discount_amount == "":
            return 0
        if discount_amount < 0:
            raise forms.ValidationError("Discount amount cannot be negative")
        return discount_amount

    def clean_advance_amount(self):
        advance_amount = self.cleaned_data.get("advance_amount")
        if advance_amount is None or advance_amount == "":
            return 0
        if advance_amount < 0:
            raise forms.ValidationError("Advance amount cannot be negative")
        return advance_amount

    def clean_due_date(self):
        due_date = self.cleaned_data.get("due_date")
        if due_date is None or due_date == "":
            return timezone.now() + timedelta(days=30)
        return due_date


class AuditTableForm(forms.ModelForm):
    """Form for creating audit table sessions"""

    class Meta:
        model = AuditTable
        fields = [
            "title",
            "description",
            "audit_type",
            "start_date",
            "end_date",
            "financial_year",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter audit session title...",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "placeholder": "Describe the purpose of this audit session...",
                    "rows": 3,
                }
            ),
            "audit_type": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "financial_year": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g., 24-25"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required field indicators
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"


class AuditFilterForm(forms.Form):
    """Form for filtering audit trail records"""

    # Search field
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Search by invoice number, reason, or user name...",
            }
        ),
    )

    # Date range fields
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )

    # Filter fields
    financial_year = forms.ChoiceField(
        required=False,
        choices=[("", "All Financial Years")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate financial year choices dynamically
        current_year = timezone.now().year
        fy_choices = [("", "All Financial Years")]

        # Add current and previous financial years
        for year in range(current_year - 2, current_year + 1):
            fy_choices.append((str(year), str(year)))

        self.fields["financial_year"].choices = fy_choices

        # Populate changed_by queryset with users who have made audit records
        audit_users = CustomUser.objects.filter(
            id__in=InvoiceAudit.objects.values_list("changed_by", flat=True).distinct()
        ).order_by("full_name")
        self.fields["changed_by"].queryset = audit_users


class ReturnInvoiceForm(forms.ModelForm):
    """Form for creating return invoices"""

    class Meta:
        model = ReturnInvoice
        fields = [
            "invoice",
            "refund_type",
            "status",
            "reason",
            "total_amount",
            "refund_amount",
            "restocking_fee",
            "return_date",
            "notes",
            "internal_notes",
        ]
        widgets = {
            "invoice": forms.Select(
                attrs={"class": "form-select", "placeholder": "Select original invoice"}
            ),
            "refund_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Select(attrs={"class": "form-select"}),
            "total_amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "refund_amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "restocking_fee": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "return_date": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "placeholder": "Enter any additional notes for the customer",
                    "rows": "3",
                }
            ),
            "internal_notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "placeholder": "Enter internal notes for staff only",
                    "rows": "3",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required field indicators
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label} *"

        # Set default values
        self.fields["status"].initial = ReturnInvoice.RefundStatus.PENDING
        self.fields["refund_type"].initial = ReturnInvoice.RefundType.CASH_REFUND
        self.fields["reason"].initial = ReturnInvoice.RefundReason.CUSTOMER_REQUEST
        self.fields["return_date"].initial = timezone.now()

        # Make some fields not required
        self.fields["restocking_fee"].required = False
        self.fields["notes"].required = False
        self.fields["internal_notes"].required = False

    def clean(self):
        cleaned_data = super().clean()
        total_amount = cleaned_data.get("total_amount")
        refund_amount = cleaned_data.get("refund_amount")
        restocking_fee = cleaned_data.get("restocking_fee")

        # Handle empty fields by setting them to 0
        if restocking_fee is None or restocking_fee == "":
            cleaned_data["restocking_fee"] = 0

        # Validate refund amount doesn't exceed total amount
        if total_amount and refund_amount and refund_amount > total_amount:
            raise forms.ValidationError("Refund amount cannot exceed total amount")

        return cleaned_data

    def clean_total_amount(self):
        total_amount = self.cleaned_data.get("total_amount")
        if total_amount and total_amount < 0:
            raise forms.ValidationError("Total amount cannot be negative")
        return total_amount

    def clean_refund_amount(self):
        refund_amount = self.cleaned_data.get("refund_amount")
        if refund_amount is None or refund_amount == "":
            return 0
        if refund_amount < 0:
            raise forms.ValidationError("Refund amount cannot be negative")
        return refund_amount

    def clean_restocking_fee(self):
        restocking_fee = self.cleaned_data.get("restocking_fee")
        if restocking_fee is None or restocking_fee == "":
            return 0
        if restocking_fee < 0:
            raise forms.ValidationError("Restocking fee cannot be negative")
        return restocking_fee

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Auto-populate customer from the selected invoice
        if instance.invoice:
            instance.customer = instance.invoice.customer
        if commit:
            instance.save()
        return instance
