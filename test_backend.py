#!/usr/bin/env python3
"""
Simple test script to verify the backend chat endpoint is working.
Run this after starting the backend server.
"""

import requests
import json

def test_chat_endpoint():
    """Test the chat endpoint with a sample health issue."""
    
    url = "http://localhost:8000/chat"
    
    # Test data - user describing a UTI
    test_data = {
        "message": "I think I have a UTI, I'm experiencing burning when I pee and frequent urination",
        "session_id": None
    }
    
    try:
        print("Testing chat endpoint...")
        print(f"URL: {url}")
        print(f"Data: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(url, json=test_data)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nSuccess! Response:")
            print(json.dumps(data, indent=2))
            
            # Check if we got a session ID
            if data.get("session_id"):
                print(f"\n✅ Session ID received: {data['session_id']}")
            else:
                print("\n❌ No session ID received")
                
            # Check if we got a message/question
            if data.get("message"):
                print(f"\n✅ Message/Question received: {data['message']}")
            else:
                print("\n❌ No message/question received")
                
        else:
            print(f"\n❌ Error response:")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed! Make sure the backend server is running on localhost:8000")
        print("Run: python main.py")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    test_chat_endpoint()
