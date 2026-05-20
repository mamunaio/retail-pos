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

### Phase 1 — MVP (4–6 weeks)

- [x] Project scaffold (this PR)
- [ ] User Auth (PIN-based login, admin/cashier roles)
- [ ] Product Management (add/edit, barcode, category, price)
- [ ] Inventory (stock count, low stock alert, adjust stock)
- [ ] Sales / POS (scan, cart, payment, receipt)
- [ ] Basic Reports (daily sales, cash register)

### Phase 2 — Core (6–10 weeks)

- [ ] Offline Sync engine
- [ ] Customer Management
- [ ] Supplier / Purchase
- [ ] Discount / Promo
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

## License

Proprietary — All rights reserved.
