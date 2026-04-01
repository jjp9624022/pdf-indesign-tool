"""
Unified LLM API client - Supports both local Ollama and SiliconFlow API
"""

import os
import json
import base64
import io
from typing import List, Dict, Any, Optional, Union
from PIL import Image

# Try importing ollama, but make it optional
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ============================================================
# Configuration
# ============================================================

# SiliconFlow API Configuration â€?managed via config.json
SILICONFLOW_API_KEY = ""
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# Default models
DEFAULT_OLLAMA_TEXT_MODEL = "deepseek-chat"
DEFAULT_OLLAMA_VISION_MODEL = "qwen2.5vl"
DEFAULT_SILICONFLOW_TEXT_MODEL = "deepseek-ai/DeepSeek-V2-Chat"
DEFAULT_SILICONFLOW_VISION_MODEL = "Qwen/Qwen2-VL-72B-Instruct"


# ============================================================
# Model Provider Enum
# ============================================================


class ModelProvider:
    OLLAMA = "ollama"
    SILICONFLOW = "siliconflow"


# ============================================================
# Base Client Interface
# ============================================================


class BaseLLMClient:
    """Base class for LLM clients"""

    def __init__(self, model: str):
        self.model = model

    def chat(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        stream: bool = False,
        format: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send chat request - implement in subclass"""
        raise NotImplementedError

    def chat_with_image(self, image: Image.Image, prompt: str, **kwargs) -> str:
        """Send image + text request - implement in subclass"""
        raise NotImplementedError


# ============================================================
# Ollama Client
# ============================================================


class OllamaClient(BaseLLMClient):
    """Local Ollama client"""

    def __init__(self, model: str):
        super().__init__(model)
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama package not installed. Run: pip install ollama")

    def chat(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        stream: bool = False,
        format: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send chat request to local Ollama"""

        # Handle images - convert to bytes if needed
        processed_messages = []
        for msg in messages:
            processed_msg = msg.copy()

            if images and msg.get("role") == "user":
                # Add images to the user message
                processed_images = []
                for img in images:
                    if isinstance(img, Image.Image):
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format="PNG")
                        img_bytes.seek(0)
                        processed_images.append(img_bytes.getvalue())
                    elif isinstance(img, bytes):
                        processed_images.append(img)
                    elif isinstance(img, str):
                        # File path
                        with open(img, "rb") as f:
                            processed_images.append(f.read())

                processed_msg["images"] = processed_images

            processed_messages.append(processed_msg)

        params = {"model": self.model, "messages": processed_messages, "stream": stream}

        if format:
            params["format"] = format

        return ollama.chat(**params)

    def chat_with_image(
        self, image: Image.Image, prompt: str, max_retries: int = 3, **kwargs
    ) -> str:
        """Send image + text to Ollama vision model with retry logic"""
        from image_utils import prepare_image_for_ollama
        import time

        # Compress image before sending
        image_bytes = prepare_image_for_ollama(image, max_size=(1024, 1024), quality=85)

        for attempt in range(max_retries):
            try:
                response = self.chat(
                    messages=[
                        {"role": "user", "content": prompt, "images": [image_bytes]}
                    ],
                    **kwargs,
                )
                return response.message.content
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    print(f"  Error: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  Failed after {max_retries} attempts: {e}")
                    return ""
        return ""


# ============================================================
# SiliconFlow API Client
# ============================================================


