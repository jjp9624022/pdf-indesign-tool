"""框管理器 — 框列表UI渲染/框选择/框编辑/框删除"""

import customtkinter as ctk


class BoxManager:
    def edit_box_content(self, index):
        if not self.page_canvas or index < 0 or index >= len(self.page_canvas.boxes):
            return

        box = self.page_canvas.boxes[index]

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"编辑区域 {index + 1}")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"坐标: ({box['x1']}, {box['y1']}) - ({box['x2']}, {box['y2']})",
        ).pack(pady=5)

        textbox = ctk.CTkTextbox(dialog, height=300)
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        textbox.insert("1.0", box.get("text", ""))

        def save():
            box["text"] = textbox.get("1.0", "end-1c")
            box["processed"] = True
            self._update_box_list()
            dialog.destroy()

        ctk.CTkButton(dialog, text="💾 保存", command=save, width=100).pack(pady=10)

    def delete_box(self, index):
        if self.page_canvas:
            self.page_canvas.delete_box(index)
            self._save_current_page_boxes()
            self._update_box_list()
            self.textbox.delete("1.0", "end")
            self.indesign_matches = []
            self._show_search_results()

    def clear_all_boxes(self):
        if self.page_canvas:
            self.page_canvas.clear_all_boxes()
            self.all_boxes.clear()
            self._update_box_list()

    def _select_box_by_index(self, page_index, box_index):
        if page_index != self.current_page:
            self._save_current_page_boxes()
            self.current_page = page_index
            self._load_page()

        if self.page_canvas and 0 <= box_index < len(self.page_canvas.boxes):
            box = self.page_canvas.boxes[box_index]
            self.page_canvas._select_box(box)
            self._update_box_list()
            text = box.get("text", "")
            display_text = text.replace("\r", "\n")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", display_text)

            if (
                self.indesign_connected
                and text
                and not text.startswith("识别")
                and not text.startswith("待识别")
            ):
                try:
                    matches = self.indesign_client.search_text(
                        text, fuzzy_threshold=self.similarity_var.get()
                    )
                    if matches:
                        self.search_matches = matches
                        self.selected_match_index = 0
                        self._show_search_results()
                        self.indesign_client.locate_text_frame(matches[0].text_frame_id)
                        self._update_status(
                            f"ID 匹配: {len(matches)} 项 - {matches[0].text_frame_name}"
                        )
                    else:
                        self.search_matches = []
                        self.selected_match_index = None
                        self._show_search_results()
                        self._update_status("ID 无匹配")
                except Exception as e:
                    self._update_status(f"ID 搜索异常: {e}")

    def _on_edit_box(self):
        if self.page_canvas and self.page_canvas.selected_box:
            idx = self.page_canvas.boxes.index(self.page_canvas.selected_box)
            self.edit_box_content(idx)

    def _on_clear_boxes(self):
        if self.current_page is not None:
            self.all_boxes[self.current_page] = []
        self._update_box_list()
        self.textbox.delete("1.0", "end")
        self.indesign_matches = []
        self._show_search_results()

    def _on_box_deleted(self):
        self._save_current_page_boxes()
        self._update_box_list()
        self.textbox.delete("1.0", "end")
        self.indesign_matches = []
        self._show_search_results()

    def _on_box_added(self, box_index, auto_ocr=True):
        if (
            box_index < 0
            or not self.page_canvas
            or box_index >= len(self.page_canvas.boxes)
        ):
            return

        box = self.page_canvas.boxes[box_index]

        if auto_ocr:
            box["text"] = "识别中..."
            self._save_current_page_boxes()
            self._update_box_list()
            self._do_box_ocr(self.current_page, box_index)
        else:
            box["text"] = "待识别"
            box["processed"] = False
            self._save_current_page_boxes()
            self._update_box_list()

    def _update_box_list(self):
        if not hasattr(self, "box_list_frame"):
            return

        for widget in self.box_list_frame.winfo_children():
            widget.destroy()

        if not self.all_boxes:
            ctk.CTkLabel(
                self.box_list_frame, text="(暂无框)", text_color="gray50"
            ).pack(pady=10)
            return

        for page_idx, boxes in sorted(self.all_boxes.items()):
            for box_idx, box in enumerate(boxes):
                self._add_box_list_item(page_idx, box_idx, box)

    def _get_box_list_flat_index(self, page_index, box_index):
        idx = 0
        for p, boxes in sorted(self.all_boxes.items()):
            if p == page_index:
                return idx + box_index
            idx += len(boxes)
        return -1

    def _update_single_box_item(self, page_index, box_index):
        if not hasattr(self, "box_list_frame"):
            return
        flat_idx = self._get_box_list_flat_index(page_index, box_index)
        if flat_idx < 0:
            return
        children = self.box_list_frame.winfo_children()
        if flat_idx < len(children):
            children[flat_idx].destroy()
            box = self.all_boxes[page_index][box_index]
            self._add_box_list_item(page_index, box_index, box)

    def _add_box_list_item(self, page_index, box_index, box):
        is_current_page = page_index == self.current_page
        is_selected = False
        if is_current_page and self.page_canvas:
            is_selected = self.page_canvas.selected_box == box

        is_processed = box.get("processed", False)
        is_applied = box.get("applied_to_indesign", False)
        text = box.get("text", "")
        is_recognizing = text == "识别中..."
        is_failed = text.startswith("识别失败")

        if not is_current_page:
            bg_color = ("gray25", "gray18")
        elif is_applied:
            bg_color = ("gray35", "gray25")
        elif is_selected:
            bg_color = ("#3B8ED0", "#1F6AA5")
        else:
            bg_color = ("gray20", "gray15")

        item_frame = ctk.CTkFrame(
            self.box_list_frame, corner_radius=6, fg_color=bg_color
        )
        item_frame.pack(fill="x", padx=3, pady=2)

        item_frame.grid_columnconfigure(1, weight=1)

        page_img = self.page_images.get(page_index)
        thumb_image = None
        if page_img:
            x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
            region = page_img.crop((x1, y1, x2, y2))
            thumb = region.copy()
            thumb.thumbnail((50, 50))
            thumb_image = ctk.CTkImage(thumb, size=(thumb.width, thumb.height))

        if thumb_image:
            thumb_label = ctk.CTkLabel(
                item_frame, image=thumb_image, text="", width=55, height=55
            )
            thumb_label.grid(row=0, column=0, padx=5, pady=5)
        else:
            size_label = ctk.CTkLabel(
                item_frame,
                text=f"P{page_index + 1}#{box_index + 1}",
                width=55,
                font=ctk.CTkFont(size=10),
            )
            size_label.grid(row=0, column=0, padx=5, pady=5)

        ocr_source = box.get("ocr_source", "")
        ocr_model = box.get("ocr_model", "")

        if is_applied:
            status_icon = "✓✓"
            status_color = "#8B5CF6"
        elif is_failed:
            status_icon = "❌"
            status_color = "red"
        elif is_recognizing:
            status_icon = "⟳"
            status_color = "orange"
        elif is_processed:
            status_icon = "✓"
            status_color = "#4ECDC4"
        else:
            status_icon = "○"
            status_color = "gray50"

        page_tag = f"[P{page_index + 1}]" if not is_current_page else ""
        status_label = ctk.CTkLabel(
            item_frame,
            text=f"{page_tag}#{box_index + 1} {status_icon}",
            anchor="w",
            text_color=status_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        status_label.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="ew")

        if ocr_source == "rapidocr":
            model_tag = "[RapidOCR]"
            model_color = "gray50"
        elif ocr_source == "llm" and ocr_model:
            short = ocr_model.split("/")[-1] if "/" in ocr_model else ocr_model
            if len(short) > 15:
                short = short[:13] + ".."
            model_tag = f"[{short}]"
            model_color = "#8B5CF6" if is_applied else "#4ECDC4"
        elif is_processed:
            model_tag = "[LLM]"
            model_color = "#4ECDC4"
        else:
            model_tag = ""
            model_color = "gray50"

        if model_tag:
            model_label = ctk.CTkLabel(
                item_frame,
                text=model_tag,
                anchor="w",
                text_color=model_color,
                font=ctk.CTkFont(size=8),
            )
            model_label.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="w")

        if is_failed:
            preview_text = text[:25]
        elif is_recognizing:
            preview_text = text
        elif is_applied:
            preview_text = "✓ " + (text[:23] or "(未识别)")
        else:
            preview_text = text[:25] or "(未识别)"

        if len(text) > 25 and not is_recognizing and not is_applied:
            preview_text += "..."

        if is_recognizing:
            text_color = "orange"
        elif is_failed:
            text_color = "red"
        elif is_applied:
            text_color = "gray50"
        elif is_processed:
            text_color = "gray80"
        else:
            text_color = "gray50"

        text_label = ctk.CTkLabel(
            item_frame,
            text=preview_text,
            anchor="w",
            justify="left",
            text_color=text_color,
            font=ctk.CTkFont(size=9),
        )
        text_label.grid(row=1, column=1, padx=5, pady=(0, 5), sticky="ew")

        retry_color = ("#2D8C4E", "#1E6B3A") if is_processed else ("gray40", "gray30")

        retry_btn = ctk.CTkButton(
            item_frame,
            text="🔄",
            width=35,
            height=35,
            command=lambda p=page_index, b=box_index: self._retry_single_box(p, b),
            fg_color=retry_color,
            hover_color=("#3DA861", "#2D8C4E"),
        )
        retry_btn.grid(row=0, column=2, rowspan=2, padx=(0, 5), pady=5, sticky="ns")

        def on_click(e, p=page_index, b=box_index):
            self._select_box_by_index(p, b)

        item_frame.bind("<Button-1>", on_click)
        text_label.bind("<Button-1>", on_click)
        status_label.bind("<Button-1>", on_click)
        for child in item_frame.winfo_children():
            child.bind("<Button-1>", on_click)
