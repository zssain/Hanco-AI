"""
Hanco AI Chatbot Orchestrator - Production Architecture
- Async-safe Firestore operations (asyncio.to_thread)
- Strict state machine with enforcement
- Intent gate (no LLM for irrelevant messages)
- Robust date parsing
- Transactional booking with vehicle locking
- Dynamic pricing integration with decision logging
- Narrow Gemini usage (vehicle type extraction only)
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Literal

import httpx
from google.cloud import firestore

from app.core.config import settings
from app.core.firebase import db, Collections

logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-1.5-flash:generateContent"
)

# -------------------------
# State Machine Definition
# -------------------------

STATE_IDLE = "idle"
STATE_VEHICLE_TYPE = "vehicle_type"
STATE_SELECTION = "selection"
STATE_DATES = "dates"
STATE_PICKUP = "pickup"
STATE_DROPOFF = "dropoff"
STATE_INSURANCE = "insurance"
STATE_PAYMENT = "payment"
STATE_QUOTE = "quote"
STATE_CONFIRM = "confirm"
STATE_COMPLETED = "completed"

ALL_STATES = {
    STATE_IDLE,
    STATE_VEHICLE_TYPE,
    STATE_SELECTION,
    STATE_DATES,
    STATE_PICKUP,
    STATE_DROPOFF,
    STATE_INSURANCE,
    STATE_PAYMENT,
    STATE_QUOTE,
    STATE_CONFIRM,
    STATE_COMPLETED,
}

STATE_MACHINE: Dict[str, str] = {
    STATE_IDLE: STATE_VEHICLE_TYPE,
    STATE_VEHICLE_TYPE: STATE_SELECTION,
    STATE_SELECTION: STATE_DATES,
    STATE_DATES: STATE_PICKUP,
    STATE_PICKUP: STATE_DROPOFF,
    STATE_DROPOFF: STATE_INSURANCE,
    STATE_INSURANCE: STATE_PAYMENT,
    STATE_PAYMENT: STATE_QUOTE,
    STATE_QUOTE: STATE_CONFIRM,
    STATE_CONFIRM: STATE_COMPLETED,
    STATE_COMPLETED: STATE_IDLE,
}

DEFAULT_VEHICLE_TYPES = ["economy", "sedan", "suv", "luxury"]
PAYMENT_MODES = ["cash", "card"]

YES_WORDS = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm"}
NO_WORDS = {"no", "n", "nope", "cancel", "stop"}

# State order for back navigation
STATE_ORDER = [
    STATE_IDLE,
    STATE_VEHICLE_TYPE,
    STATE_SELECTION,
    STATE_DATES,
    STATE_PICKUP,
    STATE_DROPOFF,
    STATE_INSURANCE,
    STATE_PAYMENT,
    STATE_QUOTE,
    STATE_CONFIRM,
    STATE_COMPLETED,
]

# Context keys to clear when rolling back to each state
CONTEXT_KEYS_TO_CLEAR_AFTER = {
    STATE_IDLE: ["available_types", "vehicle_type", "available_vehicles", "vehicle_id", "selected_vehicle",
                 "start_date", "end_date", "duration", "available_branches", "pickup_branch_id", "pickup_branch",
                 "dropoff_branch_id", "dropoff_branch", "insurance_selected", "payment_mode", "quote",
                 "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_VEHICLE_TYPE: ["vehicle_type", "available_vehicles", "vehicle_id", "selected_vehicle",
                         "start_date", "end_date", "duration", "available_branches", "pickup_branch_id",
                         "pickup_branch", "dropoff_branch_id", "dropoff_branch", "insurance_selected",
                         "payment_mode", "quote", "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_SELECTION: ["vehicle_id", "selected_vehicle", "start_date", "end_date", "duration",
                      "available_branches", "pickup_branch_id", "pickup_branch", "dropoff_branch_id",
                      "dropoff_branch", "insurance_selected", "payment_mode", "quote", "subtotal",
                      "insurance_amount", "total_price", "booking_id"],
    STATE_DATES: ["start_date", "end_date", "duration", "available_branches", "pickup_branch_id",
                  "pickup_branch", "dropoff_branch_id", "dropoff_branch", "insurance_selected",
                  "payment_mode", "quote", "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_PICKUP: ["pickup_branch_id", "pickup_branch", "dropoff_branch_id", "dropoff_branch",
                   "insurance_selected", "payment_mode", "quote", "subtotal", "insurance_amount",
                   "total_price", "booking_id"],
    STATE_DROPOFF: ["dropoff_branch_id", "dropoff_branch", "insurance_selected", "payment_mode",
                    "quote", "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_INSURANCE: ["insurance_selected", "payment_mode", "quote", "subtotal", "insurance_amount",
                      "total_price", "booking_id"],
    STATE_PAYMENT: ["payment_mode", "quote", "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_QUOTE: ["quote", "subtotal", "insurance_amount", "total_price", "booking_id"],
    STATE_CONFIRM: ["booking_id"],
}

# -------------------------
# Utility Functions
# -------------------------

def utcnow() -> datetime:
    """Return timezone-aware UTC datetime"""
    return datetime.now(tz=timezone.utc)


def safe_int_from_text(text: str) -> Optional[int]:
    """Extract first integer from text"""
    m = re.search(r"\d+", text)
    if not m:
        return None
    try:
        return int(m.group())
    except ValueError:
        return None


def normalize_whitespace(s: str) -> str:
    """Normalize whitespace in string"""
    return re.sub(r"\s+", " ", s.strip())


# -------------------------
# Intent Gate (No LLM)
# -------------------------

@dataclass
class IntentGateResult:
    """Result of intent classification"""
    kind: Literal["continue", "restart", "back", "help", "irrelevant"]
    reply: Optional[str] = None


class IntentGate:
    """
    Cheap intent classification without calling LLM.
    Handles global commands and filters irrelevant messages.
    """

    GLOBAL_RESTART = {"restart", "start over", "reset", "new booking", "begin again"}
    GLOBAL_HELP = {"help", "how", "what can you do", "commands"}
    GLOBAL_BACK = {"back", "go back", "previous", "undo"}

    IRRELEVANT_HINTS = {
        "weather", "temperature", "forecast", "rain", "sunny",
        "who are you", "what is hanco", "company info",
        "joke", "meme", "funny",
        "complaint", "refund", "policy", "terms",
    }

    def check(self, user_message: str) -> IntentGateResult:
        """Check user intent without LLM"""
        msg = normalize_whitespace(user_message.lower())

        # Greetings always restart (handles stuck sessions)
        if msg in {"hi", "hello", "hey"}:
            return IntentGateResult(kind="restart")

        # Global restart
        if any(phrase in msg for phrase in self.GLOBAL_RESTART):
            return IntentGateResult(kind="restart")

        # Global help
        if any(phrase in msg for phrase in self.GLOBAL_HELP):
            return IntentGateResult(kind="help")

        # Global back
        if any(phrase in msg for phrase in self.GLOBAL_BACK):
            return IntentGateResult(kind="back")

        # Irrelevant message detection
        if any(hint in msg for hint in self.IRRELEVANT_HINTS):
            return IntentGateResult(kind="irrelevant")

        return IntentGateResult(kind="continue")


# -------------------------
# Date Parser (Robust)
# -------------------------

class DateParser:
    """
    Robust date parsing supporting multiple formats:
    - ISO: 2026-01-15 to 2026-01-20
    - Casual: Jan 15 to Jan 20, 15 Jan - 20 Jan
    - With year: Jan 15 2026 to Jan 20 2026
    - Ordinals: 15th Jan to 20th Jan
    """

    def parse_range(self, text: str) -> Tuple[Optional[date], Optional[date]]:
        """Parse date range from text"""
        raw = text.strip()
        # Normalize separators
        s = raw.lower().replace("–", "-").replace("—", "-")
        # Remove ordinal suffixes
        s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s)

        # Try splitting by common separators (exclude plain '-' to avoid breaking ISO dates)
        parts = []
        for separator in [" to ", " - "]:
            if separator in s:
                parts = [p.strip() for p in s.split(separator, 1)]
                break

        if len(parts) == 2:
            start = self.parse_single(parts[0])
            end = self.parse_single(parts[1])
            if start and end:
                return start, end

        # Try finding ISO dates in text
        iso_dates = re.findall(r"\d{4}-\d{2}-\d{2}", s)
        if len(iso_dates) >= 2:
            try:
                return date.fromisoformat(iso_dates[0]), date.fromisoformat(iso_dates[1])
            except Exception:
                pass

        # Optional: dateparser fallback
        try:
            import dateparser
            # Try parsing as two separate dates (exclude plain '-' to avoid breaking ISO dates)
            for separator in [" to ", " - ", " until "]:
                if separator in s:
                    parts = s.split(separator, 1)
                    if len(parts) == 2:
                        d1 = dateparser.parse(parts[0].strip())
                        d2 = dateparser.parse(parts[1].strip())
                        if d1 and d2:
                            return d1.date(), d2.date()
        except ImportError:
            pass
        except Exception:
            pass

        return None, None

    def parse_single(self, text: str) -> Optional[date]:
        """Parse single date from text"""
        t = text.strip()
        # Remove ordinal suffixes
        t = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", t)

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%b %d %Y",      # Jan 15 2026
            "%B %d %Y",      # January 15 2026
            "%d %b %Y",      # 15 Jan 2026
            "%d %B %Y",      # 15 January 2026
            "%b %d, %Y",     # Jan 15, 2026
            "%B %d, %Y",     # January 15, 2026
            "%b %d",         # Jan 15 (no year)
            "%B %d",         # January 15
            "%d %b",         # 15 Jan
            "%d %B",         # 15 January
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(t, fmt)
                # Handle missing year
                if dt.year == 1900:
                    today = date.today()
                    dt = dt.replace(year=today.year)
                    # If date is in the past, assume next year
                    if dt.date() < today:
                        dt = dt.replace(year=today.year + 1)
                return dt.date()
            except ValueError:
                continue

        # Optional: dateparser fallback
        try:
            import dateparser
            dt2 = dateparser.parse(t)
            if dt2:
                d = dt2.date()
                today = date.today()
                # If parsed date is in past (>30 days), push to next year
                if d < today and (today - d).days > 30:
                    try:
                        return date(today.year + 1, d.month, d.day)
                    except ValueError:
                        pass
                return d
        except ImportError:
            pass
        except Exception:
            pass

        return None


# -------------------------
# Firestore Store (Async-Safe)
# -------------------------

class FirestoreStore:
    """
    Async-safe Firestore operations using asyncio.to_thread.
    All sync Firestore calls are wrapped to prevent blocking FastAPI.
    """

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        def _work():
            doc = db.collection(Collections.CHAT_SESSIONS).document(session_id).get()
            return doc.to_dict() if doc.exists else None
        return await asyncio.to_thread(_work)

    async def create_session(self, session_id: str, guest_id: str) -> Dict[str, Any]:
        """Create new chat session"""
        session_data = {
            "session_id": session_id,
            "guest_id": guest_id,
            "state": STATE_IDLE,
            "context": {},
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }

        def _work():
            db.collection(Collections.CHAT_SESSIONS).document(session_id).set(session_data)
            return session_data

        return await asyncio.to_thread(_work)

    async def update_session(self, session_id: str, state: str, context: Dict[str, Any]) -> None:
        """Update session state and context"""
        def _work():
            db.collection(Collections.CHAT_SESSIONS).document(session_id).set({
                "state": state,
                "context": context,
                "updated_at": utcnow(),
            }, merge=True)
        await asyncio.to_thread(_work)

    async def store_message(self, session_id: str, user_message: str, bot_reply: str) -> None:
        """Store chat message"""
        def _work():
            message_id = str(uuid.uuid4())
            data = {
                "id": message_id,
                "session_id": session_id,
                "user_message": user_message,
                "bot_reply": bot_reply,
                "timestamp": utcnow(),
            }
            db.collection(Collections.CHAT_MESSAGES).document(message_id).set(data)
        await asyncio.to_thread(_work)

    async def fetch_available_vehicle_types(self) -> List[str]:
        """Fetch available vehicle categories"""
        def _work():
            categories = set()
            docs = (
                db.collection(Collections.VEHICLES)
                .where("availability_status", "==", "available")
                .limit(200)
                .stream()
            )
            for doc in docs:
                v = doc.to_dict()
                cat = v.get("category")
                if cat:
                    categories.add(cat)
            return sorted(list(categories))
        return await asyncio.to_thread(_work)

    async def fetch_vehicles_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch available vehicles for category"""
        def _work():
            out = []
            docs = (
                db.collection(Collections.VEHICLES)
                .where("category", "==", category)
                .where("availability_status", "==", "available")
                .limit(limit)
                .stream()
            )
            for doc in docs:
                v = doc.to_dict()
                daily_rate = v.get("current_price", v.get("base_daily_rate", 0))
                out.append({
                    "id": doc.id,
                    "make": v.get("make"),
                    "model": v.get("model"),
                    "year": v.get("year"),
                    "daily_rate": float(daily_rate or 0),
                })
            return out
        return await asyncio.to_thread(_work)

    async def fetch_active_branches(self) -> List[Dict[str, Any]]:
        """Fetch active branches"""
        def _work():
            out = []
            docs = (
                db.collection(Collections.BRANCHES)
                .where("is_active", "==", True)
                .stream()
            )
            for doc in docs:
                b = doc.to_dict()
                out.append({
                    "id": doc.id,
                    "name": b.get("name"),
                    "city": b.get("city"),
                    "address": b.get("address"),
                })
            return out
        return await asyncio.to_thread(_work)

    async def create_booking_transactional(
        self,
        booking_data: Dict[str, Any],
        vehicle_id: str,
    ) -> None:
        """
        Create booking with transactional vehicle locking.
        Atomically:
        - Verify vehicle is available
        - Create booking
        - Lock vehicle (set to reserved)
        """
        booking_id = booking_data["id"]

        def _work():
            vehicle_ref = db.collection(Collections.VEHICLES).document(vehicle_id)
            booking_ref = db.collection(Collections.BOOKINGS).document(booking_id)

            @firestore.transactional
            def txn_create(transaction):
                # Read vehicle state
                snap = vehicle_ref.get(transaction=transaction)
                if not snap.exists:
                    raise ValueError("Vehicle not found")

                v = snap.to_dict() or {}
                status = v.get("availability_status")
                expires_at = v.get("reservation_expires_at")
                now = utcnow()

                # Check if vehicle is available or has expired reservation
                if status == "reserved":
                    if not expires_at or expires_at > now:
                        raise ValueError("Vehicle is no longer available")
                    # else: expired reservation -> allow booking
                elif status != "available":
                    raise ValueError("Vehicle is no longer available")

                # Write booking
                transaction.set(booking_ref, booking_data)
                
                # Lock vehicle with TTL expiration
                transaction.update(vehicle_ref, {
                    "availability_status": "reserved",
                    "reserved_at": now,
                    "reserved_booking_id": booking_id,
                    "reservation_expires_at": now + timedelta(minutes=15),
                    "updated_at": now,
                })

            transaction = db.transaction()
            txn_create(transaction)

        await asyncio.to_thread(_work)

    async def log_pricing_decision(self, decision: Dict[str, Any]) -> None:
        """Log pricing decision for audit and ML training"""
        def _work():
            decision_id = decision.get("id") or str(uuid.uuid4())
            decision["id"] = decision_id
            decision["created_at"] = utcnow()
            db.collection(Collections.PRICING_DECISIONS).document(decision_id).set(decision)
        await asyncio.to_thread(_work)


