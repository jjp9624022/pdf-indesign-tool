"""OCR 处理器 — 自动检测/区域合并/批量OCR/单框OCR"""

import threading
import logging
import os
import tempfile

import fitz
from PIL import Image
from tkinter import messagebox

from ..constants import BOX_COLORS

logger = logging.getLogger(__name__)


class OCRHandler:
    def auto_detect(self):
        if not self.current_pdf:
            messagebox.showwarning("提示", "请先打开 PDF 文件")
            return

        pages_to_process = [self.current_page + 1]
        if messagebox.askyesno("批量选区", "是否处理所有页面？（否则只处理当前页）"):
            pages_to_process = list(range(1, self.total_pages + 1))

        self.auto_detect_btn.configure(state="disabled", text="分析中...")
        self.update()

        try:
            h_gap = int(self.h_gap_var.get())
            v_gap = int(self.v_gap_var.get())
        except ValueError:
            h_gap, v_gap = 50, 30

        def do_detect():
            try:
                from rapidocr_onnxruntime import RapidOCR

                ocr_engine = RapidOCR()
                all_regions = []

                for page_num in pages_to_process:
                    page_idx = page_num - 1
                    page_img = self.page_images.get(page_idx)

                    if not page_img:
                        page = self.current_pdf[page_idx]
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        page_img = Image.frombytes(
                            "RGB", [pix.width, pix.height], pix.samples
                        )
                        self.page_images[page_idx] = page_img

                    temp_path = os.path.join(
                        tempfile.gettempdir(), f"pdf_detect_p{page_num}.png"
                    )
                    page_img.save(temp_path)

                    result, _ = ocr_engine(temp_path)

                    if result:
                        for item in result:
                            box = item[0]
                            text = item[1]
                            score = item[2]
                            xs = [p[0] for p in box]
                            ys = [p[1] for p in box]

                            all_regions.append(
                                {
                                    "page": page_num,
                                    "x1": int(min(xs)),
                                    "y1": int(min(ys)),
                                    "x2": int(max(xs)),
                                    "y2": int(max(ys)),
                                    "content": text.replace("\n", "\r"),
                                    "score": float(score),
                                    "type": "text",
                                }
                            )

                merged = self._merge_regions(all_regions, h_gap=h_gap, v_gap=v_gap)
                raw_count = len(all_regions)

                def update_ui():
                    if self.page_canvas:
                        self.page_canvas.clear_all_boxes()

                    current_regions = [
                        r for r in merged if r["page"] == self.current_page + 1
                    ]

                    for region in current_regions:
                        x1, y1 = region.get("x1", 0), region.get("y1", 0)
                        x2, y2 = region.get("x2", 0), region.get("y2", 0)

                        if x2 > x1 and y2 > y1:
                            box = {
                                "x1": x1,
                                "y1": y1,
                                "x2": x2,
                                "y2": y2,
                                "text": region.get("content", ""),
                                "processed": True,
                                "ocr_source": "rapidocr",
                                "type": region.get("type", "text"),
                            }
                            if self.page_canvas:
                                self.page_canvas.boxes.append(box)
                                vx1, vy1 = self.page_canvas.to_view_coords(x1, y1)
                                vx2, vy2 = self.page_canvas.to_view_coords(x2, y2)
                                rect_id = self.pdf_canvas.create_rectangle(
                                    vx1,
                                    vy1,
                                    vx2,
                                    vy2,
                                    outline=BOX_COLORS["processed"],
                                    width=2,
                                )
                                box["id"] = rect_id
                                box["canvas_id"] = rect_id

                    self._save_current_page_boxes()
                    self._update_box_list()
                    self.all_detected_regions = merged
                    self.raw_region_count = raw_count

                    if merged:
                        messagebox.showinfo(
                            "完成",
                            f"原始: {raw_count} 个区域\n合并后: {len(merged)} 个区域",
                        )
                    else:
                        messagebox.showinfo("提示", "未检测到文字区域")

                self.after(0, update_ui)

            except Exception as e:
                logging.error(f"版面检测失败: {e}")
                self.after(
                    0, lambda: messagebox.showerror("错误", f"版面检测失败: {e}")
                )
            finally:
                self.after(
                    0,
                    lambda: self.auto_detect_btn.configure(
                        state="normal", text="🔍 自动检测文字"
                    ),
                )

        threading.Thread(target=do_detect, daemon=True).start()

    def _merge_regions(self, regions, h_gap=50, v_gap=30):
        if not regions:
            return regions

        result = []
        for page in set(r["page"] for r in regions):
            page_regs = sorted(
                [r for r in regions if r["page"] == page],
                key=lambda r: (r["y1"], r["x1"]),
            )

            changed = True
            while changed:
                changed = False
                i = 0
                while i < len(page_regs):
                    j = i + 1
                    merged_this_i = False
                    while j < len(page_regs):
                        r1, r2 = page_regs[i], page_regs[j]

                        y_overlap = max(
                            0, min(r1["y2"], r2["y2"]) - max(r1["y1"], r2["y1"])
                        )
                        x_overlap = max(
                            0, min(r1["x2"], r2["x2"]) - max(r1["x1"], r2["x1"])
                        )

                        merged = False

                        if y_overlap > 0:
                            gap = r2["x1"] - r1["x2"]
                            if gap > 0 and gap <= h_gap:
                                page_regs[i] = {
                                    "page": r1["page"],
                                    "x1": r1["x1"],
                                    "y1": min(r1["y1"], r2["y1"]),
                                    "x2": r2["x2"],
                                    "y2": max(r1["y2"], r2["y2"]),
                                    "content": r1["content"] + r2["content"],
                                    "score": (r1["score"] + r2["score"]) / 2,
                                    "type": r1.get("type", "text"),
                                }
                                page_regs.pop(j)
                                merged = True
                                changed = True
                                merged_this_i = True
                                continue

                        if x_overlap > 0 or (
                            abs(r1["x1"] - r2["x1"]) < h_gap
                            and abs(r1["x2"] - r2["x2"]) < h_gap
                        ):
                            gap = r2["y1"] - r1["y2"]
                            if gap > 0 and gap <= v_gap:
                                page_regs[i] = {
                                    "page": r1["page"],
                                    "x1": min(r1["x1"], r2["x1"]),
                                    "y1": r1["y1"],
                                    "x2": max(r1["x2"], r2["x2"]),
                                    "y2": r2["y2"],
                                    "content": r1["content"] + "\r" + r2["content"],
                                    "score": (r1["score"] + r2["score"]) / 2,
                                    "type": r1.get("type", "text"),
                                }
                                page_regs.pop(j)
                                merged = True
                                changed = True
                                merged_this_i = True
                                continue

                        j += 1

                    if merged_this_i:
                        continue
                    i += 1

            result.extend(page_regs)

        return result

    def batch_ocr(self):
        boxes = [b for b in self.page_canvas.boxes if b.get("ocr_source") != "llm"]
        if not boxes:
            messagebox.showinfo("提示", "所有框都已通过大模型识别完成")
            return
        self._process_ocr_async(boxes)

    def _process_ocr_async(self, boxes):
        import ocr_client

        selected_model = self.model_var.get()
        provider = self.config.get_provider_by_model_id(selected_model)

        kwargs = {}
        if provider:
            if provider.api_key:
                kwargs["api_key"] = provider.api_key
            if provider.base_url:
                kwargs["base_url"] = provider.base_url

        selected_prompt_key = self.prompt_var.get()
        selected_prompt = self.prompt_mgr.get(
            selected_prompt_key, self.prompt_mgr.get("原文识别", "")
        )
        page_img = self.page_images.get(self.current_page)
        total = len(boxes)

        logger.info(
            f"[OCR] 开始识别: provider={provider}, model={selected_model}, prompt={selected_prompt_key}, 共 {total} 个框"
        )

        def do_ocr():
            try:
                ocr = ocr_client.OCRClient(
                    provider=provider, model=selected_model, **kwargs
                )
                logger.info(f"[OCR] 初始化 OCR 客户端成功")

                for i, box in enumerate(boxes):
                    if not page_img:
                        logger.warning(f"[OCR] 框 {i + 1}: 无页面图片")
                        continue

                    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
                    region = page_img.crop((x1, y1, x2, y2))

                    logger.info(
                        f"[OCR] 正在识别框 {i + 1}/{total}: ({x1},{y1})-({x2},{y2})"
                    )

                    try:
                        result = ocr.analyze_with_prompt(region, selected_prompt)
                        if result:
                            result_preview = (
                                result[:50] + "..." if len(result) > 50 else result
                            )
                        else:
                            result_preview = "(空)"
                        logger.info(f"[OCR] 框 {i + 1} 识别完成: {result_preview}")
                        self.after(
                            0,
                            lambda idx=self.page_canvas.boxes.index(box),
                            res=result: self.page_canvas.mark_processed(idx, res),
                        )
                    except Exception as e:
                        logger.error(f"[OCR] 框 {i + 1} 识别失败: {e}")
                        self.after(
                            0,
                            lambda idx=self.page_canvas.boxes.index(box),
                            err=str(e): self.page_canvas.mark_processed(
                                idx, f"识别失败: {err}"
                            ),
                        )

                    self.after(
                        0,
                        lambda p=i + 1, t=total: self.batch_ocr_btn.configure(
                            text=f"识别中 {p}/{t}..."
                        )
                        if hasattr(self, "batch_ocr_btn")
                        else None,
                    )

                def done():
                    self._update_box_list()
                    messagebox.showinfo(
                        "完成", f"【{selected_prompt_key}】完成，共 {total} 个框"
                    )
                    self.batch_ocr_btn.configure(state="normal", text="📝 批量识别")

                self.after(0, done)
                logger.info(f"[OCR] 批量识别完成: 共 {total} 个框")

            except Exception as e:
                logger.error(f"[OCR] 初始化失败: {e}")
                self.after(
                    0, lambda: messagebox.showerror("错误", f"OCR 初始化失败: {e}")
                )
                self.after(
                    0,
                    lambda: self.batch_ocr_btn.configure(
                        state="normal", text="📝 批量识别"
                    ),
                )

        self.batch_ocr_btn.configure(state="disabled", text=f"识别中 0/{total}...")
        threading.Thread(target=do_ocr, daemon=True).start()

    def _do_box_ocr(self, page_index, box_index):
        if (
            not self.page_canvas
            or box_index < 0
            or box_index >= len(self.page_canvas.boxes)
        ):
            return

        box = self.page_canvas.boxes[box_index]
        page_img = self.page_images.get(page_index)

        import ocr_client

        selected_model = self.model_var.get()
        provider = self.config.get_provider_by_model_id(selected_model)

        kwargs = {}
        if provider:
            if provider.api_key:
                kwargs["api_key"] = provider.api_key
            if provider.base_url:
                kwargs["base_url"] = provider.base_url

        selected_prompt_key = self.prompt_var.get()
        selected_prompt = self.prompt_mgr.get(
            selected_prompt_key, self.prompt_mgr.get("原文识别", "")
        )

        logger.info(
            f"[OCR] 识别框 P{page_index + 1}#{box_index + 1}: model={selected_model}, prompt={selected_prompt_key}"
        )

        def do_ocr():
            try:
                ocr = ocr_client.OCRClient(
                    provider=provider, model=selected_model, **kwargs
                )

                if page_img:
                    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
                    region = page_img.crop((x1, y1, x2, y2))
                    logger.info(
                        f"[OCR] 正在识别 P{page_index + 1}#{box_index + 1}: ({x1},{y1})-({x2},{y2})"
                    )
                    result = ocr.analyze_with_prompt(region, selected_prompt)
                    if result:
                        result_preview = (
                            result[:50] + "..." if len(result) > 50 else result
                        )
                    else:
                        result_preview = "(空)"
                    logger.info(
                        f"[OCR] P{page_index + 1}#{box_index + 1} 完成: {result_preview}"
                    )
                    self.after(
                        0,
                        lambda p=page_index,
                        b=box_index,
                        r=result: self._on_single_ocr_done(p, b, r),
                    )
                else:
                    logger.warning(
                        f"[OCR] P{page_index + 1}#{box_index + 1}: 无页面图片"
                    )
                    self.after(
                        0,
                        lambda p=page_index, b=box_index: self._on_single_ocr_done(
                            p, b, "识别失败: 无页面图片"
                        ),
                    )
            except Exception as e:
                logger.error(f"[OCR] P{page_index + 1}#{box_index + 1} 失败: {e}")
                self.after(
                    0,
                    lambda p=page_index,
                    b=box_index,
                    err=str(e): self._on_single_ocr_done(p, b, f"识别失败: {err}"),
                )

        threading.Thread(target=do_ocr, daemon=True).start()

    def _on_single_ocr_done(self, page_index, box_index, result):
        if page_index == self.current_page and self.page_canvas:
            if 0 <= box_index < len(self.page_canvas.boxes):
                model_name = self.model_var.get()
                self.page_canvas.mark_processed(
                    box_index, result, model_name=model_name
                )
                self._save_current_page_boxes()
                self._update_box_list()
                if self.page_canvas.selected_box == self.page_canvas.boxes[box_index]:
                    self.textbox.delete("1.0", "end")
                    self.textbox.insert("1.0", result.replace("\r", "\n"))
        else:
            if page_index in self.all_boxes and 0 <= box_index < len(
                self.all_boxes[page_index]
            ):
                box = self.all_boxes[page_index][box_index]
                box["text"] = result
                box["processed"] = True
                box["ocr_source"] = "llm"
                box["ocr_model"] = self.model_var.get()
                self._update_box_list()

    def _retry_single_box(self, page_index, box_index):
        if page_index != self.current_page:
            self._save_current_page_boxes()
            self.current_page = page_index
            self._load_page()

        if (
            not self.page_canvas
            or box_index < 0
            or box_index >= len(self.page_canvas.boxes)
        ):
            return

        box = self.page_canvas.boxes[box_index]
        box["processed"] = False
        box["text"] = "识别中..."
        self._save_current_page_boxes()
        self._update_box_list()
        self._do_box_ocr(page_index, box_index)
