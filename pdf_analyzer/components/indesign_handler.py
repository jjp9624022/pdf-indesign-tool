"""InDesign 处理器 — 搜索/替换/索引"""

import customtkinter as ctk
from tkinter import messagebox

try:
    from indesign_client import InDesignClient, TextMatch

    INDESIGN_AVAILABLE = True
except ImportError:
    INDESIGN_AVAILABLE = False


class InDesignHandler:
    def connect_indesign(self):
        if not INDESIGN_AVAILABLE:
            messagebox.showerror("错误", "InDesign 客户端不可用")
            return

        try:
            success, version = self.indesign_client.connect()
            if success:
                self.indesign_connected = True
                page_count = self.indesign_client.get_active_document().Pages.Count
                messagebox.showinfo(
                    "成功", f"已连接到 InDesign {version} ({page_count} 页)"
                )
            else:
                messagebox.showerror(
                    "错误", "无法连接到 InDesign，请确保 InDesign 已启动"
                )
        except Exception as e:
            self._update_status(f"连接 InDesign 失败: {e}")

    def search_in_indesign(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        search_text = self.textbox.get("1.0", "end-1c").strip()
        if not search_text:
            if self.page_canvas and self.page_canvas.selected_box:
                search_text = self.page_canvas.selected_box.get("text", "")

        if not search_text:
            messagebox.showwarning("提示", "请先选中一个有文本的框或输入搜索文本")
            return

        self.btn_search_id.configure(state="disabled", text="搜索中...")
        self.update()

        matches = self.indesign_client.search_text(search_text, fuzzy_threshold=0.5)

        self.btn_search_id.configure(state="normal", text="🔍 ID搜索")

        self.search_matches = matches
        self._show_search_results()

        if matches:
            self._select_match(0)
            self._update_status(f"找到 {len(matches)} 个匹配项")
        else:
            self._update_status("未找到匹配项")

    def _show_search_results(self):
        for widget in self.search_result_frame.winfo_children():
            widget.destroy()

        if not self.search_matches:
            self.search_hint = ctk.CTkLabel(
                self.search_result_frame,
                text="无匹配项",
                text_color="gray50",
                font=ctk.CTkFont(size=10),
            )
            self.search_hint.pack(pady=10)
            return

        for i, match in enumerate(self.search_matches):
            text_preview = match.text[:40].replace("\n", " ") + "..."
            btn = ctk.CTkButton(
                self.search_result_frame,
                text=f"{match.text_frame_name}: {text_preview}",
                command=lambda idx=i: self._select_match(idx),
                height=28,
                fg_color=("gray20", "gray15"),
                hover_color=("gray30", "gray25"),
                anchor="w",
            )
            btn.pack(fill="x", padx=5, pady=2)
            btn.match_index = i

    def _select_match(self, index):
        self.selected_match_index = index
        match = self.search_matches[index]

        for widget in self.search_result_frame.winfo_children():
            if hasattr(widget, "match_index") and widget.match_index == index:
                widget.configure(fg_color=("#3B8ED0", "#1F6AA5"))
            elif hasattr(widget, "match_index"):
                widget.configure(fg_color=("gray20", "gray15"))

        self.indesign_client.locate_text_frame(match.text_frame_id)

    def replace_in_indesign(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        if self.selected_match_index is None:
            self._update_status("⚠️ 请先选择搜索结果")
            return

        match = self.search_matches[self.selected_match_index]
        new_text = self.textbox.get("1.0", "end-1c")
        mode = self.replace_mode_var.get()

        if mode == "precise":
            ok = self.indesign_client.replace_text_precise(
                match.text_frame_id, match.text, new_text
            )
        else:
            ok = self.indesign_client.replace_text_in_frame(
                match.text_frame_id, new_text
            )

        if ok:
            self._update_status(f"✓ 已替换: {match.text_frame_name}")
            self._mark_box_applied()
            self.search_in_indesign()
        else:
            self._update_status("✗ 替换失败")

    def search_and_replace(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        new_text = self.textbox.get("1.0", "end-1c").strip()
        if not new_text:
            self._update_status("⚠️ 请先编辑要替换的文本")
            return

        search_text = new_text

        self.btn_search_replace.configure(state="disabled", text="查找并替换中...")
        self.update()

        matches = self.indesign_client.search_text(
            search_text, fuzzy_threshold=self.similarity_var.get()
        )

        if not matches:
            self.btn_search_replace.configure(state="normal", text="🔍➜✓ 查找并替换")
            self._update_status(
                f"⚠️ 未找到高相似度匹配项 (≥{self.similarity_var.get():.0%})"
            )
            return

        match = matches[0]
        mode = self.replace_mode_var.get()
        if mode == "precise":
            ok = self.indesign_client.replace_text_precise(
                match.text_frame_id, match.text, new_text
            )
        else:
            ok = self.indesign_client.replace_text_in_frame(
                match.text_frame_id, new_text
            )
        if ok:
            self._update_status(f"✓ 已查找并替换: {match.text_frame_name}")
            self._mark_box_applied()
        else:
            self._update_status("✗ 替换失败")

        self.btn_search_replace.configure(state="normal", text="🔍➜✓ 查找并替换")

    def replace_and_find_next(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        new_text = self.textbox.get("1.0", "end-1c").strip()
        if not new_text:
            self._update_status("⚠️ 请先编辑要替换的文本")
            return

        if self.selected_match_index is None:
            self.selected_match_index = 0

        if self.selected_match_index >= len(self.search_matches):
            self._update_status("已是最后一项")
            return

        match = self.search_matches[self.selected_match_index]
        mode = self.replace_mode_var.get()
        if mode == "precise":
            ok = self.indesign_client.replace_text_precise(
                match.text_frame_id, match.text, new_text
            )
        else:
            ok = self.indesign_client.replace_text_in_frame(
                match.text_frame_id, new_text
            )
        if ok:
            self._mark_box_applied()

            for widget in self.search_result_frame.winfo_children():
                if (
                    hasattr(widget, "match_index")
                    and widget.match_index == self.selected_match_index
                ):
                    widget.configure(
                        fg_color=("#2D8C4E", "#1E6B3A"),
                        text=f"✓ {widget.cget('text')}",
                    )
                    break

            self.selected_match_index += 1

            if self.selected_match_index < len(self.search_matches):
                self._select_match(self.selected_match_index)
                self._update_status(
                    f"✓ 已替换，移动到下一项 ({self.selected_match_index}/{len(self.search_matches)})"
                )
            else:
                self._update_status("✓ 已替换 (已是最后一项)")
        else:
            self._update_status("✗ 替换失败")

    def _mark_box_applied(self):
        if self.page_canvas and self.page_canvas.selected_box:
            idx = self.page_canvas.boxes.index(self.page_canvas.selected_box)
            self.page_canvas.mark_applied(idx)
            self._save_current_page_boxes()
            self._update_single_box_item(self.current_page, idx)

    def rebuild_index(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        self.btn_reindex.configure(state="disabled", text="索引中...")
        self.update()

        success = self.indesign_client._refresh_cache()

        self.btn_reindex.configure(state="normal", text="🔄 索引")

        if success:
            count = len(self.indesign_client._textframe_cache)
            self._update_status(f"✓ 索引完成: {count} 个文本框")
        else:
            self._update_status("✗ 索引失败")

    def _update_status(self, message):
        if hasattr(self, "status_bar"):
            self.status_bar.configure(text=message)

    def batch_replace_indesign(self):
        if not self.indesign_connected:
            self.connect_indesign()
            if not self.indesign_connected:
                return

        if not self.page_canvas or not self.page_canvas.boxes:
            messagebox.showwarning("提示", "当前没有框")
            return

        processed_boxes = [
            b for b in self.page_canvas.boxes if b.get("processed") and b.get("text")
        ]
        if not processed_boxes:
            messagebox.showwarning("提示", "没有已识别的框")
            return

        if not messagebox.askyesno(
            "确认", f"将替换 InDesign 中 {len(processed_boxes)} 个匹配项，继续？"
        ):
            return

        success_count = 0
        for box in processed_boxes:
            search_text = box.get("text", "")
            if not search_text:
                continue

            matches = self.indesign_client.search_text(
                search_text, fuzzy_threshold=self.similarity_var.get()
            )
            for match in matches:
                if self.indesign_client.replace_text_in_frame(
                    match.text_frame_id, search_text
                ):
                    success_count += 1

        messagebox.showinfo("完成", f"已替换 {success_count} 个匹配项")
