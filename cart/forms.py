from django import forms
from .models import Cart


class CartForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ["name", "status", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter cart name (e.g., Customer Order #123)",
                "maxlength": "255",
                "autofocus": True,
                "value": "Walk in"
            }),
            "status": forms.Select(attrs={
                "class": "form-input"
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-input",
                "placeholder": "Add any special notes or instructions for this cart",
                "rows": "4"
            }),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        
        # Customize field labels and help text
        self.fields['name'].label = "Cart Name"
        self.fields['name'].help_text = "Give your cart a descriptive name for easy identification"
        
        self.fields['status'].label = "Cart Status"
        self.fields['status'].help_text = "Choose whether the cart is open for editing or archived"
        
        self.fields['notes'].label = "Notes"
        self.fields['notes'].help_text = "Optional notes about this cart (e.g., customer preferences, special instructions)"
        
        # Set initial status to OPEN for new carts
        if not self.instance.pk:
            self.fields['status'].initial = Cart.CartStatus.OPEN