from django import forms
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
import logging

logger = logging.getLogger(__name__)


class ProductForm(forms.ModelForm):
    """Form for creating a product"""

    class Meta:
        model = Product
        exclude = ["status"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter product name",
                }
            ),
            "brand": forms.TextInput(
                attrs={
                    "placeholder": "Enter brand name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "placeholder": "Enter product description",
                    "rows": 3,
                }
            ),
            "category": forms.Select(attrs={"placeholder": "Select category"}),
            "cloth_type": forms.Select(attrs={"placeholder": "Select cloth type"}),
            "uom": forms.Select(attrs={"placeholder": "Select UOM"}),
            "hsn_code": forms.Select(attrs={"placeholder": "Select HSN Code"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required field indicators and form-control class
        for field in self.fields.values():
            if field.required:
                field.label = f"{field.label} *"
            field.widget.attrs["class"] = "form-input"

        # Restrict to active querysets
        self._set_active_queryset("hsn_code", GSTHsnCode)
        self._set_active_queryset("uom", UOM)

    def _set_active_queryset(self, field_name, model):
        """Helper method to set active queryset for a field"""
        try:
            active_qs = model.objects.filter(is_active=True)
            self.fields[field_name].queryset = active_qs

            if active_qs.exists():
                if not self.instance.pk:
                    self.fields[field_name].initial = active_qs.first()
            else:
                model_name = model._meta.verbose_name or model.__name__
                self.fields[field_name].help_text = (
                    f"Add an active {model_name} before assigning it to a product."
                )
        except Exception as e:
            pass

    def clean_brand(self):
        """Validate brand name length"""
        brand = self.cleaned_data.get("brand")
        if brand and len(brand) > 255:
            raise forms.ValidationError(
                "Brand name must be less than 255 characters long"
            )
        return brand

    def clean_name(self):
        """Validate product name length"""
        name = self.cleaned_data.get("name")
        if name and len(name) > 255:
            raise forms.ValidationError(
                "Product name must be less than 255 characters long"
            )
        return name


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
            "status",
            "created_by",
            "extra_attributes",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"placeholder": "Select supplier"}),
            "quantity": forms.NumberInput(
                attrs={"placeholder": "Enter quantity", "step": "1"}
            ),
            "minimum_quantity": forms.NumberInput(
                attrs={"placeholder": "Enter minimum quantity", "step": "1"}
            ),
            "discount_percentage": forms.NumberInput(
                attrs={"placeholder": "Enter discount percentage", "step": "1"}
            ),
            "commission_percentage": forms.NumberInput(
                attrs={"placeholder": "Enter commission percentage", "step": "1"}
            ),
            "purchase_price": forms.NumberInput(
                attrs={"placeholder": "Enter purchase price", "step": "1"}
            ),
            "mrp": forms.NumberInput(
                attrs={"placeholder": "Enter selling price", "step": "1"}
            ),
            "size": forms.Select(attrs={"placeholder": "Select size"}),
            "color": forms.Select(attrs={"placeholder": "Select color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required field indicators and form-control class
        for field in self.fields.values():
            if field.required:
                field.label = f"{field.label} *"
            field.widget.attrs["class"] = "form-input"

        try:
            if not self.instance.pk:
                self.fields["commission_percentage"].initial = 1
        except Exception as e:
            logger.error(f"Failed to set initial commission percentage: {e}")

    def _validate_positive_number(self, value, field_name, error_message):
        """Helper method to validate positive numbers"""
        if value is not None and value <= 0:
            raise forms.ValidationError(error_message)
        return value

    def clean_quantity(self):
        """Validate quantity is greater than 0"""
        return self._validate_positive_number(
            self.cleaned_data.get("quantity"),
            "quantity",
            "Quantity must be greater than 0",
        )

    def clean_purchase_price(self):
        """Validate purchase price is greater than 0"""
        return self._validate_positive_number(
            self.cleaned_data.get("purchase_price"),
            "purchase_price",
            "Purchase price must be greater than 0",
        )

    def clean_mrp(self):
        """Validate selling price (MRP) is greater than 0"""
        return self._validate_positive_number(
            self.cleaned_data.get("mrp"),
            "mrp",
            "Selling price must be greater than 0",
        )


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""

    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter category name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Enter category description",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to all fields
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

    def clean_name(self):
        """Ensure category name is unique (case-insensitive)"""
        name = self.cleaned_data.get("name")
        if name:
            name = name.strip()
            # Check for duplicate (case-insensitive), excluding current instance
            qs = Category.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("A category with this name already exists.")
        return name


class ColorForm(forms.ModelForm):
    """Form for creating and editing colors"""

    class Meta:
        model = Color
        fields = ["name", "hex_code"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter color name",
                    "autofocus": True,
                }
            ),
            "hex_code": forms.TextInput(
                attrs={
                    "placeholder": "#FF0000",
                    "pattern": "#[0-9A-Fa-f]{6}",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to all fields
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

        # Override maxlength for hex_code to enforce 6 digits
        self.fields["hex_code"].widget.attrs["maxlength"] = "6"

    def clean_name(self):
        """Ensure color name is unique (case-insensitive)"""
        name = self.cleaned_data.get("name")
        if name:
            name = name.strip()
            # Check for duplicate (case-insensitive), excluding current instance
            qs = Color.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("A color with this name already exists.")
        return name

    def clean_hex_code(self):
        """Validate and normalize hex color code"""
        hex_code = self.cleaned_data.get("hex_code")
        if hex_code:
            hex_code = hex_code.strip().upper()
            if not hex_code.startswith("#"):
                hex_code = "#" + hex_code
            if len(hex_code) != 7 or not all(
                c in "0123456789ABCDEF" for c in hex_code[1:]
            ):
                raise forms.ValidationError(
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
                    "placeholder": "Enter size name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Enter size description",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to all fields
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

    def clean_name(self):
        """Ensure size name is unique (case-insensitive)"""
        name = self.cleaned_data.get("name")
        if name:
            name = name.strip()
            # Check for duplicate (case-insensitive), excluding current instance
            qs = Size.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("A size with this name already exists.")
        return name


class ClothTypeForm(forms.ModelForm):
    """Form for creating and editing cloth types"""

    class Meta:
        model = ClothType
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Enter cloth type name",
                    "autofocus": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Enter cloth type description",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to all fields
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-input"

    def clean_name(self):
        """Ensure cloth type name is unique (case-insensitive)"""
        name = self.cleaned_data.get("name")
        if name:
            name = name.strip()
            # Check for duplicate (case-insensitive), excluding current instance
            qs = ClothType.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "A cloth type with this name already exists."
                )
        return name


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
                    "placeholder": "Enter UOM name (e.g., Piece, Dozen, Meter)",
                    "autofocus": True,
                }
            ),
            "short_code": forms.TextInput(
                attrs={
                    "placeholder": "Enter short code (e.g., pcs, doz, m)",
                    "maxlength": "10",
                }
            ),
            "category": forms.TextInput(
                attrs={
                    "placeholder": "Enter category (e.g., Quantity, Weight, Length)",
                }
            ),
            "base_unit": forms.CheckboxInput(),
            "conversion_factor": forms.NumberInput(
                attrs={
                    "placeholder": "Enter conversion factor (e.g., 12 for dozen)",
                    "step": "0.0001",
                    "min": "0.0001",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Enter UOM description (optional)",
                }
            ),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to text/number fields, form-check-input to checkboxes
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            else:
                widget.attrs["class"] = "form-input"

    def clean_short_code(self):
        """Validate and normalize short code, ensure uniqueness"""
        short_code = self.cleaned_data.get("short_code")
        if short_code:
            short_code = short_code.strip().upper()
            # Check for duplicate, excluding current instance
            qs = UOM.objects.filter(short_code=short_code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "A UOM with this short code already exists."
                )
        return short_code

    def clean_conversion_factor(self):
        """Validate conversion factor is greater than 0"""
        conversion_factor = self.cleaned_data.get("conversion_factor")
        if conversion_factor is not None and conversion_factor <= 0:
            raise forms.ValidationError("Conversion factor must be greater than 0")
        return conversion_factor


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
                    "placeholder": "Enter HSN Code (e.g., 61091000)",
                    "autofocus": True,
                    "maxlength": "10",
                }
            ),
            "gst_percentage": forms.NumberInput(
                attrs={
                    "placeholder": "Enter GST percentage (e.g., 12.00)",
                    "step": "0.01",
                    "min": "0.00",
                    "max": "40.00",
                }
            ),
            "cess_rate": forms.NumberInput(
                attrs={
                    "placeholder": "Enter Cess rate (e.g., 0.00)",
                    "step": "0.01",
                    "min": "0.00",
                    "max": "25.00",
                }
            ),
            "effective_from": forms.DateInput(
                attrs={
                    "type": "date",
                    "placeholder": "Select effective date",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Enter HSN code description (optional)",
                }
            ),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add form-input class to text/number/date fields, form-check-input to checkboxes
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            else:
                widget.attrs["class"] = "form-input"

    def clean_code(self):
        """Validate HSN code format and ensure uniqueness"""
        code = self.cleaned_data.get("code")
        if code:
            code = code.strip()
            # Ensure code is numeric
            if not code.isdigit():
                raise forms.ValidationError("HSN Code must contain only numbers")
            # Validate length
            if len(code) < 4 or len(code) > 10:
                raise forms.ValidationError("HSN Code must be 4-10 digits long")
            # Check for duplicate, excluding current instance
            qs = GSTHsnCode.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    "A GST HSN Code with this code already exists."
                )
        return code

    def clean_gst_percentage(self):
        """Validate GST percentage is between 0.00 and 40.00"""
        gst_percentage = self.cleaned_data.get("gst_percentage")
        if gst_percentage is not None and (gst_percentage < 0 or gst_percentage > 40):
            raise forms.ValidationError("GST percentage must be between 0.00 and 40.00")
        return gst_percentage

    def clean_cess_rate(self):
        """Validate Cess rate is between 0.00 and 25.00"""
        cess_rate = self.cleaned_data.get("cess_rate")
        if cess_rate is not None and (cess_rate < 0 or cess_rate > 25):
            raise forms.ValidationError("Cess rate must be between 0.00 and 25.00")
        return cess_rate


