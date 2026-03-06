# GarageOS (My_Billing)

A comprehensive, scalable Django-based billing, inventory, and point-of-sale (POS) system tailored for retail and wholesale operations. It handles everything from stock tracking to compliant GST / Non-GST invoicing, customer/supplier management, and barcode-driven cart checkouts.

---

## 🚀 Key Features

### 📦 Inventory Management

- **Product Catalog**: Manage products, categories, types, and HSN codes.
- **Variants Support**: Handle complex stock types using size, color, and dynamic pricing (MRP, Purchase Price, Selling Price).
- **Mutations & Tracking**: Full audit trail for Stock In, Stock Out, Adjustments, and Damages using atomic database locks (`select_for_update`) to prevent negative stock.
- **Barcode Generation**: Automatically generate and print structured barcode tags using `python-barcode`.

### 🏢 Supplier & Purchasing

- Manage suppliers, track credit/debit, and process purchasing invoices to increase stock.

### 👥 Customer Management

- Maintain a comprehensive customer database.
- Track ledgers, credit limits, payments, and outstanding balances.

### 🛒 Point of Sale (Cart)

- High-efficiency cart optimized for fast retail checkout.
- Features multi-word auto-suggestion search (`RapidFuzz`) and direct barcode scanning.
- Dynamic discounting, tax calculations, and advance payment tracking.

### 🧾 Invoicing & Auditing

- **Compliant Invoicing**: Support for separate GST and CASH invoice sequential numbers dynamically linked to financial years (e.g., `YYYY-YY`).
- **Returns & Cancellations**: Process partial/full returns with stock replenishment. Cancel and resequence invoices to maintain chronological accounting accuracy.
- **Reporting & PDF**: Generate pixel-perfect custom estimate receipts and invoices using `WeasyPrint`.

### ⚙️ Settings & Customization

- Easily toggle report/invoice formats (A4 vs Thermal).
- Customize Terms & Conditions, Payment details (UPI/Bank), and shop branding directly from the interface.

---

## 🛠️ Technology Stack

**Backend System:**

- **Framework**: Django 5.1
- **Database**: PostgreSQL
- **Security**: Strict CSRF handling, `django-login-required-middleware`, Session Hijacking protection via inactivity timeouts.

**Frontend & Assets:**

- **Styling**: Bootstrap 5, curated theme variables (Light/Dark mode support).
- **Interactivity**: Vanilla JavaScript, jQuery, Select2.
- **PDF Generation**: WeasyPrint 63+

**Key Python Libraries (`require.txt`):**

- `python-decouple`: Environment variable management
- `cryptography`: Data encryption
- `RapidFuzz`: Advanced word suggestion and fuzzy matching
- `XlsxWriter` & `tablib`: Data extraction and accounting reports

---

## 📂 Architecture Overview

The platform uses a component-based Django "Fat Models" architectural approach:

```text
My_Billing/
├── api/          # Global endpoints (suggestions, metrics)
├── base/         # Shared utilities (currency formatting, pagination, decorators)
├── cart/         # POS checkout, session-bound temporary order states
├── customer/     # Customer records and ledger tracking
├── inventory/    # Product models, variant logic, stock mutations (Strict Atomic rules)
├── invoice/      # Finalized orders, returns, and chronological audit trails
├── report/       # WeasyPrint PDF generation and Excel summaries
├── setting/      # Global application configurations and theme data
├── supplier/     # Vendor and purchasing management
└── user/         # Custom auth user models and localized permissions
```

---

## ⚡ Setup & Local Development

### Prerequisites

- Python 3.10+
- PostgreSQL
- GTK3 Runtime (Required for `WeasyPrint` PDF engine on Windows)

### Installation Steps

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd My_Billing
   ```

2. **Set up a Virtual Environment & Install Dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r require.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the project root:

   ```env
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_NAME=your_db_name
   DB_USER=postgres
   DB_PASSWORD=postgres
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```

4. **Initialize Database:**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Run the Server:**
   ```bash
   python manage.py runserver
   ```
   Navigate to `http://127.0.0.1:8000` in your browser.

---

## 📜 Development Guidelines

- **URL Namespacing**: Always namespace App URLs internally (e.g., `invoice:detail` instead of `/invoice/`).
- **Fat Models**: Maintain core business behaviors within Model definitions; restrict `views.py` to route orchestration and permissions checking.
- **Utility Reusability**: When creating pagination, currency formatting, or sequence generators, leverage helpers in `base/utility.py`.
- **Theme Variables**: Use predefined CSS variables inside `.css` files rather than hardcoding colors to ensure Light/Dark seamless integration.
