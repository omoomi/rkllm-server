import requests

url = "http://localhost:11434/v1/chat/completions"

response = requests.post(url, json={
    "model": "Qwen3-0.6B-w8a8-ctx16384",
    "messages": [
        {"role": "user", "content": "Tell me a short joke."},
    ],
    "stream": True,
})

if response.status_code == 200:
    print("Assistant: ", end="", flush=True)
    for line in response.iter_lines():
        if line:
            line_text = line.decode('utf-8')
            if line_text.startswith("data: ") and not line_text.startswith("data: [DONE]"):
                import json
                try:
                    data = json.loads(line_text[6:])
                    if data["choices"][0]["delta"].get("content"):
                        print(data["choices"][0]["delta"]["content"], end="", flush=True)
                except:
                    pass
    print("\n")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
