from src.utils.converter import openai_to_rkllm_prompt

def test_openai_to_rkllm_prompt():
    """Test OpenAI message to RKLLM prompt conversion"""
    
    # Test simple user message
    messages = [{"role": "user", "content": "Hello!"}]
    prompt = openai_to_rkllm_prompt(messages)
    assert "<|im_start|>user" in prompt
    assert "Hello!" in prompt
    assert "<|im_start|>assistant\n" in prompt
    
    # Test system message
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi!"}
    ]
    prompt = openai_to_rkllm_prompt(messages)
    assert "<|im_start|>system" in prompt
    assert "You are helpful." in prompt
    assert "<|im_start|>user" in prompt
    
    # Test assistant message
    messages = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "Thanks!"}
    ]
    prompt = openai_to_rkllm_prompt(messages)
    assert "What is 2+2?" in prompt
    assert "4" in prompt
    assert "Thanks!" in prompt
