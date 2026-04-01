import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field


@dataclass
class ModelConfig:
    name: str
    provider: str
    model_id: str
    is_vision: bool = True


@dataclass
class ProviderConfig:
    id: str
    name: str
    api_key: str = ""
    base_url: str = ""
    models: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AppConfig:
    ocr_model: ModelConfig = None
    translation_model: ModelConfig = None
    providers: List[ProviderConfig] = field(default_factory=list)
    always_on_top: bool = True
    dock_opacity: float = 0.9
    target_language: str = "Chinese"


class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = AppConfig()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._apply_data(data)
            except Exception as e:
                print(f"Failed to load config: {e}")
                self._set_defaults()
        else:
            self._set_defaults()

    def _set_defaults(self):
        self.config.providers = [
            ProviderConfig(
                id="siliconflow",
                name="SiliconFlow",
                api_key="",
                base_url="",
                models=[
                    {
                        "model_id": "deepseek-ai/DeepSeek-OCR",
                        "name": "DeepSeek OCR",
                        "is_vision": True,
                    },
                    {
                        "model_id": "PaddlePaddle/PaddleOCR-VL",
                        "name": "PaddleOCR VL",
                        "is_vision": True,
                    },
                    {
                        "model_id": "PaddlePaddle/PaddleOCR-VL-1.5",
                        "name": "PaddleOCR VL 1.5",
                        "is_vision": True,
                    },
                    {
                        "model_id": "Qwen/Qwen2-VL-72B-Instruct",
                        "name": "Qwen2-VL 72B",
                        "is_vision": True,
                    },
                    {
                        "model_id": "Qwen/Qwen2.5-VL-72B-Instruct",
                        "name": "Qwen2.5-VL 72B",
                        "is_vision": True,
                    },
                    {
                        "model_id": "Qwen/Qwen2.5-VL-32B-Instruct",
                        "name": "Qwen2.5-VL 32B",
                        "is_vision": True,
                    },
                    {
                        "model_id": "THUDM/glm-4v-9b",
                        "name": "GLM-4V 9B",
                        "is_vision": True,
                    },
                    {
                        "model_id": "deepseek-ai/DeepSeek-V2-Chat",
                        "name": "DeepSeek V2",
                        "is_vision": False,
                    },
                    {
                        "model_id": "Qwen/Qwen2.5-72B-Instruct",
                        "name": "Qwen 2.5 72B",
                        "is_vision": False,
                    },
                    {
                        "model_id": "Qwen/Qwen2.5-7B-Instruct",
                        "name": "Qwen 2.5 7B",
                        "is_vision": False,
                    },
                ],
            ),
            ProviderConfig(
                id="doubao",
                name="豆包 (Doubao)",
                api_key="",
                base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
                models=[
                    {
                        "model_id": "doubao-seed-2-0-mini-260215",
                        "name": "豆包 Seed 2.0 Mini",
                        "is_vision": True,
                    },
                    {
                        "model_id": "doubao-seed-2-0-pro-260215",
                        "name": "豆包 Seed 2.0 Pro",
                        "is_vision": True,
                    },
                    {
                        "model_id": "doubao-seed-1-6-vision-250815",
                        "name": "豆包 Seed 1.6 视觉",
                        "is_vision": True,
                    },
                    {
                        "model_id": "doubao-seed-1-6-flash-250715",
                        "name": "豆包 Seed 1.6 Flash",
                        "is_vision": True,
                    },
                ],
            ),
            ProviderConfig(
                id="local_rapidocr",
                name="本地 RapidOCR",
                api_key="",
                base_url="",
                models=[
                    {
                        "model_id": "rapidocr_onnx",
                        "name": "RapidOCR (本地)",
                        "is_vision": True,
                    },
                ],
            ),
            ProviderConfig(
                id="local_paddleocr",
                name="本地 PaddleOCR",
                api_key="",
                base_url="",
                models=[
                    {
                        "model_id": "paddleocr_vl",
                        "name": "PaddleOCR VL (本地)",
                        "is_vision": True,
                    },
                ],
            ),
        ]

        self.config.ocr_model = ModelConfig(
            name="DeepSeek OCR (SiliconFlow)",
            provider="siliconflow",
            model_id="deepseek-ai/DeepSeek-OCR",
            is_vision=True,
        )
        self.config.translation_model = ModelConfig(
            name="DeepSeek V2 (SiliconFlow)",
            provider="siliconflow",
            model_id="deepseek-ai/DeepSeek-V2-Chat",
            is_vision=False,
        )
        self.config.always_on_top = True
        self.config.dock_opacity = 0.9
        self.config.target_language = "Chinese"

    def _apply_data(self, data: Dict):
        if "ocr_model" in data and data["ocr_model"]:
            self.config.ocr_model = ModelConfig(**data["ocr_model"])
        if "translation_model" in data and data["translation_model"]:
            self.config.translation_model = ModelConfig(**data["translation_model"])
        if "always_on_top" in data:
            self.config.always_on_top = data["always_on_top"]
        if "dock_opacity" in data:
            self.config.dock_opacity = data["dock_opacity"]
        if "target_language" in data:
            self.config.target_language = data["target_language"]

        if "providers" in data and data["providers"]:
            self.config.providers = [
                ProviderConfig(**p) if isinstance(p, dict) else p
                for p in data["providers"]
            ]
        else:
            self._set_defaults()
            self._migrate_old_keys(data)

    def _migrate_old_keys(self, data: Dict):
        sf_key = data.get("siliconflow_api_key")
        if sf_key:
            for p in self.config.providers:
                if p.id == "siliconflow":
                    p.api_key = sf_key
                    break

        vb_key = data.get("volcengine_api_key")
        if vb_key:
            for p in self.config.providers:
                if p.id == "doubao":
                    p.api_key = vb_key
                    break

        vb_url = data.get("volcengine_base_url")
        if vb_url:
            for p in self.config.providers:
                if p.id == "doubao":
                    p.base_url = vb_url
                    break

        g4f_url = data.get("g4f_base_url")
        if g4f_url:
            for p in self.config.providers:
                if p.id == "g4f":
                    p.base_url = g4f_url
                    break

        self._migrate_old_config(data)

    def _migrate_old_config(self, data: Dict):
        sf_key = data.get("siliconflow_api_key")
        if sf_key:
            sf = self.get_provider_by_id("siliconflow")
            if sf and not sf.api_key:
                sf.api_key = sf_key

        vb_key = data.get("volcengine_api_key")
        if vb_key:
            vb = self.get_provider_by_id("doubao")
            if vb and not vb.api_key:
                vb.api_key = vb_key

        vb_url = data.get("volcengine_base_url")
        if vb_url:
            vb = self.get_provider_by_id("doubao")
            if vb and not vb.base_url:
                vb.base_url = vb_url

        g4f_url = data.get("g4f_base_url")
        if g4f_url:
            g4f = self.get_provider_by_id("g4f")
            if g4f and not g4f.base_url:
                g4f.base_url = g4f_url

    def save(self):
        data = {
            "ocr_model": asdict(self.config.ocr_model)
            if self.config.ocr_model
            else None,
            "translation_model": asdict(self.config.translation_model)
            if self.config.translation_model
            else None,
            "providers": [asdict(p) for p in self.config.providers],
            "always_on_top": self.config.always_on_top,
            "dock_opacity": self.config.dock_opacity,
            "target_language": self.config.target_language,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_all_models(self) -> List[tuple]:
        result = []
        for provider in self.config.providers:
            for m in provider.models:
                result.append((m["model_id"], m["name"]))
        return result

    def get_provider_by_model_id(self, model_id: str) -> Optional[ProviderConfig]:
        for provider in self.config.providers:
            for m in provider.models:
                if m["model_id"] == model_id:
                    return provider
        return None

    def get_provider_by_id(self, provider_id: str) -> Optional[ProviderConfig]:
        for p in self.config.providers:
            if p.id == provider_id:
                return p
        return None

    def get_ocr_provider(self) -> str:
        return (
            self.config.ocr_model.provider if self.config.ocr_model else "siliconflow"
        )

    def get_ocr_model_id(self) -> str:
        return (
            self.config.ocr_model.model_id
            if self.config.ocr_model
            else "Qwen/Qwen2-VL-72B-Instruct"
        )

    def get_translation_provider(self) -> str:
        return (
            self.config.translation_model.provider
            if self.config.translation_model
            else "siliconflow"
        )

    def get_translation_model_id(self) -> str:
        return (
            self.config.translation_model.model_id
            if self.config.translation_model
            else "deepseek-ai/DeepSeek-V2-Chat"
        )

    def add_provider(
        self, provider_id: str, name: str, api_key: str = "", base_url: str = ""
    ):
        if self.get_provider_by_id(provider_id):
            raise ValueError(f"Provider '{provider_id}' already exists")
        self.config.providers.append(
            ProviderConfig(
                id=provider_id, name=name, api_key=api_key, base_url=base_url
            )
        )
        self.save()

    def remove_provider(self, provider_id: str):
        self.config.providers = [
            p for p in self.config.providers if p.id != provider_id
        ]
        self.save()

    def add_model_to_provider(
        self, provider_id: str, model_id: str, name: str, is_vision: bool = True
    ):
        provider = self.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found")
        for m in provider.models:
            if m["model_id"] == model_id:
                raise ValueError(
                    f"Model '{model_id}' already exists in provider '{provider_id}'"
                )
        provider.models.append(
            {"model_id": model_id, "name": name, "is_vision": is_vision}
        )
        self.save()

    def remove_model_from_provider(self, provider_id: str, model_id: str):
        provider = self.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found")
        provider.models = [m for m in provider.models if m["model_id"] != model_id]
        self.save()

    def update_provider(self, provider_id: str, **kwargs):
        provider = self.get_provider_by_id(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' not found")
        for key, value in kwargs.items():
            if hasattr(provider, key):
                setattr(provider, key, value)
        self.save()
