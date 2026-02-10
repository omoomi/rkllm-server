"""
RKLLM Runtime Wrapper

This module provides Python bindings to the Rockchip RKLLM C library via ctypes.
It handles model initialization, inference execution, and resource management for
RK3588 NPU-accelerated LLM inference.

Key Classes:
    - RKLLMModel: Main wrapper class for RKLLM runtime
    - RKLLMParam, RKLLMInput, RKLLMResult: C data structures

Example:
    model = RKLLMModel(
        model_path="models/model.rkllm",
        max_context_len=4096,
        temperature=0.8
    )
    result = model.run(role="user", prompt="Hello, world!")
"""

import ctypes
import logging
import sys
import time
from typing import Optional

logger = logging.getLogger("rkllm-server.rkllm_wrapper")

# Constants
INFERENCE_TIMEOUT = 120
INFERENCE_POLL_INTERVAL = 0.01

# RKLLM constants
LLMCallState = ctypes.c_int
RKLLM_RUN_NORMAL = 0
RKLLM_RUN_WAITING = 1
RKLLM_RUN_FINISH = 2
RKLLM_RUN_ERROR = 3

# Input type determines what the input_data union contains
RKLLMInputType = ctypes.c_int
RKLLM_INPUT_PROMPT = 0
RKLLM_INPUT_TOKEN = 1
RKLLM_INPUT_EMBED = 2
RKLLM_INPUT_MULTIMODAL = 3

# Inference mode selects generation behavior
RKLLMInferMode = ctypes.c_int
RKLLM_INFER_GENERATE = 0
RKLLM_INFER_GET_LAST_HIDDEN_LAYER = 1
RKLLM_INFER_GET_LOGITS = 2

# CPU core configurations for RK3588
# Performance cores (4-7): High-performance A72 cores, better for inference
RK3588_PERFORMANCE_CORES_MASK = (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7)
# Efficiency cores (0-3): Low-power A53 cores, better for background tasks
RK3588_EFFICIENCY_CORES_MASK = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)
DEFAULT_CPU_CORES_COUNT = 4


class RKLLMExtendParam(ctypes.Structure):
    """
    Extended parameters for RKLLM runtime optimizations.
    
    Fields:
        base_domain_id: Base domain ID for distributed inference (unused, always 0)
        embed_flash: Enable flash attention optimization (1=enabled, 0=disabled)
        enabled_cpus_num: Number of CPU cores to enable
        enabled_cpus_mask: Bitmask of enabled CPU cores (1<<core_id)
        n_batch: Batch size for inference (unused, always 1)
        use_cross_attn: Cross-attention support (unused, always 0)
        reserved: Padding for future API compatibility (104 bytes)
    """
    _fields_ = [
        ("base_domain_id", ctypes.c_int32),
        ("embed_flash", ctypes.c_int8),
        ("enabled_cpus_num", ctypes.c_int8),
        ("enabled_cpus_mask", ctypes.c_uint32),
        ("n_batch", ctypes.c_uint8),
        ("use_cross_attn", ctypes.c_int8),
        ("reserved", ctypes.c_uint8 * 104)
    ]


class RKLLMParam(ctypes.Structure):
    """
    Main parameter structure for RKLLM model initialization.
    
    Fields:
        model_path: Path to the .rkllm model file
        max_context_len: Maximum context window size in tokens
        max_new_tokens: Maximum tokens to generate per request
        top_k: Top-K sampling parameter (restricts token selection)
        n_keep: Number of tokens to keep from start of context (-1=all)
        top_p: Nucleus sampling probability threshold (0-1)
        temperature: Sampling temperature (0=cold, 2=creative)
        repeat_penalty: Repetition penalty factor (1=no penalty, higher=less repetition)
        frequency_penalty: Frequency-based token penalty (unused, always 0)
        presence_penalty: Presence-based token penalty (unused, always 0)
        mirostat: Mirostat sampling mode (0=disabled)
        mirostat_tau: Mirostat target entropy (unused)
        mirostat_eta: Mirostat learning rate (unused)
        skip_special_token: Skip special tokens in output (True/False)
        is_async: Enable async inference (False, uses synchronous callback)
        img_start: Image start token (unused, empty string)
        img_end: Image end token (unused, empty string)
        img_content: Image content (unused, empty string)
        extend_param: Extended parameters (RKLLMExtendParam)
    """
    _fields_ = [
        ("model_path", ctypes.c_char_p),
        ("max_context_len", ctypes.c_int32),
        ("max_new_tokens", ctypes.c_int32),
        ("top_k", ctypes.c_int32),
        ("n_keep", ctypes.c_int32),
        ("top_p", ctypes.c_float),
        ("temperature", ctypes.c_float),
        ("repeat_penalty", ctypes.c_float),
        ("frequency_penalty", ctypes.c_float),
        ("presence_penalty", ctypes.c_float),
        ("mirostat", ctypes.c_int32),
        ("mirostat_tau", ctypes.c_float),
        ("mirostat_eta", ctypes.c_float),
        ("skip_special_token", ctypes.c_bool),
        ("is_async", ctypes.c_bool),
        ("img_start", ctypes.c_char_p),
        ("img_end", ctypes.c_char_p),
        ("img_content", ctypes.c_char_p),
        ("extend_param", RKLLMExtendParam),
    ]


