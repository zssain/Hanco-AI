"""
Test script to verify chatbot integration
Tests orchestrator and API endpoints
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.chatbot.orchestrator import (
    detect_intent_and_extract,
    _fallback_intent_detection,
    _extract_basic_info,
    generate_reply
)


async def test_intent_detection():
    """Test intent detection with various messages"""
    
    test_cases = [
        {
            "message": "Hello! I'm looking for a car",
            "expected_intent": "greeting"
        },
        {
            "message": "How much does it cost to rent a sedan in Riyadh from 2025-12-10 to 2025-12-15?",
            "expected_intent": "pricing_request"
        },
        {
            "message": "Compare your prices with Budget Saudi and Hertz",
            "expected_intent": "compare_competitors"
        },
        {
            "message": "I want to book an SUV",
            "expected_intent": "booking_help"
        },
        {
            "message": "What vehicles do you have?",
            "expected_intent": "vehicle_inquiry"
        }
    ]
    
    print("=" * 80)
    print("CHATBOT INTEGRATION TEST")
    print("=" * 80)
    print()
    
    print("Testing Rule-Based Intent Detection (Fallback)")
    print("-" * 80)
    
    for i, case in enumerate(test_cases, 1):
        message = case['message']
        expected = case['expected_intent']
        
        result = _fallback_intent_detection(message)
        detected = result['intent']
        confidence = result['confidence']
        extracted = result.get('extracted', {})
        
        status = "✅ PASS" if detected == expected else f"❌ FAIL (expected {expected})"
        
        print(f"\n{i}. Test Case: \"{message}\"")
        print(f"   Expected: {expected}")
        print(f"   Detected: {detected} (confidence: {confidence})")
        print(f"   Status: {status}")
        
        if extracted:
            print(f"   Extracted: {extracted}")


async def test_extraction():
    """Test structured data extraction"""
    
    print("\n" + "=" * 80)
    print("Testing Data Extraction")
    print("-" * 80)
    
    test_messages = [
        "I need a sedan in Riyadh from 2025-12-10 to 2025-12-15",
        "Looking for an SUV in Jeddah",
        "What's the price for a luxury car in Mecca?",
        "Economy car rental in Dammam"
    ]
    
    for i, message in enumerate(test_messages, 1):
        extracted = _extract_basic_info(message)
        
        print(f"\n{i}. Message: \"{message}\"")
        print(f"   Extracted:")
        print(f"   - City: {extracted.get('city')}")
        print(f"   - Start Date: {extracted.get('start_date')}")
        print(f"   - End Date: {extracted.get('end_date')}")
        print(f"   - Vehicle Category: {extracted.get('vehicle_category')}")


async def test_reply_generation():
    """Test reply generation"""
    
    print("\n" + "=" * 80)
    print("Testing Reply Generation")
    print("-" * 80)
    
    # Test greeting
    print("\n1. Greeting Intent")
    reply = await generate_reply(
        intent="greeting",
        extracted={},
        pricing_info=None,
        user_message="Hello"
    )
    print(f"   Reply: {reply[:100]}...")
    
    # Test pricing request without data
    print("\n2. Pricing Request (missing data)")
    reply = await generate_reply(
        intent="pricing_request",
        extracted={'city': 'riyadh', 'vehicle_category': 'sedan'},
        pricing_info={'error': 'No pricing data'},
        user_message="How much for a sedan in Riyadh?"
    )
    print(f"   Reply: {reply[:100]}...")
    
    # Test booking help with missing fields
    print("\n3. Booking Help (missing fields)")
    reply = await generate_reply(
        intent="booking_help",
        extracted={'city': 'jeddah'},
        pricing_info=None,
        user_message="I want to book a car"
    )
    print(f"   Reply: {reply[:100]}...")
    
    # Test vehicle inquiry
    print("\n4. Vehicle Inquiry")
    reply = await generate_reply(
        intent="vehicle_inquiry",
        extracted={},
        pricing_info=None,
        user_message="What cars do you have?"
    )
    print(f"   Reply: {reply[:100]}...")


async def test_full_orchestrator():
    """Test the complete orchestrator flow (without Firestore)"""
    
    print("\n" + "=" * 80)
    print("Testing Full Orchestrator Flow (Without Firestore)")
    print("-" * 80)
    
    print("\nNOTE: This test uses fallback mode (no AI APIs, no Firestore)")
    print("Full integration requires:")
    print("  1. GEMINI_API_KEY configured in .env or config")
    print("  2. Firestore connection active")
    print("  3. Server running with valid Firebase credentials")
    
    test_messages = [
        "Hello!",
        "I need a sedan in Riyadh from 2025-12-10 to 2025-12-15",
        "Compare prices with competitors"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. User: \"{message}\"")
        
        # Test intent detection only (no Firestore)
        result = await detect_intent_and_extract(
            user_message=message,
            conversation_history=[],
            use_gemini=False  # Force fallback
        )
        
        print(f"   Intent: {result['intent']}")
        print(f"   Confidence: {result['confidence']}")
        if result.get('extracted'):
            print(f"   Extracted: {result['extracted']}")


async def main():
    """Run all tests"""
    try:
        await test_intent_detection()
        await test_extraction()
        await test_reply_generation()
        await test_full_orchestrator()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nNext Steps:")
        print("1. Start the server: python run-dev.py")
        print("2. Check API docs: http://localhost:8000/docs")
        print("3. Test chat endpoints:")
        print("   - POST /api/v1/chat/message")
        print("   - GET /api/v1/chat/sessions")
        print("   - GET /api/v1/chat/sessions/{session_id}")
        print("   - DELETE /api/v1/chat/sessions/{session_id}")
        print("\n4. Configure Gemini API key for full AI features")
        print("5. Test with real conversations in the API")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
