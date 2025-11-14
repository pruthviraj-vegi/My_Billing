from django import forms
from .models import (
    Supplier,
    SupplierInvoice,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "name",
            "contact_person",
            "email",
            "phone",
            "gstin",
            "first_line",
            "second_line",
            "city",
            "state",
            "pincode",
            "country",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Supplier Name",
                    "autofocus": True,
                }
            ),
            "contact_person": forms.TextInput(
                attrs={
                    "placeholder": "Contact Person",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "Enter Email",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "Enter Phone",
                }
            ),
            "gstin": forms.TextInput(
                attrs={
                    "placeholder": "Enter GSTIN",
                }
            ),
            "first_line": forms.TextInput(
                attrs={
                    "placeholder": "Enter First Line",
                }
            ),
            "second_line": forms.TextInput(
                attrs={
                    "placeholder": "Enter Second Line",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "placeholder": "Enter City",
                }
            ),
            "state": forms.TextInput(
                attrs={
                    "placeholder": "Enter State",
                }
            ),
            "pincode": forms.TextInput(
                attrs={
                    "placeholder": "Enter Pincode",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "placeholder": "Enter Country",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Adding form-control class to all fields
        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-input"

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            # Remove any non-digit characters except + and -
            phone = "".join(c for c in phone if c.isdigit() or c in "+-")
        return phone


class SupplierInvoiceForm(forms.ModelForm):
    class Meta:
        model = SupplierInvoice
        fields = [
            "invoice_number",
            "invoice_date",
            "invoice_type",
            "gst_type",
            "sub_total",
            "cgst_amount",
            "igst_amount",
            "adjustment_amount",
            "notes",
        ]
        widgets = {
            "invoice_number": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter Invoice Number",
                    "autofocus": True,
                }
            ),
            "invoice_date": forms.DateTimeInput(
                attrs={
                    "class": "form-input",
                    "type": "datetime-local",
                    "placeholder": "Enter Invoice Date",
                    "value": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                }
            ),
            "invoice_type": forms.Select(attrs={"class": "form-input"}),
            "gst_type": forms.Select(attrs={"class": "form-input"}),
            "sub_total": forms.NumberInput(attrs={"class": "form-input"}),
            "cgst_amount": forms.NumberInput(attrs={"class": "form-input"}),
            "igst_amount": forms.NumberInput(attrs={"class": "form-input"}),
            "adjustment_amount": forms.NumberInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Enter Notes (Optional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop("supplier", None)
        super().__init__(*args, **kwargs)
        self.supplier = supplier

        # Set initial values for GST fields
        if not self.instance.pk:
            self.fields["gst_type"].initial = "CGST_SGST"
            self.fields["sub_total"].initial = 0
            self.fields["cgst_amount"].initial = 0
            self.fields["igst_amount"].initial = 0
            self.fields["adjustment_amount"].initial = 0

        # Add JavaScript event handlers
        for field_name in [
            "sub_total",
            "cgst_amount",
            "igst_amount",
            "adjustment_amount",
        ]:
            self.fields[field_name].widget.attrs.update(
                {
                    "onchange": "updateTotals()",
                    "onkeyup": "updateTotals()",
                }
            )

        self.fields["invoice_type"].widget.attrs.update(
            {
                "onchange": "updateFormState()",
            }
        )

        self.fields["gst_type"].widget.attrs.update(
            {
                "onchange": "updateFormState()",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        invoice_type = cleaned_data.get("invoice_type")
        gst_type = cleaned_data.get("gst_type")
        sub_total = cleaned_data.get("sub_total") or Decimal("0")
        cgst_amount = cleaned_data.get("cgst_amount") or Decimal("0")
        igst_amount = cleaned_data.get("igst_amount") or Decimal("0")
        adjustment_amount = cleaned_data.get("adjustment_amount") or Decimal("0")

        # Validate GST type is required for GST applicable invoices
        if invoice_type == "GST_APPLICABLE" and not gst_type:
            raise ValidationError("GST type is required for GST applicable invoices.")

        # Calculate total amount
        total_amount = sub_total + adjustment_amount

        if invoice_type == "GST_APPLICABLE":
            if gst_type == "CGST_SGST":
                total_amount += cgst_amount * 2  # CGST + SGST (both same amount)
            else:  # IGST
                total_amount += igst_amount

        cleaned_data["total_amount"] = total_amount
        return cleaned_data


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = [
            "amount",
            "method",
            "transaction_id",
            "payment_date",
        ]
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "step": "0.01",
                    "autofocus": True,
                }
            ),
            "method": forms.Select(attrs={"class": "form-input"}),
            "transaction_id": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter Transaction ID",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={
                    "class": "form-input",
                    "type": "datetime-local",
                    "value": datetime.now().strftime("%Y-%m-%dT%H:%M"),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop("supplier", None)
        super().__init__(*args, **kwargs)
        self.supplier = supplier

        # Set initial payment date to current time
        if not self.instance.pk:
            from django.utils import timezone

            self.fields["payment_date"].initial = timezone.now().strftime(
                "%Y-%m-%dT%H:%M"
            )

        # Make transaction_id required for non-cash payments
        self.fields["transaction_id"].required = False

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("method")
        transaction_id = cleaned_data.get("transaction_id")
        new_amount = cleaned_data.get("amount")

        # Require transaction ID for non-cash payments
        if method in ["BANK_TRANSFER", "UPI"] and not transaction_id:
            raise ValidationError(
                f"Transaction ID is required for {method.replace('_', ' ').title()} payments."
            )

        # Prevent reducing payment amount below total allocated amount
        if self.instance.pk and new_amount:
            from django.db.models import Sum

            total_allocated = (
                self.instance.allocations.aggregate(total=Sum("amount_allocated"))[
                    "total"
                ]
                or 0
            )

            if new_amount < total_allocated:
                # Add error class to amount field for highlighting
                self.fields["amount"].widget.attrs[
                    "class"
                ] = "form-input error-highlight"
                raise ValidationError(
                    f"Cannot reduce payment amount below total allocated amount (₹{total_allocated:,.2f}). "
                    f"Please delete or reduce allocations first."
                )

        return cleaned_data


class SupplierPaymentAllocationForm(forms.ModelForm):
    class Meta:
        model = SupplierPaymentAllocation
        fields = [
            "invoice",
            "amount_allocated",
        ]
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-input"}),
            "amount_allocated": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        payment = kwargs.pop("payment", None)
        supplier = kwargs.pop("supplier", None)
        current_allocation = kwargs.pop("current_allocation", None)
        super().__init__(*args, **kwargs)
        self.payment = payment
        self.supplier = supplier
        self.current_allocation = current_allocation

        # Filter invoices to only show unpaid/partially paid invoices for this supplier
        if supplier:
            unpaid_invoices = supplier.invoices.filter(
                status__in=["UNPAID", "PARTIALLY_PAID"]
            ).order_by("invoice_date")

            # Calculate remaining amounts for each invoice
            invoice_choices = []
            for invoice in unpaid_invoices:
                remaining_amount = invoice.total_amount - invoice.paid_amount
                if remaining_amount > 0:
                    invoice_choices.append(
                        (
                            invoice.id,
                            f"{invoice.invoice_number} - {invoice.invoice_date.strftime('%M %d, %Y')} - ₹{remaining_amount:,.2f} remaining",
                        )
                    )

            self.fields["invoice"].choices = [
                ("", "Select an invoice...")
            ] + invoice_choices

        # Set max amount to unallocated amount (consider current allocation if editing)
        if payment:
            available_amount = payment.unallocated_amount
            if self.current_allocation:
                # If editing, add back the current allocation amount
                available_amount += self.current_allocation.amount_allocated

            if available_amount > 0:
                self.fields["amount_allocated"].widget.attrs.update(
                    {
                        "max": str(available_amount),
                        "placeholder": f"Max: ₹{available_amount:,.2f}",
                    }
                )

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get("invoice")
        amount_allocated = cleaned_data.get("amount_allocated")

        if not invoice or not amount_allocated:
            return cleaned_data

        # Check if amount is positive
        if amount_allocated <= 0:
            raise ValidationError("Allocation amount must be greater than zero.")

        # Check if payment has enough unallocated amount (consider current allocation if editing)
        if self.payment:
            available_amount = self.payment.unallocated_amount
            if self.current_allocation:
                # If editing, add back the current allocation amount
                available_amount += self.current_allocation.amount_allocated

            if amount_allocated > available_amount:
                raise ValidationError(
                    f"Allocation amount cannot exceed available amount (₹{available_amount:,.2f})."
                )

        # Check if invoice can accept this allocation (consider current allocation if editing)
        remaining_amount = invoice.total_amount - invoice.paid_amount
        if self.current_allocation and self.current_allocation.invoice == invoice:
            # If editing allocation for the same invoice, add back the current allocation
            remaining_amount += self.current_allocation.amount_allocated

        if amount_allocated > remaining_amount:
            raise ValidationError(
                f"Allocation amount cannot exceed remaining invoice amount (₹{remaining_amount:,.2f})."
            )

        return cleaned_data
