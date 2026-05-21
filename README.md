# Retail POS

Offline-first retail Point of Sale (POS) software for small to medium shops.

## Overview

A Windows desktop application for retail shops with multiple POS terminals. Works fully offline and syncs to the cloud automatically when internet is available.

## Tech Stack

- **Desktop UI**: PyQt6
- **Local Database**: SQLite (with SQLAlchemy ORM)
- **Migrations**: Alembic
- **Cloud Backend** (Phase 2): FastAPI + PostgreSQL
- **Packaging**: PyInstaller

## Project Structure

```
retail-pos/
├── alembic/                  # Database migrations
├── src/retail_pos/
│   ├── config.py             # App configuration
│   ├── db/                   # Database engine, session, base model
│   ├── models/               # SQLAlchemy models
│   ├── services/             # Business logic (added per module)
│   ├── ui/                   # PyQt6 UI (added later)
│   └── utils/                # Helpers (security, etc.)
├── scripts/
│   └── seed.py               # Seed sample data for development
├── tests/                    # Tests
├── pyproject.toml            # Project metadata & dependencies
└── alembic.ini               # Alembic configuration
```

## Development Roadmap

### Phase 1 — MVP (4–6 weeks) ✅ COMPLETED

- [x] Project scaffold
- [x] User Auth (PIN-based login, admin/cashier roles)
- [x] Product Management (add/edit, barcode, category, price)
- [x] Inventory (stock count, low stock alert, adjust stock)
- [x] Sales / POS (scan, cart, payment, receipt)
- [x] Basic Reports (daily sales, weekly/monthly, top products, profit analysis)

### Phase 2 — Core (6–10 weeks)

- [ ] Offline Sync engine
- [x] Customer Management (CRM, loyalty points)
- [x] Supplier / Purchase Management
- [x] Discount / Promo Management
- [ ] License Enforcement
- [ ] Advanced Reports

### Phase 3 — Advanced

- [ ] Multi-store
- [ ] Loyalty Points
- [ ] Online Payment (bKash / Nagad / Card)
- [ ] Accounting
- [ ] SMS / Notification

## Getting Started

### Prerequisites

- Python 3.11 or newer

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# Install dependencies (editable mode)
pip install -e ".[dev]"

# Initialize the local database
alembic upgrade head

# Seed sample data (admin user, terminal, sample products)
python -m scripts.seed
```

### Default credentials after seeding

- Admin: username `admin`, PIN `1234`
- Cashier: username `cashier1`, PIN `0000`

### Running the API Server (Development)

```bash
# Start the FastAPI development server
python run_api.py

# Server will be available at:
# - Web UI: http://127.0.0.1:8000/
# - API Docs: http://127.0.0.1:8000/docs
# - API Base: http://127.0.0.1:8000/api/v1
```

### API Endpoints

**Authentication:**
- `POST /api/v1/auth/login` - Login with username and PIN

**Users:**
- `GET /api/v1/users` - List all users
- `GET /api/v1/users/{id}` - Get user by ID
- `POST /api/v1/users` - Create new user

**Products:**
- `GET /api/v1/products` - List all products
- `GET /api/v1/products/{id}` - Get product by ID
- `GET /api/v1/products/barcode/{barcode}` - Get product by barcode
- `POST /api/v1/products` - Create new product
- `PATCH /api/v1/products/{id}` - Update product
- `DELETE /api/v1/products/{id}` - Soft delete product

**Terminals:**
- `GET /api/v1/terminals` - List all terminals
- `GET /api/v1/terminals/{id}` - Get terminal by ID
- `POST /api/v1/terminals` - Create new terminal

### 🎯 **Next Phase: Reports Enhancement**

এখন আমরা তৈরি করতে পারি:
1. **Advanced Reports**
   - Weekly/Monthly sales
   - Top selling products
   - Cashier performance
   - Category-wise sales
   - Profit margins

2. **Cash Register Management**
   - Opening/closing balance
   - Cash in/out tracking
   - Shift reports

3. **Export Features**
   - PDF receipts
   - Excel reports
   - Print functionality

**Phase 1 MVP প্রায় সম্পন্ন! 🎊**

আপনি কি reports enhancement করতে চান, নাকি Phase 2 এর দিকে এগোতে চান? 🚀
