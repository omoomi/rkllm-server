from openai import OpenAI

# Initialize client (points to local RKLLM server)
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"
)

# Make a chat completion request
completion = client.chat.completions.create(
    model="Qwen3-0.6B-w8a8-ctx16384",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing in simple terms."}
    ],
    max_tokens=200,
    temperature=0.7,
)

# Print the response
print(f"Assistant: {completion.choices[0].message.content}")
if completion.usage:
    print(f"\nTokens used: {completion.usage.total_tokens}")
