"""
OpenAI ↔ RKLLM Format Converter

Handles conversion between OpenAI API message format and RKLLM prompt format.

Prompt Format:
    RKLLM uses ChatML format with special tokens for conversation history:
    - <|im_start|>system\\n...content...<|im_end|>
    - <|im_start|>user\\n...content...<|im_end|>
    - <|im_start|>assistant\\n...content...<|im_end|>
    - Final <|im_start|>assistant\\n triggers generation

This format is compatible with Qwen3 and similar instruction-tuned models.

Functions:
    - extract_text_content: Extract plain text from string or structured content parts
    - openai_to_rkllm_prompt: Convert OpenAI messages to RKLLM ChatML prompt
    - rkllm_to_openai_response: Convert RKLLM output to OpenAI response format

Token Estimation:
    Uses rough heuristic (4 chars/token) since RKLLM doesn't provide
    token counts for prompts. This is approximate and may vary by content.
"""

from typing import List, Dict, Any, Union
from src.models.chat import ChatCompletionRequest


def extract_text_content(content: Union[str, List[Dict[str, Any]], None]) -> str:
    """
    Extract text from content (string or list of content parts).
    
    Args:
        content: String or list of content parts
    
    Returns:
        Extracted text string
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return "".join(text_parts)
    else:
        return str(content)


def openai_to_rkllm_prompt(messages: List[Any]) -> str:
    """
    Convert OpenAI messages to RKLLM prompt string.
    
    Args:
        messages: List of OpenAI message objects or dicts
    
    Returns:
        Formatted RKLLM prompt string
    """
    prompt_parts = []

    for msg in messages:
        role = msg.get("role") if isinstance(msg, dict) else msg.role
        content = msg.get("content") if isinstance(msg, dict) else msg.content
        
        if content is None:
            text_content = ""
        else:
            text_content = extract_text_content(content)

        if role == "system":
            prompt_parts.append(f"<|im_start|>system\n{text_content}<|im_end|>")
        elif role == "user":
            prompt_parts.append(f"<|im_start|>user\n{text_content}<|im_end|>")
        elif role == "assistant":
            prompt_parts.append(f"<|im_start|>assistant\n{text_content}<|im_end|>")

    prompt_parts.append("<|im_start|>assistant\n")
    return "".join(prompt_parts)


def rkllm_to_openai_response(
    rkllm_result: Dict[str, Any],
    request: ChatCompletionRequest,
    prompt_tokens: int
) -> Dict[str, Any]:
    """
    Convert RKLLM result to OpenAI response format.
    
    Args:
        rkllm_result: Result dictionary from RKLLM
        request: Original ChatCompletionRequest
        prompt_tokens: Estimated prompt tokens
    
    Returns:
        OpenAI-formatted response dictionary
    """
    import time
    
    completion_tokens = rkllm_result.get("tokens", 0)
    text = rkllm_result.get("text", "")
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": text,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
