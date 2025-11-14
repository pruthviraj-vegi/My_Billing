from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Product,
    ProductVariant,
    Category,
    Color,
    Size,
    ClothType,
    UOM,
    GSTHsnCode,
    SupplierInvoice,
    InventoryLog,
)


class ProductForm(forms.ModelForm):
    """Form for creating a product"""

    class Meta:
        model = Product
        exclude = ["status"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter product name",
                }
            ),
            "brand": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter brand name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter product description",
                    "rows": 4,
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-input", "placeholder": "Select category"}
            ),
            "cloth_type": forms.Select(
                attrs={"class": "form-input", "placeholder": "Select cloth type"}
            ),
            "uom": forms.Select(
                attrs={"class": "form-input", "placeholder": "Select UOM"}
            ),
            "hsn_code": forms.Select(
                attrs={
                    "class": "form-input",
                    "placeholder": "Select Hsn Code",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Restrict HSN field to active codes and set a sensible initial
        try:
            active_hsn_qs = GSTHsnCode.objects.filter(is_active=True)
            self.fields["hsn_code"].queryset = active_hsn_qs

            if active_hsn_qs.exists():
                if not self.instance.pk:
                    self.fields["hsn_code"].initial = active_hsn_qs.first()
            else:
                # Gracefully handle empty table so other parts of the app keep working
                self.fields["hsn_code"].help_text = (
                    "Add an active GST HSN code before assigning it to a product."
                )
        except Exception as e:
            # Handle case where table doesn't exist yet (during migrations)
            if "does not exist" in str(e) or "relation" in str(e):
                pass
            else:
                raise


class VariantForm(forms.ModelForm):
    """Form for creating a variant"""

    supplier_invoice = forms.ModelChoiceField(
        queryset=SupplierInvoice.objects.filter(supplier__is_deleted=False).order_by(
            "-created_at"
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-input"}),
        help_text="Select the supplier invoice for this variant (optional)",
    )

    class Meta:
        model = ProductVariant
        exclude = [
            "product",
            "barcode",
            "damaged_quantity",
            # "commission_percentage"
            "status",
            "created_by",
            "extra_attributes",
        ]
        widgets = {
            "supplier": forms.Select(
                attrs={"class": "form-input", "placeholder": "Select supplier"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "Enter quantity"}
            ),
            "minimum_quantity": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "Enter minimum quantity"}
            ),
            "discount_percentage": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter discount percentage",
                }
            ),
            "gst_percentage": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "Enter GST percentage"}
            ),
            # "commission_percentage": forms.NumberInput(
            #     attrs={
            #         "class": "form-input",
            #         "placeholder": "Enter commission percentage",
            #     }
            # ),
            "purchase_price": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "Enter purchase price"}
            ),
            "mrp": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "Enter selling price"}
            ),
            "size": forms.Select(
                attrs={"class": "form-input", "placeholder": "Select size"}
            ),
            # "color": forms.Select(
            #     attrs={"class": "form-input", "placeholder": "Select color"}
            # ),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than 0")
        return quantity

    def clean_purchase_price(self):
        purchase_price = self.cleaned_data.get("purchase_price")
        if purchase_price is not None and purchase_price <= 0:
            raise forms.ValidationError("Purchase price must be greater than 0")
        return purchase_price

    def clean_mrp(self):
        mrp = self.cleaned_data.get("mrp")
        if mrp is not None and mrp <= 0:
            raise forms.ValidationError("Selling price must be greater than 0")
        return mrp

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""

    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter category name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Enter category description",
                }
            ),
        }


class ColorForm(forms.ModelForm):
    """Form for creating and editing colors"""

    class Meta:
        model = Color
        fields = ["name", "hex_code"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter color name",
                    "autofocus": True,
                }
            ),
            "hex_code": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "#FF0000",
                    "pattern": "#[0-9A-Fa-f]{6}",
                }
            ),
        }

    def clean_hex_code(self):
        hex_code = self.cleaned_data.get("hex_code")
        if hex_code:
            if not hex_code.startswith("#"):
                hex_code = "#" + hex_code
            if len(hex_code) != 7 or not all(
                c in "0123456789ABCDEFabcdef" for c in hex_code[1:]
            ):
                raise ValidationError(
                    "Please enter a valid hex color code (e.g., #FF0000)"
                )
        return hex_code


