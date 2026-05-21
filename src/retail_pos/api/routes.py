"""API routes for users, products, and terminals."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from retail_pos.api.schemas import (
    LoginRequest,
    LoginResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    TerminalCreate,
    TerminalResponse,
    UserCreate,
    UserResponse,
)
from retail_pos.db import get_db
from retail_pos.models import Product, Terminal, User
from retail_pos.utils.security import hash_pin, verify_pin

router = APIRouter()


# --- Auth Routes ---
@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    """Authenticate user with username and PIN."""
    user = db.scalar(select(User).where(User.username == request.username))

    if not user or not user.is_active:
        return LoginResponse(success=False, message="Invalid username or PIN")

    if not verify_pin(request.pin, user.pin_hash):
        return LoginResponse(success=False, message="Invalid username or PIN")

    return LoginResponse(
        success=True, user=UserResponse.model_validate(user), message="Login successful"
    )


# --- User Routes ---
@router.get("/users", response_model=list[UserResponse])
def list_users(db: Annotated[Session, Depends(get_db)]) -> list[User]:
    """List all users."""
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Annotated[Session, Depends(get_db)]) -> User:
    """Get a single user by ID."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Annotated[Session, Depends(get_db)]) -> User:
    """Create a new user."""
    # Check if username already exists
    existing = db.scalar(select(User).where(User.username == data.username))
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        pin_hash=hash_pin(data.pin),
        full_name=data.full_name,
        role=data.role,
        is_active=data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Product Routes ---
@router.get("/products", response_model=list[ProductResponse])
def list_products(
    db: Annotated[Session, Depends(get_db)], active_only: bool = True
) -> list[Product]:
    """List all products."""
    query = select(Product).order_by(Product.name)
    if active_only:
        query = query.where(Product.is_active == True)  # noqa: E712
    return list(db.scalars(query).all())


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, db: Annotated[Session, Depends(get_db)]) -> Product:
    """Get a single product by ID."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/barcode/{barcode}", response_model=ProductResponse)
def get_product_by_barcode(barcode: str, db: Annotated[Session, Depends(get_db)]) -> Product:
    """Get a product by barcode."""
    product = db.scalar(select(Product).where(Product.barcode == barcode))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, db: Annotated[Session, Depends(get_db)]) -> Product:
    """Create a new product."""
    # Check if barcode already exists
    existing = db.scalar(select(Product).where(Product.barcode == data.barcode))
    if existing:
        raise HTTPException(status_code=400, detail="Barcode already exists")

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str, data: ProductUpdate, db: Annotated[Session, Depends(get_db)]
) -> Product:
    """Update a product."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: str, db: Annotated[Session, Depends(get_db)]) -> None:
    """Soft delete a product (set is_active to False)."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    db.commit()


# --- Terminal Routes ---
@router.get("/terminals", response_model=list[TerminalResponse])
def list_terminals(db: Annotated[Session, Depends(get_db)]) -> list[Terminal]:
    """List all terminals."""
    return list(db.scalars(select(Terminal).order_by(Terminal.terminal_code)).all())


@router.get("/terminals/{terminal_id}", response_model=TerminalResponse)
def get_terminal(terminal_id: str, db: Annotated[Session, Depends(get_db)]) -> Terminal:
    """Get a single terminal by ID."""
    terminal = db.get(Terminal, terminal_id)
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal not found")
    return terminal


@router.post("/terminals", response_model=TerminalResponse, status_code=201)
def create_terminal(data: TerminalCreate, db: Annotated[Session, Depends(get_db)]) -> Terminal:
    """Create a new terminal."""
    # Check if terminal_code already exists
    existing = db.scalar(select(Terminal).where(Terminal.terminal_code == data.terminal_code))
    if existing:
        raise HTTPException(status_code=400, detail="Terminal code already exists")

    terminal = Terminal(**data.model_dump())
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return terminal
