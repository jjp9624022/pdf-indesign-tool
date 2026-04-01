"""
InDesign COM Client - Windows only
用于与 InDesign 进行文本搜索、定位和替换

参考: G:\tools\indesign-opt\id_connector.py
"""

import logging
import re
import pythoncom
import win32com.client
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# COM 常量
ID_JAVASCRIPT = 1246973031
ID_NOTHING = 1851876449


@dataclass
class TextMatch:
    """文本匹配结果"""

    text: str  # 匹配到的文本
    page_name: str  # 页面名称
    text_frame_name: str  # 文本框名称
    text_frame_id: int  # 文本框ID
    bounds: Tuple[int, int, int, int]  # 坐标


class InDesignClient:
    """InDesign COM 客户端"""

    def __init__(self):
        self.app = None
        self.connected = False
        self.pythoncom_init = False
        # 缓存：文档中的所有文本框
        self._textframe_cache = []  # [{id, name, text, page_name, bounds}, ...]
        self._cache_doc_name = None  # 缓存对应的文档名

    def connect(self) -> tuple:
        """连接到已运行的 InDesign（自动检测版本）

        Returns:
            (success, actual_version)
        """
        try:
            # 初始化 COM
            if not self.pythoncom_init:
                pythoncom.CoInitialize()
                self.pythoncom_init = True

            # 尝试连接的版本列表（按优先级）
            versions = [
                "InDesign.Application.2024",
                "InDesign.Application.2023",
                "InDesign.Application.2022",
                "InDesign.Application.CC",
                "InDesign.Application",
            ]

            for ver in versions:
                try:
                    # 优先使用 Dispatch（更可靠）
                    self.app = win32com.client.Dispatch(ver)
                    self.connected = True
                    actual_version = self.app.Version
                    logger.info(f"已连接到 InDesign {actual_version}")
                    return True, actual_version
                except:
                    continue

            logger.error("未找到运行中的 InDesign")
            return False, None

        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.connected = False
            return False, None

    def disconnect(self):
        """断开连接"""
        if self.pythoncom_init:
            pythoncom.CoUninitialize()
            self.pythoncom_init = False
        self.app = None
        self.connected = False
        logger.info("已断开 InDesign 连接")

    def is_connected(self) -> bool:
        """检查连接状态"""
        if not self.connected or not self.app:
            return False
        try:
            _ = self.app.Version
            return True
        except:
            return False

    def get_active_document(self):
        """获取活动文档"""
        if not self.is_connected():
            return None
        try:
            if self.app.Documents.Count > 0:
                return self.app.ActiveDocument
        except:
            pass
        return None

    def _refresh_cache(self) -> bool:
        """
        刷新文本框缓存
        只在文档变化时调用
        """
        doc = self.get_active_document()
        if not doc:
            return False

        doc_name = doc.Name

        # 如果缓存已存在且文档未变，跳过
        if self._cache_doc_name == doc_name and self._textframe_cache:
            logger.info(f"使用缓存的文本框数据 ({len(self._textframe_cache)} 个)")
            return True

        logger.info("扫描文档中的文本框...")
        self._textframe_cache = []

        try:
            for page in doc.Pages:
                page_name = str(page.Name)

                for tf in page.TextFrames:
                    try:
                        tf_id = tf.ID
                        tf_name = str(tf.Name) if hasattr(tf, "Name") else f"TF_{tf_id}"
                        text = tf.Contents

                        if text:  # 只缓存有内容的文本框
                            try:
                                bounds = (
                                    int(tf.GeometricBounds[0]),
                                    int(tf.GeometricBounds[1]),
                                    int(tf.GeometricBounds[2]),
                                    int(tf.GeometricBounds[3]),
                                )
                            except:
                                bounds = (0, 0, 0, 0)

                            self._textframe_cache.append(
                                {
                                    "id": tf_id,
                                    "name": tf_name,
                                    "text": text,
                                    "page_name": page_name,
                                    "bounds": bounds,
                                }
                            )
                    except Exception as e:
                        logger.debug(f"读取文本框失败: {e}")
                        continue

            self._cache_doc_name = doc_name
            logger.info(f"缓存完成: {len(self._textframe_cache)} 个文本框")
            return True

        except Exception as e:
            logger.error(f"扫描文档失败: {e}")
            return False

    def search_text(
        self, search_text: str, fuzzy_threshold: float = 0.5
    ) -> List[TextMatch]:
        if not self._refresh_cache():
            return []

        matches = self._do_search(search_text, fuzzy_threshold)

        if not matches:
            logger.info("未找到匹配，刷新缓存后重试...")
            self._textframe_cache = []
            self._cache_doc_name = None
            if self._refresh_cache():
                matches = self._do_search(search_text, fuzzy_threshold)

        return matches

    def _do_search(self, search_text: str, fuzzy_threshold: float) -> List[TextMatch]:
        matches = []
        logger.info(f"开始模糊搜索: '{search_text}', 阈值: {fuzzy_threshold}")

        for tf_info in self._textframe_cache:
            text = tf_info["text"]
            similarity = self._fuzzy_match(search_text, text)
            if similarity >= fuzzy_threshold:
                match = TextMatch(
                    text=text,
                    page_name=tf_info["page_name"],
                    text_frame_name=tf_info["name"],
                    text_frame_id=tf_info["id"],
                    bounds=tf_info["bounds"],
                )
                matches.append(match)
                logger.info(
                    f"匹配 (相似度 {similarity:.2f}): {tf_info['name']} -> {text[:50]}..."
                )

        matches.sort(key=lambda m: self._fuzzy_match(search_text, m.text), reverse=True)
        logger.info(f"搜索完成，找到 {len(matches)} 个匹配")
        return matches

    def _get_text_frame_info(self, text_item) -> dict:
        """获取文本所属 TextFrame 的信息"""
        info = {"name": "Unknown", "id": 0, "page_name": "", "bounds": (0, 0, 0, 0)}

        try:
            # 向上遍历找到 TextFrame
            parent = text_item
            max_depth = 10
            while max_depth > 0:
                try:
                    parent = parent.Parent
                    if parent is None:
                        break

                    # 检查是否是 TextFrame
                    if hasattr(parent, "Parent") and "TextFrame" in str(type(parent)):
                        info["name"] = (
                            str(parent.Name) if hasattr(parent, "Name") else "TextFrame"
                        )
                        info["id"] = parent.ID if hasattr(parent, "ID") else 0

                        try:
                            info["bounds"] = (
                                int(parent.GeometricBounds[0]),
                                int(parent.GeometricBounds[1]),
                                int(parent.GeometricBounds[2]),
                                int(parent.GeometricBounds[3]),
                            )
                        except:
                            pass

                        # 获取页面名
                        try:
                            if hasattr(parent, "ParentPage"):
                                info["page_name"] = str(parent.ParentPage.Name)
                        except:
                            pass

                        break
                    max_depth -= 1
                except:
                    break
        except:
            pass

        return info

    def _fuzzy_match(self, source: str, target: str) -> float:
        """
        模糊匹配算法
        优先级：完全匹配 > 包含 > SequenceMatcher 序列相似度
        """
        if not source or not target:
            return 0.0

        source = source.strip()
        target = target.strip()

        # 最短搜索长度
        if len(source) < 3:
            return 0.0

        # 完全匹配
        if source == target:
            return 1.0

        # 包含关系
        if source in target:
            return 0.75 + 0.2 * (len(source) / len(target))

        if target in source:
            return 0.75 + 0.2 * (len(target) / len(source))

        # 长度比惩罚：搜索词比目标长太多时降分
        len_ratio = len(source) / len(target) if len(target) > 0 else 0
        if len_ratio > 3.0 or len_ratio < 0.2:
            return 0.0

        # SequenceMatcher 序列相似度（考虑字符顺序）
        from difflib import SequenceMatcher

        seq_ratio = SequenceMatcher(None, source, target).ratio()

        # 归一化到 0-1
        return seq_ratio

    def find_all_textframes(self) -> List[dict]:
        """获取文档中所有文本框"""
        doc = self.get_active_document()
        if not doc:
            return []

        frames = []
        try:
            for page in doc.Pages:
                for tf in page.TextFrames:
                    try:
                        frames.append(
                            {
                                "name": str(tf.Name)
                                if hasattr(tf, "Name")
                                else f"TF_{tf.ID}",
                                "id": tf.ID,
                                "text": tf.Contents[:100] if tf.Contents else "",
                                "page": str(page.Name),
                            }
                        )
                    except:
                        continue
        except Exception as e:
            logger.error(f"获取文本框失败: {e}")

        return frames

    def replace_text_in_frame(self, text_frame_id: int, new_text: str) -> bool:
        doc = self.get_active_document()
        if not doc:
            return False

        try:
            tf = doc.TextFrames.ItemByID(text_frame_id)
            tf.Contents = new_text
            logger.info(f"已替换文本框 {text_frame_id} 的内容")
            return True
        except Exception as e:
            logger.error(f"替换失败: {e}")
            return False

    def search_text_in_frame(
        self, text_frame_id: int, search_text: str, fuzzy_threshold: float = 0.5
    ) -> List[dict]:
        """
        在指定文本框内搜索精确文本位置

        Args:
            text_frame_id: 文本框 ID
            search_text: 要搜索的文本
            fuzzy_threshold: 模糊匹配阈值

        Returns:
            匹配列表，每项包含 {text, start_index, end_index, paragraph_index}
        """
        doc = self.get_active_document()
        if not doc:
            return []

        try:
            tf = doc.TextFrames.ItemByID(text_frame_id)
            tf_text = str(tf.Contents) if tf.Contents else ""
            if not tf_text:
                return []

            matches = []

            # 先尝试精确包含
            if search_text in tf_text:
                start = tf_text.find(search_text)
                matches.append(
                    {
                        "text": search_text,
                        "start_index": start,
                        "end_index": start + len(search_text),
                        "score": 1.0,
                    }
                )
            else:
                # 按段落搜索
                try:
                    for i, para in enumerate(tf.Paragraphs):
                        para_text = str(para.Contents) if para.Contents else ""
                        similarity = self._fuzzy_match(search_text, para_text)
                        if similarity >= fuzzy_threshold:
                            matches.append(
                                {
                                    "text": para_text.strip(),
                                    "paragraph_index": i,
                                    "score": similarity,
                                }
                            )
                except Exception:
                    pass

                # 全框模糊搜索
                if not matches:
                    similarity = self._fuzzy_match(search_text, tf_text)
                    if similarity >= fuzzy_threshold:
                        matches.append(
                            {
                                "text": tf_text.strip(),
                                "score": similarity,
                            }
                        )

            matches.sort(key=lambda m: m.get("score", 0), reverse=True)
            return matches
        except Exception as e:
            logger.error(f"框内搜索失败: {e}")
            return []

    def replace_text_precise(
        self, text_frame_id: int, search_text: str, new_text: str
    ) -> bool:
        doc = self.get_active_document()
        if not doc:
            return False

        try:
            tf = doc.TextFrames.ItemByID(text_frame_id)

            self.app.FindTextPreferences = ID_NOTHING
            self.app.FindTextPreferences.FindWhat = search_text
            self.app.ChangeTextPreferences = ID_NOTHING
            self.app.ChangeTextPreferences.ChangeTo = new_text

            results = tf.ChangeText()
            count = results.Count if results else 0

            self.app.FindTextPreferences = ID_NOTHING
            self.app.ChangeTextPreferences = ID_NOTHING

            if count > 0:
                logger.info(f"精确替换成功: 文本框 {text_frame_id}, 替换 {count} 处")
                return True
            else:
                logger.warning(
                    f"精确替换失败: 文本框 {text_frame_id} 中未找到 '{search_text[:30]}...'"
                )
                return False
        except Exception as e:
            self.app.FindTextPreferences = ID_NOTHING
            self.app.ChangeTextPreferences = ID_NOTHING
            logger.error(f"精确替换失败: {e}")
            return False

    def locate_text_frame(self, text_frame_id: int) -> bool:
        """
        定位并选中指定文本框

        Args:
            text_frame_id: 文本框 ID

        Returns:
            是否成功
        """
        doc = self.get_active_document()
        if not doc:
            return False

        try:
            tf = doc.TextFrames.ItemByID(text_frame_id)

            # 选中文本框
            tf.Select()
            return True

        except Exception as e:
            logger.error(f"定位失败: {e}")
            return False

    def replace_text_with_grep(self, find_pattern: str, replace_text: str) -> int:
        """
        使用 GREP 模式替换文本

        Args:
            find_pattern: GREP 查找模式
            replace_text: 替换文本 ($0 表示原文本)

        Returns:
            替换的数量
        """
        doc = self.get_active_document()
        if not doc:
            return 0

        try:
            # 清空偏好设置
            self.app.FindGrepPreferences = ID_NOTHING
            self.app.ChangeGrepPreferences = ID_NOTHING

            # 设置 GREP 模式
            self.app.FindGrepPreferences.FindWhat = find_pattern
            self.app.ChangeGrepPreferences.ChangeTo = replace_text

            # 执行替换
            results = doc.ChangeGrep()
            count = results.Count if results else 0

            # 清空偏好设置
            self.app.FindGrepPreferences = ID_NOTHING
            self.app.ChangeGrepPreferences = ID_NOTHING

            logger.info(f"GREP 替换完成，替换了 {count} 处")
            return count

        except Exception as e:
            logger.error(f"GREP 替换失败: {e}")
            return 0

    def get_page_count(self) -> int:
        """获取当前文档页数"""
        doc = self.get_active_document()
        if doc:
            return doc.Pages.Count
        return 0

    def get_document_info(self) -> dict:
        """获取文档信息"""
        doc = self.get_active_document()
        if not doc:
            return {}

        return {
            "name": doc.Name,
            "saved": doc.Saved,
            "page_count": doc.Pages.Count,
            "textframe_count": len(self.find_all_textframes()),
        }


# 单例实例
_indesign_client = None


def get_indesign_client() -> InDesignClient:
    global _indesign_client
    if _indesign_client is None:
        _indesign_client = InDesignClient()
    return _indesign_client


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    client = InDesignClient()

    if client.connect():
        info = client.get_document_info()
        print(f"文档: {info}")

        # 测试查找
        matches = client.search_text("test")
        print(f"搜索 'test': {len(matches)} 个结果")

        client.disconnect()
    else:
        print("连接失败，请确保 InDesign 已启动")
