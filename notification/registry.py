"""
Notification Type Registry.

Defines display metadata for each notification type used in the
frontend notification panel. New types can be added without migrations.

HOW TO ADD A NEW TYPE:
    1. Add an entry to NOTIFICATION_REGISTRY below:
           "your_type_key": {
               "icon":  "fa-icon-name",   # Font Awesome 5 icon class
               "color": "var(--primary)",  # CSS variable for icon colour
               "label": "Category",        # Badge label shown on the card
           },
    2. Call notify() from anywhere:
           from notification.services import notify
           notify(user=user, notification_type="your_type_key", ...)
    3. No database migration required.
"""

NOTIFICATION_REGISTRY = {
    # ── Active types (currently wired to producers) ─────────
    "pdf_ready": {
        "icon": "fa-file-pdf",
        "color": "var(--success)",
        "label": "PDF",
    },
    "pdf_failed": {
        "icon": "fa-file-excel",
        "color": "var(--danger)",
        "label": "PDF",
    },
    # ── Reserved types (no producer yet — wire up as needed) ─
    "low_stock": {
        "icon": "fa-box-open",
        "color": "var(--warning)",
        "label": "Inventory",
    },
    "payment_due": {
        "icon": "fa-credit-card",
        "color": "var(--warning)",
        "label": "Payment",
    },
    "payment_received": {
        "icon": "fa-rupee-sign",
        "color": "var(--success)",
        "label": "Payment",
    },
    "new_order": {
        "icon": "fa-shopping-cart",
        "color": "var(--primary)",
        "label": "Order",
    },
    "invoice_created": {
        "icon": "fa-file-invoice-dollar",
        "color": "var(--primary)",
        "label": "Invoice",
    },
    "login_alert": {
        "icon": "fa-shield-alt",
        "color": "var(--danger)",
        "label": "Security",
    },
    # ── Generic fallback ─────────────────────────────────────
    "info": {
        "icon": "fa-info-circle",
        "color": "var(--secondary)",
        "label": "Info",
    },
}

_DEFAULT_META = NOTIFICATION_REGISTRY["info"]


def get_meta(notification_type: str) -> dict:
    """Get display metadata (icon, color, label) for a notification type.

    Falls back to 'info' defaults if the type is not registered.
    """
    return NOTIFICATION_REGISTRY.get(notification_type, _DEFAULT_META)
