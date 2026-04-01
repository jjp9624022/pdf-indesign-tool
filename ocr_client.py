"""
OCR Client - Multi-provider OCR support (Ollama, SiliconFlow, G4F, Volcengine)
"""

import json
import io
import os
import base64
import re
from typing import List, Optional
from PIL import Image


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


SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


class TextRegion:
    def __init__(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
        confidence: float = 1.0,
    ):
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = confidence

    @property
    def bbox(self) -> tuple:
        return (self.x, self.y, self.width, self.height)

    def __repr__(self):
        return f"TextRegion(text='{self.text[:30]}...', bbox={self.bbox})"


TEXT_DETECTION_PROMPT = """You are an OCR system. Analyze this image and identify all text regions with their bounding box coordinates.

Respond in JSON format:
```json
{
  "regions": [
    {"text": "text content here", "x": 100, "y": 50, "width": 200, "height": 30},
    ...
  ]
}
```

Only respond with JSON, no other text. If no text found, return {"regions": []}"""

EXTRACT_TEXT_PROMPT = """Extract all text from this image. Return only the extracted text, maintaining the original reading order and layout.
Include all punctuation, symbols, and special characters exactly as they appear.
Do not summarize or translate - return the raw text."""


def encode_image_to_base64(image: Image.Image) -> str:
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return base64.b64encode(img_bytes.getvalue()).decode("utf-8")


def parse_json_response(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except:
        pass

    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass

    print(f"Cannot parse JSON: {text[:200]}...")
    return None


class BaseOCRClient:
    def __init__(self, model: str):
        self.model = model

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        raise NotImplementedError

    def extract_text(self, image: Image.Image) -> str:
        raise NotImplementedError


class OllamaOCRClient(BaseOCRClient):
    def __init__(self, model: str):
        super().__init__(model)

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        if not OLLAMA_AVAILABLE:
            print("Ollama not available")
            return []

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": TEXT_DETECTION_PROMPT,
                        "images": [img_bytes.getvalue()],
                    }
                ],
                format="json",
            )
            content = response.message.content
            data = json.loads(content)

            regions = []
            for item in data.get("regions", []):
                region = TextRegion(
                    text=item.get("text", ""),
                    x=item.get("x", 0),
                    y=item.get("y", 0),
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    confidence=item.get("confidence", 1.0),
                )
                regions.append(region)
            return regions
        except Exception as e:
            print(f"Ollama OCR error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACT_TEXT_PROMPT,
                        "images": [img_bytes.getvalue()],
                    }
                ],
            )
            return response.message.content
        except Exception as e:
            print(f"Extract error: {e}")
            return ""


