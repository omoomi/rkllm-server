#!/bin/bash

# RKLLM Server Startup Script

echo "Activating virtual environment..."
source venv/bin/activate

echo "Loading environment variables..."
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "Environment loaded from .env"
else
    echo "Warning: .env file not found, using defaults"
fi

echo "Starting RKLLM server on ${HOST}:${PORT}..."
python3 -m uvicorn src.server:app \
    --host ${HOST} \
    --port ${PORT} \
    --log-level ${LOG_LEVEL}
