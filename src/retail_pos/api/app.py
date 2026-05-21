"""FastAPI application for Retail POS."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from retail_pos.api.customer_routes import router as customer_router
from retail_pos.api.discount_routes import router as discount_router
from retail_pos.api.inventory_routes import router as inventory_router
from retail_pos.api.purchase_routes import router as purchase_router
from retail_pos.api.routes import router
from retail_pos.api.sales_routes import router as sales_router
from retail_pos.api.supplier_routes import router as supplier_router
from retail_pos.config import settings
from retail_pos.utils.exceptions import RetailPOSException
from retail_pos.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Retail POS API",
    description="Professional Point of Sale system with inventory management",
    version="1.0.0",
    debug=settings.debug,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RetailPOSException)
async def retail_pos_exception_handler(
    request: Request, exc: RetailPOSException
) -> JSONResponse:
    """Handle custom application exceptions."""
    logger.error(f"Application error: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.code,
            "message": exc.message,
            "detail": str(exc),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.debug else "Please contact support",
        },
    )


# Mount static files
static_dir = Path(__file__).parent.parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1", tags=["inventory"])
app.include_router(sales_router, prefix="/api/v1", tags=["sales"])
app.include_router(customer_router, prefix="/api/v1", tags=["customers"])
app.include_router(supplier_router, prefix="/api/v1", tags=["suppliers"])
app.include_router(purchase_router, prefix="/api/v1", tags=["purchases"])
app.include_router(discount_router, prefix="/api/v1", tags=["discounts"])


@app.on_event("startup")
async def startup_event() -> None:
    """Run on application startup."""
    logger.info("🚀 Retail POS API starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database: {settings.db_path}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Run on application shutdown."""
    logger.info("👋 Retail POS API shutting down...")


@app.get("/")
def root() -> FileResponse:
    """Serve the demo HTML page."""
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return JSONResponse(
        content={
            "message": "Retail POS API",
            "version": "1.0.0",
            "docs": "/docs",
            "database": str(settings.db_path),
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