class SiliconFlowClient(BaseLLMClient):
    """SiliconFlow API client (OpenAI-compatible)"""

    def __init__(
        self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None
    ):
        super().__init__(model)
        self.api_key = api_key or SILICONFLOW_API_KEY
        self.base_url = base_url or SILICONFLOW_BASE_URL

        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests package not installed. Run: pip install requests"
            )

    def _encode_image(self, image: Union[Image.Image, bytes, str]) -> str:
        """Encode image to base64"""
        if isinstance(image, Image.Image):
            img_bytes = io.BytesIO()
            image.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return base64.b64encode(img_bytes.getvalue()).decode("utf-8")
        elif isinstance(image, bytes):
            return base64.b64encode(image).decode("utf-8")
        elif isinstance(image, str):
            # File path or URL
            if os.path.exists(image):
                with open(image, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            else:
                # Assume URL
                return image
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

    def _is_vision_model(self) -> bool:
        """Check if current model is a vision model"""
        vision_indicators = ["vl", "vision", "qwen2-vl", "qwen2.5-vl"]
        return any(indicator in self.model.lower() for indicator in vision_indicators)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[Union[str, bytes, Image.Image]]] = None,
        stream: bool = False,
        format: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send chat request to SiliconFlow API"""

        # Process messages for vision models
        processed_messages = []

        for i, msg in enumerate(messages):
            processed_msg = {"role": msg["role"], "content": msg.get("content", "")}

            # Add images to the last user message
            if images and msg.get("role") == "user":
                if self._is_vision_model():
                    # Vision model - use multimodal format
                    content_parts = []

                    # Add text part
                    if processed_msg["content"]:
                        content_parts.append(
                            {"type": "text", "text": processed_msg["content"]}
                        )

                    # Add image parts
                    for img in images:
                        image_data = self._encode_image(img)
                        content_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                },
                            }
                        )

                    processed_msg["content"] = content_parts
                else:
                    # Non-vision model - can't handle images
                    processed_msg["content"] = (
                        msg.get("content", "")
                        + f"\n\n[Image provided but model {self.model} may not support vision]"
                    )

            processed_messages.append(processed_msg)

        # Build request
        payload = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream,
        }

        if format:
            # For JSON mode
            payload["response_format"] = {"type": "json_object"}

        # Add any additional parameters
        payload.update(kwargs)

        # Make request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"

        if stream:
            response = requests.post(
                endpoint, json=payload, headers=headers, stream=True, **kwargs
            )
            response.raise_for_status()

            # Handle streaming response
            result = ""
            for chunk in response.iter_lines():
                if chunk:
                    line = chunk.decode("utf-8")
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                result += delta["content"]
            return {"message": {"content": result}}
        else:
            response = requests.post(endpoint, json=payload, headers=headers, **kwargs)
            response.raise_for_status()
            result = response.json()

            # Parse response
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]

                # Handle JSON format response
                if format == "json" or format == "json_object":
                    try:
                        # Wrap in dict if needed
                        if isinstance(content, str):
                            parsed = json.loads(content)
                        else:
                            parsed = content
                        return {"message": {"content": json.dumps(parsed)}}
                    except json.JSONDecodeError:
                        pass

                return {"message": {"content": content}}

            return result

    def chat_with_image(self, image: Image.Image, prompt: str, **kwargs) -> str:
        """Send image + text to SiliconFlow vision model"""
        response = self.chat(
            messages=[{"role": "user", "content": prompt}], images=[image], **kwargs
        )
        return response.message.content


# ============================================================
# Factory Function
# ============================================================


def get_client(
    provider: str = ModelProvider.OLLAMA, model: Optional[str] = None, **kwargs
) -> BaseLLMClient:
    """
    Get LLM client based on provider

    Args:
        provider: "ollama" or "siliconflow"
        model: Model name (defaults based on provider)
        **kwargs: Additional parameters for client

    Returns:
        LLM client instance
    """
    if provider == ModelProvider.OLLAMA:
        model = model or DEFAULT_OLLAMA_VISION_MODEL
        return OllamaClient(model)
    elif provider == ModelProvider.SILICONFLOW:
        model = model or DEFAULT_SILICONFLOW_VISION_MODEL
        return SiliconFlowClient(model, **kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_text_client(
    provider: str = ModelProvider.OLLAMA, model: Optional[str] = None, **kwargs
) -> BaseLLMClient:
    """Get LLM client for text-only models"""
    if provider == ModelProvider.OLLAMA:
        model = model or DEFAULT_OLLAMA_TEXT_MODEL
    else:
        model = model or DEFAULT_SILICONFLOW_TEXT_MODEL
    return get_client(provider, model, **kwargs)


def get_vision_client(
    provider: str = ModelProvider.OLLAMA, model: Optional[str] = None, **kwargs
) -> BaseLLMClient:
    """Get LLM client for vision models"""
    if provider == ModelProvider.OLLAMA:
        model = model or DEFAULT_OLLAMA_VISION_MODEL
    else:
        model = model or DEFAULT_SILICONFLOW_VISION_MODEL
    return get_client(provider, model, **kwargs)


# ============================================================
# Convenience Functions
# ============================================================


def analyze_image_with_provider(
    image: Image.Image,
    prompt: str,
    provider: str = ModelProvider.OLLAMA,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Analyze image with specified provider

    Args:
        image: PIL Image
        prompt: Question about the image
        provider: "ollama" or "siliconflow"
        model: Model name (optional)

    Returns:
        Model's response
    """
    client = get_vision_client(provider, model, **kwargs)
    return client.chat_with_image(image, prompt)


def chat_with_provider(
    messages: List[Dict[str, Any]],
    provider: str = ModelProvider.OLLAMA,
    model: Optional[str] = None,
    images: Optional[List[Image.Image]] = None,
    format: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Send chat request with specified provider

    Args:
        messages: List of message dicts
        provider: "ollama" or "siliconflow"
        model: Model name (optional)
        images: Optional images to include
        format: Response format ("json")

    Returns:
        Response dict
    """
    if images:
        client = get_vision_client(provider, model, **kwargs)
    else:
        client = get_text_client(provider, model, **kwargs)

    return client.chat(messages, images=images, format=format)
