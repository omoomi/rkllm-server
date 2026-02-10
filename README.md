# RKLLM OpenAI-Compatible Server

Single LLM server for Orange Pi 5 Max (RK3588) with full OpenAI API compatibility.

**Status**: ✅ Production Ready (Limited) | **Last Updated**: February 9, 2026

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Verify models (optional)
bash scripts/verify_models.sh

# 3. Download required files
# - RKLLM Runtime: https://console.zbox.filez.com/l/RJJDmB (code: rkllm)
# - Model: https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B

# 4. Configure server (optional)
cp .env.example .env
# Edit .env to customize model, port, and settings

# 5. Start server
./run_server.sh

# 6. Test the server
curl http://localhost:11434/health
```

## Features

- Multiple model support (0.6B, 4B, large context variants)
- OpenAI-compatible `/v1/chat/completions` endpoint with **tool calling support**
- Streaming and non-streaming responses
- NPU acceleration (~11-12 tokens/s)
- Model selection via `.env` configuration
- **Function/Tool calling**: Parse tool definitions and return structured tool calls from model output

## Models

Select model in `.env`:

**Important Note on Tool Calling:**
- **Qwen3-0.6B-w8a8**: Basic tool calling support, but may be inconsistent
- **Qwen3-1.7B**: Better tool calling with larger model, more consistent
- **For production tool calling**: Consider using models specifically trained for function calling:
  - Llama 3.2-3B-Instruct (excellent tool calling)
  - Qwen3-Coder-1.7B-Instruct (optimized for tools)
  - Qwen3-Coder-1.5B-Instruct (smaller, faster)

**Model comparison for tool calling:**

 | Model | Size | Context | Speed | Tool Calling | Description |
 |--------|------|---------|--------|-------------|-------------|
 | `Qwen3-4B-1.2.0` | 4B | 4096 | ~3-4 t/s | Good | Larger, more capable |
 | `Qwen3-1.7B` | 1.7B | 16384 | ~6-8 t/s | Good | Balanced size and performance |
 | `Qwen3-0.6B-w8a8-ctx16384` | 0.6B | 16384 | ~11-12 t/s | Basic | Default, 16K context |

**Recommended models for tool calling:**
- **Llama 3.2-3B-Instruct**: Excellent tool calling, but needs RKNN conversion
- **Qwen3-Coder-1.7B**: Good tool calling, optimized for code
- Consider using vLLM/llama.cpp for better function call support

**Switch models**:
```bash
# Edit .env
MODEL_NAME=Qwen3-4B-1.2.0

# Restart server
./run_server.sh
```

## Configuration

Edit `.env` to customize:

```bash
# Server
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=info

# Model selection
MODEL_NAME=Qwen3-0.6B-w8a8-ctx16384

# Model settings (optional - overrides model defaults)
MAX_CONTEXT_LEN=4096
MAX_NEW_TOKENS=2048
TEMPERATURE=0.8
TOP_P=0.9
TOP_K=1
REPEAT_PENALTY=1.1

# Performance
CPU_CORES=AUTO                # AUTO, range (4-7), or list (4,5,6,7)
ENABLE_EMBED_FLASH=1
```

## Testing

```bash
# Test health
curl http://localhost:11434/health

# List models
curl http://localhost:11434/v1/models

# Run tests
source venv/bin/activate
pytest tests/
```

## Usage Examples

### cURL - Basic Chat

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-0.6B-w8a8-ctx16384",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### cURL - Tool Calling

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-1.7B",
    "messages": [
      {"role": "user", "content": "Read the README.md file"}
    ],
    "tools": [{
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read file contents from the filesystem",
        "parameters": {
          "type": "object",
          "properties": {
            "filePath": {
              "type": "string",
              "description": "Path to the file to read"
            }
          },
          "required": ["filePath"]
        }
      }
    }],
    "tool_choice": "auto",
    "temperature": 0.3
  }'
```

