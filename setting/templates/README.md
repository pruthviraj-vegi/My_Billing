# Setting App Templates

This directory contains templates organized by functionality for better maintainability.

## Structure

### `/shop/` - Shop/Business Settings
- `shop_details_list.html` - List all shop details
- `shop_details_form.html` - Create/edit shop details form
- `shop_details_detail.html` - View shop details
- `shop_details_delete.html` - Delete confirmation
- `shop_settings_dashboard.html` - Main dashboard for shop settings
- `home.html` - Shop settings home page

### `/reports/` - Report Configuration Settings
- `report_config_list.html` - List all report configurations
- `report_config_form.html` - Create/edit report configuration form
- `report_config_detail.html` - View report configuration
- `report_config_delete.html` - Delete confirmation
- `quick_report_settings.html` - Quick settings for common report options

## Benefits of This Organization

1. **Clear Separation**: Shop settings vs Report configurations are now clearly separated
2. **Easy Navigation**: Developers can quickly find templates by functionality
3. **Maintainability**: Related templates are grouped together
4. **Scalability**: Easy to add new templates in the appropriate folder
5. **Team Collaboration**: Different team members can work on different areas without conflicts

## Usage

Views in `setting/views.py` now reference templates using the new paths:
- Shop templates: `'setting/shop/template_name.html'`
- Report templates: `'setting/reports/template_name.html'`