class RKLLMInputUnion(ctypes.Structure):
    """
    Union type for input data (only prompt_input is used).
    
    Fields:
        prompt_input: Text prompt to encode and process
    """
    _fields_ = [
        ("prompt_input", ctypes.c_char_p),
    ]


class RKLLMInput(ctypes.Structure):
    """
    Input structure for a single inference request.
    
    Fields:
        role: Message role ("user", "assistant", "system")
        enable_thinking: Enable thinking mode (experimental)
        input_type: Type of input data (PROMPT/TOKEN/EMBED/MULTIMODAL)
        input_data: Union containing the actual input (prompt_input)
    """
    _fields_ = [
        ("role", ctypes.c_char_p),
        ("enable_thinking", ctypes.c_bool),
        ("input_type", RKLLMInputType),
        ("input_data", RKLLMInputUnion),
    ]


class RKLLMInferParam(ctypes.Structure):
    """
    Parameters for the inference operation itself.
    
    Fields:
        mode: Inference mode (GENERATE/GET_LAST_HIDDEN_LAYER/GET_LOGITS)
        lora_params: LoRA adapter parameters (unused, NULL)
        prompt_cache_params: Prompt cache parameters (unused, NULL)
        keep_history: Whether to keep conversation history (0=reset each request)
    """
    _fields_ = [
        ("mode", RKLLMInferMode),
        ("lora_params", ctypes.POINTER(ctypes.c_void_p)),
        ("prompt_cache_params", ctypes.POINTER(ctypes.c_void_p)),
        ("keep_history", ctypes.c_int)
    ]


class RKLLMResult(ctypes.Structure):
    """
    Result structure from the RKLLM callback function.
    
    Fields:
        text: Generated text output (null-terminated string)
        token_id: Generated token ID (for debugging)
        last_hidden_layer: Pointer to last hidden layer (unused, NULL)
        logits: Pointer to logits tensor (unused, NULL)
        perf: Pointer to performance metrics (unused, NULL)
    """
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("token_id", ctypes.c_int),
        ("last_hidden_layer", ctypes.c_void_p),
        ("logits", ctypes.c_void_p),
        ("perf", ctypes.c_void_p)
    ]


class RKLLMParam(ctypes.Structure):
    _fields_ = [
        ("model_path", ctypes.c_char_p),
        ("max_context_len", ctypes.c_int32),
        ("max_new_tokens", ctypes.c_int32),
        ("top_k", ctypes.c_int32),
        ("n_keep", ctypes.c_int32),
        ("top_p", ctypes.c_float),
        ("temperature", ctypes.c_float),
        ("repeat_penalty", ctypes.c_float),
        ("frequency_penalty", ctypes.c_float),
        ("presence_penalty", ctypes.c_float),
        ("mirostat", ctypes.c_int32),
        ("mirostat_tau", ctypes.c_float),
        ("mirostat_eta", ctypes.c_float),
        ("skip_special_token", ctypes.c_bool),
        ("is_async", ctypes.c_bool),
        ("img_start", ctypes.c_char_p),
        ("img_end", ctypes.c_char_p),
        ("img_content", ctypes.c_char_p),
        ("extend_param", RKLLMExtendParam),
    ]


class RKLLMInputUnion(ctypes.Union):
    _fields_ = [
        ("prompt_input", ctypes.c_char_p),
    ]


class RKLLMInput(ctypes.Structure):
    _fields_ = [
        ("role", ctypes.c_char_p),
        ("enable_thinking", ctypes.c_bool),
        ("input_type", RKLLMInputType),
        ("input_data", RKLLMInputUnion),
    ]


class RKLLMInferParam(ctypes.Structure):
    _fields_ = [
        ("mode", RKLLMInferMode),
        ("lora_params", ctypes.POINTER(ctypes.c_void_p)),
        ("prompt_cache_params", ctypes.POINTER(ctypes.c_void_p)),
        ("keep_history", ctypes.c_int)
    ]


class RKLLMResult(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("token_id", ctypes.c_int),
        ("last_hidden_layer", ctypes.c_void_p),
        ("logits", ctypes.c_void_p),
        ("perf", ctypes.c_void_p)
    ]