class SizeForm(forms.ModelForm):
    """Form for creating and editing sizes"""

    class Meta:
        model = Size
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter size name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Enter size description",
                }
            ),
        }


class ClothTypeForm(forms.ModelForm):
    """Form for creating and editing cloth types"""

    class Meta:
        model = ClothType
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter cloth type name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Enter cloth type description",
                }
            ),
        }


class UOMForm(forms.ModelForm):
    """Form for creating and editing UOM (Unit of Measurement)"""

    class Meta:
        model = UOM
        fields = [
            "name",
            "short_code",
            "category",
            "base_unit",
            "conversion_factor",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter UOM name (e.g., Piece, Dozen, Meter)",
                    "autofocus": True,
                }
            ),
            "short_code": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter short code (e.g., pcs, doz, m)",
                    "maxlength": "10",
                }
            ),
            "category": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter category (e.g., Quantity, Weight, Length)",
                }
            ),
            "base_unit": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "conversion_factor": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter conversion factor (e.g., 12 for dozen)",
                    "step": "0.0001",
                    "min": "0.0001",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Enter UOM description (optional)",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def clean_conversion_factor(self):
        conversion_factor = self.cleaned_data.get("conversion_factor")
        if conversion_factor is not None and conversion_factor <= 0:
            raise ValidationError("Conversion factor must be greater than 0")
        return conversion_factor

    def clean_short_code(self):
        short_code = self.cleaned_data.get("short_code")
        if short_code:
            short_code = short_code.upper()
        return short_code


class StockInForm(forms.ModelForm):
    """Form specifically for stock in operations"""

    class Meta:
        model = InventoryLog
        fields = [
            "variant",
            "quantity_change",
            "purchase_price",
            "mrp",
            "supplier_invoice",
            "notes",
        ]
        widgets = {
            "variant": forms.Select(attrs={"class": "form-input"}),
            "quantity_change": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "step": "0.01",
                    "autofocus": True,
                    "placeholder": "Enter quantity",
                }
            ),
            "purchase_price": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01"}
            ),
            "mrp": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "supplier_invoice": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.variant = kwargs.pop("variant", None)  # Get variant from kwargs
        super().__init__(*args, **kwargs)

        # If variant is provided, hide the variant field and set it
        if self.variant:
            self.fields["variant"].widget = forms.HiddenInput()
            self.fields["variant"].initial = self.variant
            self.fields["variant"].required = False
        else:
            # Only show variant dropdown if no variant provided
            self.fields["variant"].queryset = ProductVariant.objects.filter(
                is_deleted=False
            )

        # For stock-in operations, show all active supplier invoices
        # This allows linking to any supplier invoice (same product from different suppliers)
        self.fields["supplier_invoice"].queryset = SupplierInvoice.objects.filter(
            supplier__is_deleted=False
        )

        # Make supplier_invoice optional
        self.fields["supplier_invoice"].required = False
        # Make purchase price required for stock in
        self.fields["purchase_price"].required = True

    def clean(self):
        cleaned_data = super().clean()
        quantity_change = cleaned_data.get("quantity_change")
        purchase_price = cleaned_data.get("purchase_price")
        mrp = cleaned_data.get("mrp")
        supplier_invoice = cleaned_data.get("supplier_invoice")
        variant = (
            cleaned_data.get("variant") or self.variant
        )  # Use passed variant if available

        # Validate variant is available
        if not variant:
            raise forms.ValidationError("Please select a product variant.")

        # For stock-in operations, we don't validate supplier invoice contains the variant
        # This allows linking to any supplier invoice (same product from different suppliers)

        # Allow zero values for all fields
        if quantity_change is not None and quantity_change <= 0:
            raise forms.ValidationError("Stock in quantity cannot be negative.")

        if purchase_price is not None and purchase_price < 0:
            raise forms.ValidationError("Purchase price cannot be negative.")

        if mrp is not None and mrp < 0:
            raise forms.ValidationError("Selling price cannot be negative.")

        return cleaned_data

    def save(self, commit=True):
        """Override save to set variant and transaction_type"""
        instance = super().save(commit=False)

        # Set variant if passed from view
        if self.variant and not instance.variant:
            instance.variant = self.variant

        # Set transaction type for stock in
        instance.transaction_type = InventoryLog.TransactionTypes.STOCK_IN

        if commit:
            instance.save()
        return instance