class SiliconFlowOCRClient(BaseOCRClient):
    def __init__(self, model: str, api_key: str = SILICONFLOW_API_KEY):
        super().__init__(model)
        self.api_key = api_key

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return []

        image_data = encode_image_to_base64(image)
        content = [
            {"type": "text", "text": TEXT_DETECTION_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_data}"},
            },
        ]

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{SILICONFLOW_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

            text_content = result["choices"][0]["message"]["content"]
            data = parse_json_response(text_content)
            if not data:
                return []

            regions = []
            for item in data.get("regions", []):
                region = TextRegion(
                    text=item.get("text", ""),
                    x=item.get("x", 0),
                    y=item.get("y", 0),
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    confidence=item.get("confidence", 1.0),
                )
                regions.append(region)
            return regions
        except Exception as e:
            print(f"SiliconFlow OCR error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        image_data = encode_image_to_base64(image)
        content = [
            {"type": "text", "text": EXTRACT_TEXT_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_data}"},
            },
        ]

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{SILICONFLOW_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Extract error: {e}")
            return ""


class G4FOCRClient(BaseOCRClient):
    def __init__(self, model: str, base_url: str = "http://192.168.1.29:1337"):
        super().__init__(model)
        self.base_url = base_url.rstrip("/")

    def _is_vision_model(self) -> bool:
        vision_indicators = ["vl", "vision", "qwen", "kimi", "sonar"]
        return any(indicator in self.model.lower() for indicator in vision_indicators)

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return []

        image_data = encode_image_to_base64(image)

        if self._is_vision_model():
            content = [
                {"type": "text", "text": TEXT_DETECTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
        else:
            content = (
                TEXT_DETECTION_PROMPT
                + f"\n\n[Image: data:image/png;base64,{image_data}]"
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions", json=payload, timeout=120
            )
            response.raise_for_status()
            result = response.json()

            text_content = result["choices"][0]["message"]["content"]
            data = parse_json_response(text_content)
            if not data:
                return []

            regions = []
            for item in data.get("regions", []):
                region = TextRegion(
                    text=item.get("text", ""),
                    x=item.get("x", 0),
                    y=item.get("y", 0),
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    confidence=item.get("confidence", 1.0),
                )
                regions.append(region)
            return regions
        except Exception as e:
            print(f"G4F OCR error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return ""

        image_data = encode_image_to_base64(image)

        if self._is_vision_model():
            content = [
                {"type": "text", "text": EXTRACT_TEXT_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
        else:
            content = (
                EXTRACT_TEXT_PROMPT + f"\n\n[Image: data:image/png;base64,{image_data}]"
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions", json=payload, timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"G4F extract error: {e}")
            return ""


class VolcengineOCRClient(BaseOCRClient):
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://ark.cn-beijing.volces.com/api/coding/v3",
    ):
        super().__init__(model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _is_vision_model(self) -> bool:
        vision_indicators = ["vl", "vision", "doubao", "ve"]
        return any(indicator in self.model.lower() for indicator in vision_indicators)

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return []

        image_data = encode_image_to_base64(image)

        if self._is_vision_model():
            content = [
                {"type": "text", "text": TEXT_DETECTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
        else:
            content = (
                TEXT_DETECTION_PROMPT
                + f"\n\n[Image: data:image/png;base64,{image_data}]"
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            text_content = result["choices"][0]["message"]["content"]
            data = parse_json_response(text_content)
            if not data:
                return []

            regions = []
            for item in data.get("regions", []):
                region = TextRegion(
                    text=item.get("text", ""),
                    x=item.get("x", 0),
                    y=item.get("y", 0),
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    confidence=item.get("confidence", 1.0),
                )
                regions.append(region)
            return regions
        except Exception as e:
            print(f"Volcengine OCR error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return ""

        image_data = encode_image_to_base64(image)

        if self._is_vision_model():
            content = [
                {"type": "text", "text": EXTRACT_TEXT_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
        else:
            content = (
                EXTRACT_TEXT_PROMPT + f"\n\n[Image: data:image/png;base64,{image_data}]"
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Volcengine extract error: {e}")
            return ""


def get_ocr_client(provider: str, model: str, **kwargs) -> BaseOCRClient:
    if provider == "ollama":
        return OllamaOCRClient(model)
    elif provider == "siliconflow":
        return SiliconFlowOCRClient(model, kwargs.get("api_key", SILICONFLOW_API_KEY))
    elif provider == "g4f":
        return G4FOCRClient(model, kwargs.get("base_url", "http://192.168.1.29:1337"))
    elif provider == "volcengine":
        return VolcengineOCRClient(
            model,
            api_key=kwargs.get("api_key", ""),
            base_url=kwargs.get(
                "base_url", "https://ark.cn-beijing.volces.com/api/coding/v3"
            ),
        )
    elif provider == "local_rapidocr":
        return RapidOCRLocalClient(model)
    else:
        raise ValueError(f"Unknown provider: {provider}")


class RapidOCRLocalClient(BaseOCRClient):
    def __init__(self, model: str = "rapidocr_onnx"):
        super().__init__(model)
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        try:
            import tempfile
            import os

            temp_path = os.path.join(tempfile.gettempdir(), "rapidocr_detect.png")
            image.save(temp_path)
            result, _ = self.engine(temp_path)
            regions = []
            if result:
                for item in result:
                    box = item[0]
                    text = item[1]
                    score = item[2]
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    regions.append(
                        TextRegion(
                            text=text,
                            x=int(min(xs)),
                            y=int(min(ys)),
                            width=int(max(xs) - min(xs)),
                            height=int(max(ys) - min(ys)),
                            confidence=float(score),
                        )
                    )
            return regions
        except Exception as e:
            print(f"RapidOCR detect error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        try:
            import tempfile
            import os

            temp_path = os.path.join(tempfile.gettempdir(), "rapidocr_extract.png")
            image.save(temp_path)
            result, _ = self.engine(temp_path)
            if result:
                return "\n".join(item[1] for item in result)
            return ""
        except Exception as e:
            print(f"RapidOCR extract error: {e}")
            return ""

    def analyze_with_prompt(self, image: Image.Image, prompt: str) -> str:
        return self.extract_text(image)


class RapidOCRLocalClient(BaseOCRClient):
    def __init__(self, model: str = "rapidocr_onnx"):
        super().__init__(model)
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        try:
            import tempfile
            import os

            temp_path = os.path.join(tempfile.gettempdir(), "rapidocr_detect.png")
            image.save(temp_path)
            result, _ = self.engine(temp_path)
            regions = []
            if result:
                for item in result:
                    box = item[0]
                    text = item[1]
                    score = item[2]
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    regions.append(
                        TextRegion(
                            text=text,
                            x=int(min(xs)),
                            y=int(min(ys)),
                            width=int(max(xs) - min(xs)),
                            height=int(max(ys) - min(ys)),
                            confidence=float(score),
                        )
                    )
            return regions
        except Exception as e:
            print(f"RapidOCR detect error: {e}")
            return []

    def extract_text(self, image: Image.Image) -> str:
        try:
            import tempfile
            import os

            temp_path = os.path.join(tempfile.gettempdir(), "rapidocr_extract.png")
            image.save(temp_path)
            result, _ = self.engine(temp_path)
            if result:
                return "\n".join(item[1] for item in result)
            return ""
        except Exception as e:
            print(f"RapidOCR extract error: {e}")
            return ""

    def analyze_with_prompt(self, image: Image.Image, prompt: str) -> str:
        return self.extract_text(image)


class OCRClient:
    def __init__(self, provider: str = "g4f", model: str = "qwen-2.5-vl-72b", **kwargs):
        self.provider = provider
        self.model = model
        self.kwargs = kwargs
        self._client = None

    @property
    def client(self) -> BaseOCRClient:
        if self._client is None:
            self._client = get_ocr_client(self.provider, self.model, **self.kwargs)
        return self._client

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        return self.client.detect_text(image)

    def extract_text(self, image: Image.Image) -> str:
        return self.client.extract_text(image)

    def analyze_with_prompt(self, image: Image.Image, prompt: str) -> str:
        if not REQUESTS_AVAILABLE:
            print("requests not available")
            return ""

        image_data = encode_image_to_base64(image)

        if self.provider == "doubao":
            api_key = self.kwargs.get("api_key", "")
            base_url = self.kwargs.get(
                "base_url", "https://ark.cn-beijing.volces.com/api/coding/v3"
            )

            # 使用与 volcengine 相同的 chat/completions 接口
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            try:
                response = requests.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Doubao analyze error: {e}")
                return ""

        elif self.provider == "g4f":
            base_url = self.kwargs.get("base_url", "http://192.168.1.29:1337")
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
            try:
                response = requests.post(
                    f"{base_url}/v1/chat/completions", json=payload, timeout=120
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"G4F analyze error: {e}")
                return ""

        elif self.provider == "volcengine":
            base_url = self.kwargs.get(
                "base_url", "https://ark.cn-beijing.volces.com/api/coding/v3"
            )
            api_key = self.kwargs.get("api_key", "")
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            try:
                response = requests.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Volcengine analyze error: {e}")
                return ""

        elif self.provider == "siliconflow":
            api_key = self.kwargs.get("api_key", SILICONFLOW_API_KEY)
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ]
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": content}],
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            try:
                response = requests.post(
                    f"{SILICONFLOW_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                if response.status_code != 200:
                    print(
                        f"SiliconFlow error: {response.status_code} - {response.text[:500]}"
                    )
                    response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"SiliconFlow analyze error: {e}")
                return ""

        elif self.provider == "ollama":
            img_bytes = io.BytesIO()
            image.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [img_bytes.getvalue()],
                        }
                    ],
                )
                return response.message.content
            except Exception as e:
                print(f"Ollama analyze error: {e}")
                return ""

        elif self.provider == "local_rapidocr":
            local_client = RapidOCRLocalClient(self.model)
            return local_client.extract_text(image)

        return ""