def get_cpu_core_mask(cpu_cores: str, platform: str = "rk3588") -> tuple[int, int]:
    """
    Parse CPU cores configuration and return (mask, count)
    
    Args:
        cpu_cores: Configuration string (AUTO, range "4-7", list "4,5,6,7", or single "4")
        platform: Platform identifier (default rk3588)
    
    Returns:
        tuple: (cpu_mask, cpu_count)
    """
    if cpu_cores.upper() == "AUTO":
        if platform.lower() in ["rk3576", "rk3588"]:
            return RK3588_PERFORMANCE_CORES_MASK, DEFAULT_CPU_CORES_COUNT
        else:
            return RK3588_EFFICIENCY_CORES_MASK, DEFAULT_CPU_CORES_COUNT
    
    try:
        if "-" in cpu_cores:
            start, end = map(int, cpu_cores.split("-"))
            if start < 0 or end > 7:
                return get_cpu_core_mask("AUTO", platform)
            mask = sum(1 << i for i in range(start, end + 1))
            return mask, end - start + 1
        elif "," in cpu_cores:
            cores = list(map(int, cpu_cores.split(",")))
            mask = sum(1 << i for i in cores if 0 <= i <= 7)
            return mask, len(cores)
        else:
            core = int(cpu_cores)
            if 0 <= core <= 7:
                return 1 << core, 1
            return get_cpu_core_mask("AUTO", platform)
    except Exception:
        return get_cpu_core_mask("AUTO", platform)


def validate_temperature(temp: float) -> float:
    """Validate temperature parameter (0.0 to 2.0)"""
    if temp < 0.0:
        logger.warning(f"Temperature {temp} is below 0.0, clamping to 0.0")
        return 0.0
    if temp > 2.0:
        logger.warning(f"Temperature {temp} is above 2.0, clamping to 2.0")
        return 2.0
    return temp


def validate_top_p(value: float) -> float:
    """Validate top_p parameter (0.0 to 1.0)"""
    if value < 0.0:
        logger.warning(f"Top-p {value} is below 0.0, clamping to 0.0")
        return 0.0
    if value > 1.0:
        logger.warning(f"Top-p {value} is above 1.0, clamping to 1.0")
        return 1.0
    return value


def validate_top_k(value: int) -> int:
    """Validate top_k parameter (>= 0)"""
    if value < 0:
        logger.warning(f"Top-k {value} is negative, setting to 1")
        return 1
    return value


def validate_repeat_penalty(penalty: float) -> float:
    """Validate repeat_penalty parameter (>= 0)"""
    if penalty < 0.0:
        logger.warning(f"Repeat penalty {penalty} is negative, setting to 1.0")
        return 1.0
    return penalty