class InventoryAdjustmentForm(forms.ModelForm):
    """Unified form for inventory adjustments (in, out, damage)"""

    class Meta:
        model = InventoryLog
        fields = [
            "variant",
            "supplier_invoice",
            "quantity_change",
            "notes",
        ]
        widgets = {
            "variant": forms.Select(attrs={"class": "form-input"}),
            "quantity_change": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "autofocus": True}
            ),
            "supplier_invoice": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.adjustment_type = kwargs.pop("adjustment_type", "adjustment_in")
        self.variant = kwargs.pop("variant", None)  # Get variant from kwargs
        super().__init__(*args, **kwargs)

        # If variant is provided, hide the variant field and set it
        if self.variant:
            self.fields["variant"].widget = forms.HiddenInput()
            self.fields["variant"].initial = self.variant
            self.fields["variant"].required = False
        else:
            # Only show variant dropdown if no variant provided
            self.fields["variant"].queryset = ProductVariant.objects.filter(
                is_deleted=False
            )

        # Filter supplier invoices based on variant and operation type
        if self.variant:
            # For damage operations, only show supplier invoices that contain this variant
            if self.adjustment_type == "damage":
                self.fields["supplier_invoice"].queryset = (
                    SupplierInvoice.objects.filter(
                        supplier__is_deleted=False, inventory_logs__variant=self.variant
                    ).distinct()
                )
            else:
                # For other operations, show all active supplier invoices
                self.fields["supplier_invoice"].queryset = (
                    SupplierInvoice.objects.filter(supplier__is_deleted=False)
                )
        else:
            # If no variant provided, show all active supplier invoices
            self.fields["supplier_invoice"].queryset = SupplierInvoice.objects.filter(
                supplier__is_deleted=False
            )

        # Make supplier_invoice optional
        self.fields["supplier_invoice"].required = False

        # Set labels based on adjustment type
        labels = {
            "adjustment_in": {
                "quantity_change": "Quantity to Add",
                "notes": "Reason for Adjustment",
            },
            "adjustment_out": {
                "quantity_change": "Quantity to Remove",
                "notes": "Reason for Adjustment",
            },
            "damage": {
                "quantity_change": "Quantity to Mark as Damaged",
                "notes": "Damage Details",
            },
        }

        # Apply appropriate labels
        if self.adjustment_type in labels:
            for field_name, label in labels[self.adjustment_type].items():
                if field_name in self.fields:
                    self.fields[field_name].label = label

    def clean(self):
        cleaned_data = super().clean()
        quantity_change = cleaned_data.get("quantity_change")
        supplier_invoice = cleaned_data.get("supplier_invoice")
        variant = (
            cleaned_data.get("variant") or self.variant
        )  # Use passed variant if available

        # Validate variant is available (either from form or passed)
        if not variant:
            raise forms.ValidationError("Please select a product variant.")

        # Validate supplier invoice contains this variant (if supplier invoice is selected)
        if supplier_invoice and variant:
            if not supplier_invoice.inventory_logs.filter(variant=variant).exists():
                raise forms.ValidationError(
                    f"The selected supplier invoice does not contain the variant '{variant.full_name}'. "
                    "Please select a supplier invoice that contains this variant."
                )

        # Validate quantity based on adjustment type
        if quantity_change is not None:
            if quantity_change <= 0:
                error_messages = {
                    "adjustment_in": "Adjustment in quantity must be positive.",
                    "adjustment_out": "Adjustment out quantity must be positive.",
                    "damage": "Damage quantity must be positive.",
                }
                raise forms.ValidationError(
                    error_messages.get(
                        self.adjustment_type, "Quantity must be positive."
                    )
                )

            # For adjustment_out and damage, check if sufficient stock exists
            if self.adjustment_type in ["adjustment_out", "damage"]:
                if variant.quantity < quantity_change:
                    raise forms.ValidationError(
                        f"Insufficient stock. Available: {variant.quantity}, "
                        f"Requested: {quantity_change}"
                    )

        return cleaned_data

    def save(self, commit=True):
        """Override save to set transaction_type based on adjustment_type"""
        instance = super().save(commit=False)

        # Set variant if passed from view
        if self.variant and not instance.variant:
            instance.variant = self.variant

        # Map adjustment_type to transaction_type
        transaction_type_mapping = {
            "adjustment_in": InventoryLog.TransactionTypes.ADJUSTMENT_IN,
            "adjustment_out": InventoryLog.TransactionTypes.ADJUSTMENT_OUT,
            "damage": InventoryLog.TransactionTypes.DAMAGE,
        }

        instance.transaction_type = transaction_type_mapping.get(
            self.adjustment_type, InventoryLog.TransactionTypes.ADJUSTMENT_IN
        )

        if commit:
            instance.save()
        return instance


