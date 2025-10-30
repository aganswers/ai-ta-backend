#!/usr/bin/env python3
"""
Test the /Chat endpoint with the exact request from the frontend.
"""

import requests
import json
import time

def test_real_chat_request():
    """Test with the actual frontend request."""
    
    url = "http://127.0.0.1:8001/Chat"
    
    # Exact payload from frontend
    payload = {
        "conversation": {
            "id": "9a7f3306-0026-44ea-94d6-3fdfb583333e",
            "name": "find all strawberries and thei...",
            "messages": [
                {
                    "id": "e3137a75-1917-4439-a3fd-63c25899142b",
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "find all strawberries and their control methods for pests then search what the best next steps are"
                        }
                    ],
                    "contexts": []
                }
            ],
            "model": {
                "id": "google/gemini-2.5-flash",
                "name": "Google Gemini 2.5 Flash",
                "provider": "Google",
                "tokenLimit": 250000,
                "enabled": True,
                "logo": "/media/models/google.png"
            },
            "prompt": "You are a helpful AI assistant. Follow instructions carefully. Respond using markdown.",
            "temperature": 0.1,
            "userEmail": "aidanandrews0@gmail.com",
            "projectName": "test",
        },
        "key": "",
        "course_name": "test",
        "stream": True,
        "model": {
            "id": "google/gemini-2.5-flash",
            "name": "Google Gemini 2.5 Flash",
            "provider": "Google",
            "tokenLimit": 250000,
            "enabled": True,
            "logo": "/media/models/google.png"
        },
        "skipQueryRewrite": True
    }
    
    print("="*80)
    print("TESTING REAL CHAT REQUEST")
    print("="*80)
    print(f"URL: {url}")
    print(f"Course: test")
    print(f"Query: find all strawberries and their control methods for pests...")
    print()
    
    try:
        print("Sending request...")
        start_time = time.time()
        
        response = requests.post(
            url,
            json=payload,
            stream=True,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
        
        print()
        print("="*80)
        print("STREAMING RESPONSE")
        print("="*80)
        
        text_content = []
        event_count = 0
        tool_calls = []
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
                
            if line.startswith("data: "):
                event_json = line[6:]
                try:
                    event = json.loads(event_json)
                    event_count += 1
                    event_type = event.get("type", "unknown")
                    
                    # Debug: print all events
                    print(f"\n[Event {event_count}: {event_type}]", flush=True)
                    if event_count <= 3:  # Print first 3 events in detail
                        print(f"  {json.dumps(event, indent=2)[:500]}")
                    
                    if event_type == "content_update":
                        content = event.get("content", {})
                        parts = content.get("parts", [])
                        for part in parts:
                            if "text" in part and part["text"]:
                                text = part["text"]
                                text_content.append(text)
                                print(text, end="", flush=True)
                    
                    elif event_type == "tool_invocation":
                        tool_name = event.get("toolName", "unknown")
                        tool_calls.append(f"Calling: {tool_name}")
                        print(f"\n\n🔧 [Tool Call: {tool_name}]", flush=True)
                    
                    elif event_type == "tool_result":
                        tool_name = event.get("toolName", "unknown")
                        print(f"\n✅ [Tool Result: {tool_name}]", flush=True)
                    
                except json.JSONDecodeError:
                    pass
        
        elapsed = time.time() - start_time
        
        print("\n")
        print("="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total events: {event_count}")
        print(f"Tool calls: {len(tool_calls)}")
        print(f"Response length: {len(''.join(text_content))} chars")
        print(f"Time elapsed: {elapsed:.2f}s")
        
        if tool_calls:
            print(f"\nTools used:")
            for tool in tool_calls:
                print(f"  - {tool}")
        
        full_response = "".join(text_content)
        
        # Check if the response references the data
        print("\n" + "="*80)
        print("DATA ACCESS CHECK")
        print("="*80)
        
        checks = [
            ("mentions 'strawberries'", "strawberr" in full_response.lower()),
            ("mentions 'biological'", "biological" in full_response.lower()),
            ("mentions 'pest'", "pest" in full_response.lower()),
            ("used file/code tools", any("run_code" in t or "file" in t.lower() for t in tool_calls)),
            ("response has content", len(full_response) > 50)
        ]
        
        for check_name, result in checks:
            status = "✅" if result else "❌"
            print(f"{status} {check_name}")
        
        all_passed = all(result for _, result in checks)
        
        print("\n" + "="*80)
        if all_passed:
            print("✅ SUCCESS: Agent accessed and used Drive files!")
        else:
            print("⚠️  PARTIAL: Review checks above")
        print("="*80)
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_real_chat_request()