class RKLLMModel:
    def __init__(
        self,
        model_path: str,
        max_context_len: int = 4096,
        max_new_tokens: int = 2048,
        temperature: float = 0.8,
        top_p: float = 0.9,
        top_k: int = 1,
        repeat_penalty: float = 1.1,
        cpu_cores: str = "AUTO",
        enable_embed_flash: int = 1,
        platform: str = "rk3588",
        library_path: str = "lib/librkllmrt.so",
    ):
        self.model_path = model_path
        self.max_context_len = max_context_len
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.cpu_cores = cpu_cores
        self.enable_embed_flash = enable_embed_flash
        self.platform = platform
        
        # Instance variables for callback state (thread-safe per instance)
        self._callback_text = []
        self._callback_state = -1
        
        # Load library
        self.rkllm_lib = ctypes.CDLL(library_path)
        
        # Build callback
        callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int,
            ctypes.POINTER(RKLLMResult),
            ctypes.c_void_p,
            ctypes.c_int
        )
        self._callback = callback_type(self._callback_impl)
        
        # Initialize parameters
        rkllm_param = RKLLMParam()
        rkllm_param.model_path = bytes(model_path, 'utf-8')
        rkllm_param.max_context_len = max_context_len
        rkllm_param.max_new_tokens = max_new_tokens
        rkllm_param.skip_special_token = True
        rkllm_param.n_keep = -1
        rkllm_param.top_k = validate_top_k(top_k)
        rkllm_param.top_p = validate_top_p(top_p)
        rkllm_param.temperature = validate_temperature(temperature)
        rkllm_param.repeat_penalty = validate_repeat_penalty(repeat_penalty)
        rkllm_param.frequency_penalty = 0.0
        rkllm_param.presence_penalty = 0.0
        rkllm_param.mirostat = 0
        rkllm_param.mirostat_tau = 5.0
        rkllm_param.mirostat_eta = 0.1
        rkllm_param.is_async = False
        rkllm_param.img_start = "".encode('utf-8')
        rkllm_param.img_end = "".encode('utf-8')
        rkllm_param.img_content = "".encode('utf-8')
        
        # Set extended parameters
        rkllm_param.extend_param.base_domain_id = 0
        rkllm_param.extend_param.embed_flash = enable_embed_flash
        rkllm_param.extend_param.n_batch = 1
        rkllm_param.extend_param.use_cross_attn = 0
        
        # Set CPU cores
        cpu_mask, cpu_count = get_cpu_core_mask(cpu_cores, platform)
        rkllm_param.extend_param.enabled_cpus_mask = cpu_mask
        rkllm_param.extend_param.enabled_cpus_num = cpu_count
        
        # Store library functions
        self.rkllm_init = self.rkllm_lib.rkllm_init
        self.rkllm_init.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(RKLLMParam),
            callback_type
        ]
        self.rkllm_init.restype = ctypes.c_int
        
        self.rkllm_run = self.rkllm_lib.rkllm_run
        self.rkllm_run.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(RKLLMInput),
            ctypes.POINTER(RKLLMInferParam),
            ctypes.c_void_p
        ]
        self.rkllm_run.restype = ctypes.c_int
        
        self.rkllm_destroy = self.rkllm_lib.rkllm_destroy
        self.rkllm_destroy.argtypes = [ctypes.c_void_p]
        self.rkllm_destroy.restype = ctypes.c_int
        
        self.rkllm_abort = self.rkllm_lib.rkllm_abort
        
        # Initialize model
        self.handle = ctypes.c_void_p()
        ret = self.rkllm_init(
            ctypes.byref(self.handle),
            ctypes.byref(rkllm_param),
            self._callback
        )
        if ret != 0:
            raise RuntimeError("RKLLM initialization failed. Check model file path and RKLLM runtime compatibility.")
        logger.info("RKLLM initialized successfully")
        
        # Set up inference parameters
        self.rkllm_infer_params = RKLLMInferParam()
        ctypes.memset(
            ctypes.byref(self.rkllm_infer_params),
            0,
            ctypes.sizeof(RKLLMInferParam)
        )
        self.rkllm_infer_params.mode = RKLLM_INFER_GENERATE
        self.rkllm_infer_params.lora_params = None
        self.rkllm_infer_params.keep_history = 0
    
    def _callback_impl(self, result, userdata, state):
        """Internal callback implementation that receives streaming output from RKLLM"""
        if state == RKLLM_RUN_FINISH:
            self._callback_state = state
            sys.stdout.write("\n")
            sys.stdout.flush()
        elif state == RKLLM_RUN_ERROR:
            self._callback_state = state
            logger.error("RKLLM inference error during generation")
            sys.stdout.write("run error\n")
            sys.stdout.flush()
        elif state == RKLLM_RUN_NORMAL:
            self._callback_state = state
            self._callback_text.append(result.contents.text.decode('utf-8'))
        return 0
    
    def run(
        self,
        role: Optional[str],
        enable_thinking: Optional[bool],
        prompt: str
    ) -> str:
        """Run inference and return generated text"""
        # Reset callback state
        self._callback_text = []
        self._callback_state = -1
        
        # Build input
        rkllm_input = RKLLMInput()
        rkllm_input.role = (role.encode('utf-8') if role is not None else b"user")
        rkllm_input.enable_thinking = ctypes.c_bool(enable_thinking if enable_thinking is not None else False)
        rkllm_input.input_type = RKLLM_INPUT_PROMPT
        rkllm_input.input_data.prompt_input = ctypes.c_char_p(prompt.encode('utf-8'))
        
        # Run inference
        self.rkllm_run(
            self.handle,
            ctypes.byref(rkllm_input),
            ctypes.byref(self.rkllm_infer_params),
            None
        )
        
        # Wait for completion
        start_time = time.time()
        while (
            self._callback_state != RKLLM_RUN_FINISH and
            self._callback_state != RKLLM_RUN_ERROR
        ):
            if time.time() - start_time > INFERENCE_TIMEOUT:
                raise TimeoutError("Inference timeout")
            time.sleep(INFERENCE_POLL_INTERVAL)
        
        if self._callback_state == RKLLM_RUN_ERROR:
            raise RuntimeError("Inference error")
        
        return ''.join(self._callback_text)
    
    def abort(self) -> None:
        """Abort current inference"""
        return self.rkllm_abort(self.handle)
    
    def get_config(self) -> dict:
        """Return current configuration for logging"""
        return {
            "model_path": self.model_path,
            "max_context_len": self.max_context_len,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "cpu_cores": self.cpu_cores,
            "enable_embed_flash": self.enable_embed_flash,
        }
    
    def release(self) -> None:
        """Release model resources"""
        self.rkllm_destroy(self.handle)
