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


from django import forms
from django.core.exceptions import ValidationError
from .models import ShopDetails, ReportConfiguration
from base.manager import phone_regex


class ShopDetailsForm(forms.ModelForm):
    """Form for managing shop details."""
    
    class Meta:
        model = ShopDetails
        fields = [
            'shop_name', 'first_line', 'second_line', 'city', 'state', 
            'pincode', 'country', 'gst_no', 'phone_number', 'phone_two',
            'email', 'website', 'logo', 'is_active'
        ]
        widgets = {
            'shop_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter shop/business name'
            }),
            'first_line': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Building name, Street'
            }),
            'second_line': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Area, Locality (optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City name'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'State name'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'PIN/ZIP code'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Country name'
            }),
            'gst_no': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'GST Registration Number (optional)'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Primary phone number'
            }),
            'phone_two': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Secondary phone number (optional)'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Business email (optional)'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'Website URL (optional)'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add form labels
        self.fields['shop_name'].label = 'Shop/Business Name'
        self.fields['first_line'].label = 'Address Line 1'
        self.fields['second_line'].label = 'Address Line 2'
        self.fields['city'].label = 'City'
        self.fields['state'].label = 'State'
        self.fields['pincode'].label = 'PIN Code'
        self.fields['country'].label = 'Country'
        self.fields['gst_no'].label = 'GST Number'
        self.fields['phone_number'].label = 'Primary Phone'
        self.fields['phone_two'].label = 'Secondary Phone'
        self.fields['email'].label = 'Email Address'
        self.fields['website'].label = 'Website'
        self.fields['logo'].label = 'Logo Image'
        self.fields['is_active'].label = 'Active'

        # Add help text
        self.fields['shop_name'].help_text = 'The name of your shop or business'
        self.fields['first_line'].help_text = 'Building name, street address'
        self.fields['second_line'].help_text = 'Area, locality, landmark (optional)'
        self.fields['gst_no'].help_text = 'GST registration number (optional)'
        self.fields['phone_number'].help_text = 'Primary contact number'
        self.fields['phone_two'].help_text = 'Secondary contact number (optional)'
        self.fields['logo'].help_text = 'Upload your shop logo (optional)'

    def clean_phone_number(self):
        """Validate primary phone number."""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            if not phone_regex.regex.match(phone):
                raise ValidationError('Phone number must be exactly 10 digits.')
        return phone

    def clean_phone_two(self):
        """Validate secondary phone number."""
        phone = self.cleaned_data.get('phone_two')
        if phone:
            if not phone_regex.regex.match(phone):
                raise ValidationError('Phone number must be exactly 10 digits.')
        return phone

    def clean_gst_no(self):
        """Validate GST number format."""
        gst = self.cleaned_data.get('gst_no')
        if gst:
            # Basic GST validation (15 characters, alphanumeric)
            if len(gst) != 15 or not gst.replace(' ', '').isalnum():
                raise ValidationError('GST number must be 15 characters long and alphanumeric.')
        return gst


class ReportConfigurationForm(forms.ModelForm):
    """Form for managing report configuration settings."""
    
    class Meta:
        model = ReportConfiguration
        fields = [
            'report_type', 'paper_size', 'currency',
            'show_logo', 'show_shop_name', 'show_address', 'show_contact', 'show_gst',
            'show_invoice_number', 'show_date', 'show_due_date', 'show_payment_method', 'show_customer_details',
            'show_item_description', 'show_quantity', 'show_unit_price', 'show_discount', 'show_tax_breakdown', 'show_total',
            'show_terms_conditions', 'show_qr_code', 'show_thank_you', 'show_signature',
            'terms_conditions', 'thank_you_message', 'footer_note',
            'is_default', 'is_active'
        ]
        widgets = {
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'paper_size': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'terms_conditions': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Enter custom terms and conditions...'
            }),
            'thank_you_message': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Enter custom thank you message...'
            }),
            'footer_note': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Enter additional footer note...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add form labels
        self.fields['report_type'].label = 'Report Type'
        self.fields['paper_size'].label = 'Paper Size'
        self.fields['currency'].label = 'Currency'
        
        # Header settings
        self.fields['show_logo'].label = 'Show Logo'
        self.fields['show_shop_name'].label = 'Show Shop Name'
        self.fields['show_address'].label = 'Show Address'
        self.fields['show_contact'].label = 'Show Contact Info'
        self.fields['show_gst'].label = 'Show GST Number'
        
        # Invoice content
        self.fields['show_invoice_number'].label = 'Show Invoice Number'
        self.fields['show_date'].label = 'Show Date'
        self.fields['show_due_date'].label = 'Show Due Date'
        self.fields['show_payment_method'].label = 'Show Payment Method'
        self.fields['show_customer_details'].label = 'Show Customer Details'
        
        # Item details
        self.fields['show_item_description'].label = 'Show Item Description'
        self.fields['show_quantity'].label = 'Show Quantity'
        self.fields['show_unit_price'].label = 'Show Unit Price'
        self.fields['show_discount'].label = 'Show Discount'
        self.fields['show_tax_breakdown'].label = 'Show Tax Breakdown'
        self.fields['show_total'].label = 'Show Total'
        
        # Footer settings
        self.fields['show_terms_conditions'].label = 'Show Terms & Conditions'
        self.fields['show_qr_code'].label = 'Show QR Code'
        self.fields['show_thank_you'].label = 'Show Thank You Message'
        self.fields['show_signature'].label = 'Show Signature Line'
        
        # Custom text
        self.fields['terms_conditions'].label = 'Custom Terms & Conditions'
        self.fields['thank_you_message'].label = 'Custom Thank You Message'
        self.fields['footer_note'].label = 'Footer Note'
        
        # System settings
        self.fields['is_default'].label = 'Set as Default'
        self.fields['is_active'].label = 'Active'

        # Add help text
        self.fields['report_type'].help_text = 'Type of report this configuration applies to'
        self.fields['paper_size'].help_text = 'Paper size for report generation'
        self.fields['currency'].help_text = 'Currency symbol to display'
        self.fields['is_default'].help_text = 'Use this as the default configuration for this report type'
        self.fields['terms_conditions'].help_text = 'Leave blank to use default terms and conditions'
        self.fields['thank_you_message'].help_text = 'Leave blank to use default thank you message'

    def clean(self):
        """Custom validation."""
        cleaned_data = super().clean()
        
        # If setting as default, ensure no other config of same type is default
        if cleaned_data.get('is_default') and cleaned_data.get('report_type'):
            existing_default = ReportConfiguration.objects.filter(
                report_type=cleaned_data['report_type'],
                is_default=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_default.exists():
                raise ValidationError(
                    f'Another {cleaned_data["report_type"]} configuration is already set as default. '
                    'Please uncheck the default setting for that configuration first.'
                )
        
        return cleaned_data


class QuickReportConfigForm(forms.Form):
    """Quick form for basic report settings."""
    
    paper_size = forms.ChoiceField(
        choices=ReportConfiguration.PaperSize.choices,
        initial=ReportConfiguration.PaperSize.A5,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    show_logo = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    
    show_qr_code = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    
    show_terms_conditions = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    
    custom_terms = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Custom terms and conditions (optional)...'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['paper_size'].label = 'Paper Size'
        self.fields['show_logo'].label = 'Show Logo'
        self.fields['show_qr_code'].label = 'Show QR Code'
        self.fields['show_terms_conditions'].label = 'Show Terms & Conditions'
        self.fields['custom_terms'].label = 'Custom Terms'