class StockInForm(forms.ModelForm):
    """Optimized form for stock-in operations."""

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
            "variant": forms.Select(),
            "quantity_change": forms.NumberInput(
                attrs={
                    "autofocus": True,
                    "placeholder": "Enter quantity",
                }
            ),
            "purchase_price": forms.NumberInput(attrs={}),
            "mrp": forms.NumberInput(attrs={}),
            "supplier_invoice": forms.Select(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        variant = kwargs.pop("variant", None)
        super().__init__(*args, **kwargs)

        # Standardize widget styling using a CSS class (see main.css theming)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", "form-input multiline")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-input")
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("class", "form-input number")
                field.widget.attrs.setdefault("min", "0")
            else:
                field.widget.attrs.setdefault("class", "form-input")

        self.variant = variant

        if self.variant:
            self.fields["variant"].widget = forms.HiddenInput()
            self.fields["variant"].initial = self.variant
            self.fields["variant"].required = False
        else:
            self.fields["variant"].queryset = ProductVariant.objects.filter(
                is_deleted=False
            )

        self.fields["supplier_invoice"].queryset = SupplierInvoice.objects.filter(
            supplier__is_deleted=False
        )
        self.fields["supplier_invoice"].required = False
        self.fields["purchase_price"].required = True

    def clean_quantity_change(self):
        quantity_change = self.cleaned_data.get("quantity_change")
        if quantity_change is not None and quantity_change <= 0:
            raise forms.ValidationError("Stock in quantity must be greater than zero.")
        return quantity_change

    def clean_purchase_price(self):
        purchase_price = self.cleaned_data.get("purchase_price")
        if purchase_price is not None and purchase_price < 0:
            raise forms.ValidationError("Purchase price cannot be negative.")
        return purchase_price

    def clean_mrp(self):
        mrp = self.cleaned_data.get("mrp")
        if mrp is not None and mrp <= 0:
            raise forms.ValidationError("MRP cannot be negative.")
        return mrp

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.variant and not instance.variant:
            instance.variant = self.variant
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