**Tool Calling Response Format:**
When the model uses a tool, the response will include a `tool_calls` field:

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "choices": [{
    "message": {
      "role": "assistant",
      "tool_calls": [{
        "id": "call_1234567890_0",
        "type": "function",
        "function": {
          "name": "read_file",
          "arguments": "{\"filePath\": \"/home/user/README.md\"}"
        }
      }],
      "finish_reason": "tool_calls"
    }
  }]
}
```

### OpenAI Python Client - Basic Chat

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-needed"
)

completion = client.chat.completions.create(
    model="Qwen3-0.6B-w8a8-ctx16384",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(completion.choices[0].message.content)
```

### OpenAI Python Client - Tool Calling

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="Qwen3-1.7B",
    messages=[{"role": "user", "content": "Read the README.md file"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents from the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["filePath"]
            }
        }
    }],
    tool_choice="auto"
)

if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = tool_call.function.arguments
        print(f"Tool called: {tool_name} with args: {tool_args}")
else:
    print(response.choices[0].message.content)
```

## API Endpoints

### POST `/v1/chat/completions`

Chat completion endpoint (OpenAI-compatible with tool calling support).

**Parameters:**
- `model` (required): Model ID
- `messages` (required): Message array with `role` and `content`
- `temperature` (optional): 0.0-2.0, default 0.8
- `max_tokens` (optional): Max tokens to generate
- `stream` (optional): Enable streaming
- `tools` (optional): Array of tool definitions for function calling
- `tool_choice` (optional): Tool selection strategy ("auto", "none", or specific function)

### GET `/v1/models`

List available models.

### GET `/health`

Health check endpoint.

## Project Structure

```
rkllm-server/
├── venv/                    # Python virtual environment
├── lib/                     # RKLLM runtime library
├── models/                   # Model files
├── src/                      # Source code
│   ├── server.py             # FastAPI server
│   ├── rkllm_wrapper.py     # RKLLM bindings
│   ├── models/               # Pydantic models
│   └── utils/               # Utilities
├── examples/                 # Usage examples
├── scripts/                  # Helper scripts
├── tests/                   # Tests
├── .env                     # Configuration
└── run_server.sh           # Startup script
```

## Prerequisites

- Orange Pi 5 Max (RK3588) with NPU driver
- Python 3.12+ with python3.12-venv
- ~5GB free disk space for all models
- ~1GB RAM available

## Troubleshooting

**Model not found**
```
Error: Model file not found
```
Solution: Download model from Hugging Face to `models/` directory.

**Library not found**
```
Error: librkllmrt.so: cannot open shared object file
```
Solution: Copy `librkllmrt.so` from RKLLM SDK to `lib/` directory.

**NPU errors**
```
Error: RKLLM init failed with code -1
```

**Tool calling not working**
```
Issue: Model responds with text instead of tool_calls
```

**Possible causes:**
1. **Model not function-call capable**: Some quantized models (especially W8A8) may not be fine-tuned for function calling
   - **Solution**: Try models with better instruction following (Qwen3-1.7B, Llama 3.2)
   - Or use function-call specific models (Qwen3-Coder, Llama 3.2 tool-graded)

2. **Temperature too high**: High temperature can cause the model to ignore tool instructions
   - **Solution**: Lower temperature to 0.2-0.4 for more deterministic tool calling

3. **Insufficient context**: Tool definitions may exceed model context window
   - **Solution**: Reduce number of tools or use smaller tool definitions

4. **Model requires fine-tuning**: Not all models are trained for structured JSON output
   - **Solution**: Use models specifically trained for function calling
   - Recommended: Llama 3.2-3B-Instruct, Qwen3-Coder-1.7B-Instruct
Error: Model file not found
```
Solution: Download model from Hugging Face to `models/` directory.

**Library not found**
```
Error: librkllmrt.so: cannot open shared object file
```
Solution: Copy `librkllmrt.so` from RKLLM SDK to `lib/` directory.

**NPU errors**
```
Error: RKLLM init failed with code -1

## Links

- [Architecture Documentation](docs/ARCHITECTURE.md) - System design and data flow
- [RKLLM Framework](https://github.com/airockchip/rknn-llm) - Official RKLLM runtime
- [Model Repository](https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B) - Model files and documentation
- [Detailed Setup Guide](SETUP.md)
- [Implementation Status](STATUS.md)
- [RKLLM Framework](https://github.com/airockchip/rknn-llm)
- [Model Repository](https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B)
