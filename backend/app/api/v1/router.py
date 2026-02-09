"""
API v1 Router for Hanco-AI
Aggregates all v1 endpoints
"""
from fastapi import APIRouter

# Import all endpoint routers
from app.api.v1 import vehicles, bookings, pricing, competitors, payments, chat, branches, auth

# Create main API router
api_router = APIRouter()

# ==================== Router Registration ====================

# Authentication endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Branch locations endpoints
api_router.include_router(
    branches.router,
    prefix="/branches",
    tags=["Branches"]
)

# Vehicle management endpoints
api_router.include_router(
    vehicles.router,
    prefix="/vehicles",
    tags=["Vehicles"]
)

# Booking management endpoints
api_router.include_router(
    bookings.router,
    prefix="/bookings",
    tags=["Bookings"]
)

# Dynamic pricing endpoints
api_router.include_router(
    pricing.router,
    prefix="/pricing",
    tags=["Pricing"]
)

# Competitor monitoring endpoints
api_router.include_router(
    competitors.router,
    prefix="/competitors",
    tags=["Competitors"]
)

# Payment endpoints
api_router.include_router(
    payments.router,
    prefix="/payments",
    tags=["Payments"]
)

# Chat endpoints
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)

# Admin dashboard endpoints (to be implemented)
# api_router.include_router(
#     admin.router,
#     prefix="/admin",
#     tags=["Admin"]
# )


# ==================== Placeholder Endpoints ====================
# Temporary endpoints until routers are implemented

@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {
        "status": "online",
        "version": "1.0.0",
        "message": "Hanco AI API v1 is running",
        "implemented_endpoints": [
            "✅ /auth - Authentication (register, login, logout, me)"
        ]
    }


@api_router.get("/endpoints")
async def list_endpoints():
    """List all available API endpoints"""
    return {
        "implemented": [
            "✅ /auth - Authentication endpoints",
            "  - POST /auth/register - Register new user",
            "  - POST /auth/login - Login with Firebase token",
            "  - GET /auth/me - Get current user profile",
            "  - POST /auth/logout - Logout user",
            "  - POST /auth/password-reset - Request password reset",
            "  - DELETE /auth/account - Delete account"
        ],
        "pending": [
            "⏳ /vehicles - Vehicle management",
            "⏳ /bookings - Booking management",
            "⏳ /chat - AI Chatbot",
            "⏳ /pricing - Dynamic pricing",
            "⏳ /competitors - Competitor monitoring",
            "⏳ /payments - Payment processing",
            "⏳ /admin - Admin dashboard"
        ]
    }
