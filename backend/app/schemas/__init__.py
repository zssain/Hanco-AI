"""
Pydantic schemas for request/response validation
API input/output models
"""
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    UserResponse,
    TokenRefreshRequest,
    TokenResponse,
    PasswordResetRequest,
    PasswordUpdateRequest,
)
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
    VehicleSearchRequest,
)
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
    BookingSearchRequest,
)
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatStreamResponse,
)
from app.schemas.pricing import (
    PricingRequest,
    PricingResponse,
    PricingFactors,
    CompetitorPriceResponse,
    PricingLogResponse,
)
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentConfirmRequest,
    RefundRequest,
)

__all__ = [
    # Auth
    'RegisterRequest',
    'LoginRequest',
    'LoginResponse',
    'UserResponse',
    'TokenRefreshRequest',
    'TokenResponse',
    'PasswordResetRequest',
    'PasswordUpdateRequest',
    # Vehicle
    'VehicleCreate',
    'VehicleUpdate',
    'VehicleResponse',
    'VehicleListResponse',
    'VehicleSearchRequest',
    # Booking
    'BookingCreate',
    'BookingUpdate',
    'BookingResponse',
    'BookingListResponse',
    'BookingSearchRequest',
    # Chat
    'ChatSessionCreate',
    'ChatSessionResponse',
    'ChatMessageRequest',
    'ChatMessageResponse',
    'ChatHistoryResponse',
    'ChatStreamResponse',
    # Pricing
    'PricingRequest',
    'PricingResponse',
    'PricingFactors',
    'CompetitorPriceResponse',
    'PricingLogResponse',
    # Payment
    'PaymentCreate',
    'PaymentResponse',
    'PaymentIntentRequest',
    'PaymentIntentResponse',
    'PaymentConfirmRequest',
    'RefundRequest',
]