# -------------------------
# LLM Extractor (Narrow Use)
# -------------------------

class LLMExtractor:
    """
    Narrow LLM usage - only for vehicle type extraction when needed.
    Does NOT generate general answers.
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    async def extract_vehicle_type(self, message: str, available_types: List[str]) -> Optional[str]:
        """
        Extract vehicle type from user message using Gemini.
        Returns exact category from available_types or None.
        """
        if not self.api_key:
            return None

        available_str = ", ".join(available_types) if available_types else ", ".join(DEFAULT_VEHICLE_TYPES)

        prompt = f"""Extract vehicle category from user message.

User message: "{message}"

Available categories (return EXACTLY one, case-sensitive): {available_str}

Rules:
- Output ONLY one category from list above, exactly as shown
- If multiple mentioned, return first
- If unclear, output: none
- Synonyms:
  - "car", "small car", "compact" → economy
  - "sedan", "4-door", "medium" → sedan
  - "suv", "family car", "big" → suv
  - "luxury", "premium", "high-end" → luxury

Response (one word only):"""

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 16,
                        },
                    },
                )

            if resp.status_code != 200:
                logger.warning(f"Gemini API returned {resp.status_code}")
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            text = (candidates[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")).strip()

            if not text or text.lower() == "none":
                return None

            # Harden output: strip punctuation and whitespace
            text = text.strip().lower()
            text = re.sub(r"[^a-z0-9_-]", "", text)

            # Match exactly (case-sensitive first)
            for t in (available_types or DEFAULT_VEHICLE_TYPES):
                if text == t.lower():
                    return t

            return None

        except httpx.TimeoutException:
            logger.warning("Gemini API timeout")
            return None
        except Exception as e:
            logger.error(f"Gemini extraction error: {e}")
            return None


# -------------------------
# Pricing Service
# -------------------------

class PricingService:
    """
    Dynamic pricing service with decision logging.
    Computes quotes and logs all inputs/outputs for audit and ML.
    """

    def __init__(self, store: FirestoreStore) -> None:
        self.store = store

    async def compute_quote_and_log(
        self,
        *,
        session_id: str,
        guest_id: str,
        vehicle: Dict[str, Any],
        start_date: date,
        end_date: date,
        pickup_branch: Dict[str, Any],
        dropoff_branch: Dict[str, Any],
        insurance_selected: bool,
        payment_mode: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute dynamic quote using the UNIFIED PRICING ENGINE.
        Calls the same API that frontend uses for consistent pricing.
        """
        duration_days = (end_date - start_date).days
        vehicle_id = vehicle.get("id")
        
        # Get branch key (city) for pricing
        branch_key = pickup_branch.get("city", pickup_branch.get("name", "riyadh")).lower().replace(" ", "_")
        
        # Call the unified pricing engine API (same as frontend)
        pricing_result = await self._call_unified_pricing_api(
            vehicle_id=vehicle_id,
            branch_key=branch_key,
            pickup_date=start_date,
            dropoff_date=end_date,
            include_insurance=insurance_selected,
        )
        
        if pricing_result:
            # Use the unified pricing result
            dynamic_daily = pricing_result.get("daily_rate", 200)
            subtotal = pricing_result.get("base_total", dynamic_daily * duration_days)
            insurance_amt = pricing_result.get("insurance_amount", 0)
            total = pricing_result.get("final_total", subtotal + insurance_amt)
            competitor_avg = pricing_result.get("competitor_avg")
            pricing_factors = pricing_result.get("breakdown", {})
            base_daily = pricing_result.get("breakdown", {}).get("base_daily_rate", dynamic_daily)
            multiplier = pricing_result.get("breakdown", {}).get("multiplier", 1.0)
        else:
            # Fallback if API fails - use base_daily from vehicle
            base_daily = float(
                vehicle.get("daily_rate") or 
                vehicle.get("base_daily_rate") or 
                vehicle.get("current_price") or 
                200
            )
            dynamic_daily = base_daily
            subtotal = round(dynamic_daily * duration_days, 2)
            insurance_amt = round(subtotal * 0.15, 2) if insurance_selected else 0.0
            total = round(subtotal + insurance_amt, 2)
            competitor_avg = None
            pricing_factors = {"fallback": True, "reason": "unified_api_unavailable"}
            multiplier = 1.0

        # Log decision for audit and ML training
        decision = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "guest_id": guest_id,
            "vehicle_id": vehicle_id,
            "vehicle_category": context.get("vehicle_type"),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "duration_days": duration_days,
            "pickup_branch_id": pickup_branch.get("id"),
            "dropoff_branch_id": dropoff_branch.get("id"),
            "inputs": {
                "base_daily_rate": base_daily,
                "dynamic_multiplier": multiplier,
                "insurance_selected": insurance_selected,
                "payment_mode": payment_mode,
                "competitor_avg_price": competitor_avg,
                "pricing_factors": pricing_factors,
            },
            "outputs": {
                "dynamic_daily_rate": dynamic_daily,
                "subtotal": subtotal,
                "insurance": insurance_amt,
                "total": total,
            },
            "model_version": "unified-pricing-v1",
        }

        await self.store.log_pricing_decision(decision)

        return {
            "duration": duration_days,
            "base_daily_rate": base_daily,
            "dynamic_daily_rate": dynamic_daily,
            "subtotal": subtotal,
            "insurance": insurance_amt,
            "total": total,
            "competitor_avg_price": competitor_avg,
            "pricing_factors": pricing_factors,
            "multiplier": multiplier,
        }

    async def _call_unified_pricing_api(
        self,
        vehicle_id: str,
        branch_key: str,
        pickup_date: date,
        dropoff_date: date,
        include_insurance: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the UNIFIED PRICING API - the single source of truth.
        This is the SAME endpoint that the frontend calls.
        """
        try:
            # Get backend URL - since we're in the same backend, use localhost
            # In production, use settings.BACKEND_URL if available
            backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000')
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{backend_url}/api/v1/pricing/unified-price",
                    json={
                        "vehicle_id": vehicle_id,
                        "branch_key": branch_key,
                        "pickup_date": pickup_date.isoformat(),
                        "dropoff_date": dropoff_date.isoformat(),
                        "include_insurance": include_insurance,
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[Unified Pricing] Got price for {vehicle_id}: {data.get('daily_rate')} SAR/day, total: {data.get('final_total')} SAR")
                    return data
                else:
                    logger.warning(f"[Unified Pricing] API returned {response.status_code}: {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning("[Unified Pricing] API timeout - will use fallback")
            return None
        except Exception as e:
            logger.error(f"[Unified Pricing] API error: {e}")
            return None


# -------------------------
# Inventory Service
# -------------------------

class InventoryService:
    """Service for fetching available vehicles and branches"""

    def __init__(self, store: FirestoreStore) -> None:
        self.store = store

    async def get_available_types(self) -> List[str]:
        """Get available vehicle types"""
        return await self.store.fetch_available_vehicle_types()

    async def get_vehicles_for_type(self, category: str) -> List[Dict[str, Any]]:
        """Get available vehicles for category"""
        return await self.store.fetch_vehicles_by_category(category, limit=5)

    async def get_branches(self) -> List[Dict[str, Any]]:
        """Get active branches"""
        return await self.store.fetch_active_branches()


# -------------------------
# Session Service
# -------------------------

class SessionStore:
    """Service for managing chat sessions"""

    def __init__(self, store: FirestoreStore) -> None:
        self.store = store

    async def get_or_create(self, session_id: str, guest_id: str) -> Dict[str, Any]:
        """Get existing session or create new one"""
        sess = await self.store.get_session(session_id)
        if sess:
            # Validate state
            st = sess.get("state", STATE_IDLE)
            if st not in ALL_STATES:
                sess["state"] = STATE_IDLE
            sess.setdefault("context", {})
            return sess
        return await self.store.create_session(session_id, guest_id)

    async def save(self, session_id: str, state: str, context: Dict[str, Any]) -> None:
        """Save session state"""
        await self.store.update_session(session_id, state, context)


# -------------------------
# Main Orchestrator
# -------------------------

class ChatbotOrchestrator:
    """
    Production-ready chatbot orchestrator with:
    - Strict state machine enforcement
    - Async-safe Firestore operations
    - Intent gate for global commands
    - Robust date parsing
    - Transactional booking
    - Dynamic pricing with logging
    """

    def __init__(
        self,
        *,
        session_store: SessionStore,
        inventory: InventoryService,
        pricing: PricingService,
        llm: LLMExtractor,
        intent_gate: IntentGate,
        date_parser: DateParser,
        store: FirestoreStore,
    ) -> None:
        self.session_store = session_store
        self.inventory = inventory
        self.pricing = pricing
        self.llm = llm
        self.intent_gate = intent_gate
        self.date_parser = date_parser
        self.store = store

    async def handle_message(
        self,
        user_message: str,
        session_id: str,
        guest_id: str
    ) -> Dict[str, Any]:
        """
        Handle incoming chat message.
        Returns response with reply, state, options, and data.
        """
        try:
            # Load session
            session = await self.session_store.get_or_create(session_id, guest_id)
            current_state: str = session.get("state", STATE_IDLE)
            context: Dict[str, Any] = session.get("context", {}) or {}

            logger.info(f"Session {session_id}: state={current_state}, msg_len={len(user_message)}")

            # Intent gate (no LLM)
            gate = self.intent_gate.check(user_message)

            # Handle global commands
            if gate.kind == "restart":
                reply = "✅ Restarted. What type of vehicle are you looking for?"
                next_state = STATE_VEHICLE_TYPE
                context = {}
                options = await self._get_vehicle_type_options(context)
                await self._persist(session_id, user_message, reply, next_state, context)
                return {
                    "session_id": session_id,
                    "reply": reply,
                    "state": next_state,
                    "options": options
                }

            if gate.kind == "help":
                reply = (
                    "I can help you book a vehicle in these steps:\n"
                    "1. Choose vehicle type\n"
                    "2. Select specific vehicle\n"
                    "3. Choose dates\n"
                    "4. Pick pickup location\n"
                    "5. Pick dropoff location\n"
                    "6. Add insurance (optional)\n"
                    "7. Select payment method\n"
                    "8. Confirm booking\n\n"
                    "Say 'restart' to start over."
                )
                await self._persist(session_id, user_message, reply, current_state, context)
                return {
                    "session_id": session_id,
                    "reply": reply,
                    "state": current_state
                }

            if gate.kind == "back":
                prev_state = self._get_previous_state(current_state)
                if prev_state:
                    current_state = prev_state
                    # Roll back context to prevent stale data
                    context = self._rollback_context(context, current_state)
                    reply = f"↩️ Going back. {self._get_state_prompt(current_state, context)}"
                    await self._persist(session_id, user_message, reply, current_state, context)
                    return {
                        "session_id": session_id,
                        "reply": reply,
                        "state": current_state
                    }
                reply = "You're already at the start. Say 'hi' to begin."
                await self._persist(session_id, user_message, reply, current_state, context)
                return {
                    "session_id": session_id,
                    "reply": reply,
                    "state": current_state
                }

            if gate.kind == "irrelevant":
                # Keep funnel stable without calling LLM
                reply = f"I can help with your booking 😊 {self._get_state_prompt(current_state, context)}"
                await self._persist(session_id, user_message, reply, current_state, context)
                return {
                    "session_id": session_id,
                    "reply": reply,
                    "state": current_state
                }

            # Route to state handler
            handler = {
                STATE_IDLE: self._handle_idle,
                STATE_VEHICLE_TYPE: self._handle_vehicle_type,
                STATE_SELECTION: self._handle_selection,
                STATE_DATES: self._handle_dates,
                STATE_PICKUP: self._handle_pickup,
                STATE_DROPOFF: self._handle_dropoff,
                STATE_INSURANCE: self._handle_insurance,
                STATE_PAYMENT: self._handle_payment,
                STATE_QUOTE: self._handle_quote,
                STATE_CONFIRM: self._handle_confirm,
                STATE_COMPLETED: self._handle_completed,
            }.get(current_state, self._handle_fallback)

            response = await handler(user_message, context, session_id, guest_id)

            next_state = response.get("next_state", current_state)
            proposed_next = next_state
            # Enforce state machine
            next_state = self._enforce_transition(current_state, next_state)

            context = response.get("context", context)
            reply = response["reply"]
            
            # Override reply if transition was blocked
            if next_state != proposed_next and next_state == current_state:
                reply = f"Let's continue. {self._get_state_prompt(current_state, context)}"
            options = response.get("options")
            data = response.get("data")

            await self._persist(session_id, user_message, reply, next_state, context)

            return {
                "session_id": session_id,
                "reply": reply,
                "state": next_state,
                "options": options,
                "data": data,
            }

        except Exception as e:
            logger.exception(f"Orchestrator error: {e}")
            reply = "I ran into an error. Let's start over — what type of vehicle do you need?"
            next_state = STATE_VEHICLE_TYPE
            context = {}
            await self._persist(session_id, user_message, reply, next_state, context)
            return {
                "session_id": session_id,
                "reply": reply,
                "state": next_state,
                "options": DEFAULT_VEHICLE_TYPES
            }

    # -------------------------
    # State Handlers
    # -------------------------

    async def _handle_idle(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle idle state - start booking flow"""
        types = await self.inventory.get_available_types()
        if not types:
            return {
                "reply": "👋 Welcome to Hanco AI! Unfortunately, we don't have vehicles available right now. Please check back later.",
                "next_state": STATE_IDLE,
                "context": {},
            }

        types_list = "\n".join([f"• {t}" for t in types])
        return {
            "reply": f"👋 Welcome to Hanco AI!\n\nWhat type of vehicle are you looking for?\n\n{types_list}\n\nJust tell me one.",
            "next_state": STATE_VEHICLE_TYPE,
            "context": {"available_types": types},
            "options": types,
        }

    async def _handle_vehicle_type(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle vehicle type selection"""
        msg = message.strip()
        msg_lower = msg.lower()

        available_types = context.get("available_types") or await self.inventory.get_available_types()
        context["available_types"] = available_types

        # Handle "what options" query
        if any(w in msg_lower for w in ["what", "which", "available", "options", "list", "show"]):
            if not available_types:
                return {
                    "reply": "No vehicles available right now. Please try later.",
                    "next_state": STATE_IDLE,
                    "context": {}
                }
            types_list = "\n".join([f"• **{t}**" for t in available_types])
            return {
                "reply": f"Available vehicle types:\n\n{types_list}\n\nWhich one would you like?",
                "next_state": STATE_VEHICLE_TYPE,
                "context": context,
                "options": available_types
            }

        # Try cheap keyword match first (no LLM)
        selected = None
        for t in (available_types or DEFAULT_VEHICLE_TYPES):
            if t.lower() in msg_lower or msg_lower in t.lower():
                selected = t
                break

        # If unclear, call Gemini (narrow extraction)
        if not selected:
            selected = await self.llm.extract_vehicle_type(msg, available_types)

        if not selected:
            types_list = "\n".join([f"• {t}" for t in (available_types or DEFAULT_VEHICLE_TYPES)])
            return {
                "reply": f"I didn't catch that. Please choose one:\n\n{types_list}",
                "next_state": STATE_VEHICLE_TYPE,
                "context": context,
                "options": available_types or DEFAULT_VEHICLE_TYPES
            }

        # Fetch vehicles for selected type
        vehicles = await self.inventory.get_vehicles_for_type(selected)
        if not vehicles:
            types_list = "\n".join([f"• {t}" for t in available_types]) if available_types else ""
            reply = f"Sorry, we don't have any **{selected}** available right now.\n"
            if types_list:
                reply += f"\nTry another:\n\n{types_list}"
            else:
                reply += "\nPlease try another category."
            return {
                "reply": reply,
                "next_state": STATE_VEHICLE_TYPE,
                "context": context,
                "options": available_types
            }

        context["vehicle_type"] = selected
        context["available_vehicles"] = vehicles

        vehicle_list = "\n".join([
            f"{i+1}. {v['make']} {v['model']} ({v['year']}) - {v['daily_rate']:.2f} SAR/day"
            for i, v in enumerate(vehicles)
        ])

        return {
            "reply": f"Great! Here are available **{selected}** vehicles:\n\n{vehicle_list}\n\nSelect a vehicle by number (1-{len(vehicles)}):",
            "next_state": STATE_SELECTION,
            "context": context,
            "data": {"vehicles": vehicles},
        }

    async def _handle_selection(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle vehicle selection"""
        vehicles = context.get("available_vehicles") or []
        
        # Safety: re-fetch if vehicles list missing (e.g., after back navigation)
        if not vehicles and context.get("vehicle_type"):
            vehicles = await self.inventory.get_vehicles_for_type(context["vehicle_type"])
            context["available_vehicles"] = vehicles
        
        if not vehicles:
            return {
                "reply": "Something went wrong. What type of vehicle do you want?",
                "next_state": STATE_VEHICLE_TYPE,
                "context": {}
            }

        idx = safe_int_from_text(message)
        if not idx or idx < 1 or idx > len(vehicles):
            return {
                "reply": f"Please enter a valid number between 1 and {len(vehicles)}:",
                "next_state": STATE_SELECTION,
                "context": context
            }

        selected_vehicle = vehicles[idx - 1]
        context["vehicle_id"] = selected_vehicle["id"]
        context["selected_vehicle"] = selected_vehicle

        return {
            "reply": f"Perfect! You've selected the {selected_vehicle['make']} {selected_vehicle['model']}.\n\n📅 When do you need it? Provide rental dates (e.g., 'Jan 15 to Jan 20' or '2026-01-15 to 2026-01-20'):",
            "next_state": STATE_DATES,
            "context": context,
        }

    async def _handle_dates(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle date selection with robust parsing"""
        start, end = self.date_parser.parse_range(message)

        if not start or not end:
            return {
                "reply": "I couldn't understand those dates. Try: 'Jan 15 to Jan 20' or '2026-01-15 to 2026-01-20':",
                "next_state": STATE_DATES,
                "context": context
            }

        today = date.today()
        if start < today:
            return {
                "reply": "Start date can't be in the past. Please enter valid dates:",
                "next_state": STATE_DATES,
                "context": context
            }
        if end <= start:
            return {
                "reply": "End date must be after start date. Please enter valid dates:",
                "next_state": STATE_DATES,
                "context": context
            }
        
        # Sanity checks for date range
        validation_error = self._validate_date_range(start, end)
        if validation_error:
            return {
                "reply": validation_error,
                "next_state": STATE_DATES,
                "context": context
            }

        duration = (end - start).days
        context["start_date"] = start.isoformat()
        context["end_date"] = end.isoformat()
        context["duration"] = duration

        # Fetch branches
        branches = await self.inventory.get_branches()
        if not branches:
            return {
                "reply": "No branches are available right now. Please try later.",
                "next_state": STATE_IDLE,
                "context": {}
            }

        context["available_branches"] = branches
        branch_list = "\n".join([
            f"{i+1}. {b['name']} ({b['city']}) - {b['address']}"
            for i, b in enumerate(branches)
        ])

        return {
            "reply": f"📍 Where would you like to pick up the vehicle?\n\n{branch_list}\n\nSelect pickup location by number:",
            "next_state": STATE_PICKUP,
            "context": context,
            "data": {"branches": branches},
        }

    async def _handle_pickup(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle pickup branch selection"""
        branches = context.get("available_branches") or []
        
        # Safety: re-fetch if branches list missing (e.g., after back navigation)
        if not branches:
            branches = await self.inventory.get_branches()
            context["available_branches"] = branches
        
        if not branches:
            return {
                "reply": "No branches available. Please try later.",
                "next_state": STATE_IDLE,
                "context": {}
            }
        
        idx = safe_int_from_text(message)
        if not idx or idx < 1 or idx > len(branches):
            return {
                "reply": f"Please enter a valid number between 1 and {len(branches)}:",
                "next_state": STATE_PICKUP,
                "context": context
            }

        b = branches[idx - 1]
        context["pickup_branch_id"] = b["id"]
        context["pickup_branch"] = b

        branch_list = "\n".join([
            f"{i+1}. {x['name']} ({x['city']}) - {x['address']}"
            for i, x in enumerate(branches)
        ])
        return {
            "reply": f"✅ Pickup: {b['name']}\n\n📍 Where would you like to drop off?\n\n{branch_list}\n\nSelect dropoff location by number:",
            "next_state": STATE_DROPOFF,
            "context": context,
        }

    async def _handle_dropoff(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle dropoff branch selection"""
        branches = context.get("available_branches") or []
        
        # Safety: re-fetch if branches list missing (e.g., after back navigation)
        if not branches:
            branches = await self.inventory.get_branches()
            context["available_branches"] = branches
        
        if not branches:
            return {
                "reply": "No branches available. Please try later.",
                "next_state": STATE_IDLE,
                "context": {}
            }
        
        idx = safe_int_from_text(message)
        if not idx or idx < 1 or idx > len(branches):
            return {
                "reply": f"Please enter a valid number between 1 and {len(branches)}:",
                "next_state": STATE_DROPOFF,
                "context": context
            }

        b = branches[idx - 1]
        context["dropoff_branch_id"] = b["id"]
        context["dropoff_branch"] = b

        return {
            "reply": "🛡️ Would you like to add insurance? (15% of subtotal)\n\nReply 'yes' or 'no':",
            "next_state": STATE_INSURANCE,
            "context": context,
        }

    async def _handle_insurance(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle insurance selection"""
        msg = message.lower().strip()
        if any(w in msg for w in YES_WORDS):
            context["insurance_selected"] = True
        elif any(w in msg for w in NO_WORDS):
            context["insurance_selected"] = False
        else:
            return {
                "reply": "Please reply 'yes' or 'no' for insurance:",
                "next_state": STATE_INSURANCE,
                "context": context
            }

        return {
            "reply": f"{'✅ Insurance added' if context['insurance_selected'] else '❌ No insurance'}\n\n💳 How would you like to pay?\n\nOptions: cash, card",
            "next_state": STATE_PAYMENT,
            "context": context,
            "options": PAYMENT_MODES,
        }

    async def _handle_payment(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle payment mode selection"""
        msg = message.lower()
        payment = None
        for m in PAYMENT_MODES:
            if m in msg:
                payment = m
                break
        if not payment:
            return {
                "reply": "Please choose 'cash' or 'card':",
                "next_state": STATE_PAYMENT,
                "context": context,
                "options": PAYMENT_MODES
            }

        context["payment_mode"] = payment
        # Next state is QUOTE (fixed from inconsistency)
        return {
            "reply": "✅ Got it. Generating your quote…",
            "next_state": STATE_QUOTE,
            "context": context
        }

    async def _handle_quote(self, _message: str, context: Dict[str, Any], session_id: str, guest_id: str) -> Dict[str, Any]:
        """Handle quote generation with dynamic pricing and competitor analysis"""
        vehicle = context.get("selected_vehicle") or {}
        pickup = context.get("pickup_branch") or {}
        dropoff = context.get("dropoff_branch") or {}

        if not vehicle or not context.get("start_date") or not context.get("end_date"):
            return {
                "reply": "Something is missing. Let's restart. What type of vehicle do you want?",
                "next_state": STATE_VEHICLE_TYPE,
                "context": {}
            }

        start = date.fromisoformat(context["start_date"])
        end = date.fromisoformat(context["end_date"])

        # Compute dynamic quote with competitor analysis and log decision
        quote = await self.pricing.compute_quote_and_log(
            session_id=session_id,
            guest_id=guest_id,
            vehicle=vehicle,
            start_date=start,
            end_date=end,
            pickup_branch=pickup,
            dropoff_branch=dropoff,
            insurance_selected=bool(context.get("insurance_selected")),
            payment_mode=context.get("payment_mode", "cash"),
            context=context,
        )

        context["quote"] = quote
        context["total_price"] = quote["total"]
        context["subtotal"] = quote["subtotal"]
        context["insurance_amount"] = quote["insurance"]

        # Build competitive analysis message
        competitor_info = ""
        if quote.get("competitor_avg_price"):
            competitor_price = quote["competitor_avg_price"]
            our_price = quote["total"]
            difference = competitor_price - our_price
            savings_pct = (difference / competitor_price * 100) if competitor_price > 0 else 0
            
            if difference > 0:
                competitor_info = f"""
━━━━━━━━━━━━━━━━━━━━━━
💰 **MARKET COMPARISON**

📊 Competitor Average: {competitor_price:.2f} SAR
🎯 Our AI Price: {our_price:.2f} SAR

🎉 **YOU SAVE: {difference:.2f} SAR ({savings_pct:.1f}% cheaper!)**
━━━━━━━━━━━━━━━━━━━━━━
"""
            elif difference < 0:
                competitor_info = f"""
━━━━━━━━━━━━━━━━━━━━━━
💰 **MARKET COMPARISON**

📊 Competitor Average: {competitor_price:.2f} SAR
🎯 Our Premium Price: {our_price:.2f} SAR

⭐ Premium service (+{abs(difference):.2f} SAR for enhanced quality)
━━━━━━━━━━━━━━━━━━━━━━
"""
            else:
                competitor_info = f"""
━━━━━━━━━━━━━━━━━━━━━━
💰 **MARKET COMPARISON**

📊 Competitor Average: {competitor_price:.2f} SAR
🎯 Our Price: {our_price:.2f} SAR

✅ Competitive market rate
━━━━━━━━━━━━━━━━━━━━━━
"""

        # Build dynamic pricing explanation
        pricing_factors = ""
        if quote.get("pricing_factors"):
            factors = quote["pricing_factors"]
            factor_lines = []
            
            if factors.get("demand_surge"):
                factor_lines.append(f"  📈 High demand period (+{factors['demand_surge']:.0%})")
            if factors.get("utilization_discount"):
                factor_lines.append(f"  📊 Fleet optimization (-{abs(factors['utilization_discount']):.0%})")
            if factors.get("duration_discount"):
                factor_lines.append(f"  ⏰ Multi-day discount (-{abs(factors['duration_discount']):.0%})")
            if factors.get("seasonal_adjustment"):
                adj = factors['seasonal_adjustment']
                symbol = "+" if adj > 0 else ""
                factor_lines.append(f"  🌍 Seasonal rate ({symbol}{adj:.0%})")
            if factors.get("weekend_surge"):
                factor_lines.append(f"  🎉 Weekend demand (+{factors['weekend_surge']:.0%})")
            
            if factor_lines:
                pricing_factors = f"\n⚡ **AI Pricing Factors:**\n" + "\n".join(factor_lines) + "\n"

        reply = f"""
📊 **YOUR PERSONALIZED QUOTE**

🚗 Vehicle: {vehicle.get('make')} {vehicle.get('model')}
📅 Duration: {quote['duration']} days ({context['start_date']} to {context['end_date']})
📍 Pickup: {pickup.get('name', 'N/A')}
📍 Dropoff: {dropoff.get('name', 'N/A')}

💵 Base Rate: {quote['base_daily_rate']:.2f} SAR/day
⚡ AI-Optimized Rate: {quote['dynamic_daily_rate']:.2f} SAR/day
{pricing_factors}
💵 Subtotal: {quote['subtotal']:.2f} SAR
🛡️ Insurance (15%): {quote['insurance']:.2f} SAR
💳 Payment Method: {context.get('payment_mode', 'cash').upper()}

━━━━━━━━━━━━━━━━━━━━━━
**YOUR TOTAL: {quote['total']:.2f} SAR**
━━━━━━━━━━━━━━━━━━━━━━
{competitor_info}
✅ AI-optimized competitive pricing
🔒 Price locked for 15 minutes

Would you like to confirm this booking? (yes/no)
""".strip()

        return {
            "reply": reply,
            "next_state": STATE_CONFIRM,
            "context": context,
            "data": {"quote": quote}
        }

    async def _handle_confirm(self, message: str, context: Dict[str, Any], session_id: str, guest_id: str) -> Dict[str, Any]:
        """Handle booking confirmation with transactional vehicle locking"""
        msg = message.lower()

        if any(w in msg for w in YES_WORDS):
            # Idempotency check - prevent duplicate bookings
            if context.get("booking_id"):
                # Already booked
                existing_booking_id = context["booking_id"]
                summary = context.get("booking_summary", {})
                vehicle_info = f"{summary.get('make', 'N/A')} {summary.get('model', 'N/A')}" if summary else "your vehicle"
                return {
                    "reply": f"✅ Booking already confirmed!\n\nBooking ID: {existing_booking_id[:8]}\n\nVehicle: {vehicle_info}\n\nSay 'hi' to start a new booking.",
                    "next_state": STATE_COMPLETED,
                    "context": context,
                    "data": {"booking_id": existing_booking_id}
                }
            
            # Create booking with transactional vehicle lock
            try:
                booking_id = str(uuid.uuid4())

                booking_data = {
                    "id": booking_id,
                    "session_id": session_id,
                    "guest_id": guest_id,
                    "vehicle_id": context["vehicle_id"],
                    "start_date": context["start_date"],
                    "end_date": context["end_date"],
                    "pickup_branch_id": context["pickup_branch_id"],
                    "dropoff_branch_id": context["dropoff_branch_id"],
                    "insurance_selected": bool(context.get("insurance_selected", False)),
                    "insurance_amount": float(context.get("insurance_amount", 0)),
                    "total_price": float(context.get("total_price", 0)),
                    "payment_mode": context.get("payment_mode", "cash"),
                    "status": "pending",
                    "payment_status": "pending",
                    "created_at": utcnow(),
                    "updated_at": utcnow(),
                }

                await self.store.create_booking_transactional(
                    booking_data,
                    vehicle_id=context["vehicle_id"]
                )

                vehicle = context.get("selected_vehicle", {})
                pickup = context.get("pickup_branch", {})
                dropoff = context.get("dropoff_branch", {})

                confirmation = f"""
✅ **BOOKING CONFIRMED!**

Booking ID: {booking_id[:8]}

🚗 Vehicle: {vehicle.get('make')} {vehicle.get('model')}
📅 Dates: {context['start_date']} to {context['end_date']}
📍 Pickup: {pickup.get('name')}
📍 Dropoff: {dropoff.get('name')}
💵 Total: {float(context.get('total_price', 0)):.2f} SAR

Thank you for choosing Hanco AI! Your booking is confirmed.

Need anything else? Say 'hi' to start a new booking.
""".strip()

                # Minimize context - keep booking_id and summary for idempotency
                return {
                    "reply": confirmation,
                    "next_state": STATE_COMPLETED,
                    "context": {
                        "booking_id": booking_id,
                        "booking_summary": {
                            "make": vehicle.get("make"),
                            "model": vehicle.get("model")
                        }
                    },
                    "data": {"booking_id": booking_id}
                }

            except ValueError as e:
                # Vehicle no longer available (race condition)
                logger.warning(f"Booking failed: {e}")
                return {
                    "reply": "Sorry — that vehicle just became unavailable. Let's pick another vehicle type.",
                    "next_state": STATE_VEHICLE_TYPE,
                    "context": {}
                }
            except Exception as e:
                logger.exception(f"Booking creation failed: {e}")
                return {
                    "reply": "Sorry, there was an error creating your booking. Please try again later.",
                    "next_state": STATE_IDLE,
                    "context": {}
                }

        if any(w in msg for w in NO_WORDS):
            return {
                "reply": "Booking cancelled. Say 'hi' to start again.",
                "next_state": STATE_IDLE,
                "context": {}
            }

        return {
            "reply": "Please reply 'yes' to confirm or 'no' to cancel:",
            "next_state": STATE_CONFIRM,
            "context": context
        }

    async def _handle_completed(self, message: str, context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Handle completed state"""
        if message.strip().lower() in {"hi", "hello", "hey"}:
            return await self._handle_idle(message, {}, *_args)
        return {
            "reply": "✅ You're all set. Say 'hi' to start a new booking.",
            "next_state": STATE_COMPLETED,
            "context": {}
        }

    async def _handle_fallback(self, _message: str, _context: Dict[str, Any], *_args) -> Dict[str, Any]:
        """Fallback handler for unexpected states"""
        return {
            "reply": "I'm having trouble. Let's start over. What type of vehicle do you need?",
            "next_state": STATE_VEHICLE_TYPE,
            "context": {}
        }

    # -------------------------
    # Internal Utilities
    # -------------------------

    def _rollback_context(self, context: Dict[str, Any], to_state: str) -> Dict[str, Any]:
        """Roll back context when navigating backwards to prevent stale data"""
        keys_to_clear = CONTEXT_KEYS_TO_CLEAR_AFTER.get(to_state, [])
        for key in keys_to_clear:
            context.pop(key, None)
        return context

    def _validate_date_range(self, start: date, end: date) -> Optional[str]:
        """Validate date range for sanity checks"""
        MAX_DURATION_DAYS = 60
        MAX_FUTURE_DAYS = 365
        
        today = date.today()
        duration = (end - start).days
        days_until_start = (start - today).days
        
        if duration > MAX_DURATION_DAYS:
            return f"Maximum rental duration is {MAX_DURATION_DAYS} days. Please choose a shorter period."
        
        if days_until_start > MAX_FUTURE_DAYS:
            return f"You can only book up to {MAX_FUTURE_DAYS} days in advance. Please choose closer dates."
        
        return None

    async def _persist(
        self,
        session_id: str,
        user_message: str,
        reply: str,
        state: str,
        context: Dict[str, Any]
    ) -> None:
        """Persist session and message"""
        await self.session_store.save(session_id, state, context)
        await self.store.store_message(session_id, user_message, reply)

    def _enforce_transition(self, current_state: str, proposed_next: str) -> str:
        """Enforce strict state machine transitions"""
        if current_state not in STATE_MACHINE:
            return proposed_next if proposed_next in ALL_STATES else STATE_IDLE

        allowed_next = STATE_MACHINE[current_state]
        
        # Allow staying in same state (re-prompt)
        if proposed_next == current_state:
            return proposed_next
        
        # Allow strict forward transition
        if proposed_next == allowed_next:
            return proposed_next

        # Block invalid transition
        logger.warning(
            f"Blocked invalid transition: {current_state} -> {proposed_next} "
            f"(allowed: {allowed_next})"
        )
        return current_state

    def _get_previous_state(self, state: str) -> Optional[str]:
        """Get previous state for back navigation"""
        for s, nxt in STATE_MACHINE.items():
            if nxt == state:
                return s
        return None

    async def _get_vehicle_type_options(self, context: Dict[str, Any]) -> List[str]:
        """Get available vehicle type options"""
        types = context.get("available_types")
        if not types:
            types = await self.inventory.get_available_types()
        return types or DEFAULT_VEHICLE_TYPES

    def _get_state_prompt(self, state: str, context: Dict[str, Any]) -> str:
        """Get prompt text for current state"""
        prompts = {
            STATE_IDLE: "Say 'hi' to begin.",
            STATE_VEHICLE_TYPE: "What type of vehicle are you looking for? (e.g., economy, sedan, suv, luxury)",
            STATE_SELECTION: "Please select a vehicle by number.",
            STATE_DATES: "Please provide your rental dates (e.g., 'Jan 15 to Jan 20').",
            STATE_PICKUP: "Please choose your pickup branch by number.",
            STATE_DROPOFF: "Please choose your dropoff branch by number.",
            STATE_INSURANCE: "Do you want insurance? Reply yes/no.",
            STATE_PAYMENT: "How would you like to pay? (cash/card)",
            STATE_QUOTE: "Generating your quote…",
            STATE_CONFIRM: "Confirm booking? Reply yes/no.",
            STATE_COMPLETED: "Say 'hi' to start a new booking.",
        }
        return prompts.get(state, "Please continue.")


# -------------------------
# Dependency Injection
# -------------------------

def build_orchestrator() -> ChatbotOrchestrator:
    """
    Build orchestrator with all dependencies.
    Use this in FastAPI dependency injection.
    """
    store = FirestoreStore()
    session_store = SessionStore(store)
    inventory = InventoryService(store)
    pricing = PricingService(store)
    llm = LLMExtractor(settings.GEMINI_API_KEY)
    intent_gate = IntentGate()
    date_parser = DateParser()

    return ChatbotOrchestrator(
        session_store=session_store,
        inventory=inventory,
        pricing=pricing,
        llm=llm,
        intent_gate=intent_gate,
        date_parser=date_parser,
        store=store,
    )


# Global instance (or use FastAPI dependency injection)
orchestrator = build_orchestrator()