# RKLLM OpenAI-Compatible Server

Single LLM server for Orange Pi 5 Max (RK3588) with full OpenAI API compatibility.

**Status**: ✅ Production Ready (Single-turn) | **Last Updated**: March 12, 2026

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Verify models (optional)
bash scripts/verify_models.sh

# 3. Configure server (optional)
cp .env.example .env
# Edit .env to select model and configure settings

# 4. Start server
./run_server.sh

# 5. Test server
curl http://localhost:11434/health
```

## Features

- **Multiple model support**: Qwen3-4B, 3.2B, 1.7B, 0.6B, distilled SHELLper variants, and Llama 3.2B/1B with 16K context
- OpenAI-compatible `/v1/chat/completions` endpoint with **tool calling support**
- Streaming and non-streaming responses
- NPU acceleration (3-4 tokens/sec depending on model)
- Model selection via `.env` configuration
- **Function/Tool calling**: Parse tool definitions and return structured tool calls from model output
- Markdown code block parsing for tool calls (```json format)
- **Native callback streaming**: SSE output now forwards RKLLM callback fragments instead of re-chunking the final response in Python

## Available Models

Select model in `.env`:

| Model Name | Size | Context | Speed | Tool Calling | Recommended Use |
|-----------|------|---------|--------|-------------|-----------------|
| `Qwen3-4B-Instruct-2507_w8a8_ctx16384_RK3588` | 4.6GB | 16384 | ~3-4 t/s | Good | Complex reasoning |
| `Qwen3-1.7B` | 2.2GB | 16384 | ~6-8 t/s | Good | Balanced |
| `Qwen3-1.7B-FC_w8a8_ctx16384_RK3588` | 2.3GB | 16384 | ~6-8 t/s | Good | Better long-context reasoning |
| `Qwen3-0.6B-w8a8-ctx16384` | 0.9GB | 16384 | ~11-12 t/s | Basic | Fast chat |
| `distil-qwen3-0.6b-SHELLper_w8a8_ctx16384_RK3588` | 0.9GB | 16384 | ~11-12 t/s | Better | Fast shell/tool tasks |
| `distil-qwen3-0.6b-SHELLper_noquant_ctx16384_RK3588` | 1.5GB | 16384 | ~8-10 t/s | Better | Higher-quality shell/tool tasks |
| `Llama-3.2-3B-Instruct_w8a8_ctx16384_RK3588` | 4.0GB | 16384 | ~4-6 t/s | Excellent | Best tool calling |
| `Llama-3.2-1B-Instruct_w8a8_ctx16384_RK3588` | 1.8GB | 16384 | ~8-10 t/s | Excellent | Fast chat |

### Model Recommendations

**For Tool Calling with Direct API (single request):**
- **Qwen3-1.7B**: Best balance of speed and capability (75% success with clean prompts)
- **Qwen3-4B**: Best reasoning, but slower (3-4 t/s)
- **Llama-3.2-3B**: Best tool calling performance (75% success)

**⚠️ CRITICAL - Picoclaw Integration:**
- **NO local quantized models (W8A8) work reliably with Picoclaw's multi-turn tool loop**
- All tested models (0.6B, 1.7B, 4B) exhibit the same failure:
  - Generate correct tool calls initially
  - Fail to understand that tool result = task completion
  - Continue calling tools indefinitely until max_tool_iterations
- **For Picoclaw tool-calling workflows, use cloud models** (GPT-4, Claude, etc.)

**For General Chat:**
- **Llama-3.2-1B**: Fastest model (8-10 t/s), good for simple Q&A
- **Qwen3-0.6B-w8a8-ctx16384**: Default model, 16K context, lowest latency startup

**For Shell / Tool Experiments:**
- **distil-qwen3-0.6b-SHELLper_w8a8_ctx16384_RK3588**: Best low-latency option for shell-oriented prompts
- **distil-qwen3-0.6b-SHELLper_noquant_ctx16384_RK3588**: Higher-quality variant when you can afford the larger model

## Configuration

Edit `.env` to customize:

