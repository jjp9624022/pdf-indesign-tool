# -*- coding: utf-8 -*-
"""
PDF 批量识别工具
- 批量识别 PDF 页面文字
- 可选：自动替换到 InDesign
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image
import fitz  # PyMuPDF
import threading
import json
import tempfile
from datetime import datetime

# 设置外观
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 尝试导入 RapidOCR
try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False
    print("Warning: RapidOCR not installed, using fallback")


class PDFBatchTool(ctk.CTk):
    """PDF 批量识别工具"""
    
    def __init__(self):
        super().__init__()
        
        self.title("PDF 批量识别工具")
        self.geometry("1000x700")
        
        self.pdf_path = None
        self.total_pages = 0
        self.doc = None
        self.results = []  # 识别结果
        self.ocr_engine = None
        
        self._init_ocr()
        self._create_ui()
    
    def _init_ocr(self):
        """初始化 OCR 引擎"""
        if HAS_RAPIDOCR:
            self.ocr_engine = RapidOCR()
            print("使用 RapidOCR")
        else:
            print("RapidOCR 未安装，请安装: pip install rapidocr_onnxruntime")
    
    def _create_ui(self):
        """创建 UI"""
        # 顶部工具栏
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            toolbar,
            text="📂 打开 PDF",
            command=self.open_pdf,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(toolbar, text="页码范围:").pack(side="left", padx=(20, 5))
        
        self.start_page = ctk.CTkEntry(toolbar, width=60, placeholder_text="1")
        self.start_page.pack(side="left", padx=2)
        self.start_page.insert(0, "1")
        
        ctk.CTkLabel(toolbar, text="-").pack(side="left")
        
        self.end_page = ctk.CTkEntry(toolbar, width=60, placeholder_text="10")
        self.end_page.pack(side="left", padx=2)
        
        ctk.CTkLabel(toolbar, text="  合并间距:").pack(side="left", padx=(20, 5))
        
        self.h_gap = ctk.CTkEntry(toolbar, width=50, placeholder_text="25")
        self.h_gap.pack(side="left", padx=2)
        self.h_gap.insert(0, "25")
        
        ctk.CTkLabel(toolbar, text="px").pack(side="left")
        
        self.start_btn = ctk.CTkButton(
            toolbar,
            text="🚀 开始识别",
            command=self.start_batch,
            width=120,
            fg_color=("green", "darkgreen")
        )
        self.start_btn.pack(side="left", padx=20)
        
        self.progress_label = ctk.CTkLabel(toolbar, text="")
        self.progress_label.pack(side="left", padx=10)
        
        # 主区域
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 左侧：PDF 缩略图
        left_frame = ctk.CTkFrame(main_frame, width=300)
        left_frame.pack(side="left", fill="both", padx=(0, 5))
        left_frame.pack_propagate(False)
        
        ctk.CTkLabel(left_frame, text="📄 页面预览", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
        
        self.thumbnail_label = ctk.CTkLabel(left_frame, text="选择页面查看", fg_color=("gray85", "gray20"))
        self.thumbnail_label.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.page_nav = ctk.CTkFrame(left_frame)
        self.page_nav.pack(pady=5)
        
        ctk.CTkButton(self.page_nav, text="◀", width=40, command=self.prev_page).pack(side="left", padx=2)
        self.page_label = ctk.CTkLabel(self.page_nav, text="0/0")
        self.page_label.pack(side="left", padx=10)
        ctk.CTkButton(self.page_nav, text="▶", width=40, command=self.next_page).pack(side="left", padx=2)
        
        # 中间：识别结果列表
        center_frame = ctk.CTkFrame(main_frame)
        center_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        ctk.CTkLabel(center_frame, text="📋 识别结果", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
        
        # 结果列表
        self.result_list = ctk.CTkScrollableFrame(center_frame)
        self.result_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 底部：操作按钮
        bottom_frame = ctk.CTkFrame(center_frame)
        bottom_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(
            bottom_frame,
            text="💾 导出 JSON",
            command=self.export_json,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame,
            text="📄 导出标记 PDF",
            command=self.export_marked_pdf,
            width=120
        ).pack(side="left", padx=5)
        
        # 右侧：当前页详情
        right_frame = ctk.CTkFrame(main_frame, width=300)
        right_frame.pack(side="left", fill="both", padx=(5, 0))
        right_frame.pack_propagate(False)
        
        ctk.CTkLabel(right_frame, text="📝 页面详情", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
        
        self.detail_text = ctk.CTkTextbox(right_frame)
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)
        
    def open_pdf(self):
        """打开 PDF"""
        filepath = filedialog.askopenfilename(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            self.pdf_path = filepath
            self.doc = fitz.open(filepath)
            self.total_pages = len(self.doc)
            self.results = []
            
            # 设置结束页默认值
            self.end_page.delete(0, "end")
            self.end_page.insert(0, str(self.total_pages))
            
            # 显示第一页
            self.current_page = 0
            self._show_thumbnail(0)
            
            messagebox.showinfo("成功", f"已打开: {os.path.basename(filepath)}\n共 {self.total_pages} 页")
            
        except Exception as e:
            messagebox.showerror("错误", f"无法打开 PDF: {e}")
    
    def _show_thumbnail(self, page_idx):
        """显示页面缩略图"""
        if not self.doc:
            return
        
        page = self.doc[page_idx]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # 缩略图
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 检查旋转
        mediabox = page.mediabox
        if mediabox.width > mediabox.height and pix.width < pix.height:
            img = img.rotate(90, expand=True)
        
        # 缩放到合适大小
        max_w, max_h = 260, 350
        ratio = min(max_w / img.width, max_h / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        self.page_photo = ctk.CTkImage(img, size=(img.width, img.height))
        self.thumbnail_label.configure(image=self.page_photo, text="")
        
        self.page_label.configure(text=f"{page_idx + 1}/{self.total_pages}")
        self.current_page = page_idx
        
        # 显示该页的识别结果
        self._show_page_result(page_idx)
    
    def _show_page_result(self, page_idx):
        """显示页面识别结果"""
        self.detail_text.delete("1.0", "end")
        
        for i, result in enumerate(self.results):
            if result.get('page') == page_idx + 1:
                self.detail_text.insert("end", f"=== 区域 {i+1} ===\n")
                self.detail_text.insert("end", f"坐标: ({result['x1']}, {result['y1']}) - ({result['x2']}, {result['y2']})\n")
                self.detail_text.insert("end", f"内容: {result['content']}\n\n")
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self._show_thumbnail(self.current_page - 1)
    
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self._show_thumbnail(self.current_page + 1)
    
    def _merge_regions(self, regions, h_gap=25, v_gap=15):
        """合并相邻区域"""
        if not regions:
            return regions
        
        regions = sorted(regions, key=lambda r: (r['y1'], r['x1']))
        
        i = 0
        while i < len(regions):
            j = i + 1
            while j < len(regions):
                r1, r2 = regions[i], regions[j]
                
                y_overlap = max(0, min(r1['y2'], r2['y2']) - max(r1['y1'], r2['y1']))
                x_overlap = max(0, min(r1['x2'], r2['x2']) - max(r1['x1'], r2['x1']))
                
                merged = False
                
                # 水平合并
                if y_overlap > 0:
                    gap = r2['x1'] - r1['x2'] if r2['x1'] > r1['x2'] else r1['x1'] - r2['x2']
                    if gap <= h_gap:
                        regions[i] = {
                            'x1': min(r1['x1'], r2['x1']),
                            'y1': min(r1['y1'], r2['y1']),
                            'x2': max(r1['x2'], r2['x2']),
                            'y2': max(r1['y2'], r2['y2']),
                            'content': r1['content'] + r2['content'],
                            'score': (r1['score'] + r2['score']) / 2,
                            'type': 'text'
                        }
                        regions.pop(j)
                        merged = True
                
                # 垂直合并
                if not merged and x_overlap > 0:
                    gap = r2['y1'] - r1['y2'] if r2['y1'] > r1['y2'] else r1['y1'] - r2['y2']
                    if gap <= v_gap:
                        regions[i] = {
                            'x1': min(r1['x1'], r2['x1']),
                            'y1': min(r1['y1'], r2['y1']),
                            'x2': max(r1['x2'], r2['x2']),
                            'y2': max(r1['y2'], r2['y2']),
                            'content': r1['content'] + '\n' + r2['content'],
                            'score': (r1['score'] + r2['score']) / 2,
                            'type': 'text'
                        }
                        regions.pop(j)
                        merged = True
                
                if not merged:
                    j += 1
            i += 1
        
        return regions
    
    def _process_page(self, page_idx):
        """处理单个页面"""
        page = self.doc[page_idx]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        
        page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 处理旋转
        mediabox = page.mediabox
        if mediabox.width > mediabox.height and pix.width < pix.height:
            page_img = page_img.rotate(90, expand=True)
        
        # 保存临时图片
        temp_path = os.path.join(tempfile.gettempdir(), f'pdf_batch_page_{page_idx}.png')
        page_img.save(temp_path)
        
        # OCR
        result, elapse = self.ocr_engine(temp_path)
        
        # 转换结果
        regions = []
        if result:
            for item in result:
                box = item[0]
                text = item[1]
                score = item[2]
                
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                
                regions.append({
                    "x1": int(min(xs)),
                    "y1": int(min(ys)),
                    "x2": int(max(xs)),
                    "y2": int(max(ys)),
                    "content": text,
                    "score": float(score),
                    "type": "text",
                    "page": page_idx + 1
                })
        
        # 合并
        try:
            h_gap = int(self.h_gap.get())
        except:
            h_gap = 25
        
        regions = self._merge_regions(regions, h_gap=h_gap, v_gap=15)
        
        # 更新页面索引
        for r in regions:
            r['page'] = page_idx + 1
        
        return regions, len(result) if result else 0
    
    def start_batch(self):
        """开始批量识别"""
        if not self.doc:
            messagebox.showwarning("提示", "请先打开 PDF 文件")
            return
        
        try:
            start = int(self.start_page.get()) - 1
            end = int(self.end_page.get())
            if start < 0:
                start = 0
            if end > self.total_pages:
                end = self.total_pages
            if start >= end:
                messagebox.showerror("错误", "页码范围无效")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的页码")
            return
        
        self.results = []
        self.start_btn.configure(state="disabled", text="处理中...")
        
        def do_work():
            total_raw = 0
            for i in range(start, end):
                page_num = i + 1
                self.after(0, lambda p=page_num, r=0: self.progress_label.configure(
                    text=f"处理第 {p} 页... ({r} 个区域)"
                ))
                
                regions, raw_count = self._process_page(i)
                self.results.extend(regions)
                total_raw += raw_count
            
            self.after(0, lambda: self._on_batch_complete(end - start, total_raw))
        
        thread = threading.Thread(target=do_work)
        thread.daemon = True
        thread.start()
    
    def _on_batch_complete(self, page_count, raw_count):
        """批量处理完成"""
        self.start_btn.configure(state="normal", text="🚀 开始识别")
        self.progress_label.configure(text=f"完成！")
        
        # 更新列表
        self._update_result_list()
        
        # 切换到第一页
        self._show_thumbnail(0)
        
        messagebox.showinfo("完成", 
            f"处理了 {page_count} 页\n"
            f"原始区域: {raw_count}\n"
            f"合并后: {len(self.results)} 个区域"
        )
    
    def _update_result_list(self):
        """更新结果列表"""
        # 清除现有项
        for widget in self.result_list.winfo_children():
            widget.destroy()
        
        # 添加新项
        for i, result in enumerate(self.results):
            item_frame = ctk.CTkFrame(self.result_list, corner_radius=6)
            item_frame.pack(fill="x", padx=3, pady=2)
            
            # 标题
            ctk.CTkLabel(
                item_frame,
                text=f"区域 {i+1} [页{result['page']}]",
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w"
            ).pack(fill="x", padx=10, pady=(5, 0))
            
            # 内容预览
            content = result['content'][:40] + "..." if len(result['content']) > 40 else result['content']
            ctk.CTkLabel(
                item_frame,
                text=content,
                font=ctk.CTkFont(size=10),
                anchor="w",
                text_color="gray70"
            ).pack(fill="x", padx=10, pady=(0, 5))
    
    def export_json(self):
        """导出 JSON"""
        if not self.results:
            messagebox.showwarning("提示", "没有可导出的结果")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="保存 JSON",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            # 添加元数据
            output = {
                "pdf": self.pdf_path,
                "pages_processed": len(set(r['page'] for r in self.results)),
                "total_regions": len(self.results),
                "export_time": datetime.now().isoformat(),
                "results": self.results
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("成功", f"已保存到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
    
    def export_marked_pdf(self):
        """导出带标记的 PDF"""
        if not self.results or not self.doc:
            messagebox.showwarning("提示", "没有可导出的结果")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="保存带标记 PDF",
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            out_doc = fitz.open()
            
            # 获取处理的页面范围
            pages = sorted(set(r['page'] for r in self.results))
            
            for page_num in pages:
                page_idx = page_num - 1
                page = self.doc[page_idx]
                
                # 渲染页面
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # 处理旋转
                mediabox = page.mediabox
                if mediabox.width > mediabox.height and pix.width < pix.height:
                    page_img = page_img.rotate(90, expand=True)
                
                # 创建 PDF 页
                out_page = out_doc.new_page(width=page_img.width, height=page_img.height)
                
                # 插入图片
                temp_path = os.path.join(tempfile.gettempdir(), 'pdf_mark_export.png')
                page_img.save(temp_path)
                out_page.insert_image(out_page.rect, filename=temp_path)
                
                # 绘制该页的标记框
                page_regions = [r for r in self.results if r['page'] == page_num]
                
                for j, region in enumerate(page_regions):
                    rect = fitz.Rect(region['x1'], region['y1'], region['x2'], region['y2'])
                    out_page.draw_rect(rect, color=(0, 1, 1), width=2)
                    out_page.insert_text(
                        (region['x1'] + 3, region['y1'] + 12),
                        f"[{j+1}]",
                        fontsize=10,
                        color=(1, 1, 0),
                        fontname="helv"
                    )
            
            out_doc.save(filepath)
            out_doc.close()
            
            messagebox.showinfo("成功", f"已保存到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


def main():
    app = PDFBatchTool()
    app.mainloop()


if __name__ == "__main__":
    main()
