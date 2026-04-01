from collections import deque


class TextEditorMixin:
    """
    文本编辑混入类 — 为两个模块的 textbox 提供统一的
    编辑保存 + 撤销/重做功能
    """

    UNDO_MAX = 50

    def _init_text_editor(self):
        self._edit_undo_stack = deque(maxlen=self.UNDO_MAX)
        self._edit_redo_stack = deque(maxlen=self.UNDO_MAX)
        self._edit_original = None

    def _capture_text_state(self):
        """保存当前文本状态到 undo 栈"""
        current = self.textbox.get("1.0", "end-1c")
        if current != self._edit_original:
            self._edit_undo_stack.append(self._edit_original)
            self._edit_redo_stack.clear()
            self._edit_original = current

    def _undo_edit(self):
        if not self._edit_undo_stack:
            return
        current = self.textbox.get("1.0", "end-1c")
        self._edit_redo_stack.append(current)
        prev = self._edit_undo_stack.pop()
        self._edit_original = prev
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", prev or "")
        self._save_edited_text()

    def _redo_edit(self):
        if not self._edit_redo_stack:
            return
        current = self.textbox.get("1.0", "end-1c")
        self._edit_undo_stack.append(current)
        nxt = self._edit_redo_stack.pop()
        self._edit_original = nxt
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", nxt or "")
        self._save_edited_text()

    def _on_textbox_focus_in(self, event=None):
        """获取焦点时捕获当前状态"""
        self._edit_original = self.textbox.get("1.0", "end-1c")
        self._edit_undo_stack.clear()
        self._edit_redo_stack.clear()
