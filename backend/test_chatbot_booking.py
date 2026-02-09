"""
Test Chatbot and Booking Flow
"""
import asyncio
from app.services.chatbot.orchestrator import ChatbotOrchestrator
from app.core.firebase import db, Collections

async def test_chatbot():
    print("=" * 60)
    print("CHATBOT TEST")
    print("=" * 60)
    
    # Initialize chatbot
    try:
        orchestrator = ChatbotOrchestrator()
        print("   ✅ ChatbotOrchestrator initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        return
    
    # Test a simple booking flow
    test_session_id = "test_session_123"
    
    print("\n1. Testing greeting:")
    try:
        response = await orchestrator.process_message(
            session_id=test_session_id,
            guest_id="test_guest",
            message="Hi, I want to rent a car"
        )
        print(f"   Bot: {response.get('reply', 'No reply')[:100]}...")
        print(f"   State: {response.get('state', 'unknown')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Testing vehicle type selection:")
    try:
        response = await orchestrator.process_message(
            session_id=test_session_id,
            guest_id="test_guest",
            message="I want an SUV"
        )
        print(f"   Bot: {response.get('reply', 'No reply')[:100]}...")
        print(f"   State: {response.get('state', 'unknown')}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("CHATBOT TEST COMPLETE")
    print("=" * 60)


async def test_booking_flow():
    print("\n" + "=" * 60)
    print("BOOKING FLOW TEST")
    print("=" * 60)
    
    # Check if bookings API works
    print("\n1. Checking existing bookings:")
    try:
        bookings = list(db.collection(Collections.BOOKINGS).limit(3).stream())
        print(f"   Found {len(bookings)} bookings")
        for b in bookings[:2]:
            data = b.to_dict()
            print(f"   - {b.id}: vehicle={data.get('vehicle_id')}, status={data.get('status')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check vehicles available for booking
    print("\n2. Checking available vehicles:")
    try:
        vehicles = list(db.collection(Collections.VEHICLES).where("availability_status", "==", "available").limit(5).stream())
        print(f"   Found {len(vehicles)} available vehicles")
        for v in vehicles[:3]:
            data = v.to_dict()
            print(f"   - {v.id}: {data.get('name')}, Branch: {data.get('branch_id')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("BOOKING FLOW TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_chatbot())
    asyncio.run(test_booking_flow())
