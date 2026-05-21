"""Pydantic schemas for API request/response."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --- User Schemas ---
class UserBase(BaseModel):
    username: str
    full_name: str
    role: str
    is_active: bool = True


class UserCreate(UserBase):
    pin: str = Field(..., min_length=4, max_length=6, description="4-6 digit PIN")


class UserResponse(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    pin: str


class LoginResponse(BaseModel):
    success: bool
    user: UserResponse | None = None
    message: str


# --- Product Schemas ---
class ProductBase(BaseModel):
    barcode: str
    name: str
    category: str | None = None
    unit: str
    cost_price: Decimal
    selling_price: Decimal
    tax_rate: Decimal = Decimal("0.00")
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    cost_price: Decimal | None = None
    selling_price: Decimal | None = None
    tax_rate: Decimal | None = None
    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Terminal Schemas ---
class TerminalBase(BaseModel):
    terminal_code: str
    name: str
    is_active: bool = True


class TerminalCreate(TerminalBase):
    pass


class TerminalResponse(TerminalBase):
    id: str
    device_fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Inventory Schemas ---
class InventoryBase(BaseModel):
    quantity: Decimal
    reorder_level: Decimal
    low_stock_alert: bool = True


class InventoryResponse(InventoryBase):
    id: str
    product_id: str
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductWithInventory(ProductResponse):
    """Product with inventory information."""

    inventory: InventoryResponse | None = None


class StockAdjustmentRequest(BaseModel):
    product_id: str
    quantity_change: Decimal = Field(..., description="Positive to add, negative to subtract")
    movement_type: str = Field(
        default="adjustment",
        description="Type: initial, purchase, sale, adjustment, return",
    )
    notes: str | None = None


class StockSetRequest(BaseModel):
    product_id: str
    new_quantity: Decimal = Field(..., ge=0, description="New stock quantity")
    notes: str | None = None


class StockMovementResponse(BaseModel):
    id: str
    inventory_id: str
    movement_type: str
    quantity_change: Decimal
    quantity_after: Decimal
    reference_id: str | None = None
    user_id: str | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class LowStockItem(BaseModel):
    product: ProductResponse
    inventory: InventoryResponse

    class Config:
        from_attributes = True


# --- Sales Schemas ---
class SaleItemCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal | None = None  # If None, use product's selling price
    discount: Decimal = Decimal("0.00")


class SaleItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_barcode: str
    unit_price: Decimal
    quantity: Decimal
    tax_rate: Decimal
    discount_amount: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    terminal_id: str
    cashier_id: str
    items: list[SaleItemCreate] = Field(..., min_length=1)
    payment_method: str = Field(..., description="cash, card, mobile, mixed")
    amount_paid: Decimal = Field(..., gt=0)
    customer_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    notes: str | None = None


class SaleResponse(BaseModel):
    id: str
    invoice_number: str
    terminal_id: str
    cashier_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    payment_method: str
    amount_paid: Decimal
    change_given: Decimal
    status: str
    notes: str | None = None
    created_at: datetime
    items: list[SaleItemResponse] = []

    class Config:
        from_attributes = True


class SaleCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Reason for cancellation")


class DailySummaryResponse(BaseModel):
    date: str
    total_sales: int
    total_revenue: float
    total_tax: float
    total_discount: float
    payment_methods: dict


class PeriodSummaryResponse(BaseModel):
    start_date: str
    end_date: str
    total_sales: int
    total_revenue: float
    total_tax: float
    total_discount: float
    average_sale: float
    payment_methods: dict
    daily_breakdown: dict


class TopProductResponse(BaseModel):
    product_id: str
    product_name: str
    barcode: str
    category: str | None
    total_quantity: float
    total_revenue: float
    transaction_count: int


class CategorySalesResponse(BaseModel):
    category: str
    total_quantity: float
    total_revenue: float
    unique_products: int


class CashierPerformanceResponse(BaseModel):
    cashier_id: str
    username: str
    full_name: str
    total_sales: int
    total_revenue: float
    average_sale: float


class HourlySalesResponse(BaseModel):
    hour: int
    time_range: str
    count: int
    revenue: float


class ProfitAnalysisResponse(BaseModel):
    total_revenue: float
    total_cost: float
    gross_profit: float
    profit_margin: float


# --- Customer Schemas ---
class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=500)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class CustomerResponse(CustomerBase):
    id: str
    customer_code: str
    loyalty_points: Decimal
    total_purchases: Decimal
    purchase_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerStatsResponse(BaseModel):
    customer_id: str
    customer_code: str
    name: str
    total_purchases: float
    purchase_count: int
    loyalty_points: float
    average_purchase: float
    last_purchase_date: str | None
    member_since: str


class LoyaltyPointsRequest(BaseModel):
    points: Decimal = Field(..., description="Points to add (positive) or deduct (negative)")






# --- Supplier Schemas ---
class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    company_name: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    contact_person: str | None = Field(None, max_length=100)
    payment_terms: str | None = Field(None, max_length=100)
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = Field(None, max_length=500)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    company_name: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=255)
    contact_person: str | None = Field(None, max_length=100)
    payment_terms: str | None = Field(None, max_length=100)
    credit_limit: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class SupplierResponse(SupplierBase):
    id: str
    supplier_code: str
    total_purchases: Decimal
    purchase_count: int
    outstanding_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierStatsResponse(BaseModel):
    supplier_id: str
    supplier_code: str
    name: str
    total_purchases: float
    purchase_count: int
    outstanding_balance: float
    credit_limit: float
    credit_available: float


# --- Purchase Schemas ---
class PurchaseItemCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    notes: str | None = None


class PurchaseItemResponse(BaseModel):
    id: str
    product_id: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    notes: str | None = None

    class Config:
        from_attributes = True


class PurchaseCreate(BaseModel):
    supplier_id: str
    items: list[PurchaseItemCreate] = Field(..., min_length=1)
    purchase_date: datetime | None = None
    expected_delivery_date: datetime | None = None
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    shipping_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    reference_number: str | None = Field(None, max_length=50)
    notes: str | None = None


class PurchaseResponse(BaseModel):
    id: str
    purchase_number: str
    supplier_id: str
    supplier_name: str
    purchase_date: datetime
    expected_delivery_date: datetime | None
    received_date: datetime | None
    subtotal: Decimal
    tax_amount: Decimal
    shipping_cost: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    status: str
    payment_status: str
    reference_number: str | None
    notes: str | None
    created_by: str
    received_by: str | None
    created_at: datetime
    items: list[PurchaseItemResponse] = []

    class Config:
        from_attributes = True


class PurchaseStatusUpdate(BaseModel):
    status: str = Field(..., description="draft, ordered, received, cancelled")
    received_by: str | None = Field(None, description="Required for 'received' status")


class PurchasePaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    payment_date: datetime | None = None
    notes: str | None = None


class PurchaseCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Reason for cancellation")


class PurchaseSummaryResponse(BaseModel):
    total_purchases: int
    total_amount: float
    total_paid: float
    total_outstanding: float
    status_counts: dict


# --- Discount Schemas ---
class DiscountBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    discount_type: str = Field(..., description="percentage, fixed_amount, buy_x_get_y")
    discount_scope: str = Field(..., description="order, category, product")
    discount_value: Decimal = Field(..., gt=0)
    max_discount_amount: Decimal | None = Field(None, ge=0)
    buy_quantity: int | None = Field(None, gt=0)
    get_quantity: int | None = Field(None, gt=0)
    min_purchase_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    min_quantity: int = Field(default=0, ge=0)
    category: str | None = None
    product_ids: str | None = None
    valid_from: datetime
    valid_until: datetime | None = None
    usage_limit: int | None = Field(None, gt=0)
    usage_limit_per_customer: int | None = Field(None, gt=0)
    is_automatic: bool = False
    requires_code: bool = True
    is_stackable: bool = False
    priority: int = 0
    notes: str | None = None


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    discount_value: Decimal | None = Field(None, gt=0)
    max_discount_amount: Decimal | None = Field(None, ge=0)
    min_purchase_amount: Decimal | None = Field(None, ge=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit: int | None = Field(None, gt=0)
    usage_limit_per_customer: int | None = Field(None, gt=0)
    is_active: bool | None = None
    is_automatic: bool | None = None
    is_stackable: bool | None = None
    priority: int | None = None
    notes: str | None = None


class DiscountResponse(DiscountBase):
    id: str
    usage_count: int
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DiscountValidateRequest(BaseModel):
    code: str
    order_amount: Decimal = Field(..., gt=0)
    customer_id: str | None = None
    category: str | None = None
    product_ids: list[str] | None = None


class DiscountValidateResponse(BaseModel):
    is_valid: bool
    discount: DiscountResponse | None = None
    discount_amount: Decimal | None = None
    error_message: str | None = None


class DiscountStatsResponse(BaseModel):
    discount_id: str
    code: str
    name: str
    usage_count: int
    usage_limit: int | None
    total_discount_amount: float
    total_original_amount: float
    unique_customers: int
    is_active: bool
    is_valid: bool
