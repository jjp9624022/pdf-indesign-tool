"""PDF 控制器 — 负责 PDF 打开/翻页/缩放/框数据持久化"""

import fitz
from PIL import Image
from tkinter import messagebox

from ..constants import BOX_COLORS
from ..canvas_page import PDFPageCanvas


class PDFController:
    def open_pdf(self):
        from tkinter import filedialog

        filepath = filedialog.askopenfilename(
            title="选择 PDF 文件", filetypes=[("PDF 文件", "*.pdf")]
        )
        if not filepath:
            return

        try:
            self.current_pdf = fitz.open(filepath)
            self.total_pages = len(self.current_pdf)
            self.current_page = 0
            self.page_images.clear()
            self._load_page()
            messagebox.showinfo("成功", f"已打开 PDF，共 {self.total_pages} 页")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开 PDF: {e}")

    def _load_page(self):
        if not self.current_pdf:
            return

        page = self.current_pdf[self.current_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        self.page_images[self.current_page] = img
        self.page_label.configure(
            text=f"第 {self.current_page + 1} / {self.total_pages} 页"
        )
        self._show_page(img)

    def _show_page(self, img):
        self.pdf_canvas.delete("all")
        self.hint_label.pack_forget()

        self.pdf_frame.update_idletasks()
        w = self.pdf_canvas.winfo_width() or 800
        h = self.pdf_canvas.winfo_height() or 600

        initial_scale = min(w / img.width, h / img.height, 1.0)

        self.page_canvas = PDFPageCanvas(
            self.pdf_canvas, img, img.width, img.height, initial_scale=initial_scale
        )
        self.page_canvas.on_scale_change = self._on_scale_change
        self.page_canvas.on_clear = self._on_clear_boxes
        self.page_canvas.on_box_added = self._on_box_added
        self.page_canvas.on_box_deleted = self._on_box_deleted

        self.page_canvas.set_tool_mode(self.tool_var.get())

        self._load_page_boxes()

        self.zoom_label.configure(text=f"{int(initial_scale * 100)}%")
        self.pdf_canvas.bind("<<EditBox>>", lambda e: self._on_edit_box())

        self._update_box_list()
        self._redraw_boxes()

    def _load_page_boxes(self):
        if self.page_canvas and self.current_page in self.all_boxes:
            saved_boxes = self.all_boxes[self.current_page]
            for box_data in saved_boxes:
                box = {
                    "x1": box_data["x1"],
                    "y1": box_data["y1"],
                    "x2": box_data["x2"],
                    "y2": box_data["y2"],
                    "text": box_data.get("text", ""),
                    "processed": box_data.get("processed", False),
                }
                rect_id = self.pdf_canvas.create_rectangle(
                    box["x1"] * self.page_canvas.scale,
                    box["y1"] * self.page_canvas.scale,
                    box["x2"] * self.page_canvas.scale,
                    box["y2"] * self.page_canvas.scale,
                    outline="#FF6B6B",
                    width=2,
                )
                box["canvas_id"] = rect_id
                self.page_canvas.boxes.append(box)

    def _on_scale_change(self, scale):
        self.zoom_label.configure(text=f"{int(scale * 100)}%")

    def prev_page(self):
        if self.current_page > 0:
            self._save_current_page_boxes()
            self.current_page -= 1
            self._load_page()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self._save_current_page_boxes()
            self.current_page += 1
            self._load_page()

    def _on_page_jump(self, event=None):
        if not self.current_pdf:
            return
        try:
            val = self.page_entry.get().strip()
            if not val:
                self._update_page_label()
                return
            page_num = int(val)
            if 1 <= page_num <= self.total_pages:
                self._save_current_page_boxes()
                self.current_page = page_num - 1
                self._load_page()
            else:
                self._update_page_label()
        except ValueError:
            self._update_page_label()

    def _update_page_label(self):
        if hasattr(self, "page_label"):
            self.page_label.configure(
                text=f"第 {self.current_page + 1} / {self.total_pages} 页"
            )
        if hasattr(self, "page_entry"):
            self.page_entry.delete(0, "end")
            if self.total_pages > 0:
                self.page_entry.insert(0, str(self.current_page + 1))

    def _save_current_page_boxes(self):
        if self.page_canvas and self.current_page is not None:
            self.all_boxes[self.current_page] = [
                {k: v for k, v in box.items() if k != "canvas_id" and k != "id"}
                for box in self.page_canvas.boxes
            ]

    def refresh_canvas(self):
        if self.current_page in self.page_images:
            self._show_page(self.page_images[self.current_page])

    def _set_tool_mode(self, mode):
        self.tool_var.set(mode)
        if self.page_canvas:
            self.page_canvas.set_tool_mode(mode)

        if mode == "select":
            self.btn_select.configure(fg_color=("#3B8ED0", "#1F6AA5"))
            self.btn_draw.configure(fg_color=("gray30", "gray20"))
        else:
            self.btn_select.configure(fg_color=("gray30", "gray20"))
            self.btn_draw.configure(fg_color=("#3B8ED0", "#1F6AA5"))

    def _zoom_in(self):
        if self.page_canvas:
            self.page_canvas.zoom_in()

    def _zoom_out(self):
        if self.page_canvas:
            self.page_canvas.zoom_out()

    def _fit_window(self):
        if self.page_canvas:
            self.page_canvas.fit_to_window()

    def _redraw_boxes(self):
        if not self.page_canvas:
            return
        for box in self.page_canvas.boxes:
            x1, y1 = box["x1"], box["y1"]
            x2, y2 = box["x2"], box["y2"]
            vx1, vy1 = self.page_canvas.to_view_coords(x1, y1)
            vx2, vy2 = self.page_canvas.to_view_coords(x2, y2)
            color = (
                BOX_COLORS["processed"]
                if box.get("processed")
                else BOX_COLORS["normal"]
            )
            rect_id = self.pdf_canvas.create_rectangle(
                vx1, vy1, vx2, vy2, outline=color, width=2
            )
            box["id"] = rect_id
            box["canvas_id"] = rect_id

    def save_boxes(self):
        from tkinter import filedialog
        import json

        if not self.page_canvas:
            return

        filepath = filedialog.asksaveasfilename(
            title="保存框数据",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
        )
        if not filepath:
            return

        data = {
            "pdf_path": self.current_pdf.name if self.current_pdf else "",
            "page": self.current_page,
            "boxes": self.page_canvas.boxes,
        }

        for box in data["boxes"]:
            box_copy = box.copy()
            box_copy.pop("id", None)
            box_copy.pop("canvas_id", None)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        messagebox.showinfo("成功", f"已保存到 {filepath}")

    def load_boxes(self):
        from tkinter import filedialog
        import json
        import os

        filepath = filedialog.askopenfilename(
            title="加载框数据", filetypes=[("JSON 文件", "*.json")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            pdf_path = data.get("pdf_path", "")
            if pdf_path and os.path.exists(pdf_path) and not self.current_pdf:
                self.current_pdf = fitz.open(pdf_path)
                self.total_pages = len(self.current_pdf)
                self.current_page = data.get("page", 0)
                self.page_images.clear()
                self._load_page()
            elif not self.current_pdf:
                from tkinter import messagebox

                messagebox.showwarning("提示", f"PDF 文件不存在: {pdf_path}")
                return

            boxes = data.get("boxes", [])
            if self.page_canvas:
                self.page_canvas.clear_all_boxes()
                self.page_canvas.boxes = boxes

                for box in boxes:
                    vx1, vy1 = self.page_canvas.to_view_coords(box["x1"], box["y1"])
                    vx2, vy2 = self.page_canvas.to_view_coords(box["x2"], box["y2"])
                    rect_id = self.pdf_canvas.create_rectangle(
                        vx1,
                        vy1,
                        vx2,
                        vy2,
                        outline=BOX_COLORS["processed"]
                        if box.get("processed")
                        else BOX_COLORS["normal"],
                        width=2,
                    )
                    box["id"] = rect_id
                    box["canvas_id"] = rect_id

                self._update_box_list()
                messagebox.showinfo("成功", f"已加载 {len(boxes)} 个框")

        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {e}")
