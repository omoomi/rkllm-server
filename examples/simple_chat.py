import requests

url = "http://localhost:8080/v1/chat/completions"

def main():
    print("RKLLM Chat - Interactive Mode")
    print("Type your message and press Enter. Type 'quit' or 'exit' to stop.\n")
    
    # Initialize conversation with system message
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]
    
    while True:
        # Get user input
        user_input = input("You: ").strip()
        
        # Check for exit commands
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Skip empty input
        if not user_input:
            continue
        
        # Add user message to conversation
        messages.append({"role": "user", "content": user_input})
        
        # Send request to server
        try:
            response = requests.post(url, json={
                "model": "Qwen3-0.6B-w8a8-ctx16384",
                "messages": messages,
                "temperature": 0.7,
            }, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result["choices"][0]["message"]["content"]
                
                # Display assistant's response
                print(f"Assistant: {assistant_message}")
                print(f"[Tokens: {result['usage']['total_tokens']}]\n")
                
                # Add assistant message to conversation history
                messages.append({"role": "assistant", "content": assistant_message})
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                break
        except requests.exceptions.Timeout:
            print("Error: Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    main()