```bash
# Server
HOST=0.0.0.0
PORT=11434
LOG_LEVEL=info

# Model selection
# Default: Qwen3-0.6B-w8a8-ctx16384 for fastest responses
MODEL_NAME=Qwen3-0.6B-w8a8-ctx16384

# Model settings (optional - overrides model defaults)
MAX_CONTEXT_LEN=16384       # Maximum context window in tokens (1-16384)
MAX_NEW_TOKENS=2048         # Maximum tokens to generate (1-2048)
TEMPERATURE=0.8               # Sampling temperature (0.0-2.0, higher = more random)
TOP_P=0.9                    # Nucleus sampling parameter (0.0-1.0, controls diversity)
TOP_K=1                        # Top-K sampling (>= 1, higher = less diverse)
REPEAT_PENALTY=1.1          # Penalize repetition (>= 1.0, higher = less repetition)

# Performance (balanced)
CPU_CORES=AUTO                # AUTO, range (4-7), or list (4,5,6,7)
ENABLE_EMBED_FLASH=1          # Enable flash attention (0/1, improves performance)
```

### Temperature Guidelines

| Use Case | Recommended Temperature |
|-----------|----------------------|
| **Tool calling** | 0.2-0.4 (Low temperature = more deterministic) |
| **Creative writing** | 0.7-1.0 (Higher temperature = more creative) |
| **Code generation** | 0.3-0.5 (Balanced) |
| **General chat** | 0.6-0.8 (Default) |

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

### cURL - Tool Calling (Direct API - WORKING)

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-0.6B-w8a8-ctx16384",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant with access to tools. When a user asks you to perform an action that requires a tool, use the appropriate tool."
      },
      {
        "role": "user",
        "content": "List files in /home/elsa/repos/rkllm-server/src"
      }
    ],
    "tools": [{
      "type": "function",
      "function": {
        "name": "list_dir",
        "description": "List files and directories in a path",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {
              "type": "string",
              "description": "Path to list"
            }
          },
          "required": ["path"]
        }
      }
    }],
    "temperature": 0.3
  }'
```

**Response Format:**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "tool_calls": [{
        "id": "call_1234567890_0",
        "type": "function",
        "function": {
          "name": "list_dir",
          "arguments": "{\"path\": \"/home/elsa/repos/rkllm-server/src\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

### OpenAI Python Client

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

## API Endpoints

### POST `/v1/chat/completions`

Chat completion endpoint (OpenAI-compatible with tool calling support).

**Parameters:**
- `model` (required): Model ID
- `messages` (required): Message array with `role` and `content`
- `temperature` (optional): 0.0-2.0, default from model config
- `max_tokens` (optional): Max tokens to generate
- `stream` (optional): Enable SSE streaming from native RKLLM callback fragments
- `tools` (optional): Array of tool definitions for function calling

**Response Format:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Text response OR null if tool_calls",
      "tool_calls": [
        {
          "id": "call_1234567890_0",
          "type": "function",
          "function": {
            "name": "tool_name",
            "arguments": "{\"param\": \"value\"}"
          }
        }
      ]
    },
    "finish_reason": "stop" | "tool_calls"
  }],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 27,
    "total_tokens": 77
  }
}
```

### GET `/v1/models`

List available models.

### Streaming Response Notes

When `stream=true`, the server returns `text/event-stream` and emits OpenAI-style `chat.completion.chunk` events as RKLLM callback fragments arrive. The stream ends with a final chunk carrying `"finish_reason": "stop"` followed by `data: [DONE]`.

### GET `/health`

Health check endpoint.
```json
{
  "status": "healthy" | "unhealthy",
  "model": "Qwen3-0.6B-w8a8-ctx16384",
  "model_loaded": true
}
```

## Project Structure

```
rkllm-server/
├── venv/                    # Python virtual environment
├── lib/                      # RKLLM runtime library
├── models/                   # Model files
├── src/                      # Source code
│   ├── server.py            # FastAPI server
│   ├── rkllm_wrapper.py     # RKLLM bindings
│   ├── models/              # Pydantic models
│   └── utils/               # Utilities (converter, logging)
├── examples/                 # Usage examples
├── tests/                   # Tests
├── .env                     # Configuration
├── run_server.sh           # Startup script
└── docs/                    # Documentation
    ├── ARCHITECTURE.md          # System design
    ├── TOOL_CALLING_TEST_RESULTS.md   # Tool calling model comparison
    ├── PICOCLAW_INTEGRATION_TEST_RESULTS.md   # Picoclaw integration results
    └── QWEN4B_TEST_RESULTS.md   # Qwen3-4B test results
```

