import requests
import json
import sys
import uuid

def test_stream():
    url = "http://localhost:8000/api/chat/stream"
    conversation_id = f"test_{uuid.uuid4().hex[:8]}"
    
    print(f"--- Starting Chat Stream Test (ID: {conversation_id}) ---")
    
    # 1. First Turn: User asks for products
    payload = {
        "messages": [
            {"role": "user", "text": "I am looking for a red backpack for school."}
        ],
        "locale": "en",
        "allow_actions": True,
        "conversation_id": conversation_id
    }
    
    print(f"\n[User]: {payload['messages'][-1]['text']}")
    _run_stream(url, payload)

    # 2. Second Turn: User confirms inquiry (simulated)
    # Ideally, we would append to history, but for this simple test we just send a new message
    # The backend maintains state via conversation_id
    payload["messages"] = [
        {"role": "user", "text": "My email is tester@example.com and name is QA Bot. Please send me an inquiry for the red one."}
    ]
    
    print(f"\n[User]: {payload['messages'][-1]['text']}")
    _run_stream(url, payload)

def _run_stream(url, payload):
    try:
        with requests.post(url, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"Error: {r.status_code} {r.text}")
                return

            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        try:
                            data = json.loads(data_str)
                            event_type = data.get('type')
                            
                            if event_type == 'delta':
                                print(data.get('text', ''), end='', flush=True)
                            elif event_type == 'tool_call':
                                print(f"\n[Tool Call]: {data.get('name')} {data.get('arguments')}")
                            elif event_type == 'action_event':
                                print(f"\n[UI Action]: {data.get('action')} {data.get('action_data')}")
                            elif event_type == 'final':
                                if data.get('text'):
                                    print(f"\n[Final]: {data.get('text')}")
                            elif event_type == 'error':
                                print(f"\n[Error]: {data.get('message')}")
                                
                        except Exception as e:
                            print(f"\n[Parse Error]: {e}")
            print("\n")
    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    test_stream()
