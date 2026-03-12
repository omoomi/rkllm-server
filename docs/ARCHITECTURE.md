# RKNN-LLM Architecture

## Overview

The RKNN-LLM server is a layered FastAPI application that provides OpenAI-compatible endpoints for RKLLM inference on RK3588 NPU hardware.

## Architecture

```
┌─────────────────────────────────────────┐
│         FastAPI Layer                 │  (server.py)
│  - OpenAI API endpoints (/v1/*)        │
│  - Request validation (Pydantic)        │
│  - Error handling middleware           │
│  - Response streaming                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        Business Logic Layer             │  (converter.py)
│  - OpenAI ↔ RKLLM format conversion    │
│  - Token estimation (4 chars/token)      │
│  - ChatML prompt formatting             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        Model Abstraction Layer          │  (rkllm_wrapper.py)
│  - RKLLM C library bindings (ctypes)   │
│  - Model lifecycle (init/run/destroy)    │
│  - Parameter validation                  │
│  - Thread-safe callback streaming        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        Configuration Layer              │  (common.py + config.json)
│  - Settings management (Pydantic)      │
│  - Model registry                       │
│  - Environment variable loading          │
└─────────────────────────────────────────┘
```

## Module Responsibilities

| Module | File | Responsibilities |
|--------|------|-------------------|
| **Server** | `server.py` | FastAPI app, routing, request handling, lifecycle management |
| **RKLLM Wrapper** | `rkllm_wrapper.py` | C library bindings, inference execution, model lifecycle, stream handoff |
| **Chat Models** | `models/chat.py` | Pydantic request/response models for OpenAI API, including streaming chunks |
| **Settings** | `models/common.py` | Configuration loading, environment variable management, model registry |
| **Converter** | `utils/converter.py` | OpenAI ↔ RKLLM format conversion, token estimation |
| **Logging** | `utils/logging.py` | Centralized logging configuration |

## ChatML Prompt Format

RKLLM uses ChatML format for conversation history:

```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
Hello, how are you?<|im_end|>
<|im_start|>assistant
I'm doing well, thank you!<|im_end|>
<|im_start|>user
What's 2+2?<|im_end|>
<|im_start|>assistant
2+2 equals 4.<|im_end|>
<|im_start|>assistant
```

Special Tokens:
- `<|im_start|>` - Message start delimiter
- `<|im_end|>` - Message end delimiter
- Must be newline-separated from content

## API Endpoints

| Endpoint | Method | Purpose | Response Format |
|----------|--------|---------|----------------|
| `/health` | GET | Health check | JSON with status and model_loaded |
| `/v1/models` | GET | List available models | OpenAI format model list |
| `/v1/chat/completions` | POST | Chat completion | OpenAI format (supports SSE streaming) |
| `/api/tags` | GET | Model discovery | Ollama format |

## Configuration Flow

1. **config.json** - Model registry with default parameters
2. **.env file** - Environment variable overrides (highest priority)
3. **Settings class** - Loads and merges 1 + 2
4. **RKLLM wrapper** - Initializes model with resolved config

## Request Lifecycle

1. FastAPI receives HTTP request
2. Pydantic validates request structure
3. Converter transforms OpenAI format → RKLLM ChatML format
4. RKLLM wrapper executes inference via C library
5. Callback publishes text fragments into a thread-safe queue
6. Server converts callback fragments into OpenAI-compatible SSE chunks, or converts the final text into a non-streaming response
7. Response sent to client

## Error Handling

| Error Type | HTTP Status | Example |
|------------|--------------|---------|
| Validation Error | 422 | Invalid request structure |
| Model Not Loaded | 503 | Model initialization failed |
| Inference Error | 500 | RKLLM runtime error |
| Configuration Error | 500 | Invalid .env or config.json |

## Performance Optimizations

- **CPU Core Affinity**: Uses performance cores (4-7) for inference
- **Flash Attention**: Enabled via `embed_flash` parameter
- **Token Estimation**: Rough heuristic (4 chars/token) for usage tracking
- **Single Active Inference**: Wrapper serializes runs with a lock because RKLLM callback state is shared per model instance

## Known Limitations

1. **Single Model**: Server loads one model at startup (multi-model not supported)
2. **No Tokenization**: Relies on character-based token estimation
3. **Fixed Timeout**: 120 second inference timeout
4. **No Request Queue**: Requests are serialized per loaded model instance
5. **Streaming**: Emits callback fragments, which may not align to tokenizer token boundaries
