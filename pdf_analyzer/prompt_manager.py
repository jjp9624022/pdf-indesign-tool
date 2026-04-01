"""
Prompt 管理器 - 从 JSON 文件加载/保存 OCR 识别提示词
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "prompts.json"
)

# 最小兜底 prompt（仅当 prompts.json 不存在且加载失败时使用）
FALLBACK_PROMPTS = {
    "原文识别": "请仔细识别图片中的所有文字内容。\n\n要求：\n1. 保持原文的格式和结构\n2. 包含所有标点符号\n3. 保持原文的换行\n4. 只返回识别到的文字，不要其他解释\n\n请直接输出识别的文字：",
}


class PromptManager:
    """管理 OCR 识别提示词的加载、保存和查询"""

    def __init__(self, prompts_file: str = None):
        self._prompts_file = prompts_file or DEFAULT_PROMPTS_FILE
        self._prompts: dict = {}
        self._load()

    def _load(self):
        """从 JSON 文件加载 prompts"""
        if os.path.exists(self._prompts_file):
            try:
                with open(self._prompts_file, "r", encoding="utf-8") as f:
                    self._prompts = json.load(f)
                logger.info(
                    f"[PromptManager] 从 {self._prompts_file} 加载了 {len(self._prompts)} 个 Prompt"
                )
                return
            except Exception as e:
                logger.error(f"[PromptManager] 加载 Prompt 失败: {e}")
        else:
            logger.warning(
                f"[PromptManager] {self._prompts_file} 不存在，使用兜底 prompt"
            )

        # 兜底
        self._prompts = FALLBACK_PROMPTS.copy()

    def save(self) -> bool:
        """保存 prompts 到 JSON 文件"""
        try:
            with open(self._prompts_file, "w", encoding="utf-8") as f:
                json.dump(self._prompts, f, ensure_ascii=False, indent=2)
            logger.info(
                f"[PromptManager] 已保存 {len(self._prompts)} 个 Prompt 到 {self._prompts_file}"
            )
            return True
        except Exception as e:
            logger.error(f"[PromptManager] 保存 Prompt 失败: {e}")
            return False

    # ---- 查询 ----

    def get(self, key: str, default: str = None) -> str:
        """获取指定 prompt"""
        return self._prompts.get(key, default or "")

    def get_all(self) -> dict:
        """获取所有 prompts（返回副本）"""
        return self._prompts.copy()

    def keys(self) -> list:
        """获取所有 prompt 名称"""
        return list(self._prompts.keys())

    def first_key(self) -> str:
        """获取第一个 prompt 名称"""
        return list(self._prompts.keys())[0] if self._prompts else ""

    def count(self) -> int:
        return len(self._prompts)

    # ---- 增删改 ----

    def add(self, name: str, content: str) -> bool:
        """新增 prompt"""
        if name in self._prompts:
            return False
        self._prompts[name] = content
        return self.save()

    def update(self, name: str, content: str) -> bool:
        """更新 prompt"""
        if name not in self._prompts:
            return False
        self._prompts[name] = content
        return self.save()

    def delete(self, name: str) -> bool:
        """删除 prompt"""
        if name not in self._prompts:
            return False
        if len(self._prompts) <= 1:
            return False  # 至少保留一个
        del self._prompts[name]
        return self.save()
