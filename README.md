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

# 4. Start server
./run_server.sh
```

## Features

- Multiple model support (0.6B, 4B, large context variants)
- OpenAI-compatible `/v1/chat/completions` endpoint
- Streaming and non-streaming responses
- NPU acceleration (~11-12 tokens/s)
- Model selection via `.env` configuration

## Models

Select model in `.env`:

| Model | Size | Context | Speed | Description |
|--------|------|---------|--------|-------------|
| `Qwen3-4B-1.2.0` | 4B | 4096 | ~3-4 t/s | Larger, more capable |
| `Qwen3-0.6B-w8a8-ctx16384` | 0.6B | 16384 | ~11-12 t/s | Default, 16K context |

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
curl http://localhost:8080/health

# List models
curl http://localhost:8080/v1/models

# Run tests
source venv/bin/activate
pytest tests/
```

## Usage Examples

### cURL

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-0.6B-w8a8-ctx16384",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### OpenAI Python Client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
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

Chat completion endpoint (OpenAI-compatible).

**Parameters:**
- `model` (required): Model ID
- `messages` (required): Message array with `role` and `content`
- `temperature` (optional): 0.0-2.0, default 0.8
- `max_tokens` (optional): Max tokens to generate
- `stream` (optional): Enable streaming

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

## Links

- [Architecture Documentation](docs/ARCHITECTURE.md) - System design and data flow
- [RKLLM Framework](https://github.com/airockchip/rknn-llm) - Official RKLLM runtime
- [Model Repository](https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B) - Model files and documentation
- [Detailed Setup Guide](SETUP.md)
- [Implementation Status](STATUS.md)
- [RKLLM Framework](https://github.com/airockchip/rknn-llm)
- [Model Repository](https://huggingface.co/ThomasTheMaker/Qwen3-0.6B-RKLLM-1.2.1B)
