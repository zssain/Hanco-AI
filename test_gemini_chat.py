"""
Quick test script for Gemini chatbot integration
"""
import requests
import json

# Test endpoint
CHAT_URL = "http://localhost:8000/api/v1/chat/message"

# Test messages
test_messages = [
    "Hello, can you help me?",
    "What's the cheapest SUV for a week in Riyadh?",
    "Compare sedans vs SUVs",
    "Do you have luxury cars available?",
    "What are your office hours?",
]

def test_chat(message: str, session_id: str = "test_session_123"):
    """Send a test message to the chatbot"""
    print(f"\n{'='*60}")
    print(f"📤 USER: {message}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            CHAT_URL,
            json={
                "session_id": session_id,
                "message": message
            },
            headers={
                "Content-Type": "application/json",
                # Note: In production, you'd need a valid Firebase token
                # For testing, we can try without auth or mock it
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ STATUS: Success")
            print(f"🤖 ASSISTANT: {data.get('reply', 'No reply')}")
            print(f"🎯 INTENT: {data.get('intent', 'Unknown')}")
            if data.get('extracted'):
                print(f"📊 EXTRACTED: {json.dumps(data.get('extracted'), indent=2)}")
            if data.get('pricing_info'):
                print(f"💰 PRICING: {json.dumps(data.get('pricing_info'), indent=2)}")
        else:
            print(f"❌ ERROR: Status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the backend running on port 8000?")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🧪 Testing Gemini Chatbot Integration")
    print("=" * 60)
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:5173")
    print("=" * 60)
    
    # Test each message
    for i, msg in enumerate(test_messages, 1):
        print(f"\n\n🧪 TEST {i}/{len(test_messages)}")
        test_chat(msg)
        
    print("\n\n" + "="*60)
    print("✅ Test complete! Check the responses above.")
    print("="*60)
    print("\n💡 TIP: Open http://localhost:5173 and test the chatbot UI!")
    print("   Try asking natural questions like:")
    print("   - 'Show me available SUVs in Jeddah'")
    print("   - 'How much does it cost to rent a sedan?'")
    print("   - 'Compare your prices with competitors'")
