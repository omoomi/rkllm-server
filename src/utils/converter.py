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

from typing import List, Dict, Any, Union, Optional
from src.models.chat import ChatCompletionRequest
import json


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


def openai_to_rkllm_prompt(messages: List[Any], tools: Optional[List[Any]] = None, model_name: str = "Qwen3-0.6B-w8a8-ctx16384") -> str:
    """
    Convert OpenAI messages to RKLLM prompt string.
    
    Args:
        messages: List of OpenAI message objects or dicts
        tools: Optional list of tool definitions
        model_name: Name of the model being used
    
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
            system_msg = text_content
            if tools:
                tools_schema = []
                for i, tool in enumerate(tools):
                    if isinstance(tool, dict):
                        func = tool.get("function", {})
                    else:
                        func = tool.function
                    tools_schema.append({
                        "name": func.get('name', ''),
                        "description": func.get('description', ''),
                        "parameters": func.get('parameters', {})
                    })
                
                tools_prompt = "\n\n"
                tools_prompt += "You are an assistant with access to the following tools:\n\n"
                for tool in tools_schema:
                    tools_prompt += f"- {tool['name']}: {tool['description']}\n"
                
                tools_prompt += "\n"
                tools_prompt += "IMPORTANT INSTRUCTIONS:\n"
                tools_prompt += "1. When you need to use a tool, you MUST respond with ONLY valid JSON in the following format:\n\n"
                tools_prompt += '```json\n{"tool_calls": [{"name": "TOOL_NAME", "arguments": {"PARAM": "VALUE"}}]}\n```\n\n'
                tools_prompt += "2. Do NOT include any explanation or additional text when using a tool.\n"
                tools_prompt += "3. When no tool is needed, respond normally with text.\n\n"
                tools_prompt += "Example: To read a file, respond with:\n"
                tools_prompt += '```json\n{"tool_calls": [{"name": "read_file", "arguments": {"filePath": "/home/user/file.txt"}}]}\n```\n\n'
                
                system_msg = text_content + tools_prompt
            prompt_parts.append(f"<|im_start|>system\n{system_msg}<|im_end|>")
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
    import json
    import re
    
    completion_tokens = rkllm_result.get("tokens", 0)
    text = rkllm_result.get("text", "")
    
    tool_calls = None
    content = text
    
    if request.tools:
        tool_calls = parse_tool_calls(text)
        if tool_calls:
            content = None
    
    message_obj = {"role": "assistant"}
    if content is not None:
        message_obj["content"] = content
    if tool_calls is not None:
        message_obj["tool_calls"] = tool_calls
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": message_obj,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def parse_tool_calls(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse tool calls from model output.
    
    Looks for JSON blocks containing tool_calls in various formats:
    - ```json {...} ```
    - {"tool_calls": [...]}
    - Just {...} when in tool context
    
    Args:
        text: Model output text
    
    Returns:
        List of tool calls in OpenAI format, or None if no calls found
    """
    import json
    import re
    
    patterns = [
        r'```json\s*(\{.*?\})\s*```',
        r'\{\s*"tool_calls"\s*:\s*(\[.*?\])\s*\}',
        r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            try:
                if pattern == patterns[0]:
                    data = json.loads(matches[0])
                    if "tool_calls" in data:
                        return format_tool_calls(data["tool_calls"])
                    elif "name" in data and "arguments" in data:
                        return format_tool_calls([data])
                elif pattern == patterns[1]:
                    tool_calls = json.loads(matches[0])
                    return format_tool_calls(tool_calls)
                elif pattern == patterns[2]:
                    tool_call = {
                        "name": matches[0],
                        "arguments": json.loads(matches[1])
                    }
                    return format_tool_calls([tool_call])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    
    return None


def format_tool_calls(tool_calls_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tool calls to OpenAI API format.
    
    Args:
        tool_calls_data: Raw tool calls from model
    
    Returns:
        Tool calls in OpenAI format
    """
    import time
    import json
    
    formatted = []
    for i, tc in enumerate(tool_calls_data):
        call_id = f"call_{int(time.time())}_{i}"
        name = tc.get("name", "")
        arguments = tc.get("arguments", {})
        
        if isinstance(arguments, str):
            arguments_str = arguments
        else:
            arguments_str = json.dumps(arguments)
        
        formatted.append({
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": arguments_str
            }
        })
    
    return formatted
