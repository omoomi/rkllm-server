import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_health():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "model_loaded" in data

def test_list_models():
    """Test list models endpoint"""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "Qwen3-0.6B-w8a8-ctx16384"
    assert data["data"][0]["owned_by"] == "RKLLM"

def test_chat_completion_without_model():
    """Test chat completion without model loaded (should fail gracefully)"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen3-0.6B-w8a8-ctx16384",
            "messages": [{"role": "user", "content": "Hello!"}],
        }
    )
    # Should return 503 if model not loaded
    assert response.status_code in [200, 503]
    if response.status_code == 503:
        data = response.json()
        assert "detail" in data

def test_chat_completion_validation():
    """Test request validation"""
    # Missing messages field
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "Qwen3-0.6B-w8a8-ctx16384",
        }
    )
    assert response.status_code == 422  # Validation error
