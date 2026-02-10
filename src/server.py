"""
RKLLM OpenAI-Compatible API Server

FastAPI server providing OpenAI-compatible endpoints for RKLLM inference.
Supports chat completions, model listing, health checks, and streaming responses.

Endpoints:
    - GET  /health: Health check
    - GET  /v1/models: List available models (OpenAI format)
    - POST /v1/chat/completions: Chat completion (OpenAI format, supports streaming)
    - GET  /api/tags: Model list (Ollama format)
"""

import time
import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from src.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelsResponse,
)
from src.models.common import Settings
from src.utils.converter import openai_to_rkllm_prompt, rkllm_to_openai_response
from src.utils.logging import setup_logging
from src.rkllm_wrapper import RKLLMModel

# Constants
TOKENS_PER_CHAR_ESTIMATE = 4

# Load settings
settings = Settings()

# Setup logging
logger = setup_logging(settings.log_level)

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Initialize FastAPI app
app = FastAPI(
    title="RKLLM OpenAI-Compatible Server",
    description="Single LLM server for RK3588 NPU",
    version="1.0.0"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed logging"""
    logger.error(f"Validation error on {request.url}: {exc.errors()}")
    logger.error(f"Request body: {exc.body}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body, "message": "Request validation failed"},
    )

# Global RKLLM model instance (singleton)
rkllm_model: Optional[RKLLMModel] = None


@app.on_event("startup")
async def startup_event():
    global rkllm_model
    
    # Get resolved model config
    try:
        model_config = settings.get_resolved_config()
        logger.info(f"Loading model: {settings.model_name}")
        logger.info(f"  Path: {model_config['model_path']}")
        logger.info(f"  ID: {model_config['model_id']}")
        logger.info(f"  Description: {model_config.get('description', 'N/A')}")
    except Exception as e:
        logger.error(f"Failed to load model configuration: {e}")
        return
    
    # Check if model file exists
    model_path = model_config['model_path']
    if not os.path.exists(model_path):
        logger.error(f"Model file not found: {model_path}")
        logger.error("Please download model first. See README.md for instructions.")
        return
    
    try:
        rkllm_model = RKLLMModel(
            model_path=model_path,
            max_context_len=model_config['max_context_len'],
            max_new_tokens=model_config['max_new_tokens'],
            temperature=model_config['temperature'],
            top_p=model_config['top_p'],
            top_k=model_config['top_k'],
            repeat_penalty=model_config['repeat_penalty'],
            cpu_cores=settings.cpu_cores,
            enable_embed_flash=settings.enable_embed_flash,
            library_path=getattr(settings, 'rkllm_library_path', 'lib/librkllmrt.so'),
        )

        # Log configuration
        config = rkllm_model.get_config()
        logger.info("RKLLM model loaded successfully")
        logger.info("Model configuration:")
        for key, value in config.items():
            logger.info(f"  - {key}: {value}")
    except Exception as e:
        logger.error(f"Failed to load RKLLM model: {e}")
        logger.error(f"Model path: {model_path}")
        logger.error("Check that the model file exists and RKLLM runtime is compatible.")


@app.on_event("shutdown")
async def shutdown_event():
    global rkllm_model
    if rkllm_model:
        rkllm_model.release()
        logger.info("RKLLM model destroyed")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    model_loaded = rkllm_model is not None
    model_id = None
    if model_loaded:
        try:
            model_config = settings.get_resolved_config()
            model_id = model_config['model_id']
        except Exception:
            model_id = settings.model_name
    return {
        "status": "healthy" if model_loaded else "unhealthy",
        "model": model_id,
        "model_loaded": model_loaded
    }


@app.get("/v1/models")
async def list_models():
    """List available models (always one)"""
    model_id = None
    try:
        model_config = settings.get_resolved_config()
        model_id = model_config['model_id']
    except Exception:
        model_id = settings.model_name
    return {
        "object": "list",
        "data": [{
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "RKLLM"
        }]
    }


# Setup logging
logger = setup_logging(settings.log_level)

# Add request logging for debugging
import logging as python_logging_module
request_logger = python_logging_module.getLogger(__name__)

@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """Create chat completion (supports both streaming and non-streaming)"""
    global rkllm_model
    
    # Log request for debugging
    request_logger.info(f"Received request: model={request.model}, messages={len(request.messages)}, max_tokens={request.max_tokens}, stream={request.stream}")
    
    if rkllm_model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Please check that the model file exists and try restarting the server."
        )
    
    # Convert messages to RKLLM prompt (including tools)
    rkllm_prompt = openai_to_rkllm_prompt(request.messages, request.tools, request.model)
    
    # Estimate prompt tokens (rough estimate: 4 chars per token)
    prompt_tokens = len(rkllm_prompt) // TOKENS_PER_CHAR_ESTIMATE
    
    logger.info(f"Processing request with {len(request.messages)} messages")
    
    # Run inference
    try:
        result_text = rkllm_model.run(None, False, rkllm_prompt)
        result = {"text": result_text}
    except Exception as e:
        logger.error(f"Inference error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Convert to OpenAI response
    response = rkllm_to_openai_response(result, request, prompt_tokens)
    
    # Estimate completion tokens (rough estimate: 4 chars per token)
    completion_tokens = len(result_text) // TOKENS_PER_CHAR_ESTIMATE
    response['usage']['completion_tokens'] = completion_tokens
    response['usage']['total_tokens'] = prompt_tokens + completion_tokens
    
    logger.info(f"Generated {completion_tokens} tokens")
    
    if request.stream:
        # Stream response in word-sized chunks for better performance
        async def generate():
            text = result.get("text", "")
            words = text.split()
            
            for i, word in enumerate(words):
                chunk = {
                    "id": response["id"],
                    "object": "chat.completion.chunk",
                    "created": response["created"],
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": word + " " if i < len(words) - 1 else word},
                        "finish_reason": None,
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Final chunk
            final_chunk = {
                "id": response["id"],
                "object": "chat.completion.chunk",
                "created": response["created"],
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        # Return non-streaming response
        return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level
    )


@app.get("/api/tags")
async def ollama_api_tags():
    """Ollama-compatible /api/tags endpoint for model discovery"""
    model_id = None
    try:
        model_config = settings.get_resolved_config()
        model_id = model_config['model_id']
    except Exception:
        model_id = settings.model_name
    
    return {
        "models": [
            {
                "name": model_id,
                "modified_at": time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "size": 0,
            }
        ]
    }
