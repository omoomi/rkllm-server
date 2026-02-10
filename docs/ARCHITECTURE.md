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
| **RKLLM Wrapper** | `rkllm_wrapper.py` | C library bindings, inference execution, model lifecycle |
| **Chat Models** | `models/chat.py` | Pydantic request/response models for OpenAI API |
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
5. Callback streams tokens to Python
6. Converter transforms RKLLM result → OpenAI response
7. Response sent (streaming or complete)

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
- **Synchronous Inference**: Blocks until complete (no request queuing)

## Known Limitations

1. **Single Model**: Server loads one model at startup (multi-model not supported)
2. **No Tokenization**: Relies on character-based token estimation
3. **Fixed Timeout**: 120 second inference timeout
4. **No Request Queue**: Requests processed synchronously
5. **Streaming**: Character-by-character streaming (not token-based)
