"""
Settings and Configuration Management

Handles loading and validation of model configuration from:
1. config.json: Model registry with defaults
2. .env file: Environment variable overrides
3. Hardcoded defaults: Fallback values

Configuration Priority (highest to lowest):
    1. Environment variables (.env)
    2. config.json model defaults
    3. Class defaults

Classes:
    - Settings: Pydantic settings class with auto-loading from .env
"""

import json
import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    
    # Model selection
    model_name: str = "Qwen3-0.6B-w8a8-ctx16384"
    
    # RKLLM library path (can be absolute or relative to project root)
    rkllm_library_path: str = "lib/librkllmrt.so"
    
    # Model configuration (optional - overrides model defaults)
    max_context_len: Optional[int] = None
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    
    # Performance
    cpu_cores: str = "AUTO"
    enable_embed_flash: int = 1
    
    class Config:
        env_file = ".env"
        protected_namespaces = ('settings_',)
    
    def load_model_config(self) -> Dict[str, Any]:
        """Load model configuration from config.json"""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path) as f:
            return json.load(f)
    
    def get_resolved_config(self) -> Dict[str, Any]:
        """
        Get resolved model config (model defaults + .env overrides).
        
        Validates configuration and provides clear error messages for invalid values.
        
        Returns:
            dict: Resolved configuration with all parameters applied
            
        Raises:
            ValueError: If model_name not found or validation fails
        """
        registry = self.load_model_config()
        
        if self.model_name not in registry["models"]:
            raise ValueError(f"Model '{self.model_name}' not found in model registry. Available models: {list(registry['models'].keys())}")
        
        model_config = registry["models"][self.model_name]
        
        # Apply .env overrides
        resolved = model_config.copy()
        
        # model_id defaults to model_name if not specified in config
        if "model_id" not in resolved:
            resolved["model_id"] = self.model_name
        
        # Apply parameter overrides with validation
        if self.max_context_len is not None:
            if self.max_context_len <= 0:
                raise ValueError(f"max_context_len must be positive (got {self.max_context_len})")
            resolved["max_context_len"] = self.max_context_len
        
        if self.max_new_tokens is not None:
            if self.max_new_tokens <= 0:
                raise ValueError(f"max_new_tokens must be positive (got {self.max_new_tokens})")
            # Validate that max_new_tokens <= max_context_len
            context_len = self.max_context_len or resolved.get("max_context_len", 4096)
            if self.max_new_tokens > context_len:
                raise ValueError(f"max_new_tokens ({self.max_new_tokens}) cannot exceed max_context_len ({context_len})")
            resolved["max_new_tokens"] = self.max_new_tokens
        
        if self.temperature is not None:
            if not 0.0 <= self.temperature <= 2.0:
                raise ValueError(f"temperature must be between 0.0 and 2.0 (got {self.temperature})")
            resolved["temperature"] = self.temperature
        
        if self.top_p is not None:
            if not 0.0 <= self.top_p <= 1.0:
                raise ValueError(f"top_p must be between 0.0 and 1.0 (got {self.top_p})")
            resolved["top_p"] = self.top_p
        
        if self.top_k is not None:
            if self.top_k < 0:
                raise ValueError(f"top_k must be non-negative (got {self.top_k})")
            resolved["top_k"] = self.top_k
        
        if self.repeat_penalty is not None:
            if self.repeat_penalty < 0.0:
                raise ValueError(f"repeat_penalty must be non-negative (got {self.repeat_penalty})")
            resolved["repeat_penalty"] = self.repeat_penalty
        
        # Validate CPU cores configuration
        if self.cpu_cores.upper() == "AUTO":
            pass
        elif "-" in self.cpu_cores:
            try:
                start, end = map(int, self.cpu_cores.split("-"))
                if start < 0 or end > 7:
                    raise ValueError(f"CPU core range '{self.cpu_cores}' invalid: cores must be 0-7")
            except ValueError:
                raise ValueError(f"Invalid CPU core format '{self.cpu_cores}'. Use AUTO, range (e.g., 4-7), or list (e.g., 4,5,6)")
        elif "," in self.cpu_cores:
            try:
                cores = list(map(int, self.cpu_cores.split(",")))
                if any(not 0 <= c <= 7 for c in cores):
                    raise ValueError(f"CPU core list '{self.cpu_cores}' contains invalid core numbers (must be 0-7)")
            except ValueError:
                raise ValueError(f"Invalid CPU core format '{self.cpu_cores}'. Use AUTO, range (e.g., 4-7), or list (e.g., 4,5,6)")
        else:
            try:
                core = int(self.cpu_cores)
                if not 0 <= core <= 7:
                    raise ValueError(f"Single CPU core '{self.cpu_cores}' invalid: must be 0-7")
            except ValueError:
                raise ValueError(f"Invalid CPU core format '{self.cpu_cores}'. Use AUTO, range (e.g., 4-7), or list (e.g., 4,5,6)")
        
        # Validate performance settings
        if self.enable_embed_flash not in [0, 1]:
            raise ValueError(f"enable_embed_flash must be 0 or 1 (got {self.enable_embed_flash})")
        
        return resolved