# Convenience classes for backward compatibility
class AdjustmentInForm(InventoryAdjustmentForm):
    """Form for adjustment in operations"""

    def __init__(self, *args, **kwargs):
        kwargs["adjustment_type"] = "adjustment_in"
        super().__init__(*args, **kwargs)


class AdjustmentOutForm(InventoryAdjustmentForm):
    """Form for adjustment out operations"""

    def __init__(self, *args, **kwargs):
        kwargs["adjustment_type"] = "adjustment_out"
        super().__init__(*args, **kwargs)


class DamageForm(InventoryAdjustmentForm):
    """Form for damage operations"""

    def __init__(self, *args, **kwargs):
        kwargs["adjustment_type"] = "damage"
        super().__init__(*args, **kwargs)


class GSTHsnCodeForm(forms.ModelForm):
    """Form for creating and editing GST HSN Code"""

    class Meta:
        model = GSTHsnCode
        fields = [
            "code",
            "gst_percentage",
            "cess_rate",
            "effective_from",
            "description",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter HSN Code (e.g., 61091000)",
                    "autofocus": True,
                    "maxlength": "8",
                }
            ),
            "gst_percentage": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter GST percentage (e.g., 12.00)",
                    "step": "0.01",
                    "min": "0.00",
                    "max": "40.00",
                }
            ),
            "cess_rate": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter Cess rate (e.g., 0.00)",
                    "step": "0.01",
                    "min": "0.00",
                    "max": "25.00",
                }
            ),
            "effective_from": forms.DateInput(
                attrs={
                    "class": "form-input",
                    "type": "date",
                    "placeholder": "Select effective date",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Enter HSN code description (optional)",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code")
        if code:
            # Ensure code is numeric and 6-8 digits
            if not code.isdigit():
                raise ValidationError("HSN Code must contain only numbers")
            if len(code) < 6 or len(code) > 8:
                raise ValidationError("HSN Code must be 6-8 digits long")
        return code

    def clean_gst_percentage(self):
        gst_percentage = self.cleaned_data.get("gst_percentage")
        if gst_percentage is not None and (gst_percentage < 0 or gst_percentage > 40):
            raise ValidationError("GST percentage must be between 0.00 and 40.00")
        return gst_percentage

    def clean_cess_rate(self):
        cess_rate = self.cleaned_data.get("cess_rate")
        if cess_rate is not None and (cess_rate < 0 or cess_rate > 25):
            raise ValidationError("Cess rate must be between 0.00 and 25.00")
        return cess_rate