## Prerequisites

- Orange Pi 5 Max (RK3588) with NPU driver
- Python 3.12+ with python3.12-venv
- ~5GB free disk space for all models
- ~1GB RAM available

## Troubleshooting

### Model not found

**Error:**
```
Error: Model file not found
```

**Solution:** Download model to `models/` directory. See `src/models/config.json` for available models.

### Library not found

**Error:**
```
Error: librkllmrt.so: cannot open shared object file
```

**Solution:** Copy `librkllmrt.so` from RKLLM SDK to `lib/` directory.

### Tool calling not working

**Issue:** Model responds with text instead of tool_calls

**Possible causes:**

1. **Model not function-call capable**
   - **Solution:** Use models with better instruction following (Qwen3-1.7B, Llama-3.2-3B)

2. **Temperature too high**
   - **Solution:** Lower temperature to 0.2-0.4 for more deterministic output

3. **Complex system prompt**
   - **Solution:** Simplify system prompt, reduce bootstrap files
   - Picoclaw: Set `lean_mode: true` in config

4. **Multi-turn tool conversation failure**
   - **Problem:** Model calls tool correctly but doesn't understand tool result = answer
   - **Root cause:** Quantized W8A8 models lack reasoning for multi-turn patterns
   - **Workaround:** Use cloud models (GPT-4, Claude) for Picoclaw
   - **Long-term solution:** Fine-tune model for specific conversation pattern

5. **Picoclaw integration specific issue**
   - **All local models tested (0.6B, 1.7B, 4B) fail with Picoclaw's agent loop**
   - Model generates tool calls correctly on direct API
   - But cannot complete multi-turn tool conversations in Picoclaw
   - **Recommendation:** Use cloud models for Picoclaw workflows

### Tool calling best practices

- **Temperature:** Use 0.2-0.4 for tool requests (more deterministic)
- **System prompt:** Keep it simple, focused on tool instructions
- **Tool count:** Limit to 4-6 essential tools for small models
- **Examples:** Include 2-3 concrete examples in system prompt

## Documentation

- [Architecture Documentation](docs/ARCHITECTURE.md) - System design and data flow
- [Tool Calling Test Results](docs/TOOL_CALLING_TEST_RESULTS.md) - Comprehensive model comparison
- [Picoclaw Integration](docs/PICOCLAW_INTEGRATION_TEST_RESULTS.md) - Integration test results
- [Qwen3-4B Test Results](docs/QWEN4B_TEST_RESULTS.md) - Qwen3-4B testing details
- [RKLLM Framework](https://github.com/airockchip/rknn-llm) - Official RKLLM runtime

## Known Limitations

### Tool Calling

**Single-turn tool calling:** ✅ WORKING with direct API
- Models generate correct tool calls when given proper prompts
- Success rate: ~75% with Qwen3-1.7B and Llama-3.2-3B
- Success rate: ~75% with Qwen3-4B

**Multi-turn tool conversations:** ❌ NOT WORKING with Picoclaw
- All quantized W8A8 models (0.6B, 1.7B, 4B) fail
- Model cannot understand that tool result = task completion
- Continues calling tools indefinitely until max_tool_iterations
- This is a training pattern mismatch, not a capacity issue

**Recommendation:** For tool-calling workflows like Picoclaw, use cloud models or fine-tune local models specifically for multi-turn patterns.

## Performance Metrics

| Model | Size | Speed | Memory | NPU Usage |
|--------|------|-------|--------|-----------|
| Qwen3-0.6B | 0.9GB | 11-12 t/s | ~900MB | Low (3 cores) |
| Qwen3-1.7B | 2.2GB | 6-8 t/s | ~2GB | Medium (3 cores) |
| Qwen3-4B | 4.6GB | 3-4 t/s | ~4GB | High (3 cores) |
| Llama-3.2-1B | 1.8GB | 8-10 t/s | ~1.5GB | Low (3 cores) |
| Llama-3.2-3B | 4.0GB | 4-6 t/s | ~3GB | High (3 cores) |

## Links

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [RKLLM Framework](https://github.com/airockchip/rknn-llm)
- [Model Repository](https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B)

## License

Based on RKLLM and model licenses. See individual component licenses for details.
