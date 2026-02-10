"""
Pydantic Models for OpenAI-Compatible API

Data models for request/response validation using Pydantic v2.
Supports OpenAI's chat.completions API format including:
- Multi-modal content (text + image_url)
- Streaming and non-streaming responses
- Tool calling parameters (validation only)
- Various generation parameters (temperature, top_p, etc.)

Models:
    - ContentPart: Structured content for multi-modal messages
    - ChatMessage: Single message with role and content
    - ChatCompletionRequest: Request to chat completions endpoint
    - ChatCompletionResponse: Response from chat completions endpoint
    - Model, ModelsResponse: Model listing responses
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any

class ContentPart(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[Dict[str, Any]] = None

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[ContentPart], None] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class Tool(BaseModel):
    type: str = "function"
    function: Dict[str, Any]

class ChatCompletionRequest(BaseModel):
    model: str = Field(default="Qwen3-0.6B-w8a8-ctx16384")
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    # Additional OpenAI-compatible parameters (ignored by RKLLM)
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    n: Optional[int] = None
    top_k: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    logprobs: Optional[bool] = None
    echo: Optional[bool] = None

class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage

class Model(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "RKLLM"

class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Model]
