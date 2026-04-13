"""UI 构建器 — 负责所有界面创建"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from ..constants import INFO_PANEL_WIDTH


class UIBuilder:
    def _create_ui(self):
        self._create_toolbar()
        self._create_main_area()
        self._create_hint_label()

    def _create_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            toolbar, text="📂 打开 PDF", command=self.open_pdf, width=120
        ).pack(side="left", padx=5)

        self._create_tool_buttons(toolbar)

        self.auto_detect_btn = ctk.CTkButton(
            toolbar, text="🔍 自动检测", command=self.auto_detect, width=120
        )
        self.auto_detect_btn.pack(side="left", padx=5)

        self.batch_ocr_btn = ctk.CTkButton(
            toolbar, text="📝 批量识别", command=self.batch_ocr, width=100
        )
        self.batch_ocr_btn.pack(side="left", padx=5)

        self._create_model_selector(toolbar)

        ctk.CTkButton(
            toolbar, text="💾 保存框", command=self.save_boxes, width=100
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            toolbar, text="📂 加载框", command=self.load_boxes, width=100
        ).pack(side="right", padx=5)

    def _create_page_toolbar(self):
        page_toolbar = ctk.CTkFrame(self.pdf_frame)
        page_toolbar.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkButton(page_toolbar, text="◀", command=self.prev_page, width=35).pack(
            side="left", padx=2
        )
        self.page_label = ctk.CTkLabel(page_toolbar, text="第 0 / 0 页", width=100)
        self.page_label.pack(side="left", padx=5)
        ctk.CTkButton(page_toolbar, text="▶", command=self.next_page, width=35).pack(
            side="left", padx=2
        )

        self.page_entry = ctk.CTkEntry(
            page_toolbar, width=40, height=24, font=ctk.CTkFont(size=10)
        )
        self.page_entry.pack(side="left", padx=(10, 3))
        self.page_entry.bind("<Return>", self._on_page_jump)

        ctk.CTkButton(
            page_toolbar, text="🔄", command=self.refresh_canvas, width=35
        ).pack(side="left", padx=(5, 15))

        gap_frame = ctk.CTkFrame(page_toolbar, fg_color="transparent")
        gap_frame.pack(side="left", padx=10)

        ctk.CTkLabel(gap_frame, text="合并:", font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(0, 5)
        )

        self.h_gap_var = ctk.StringVar(value="50")
        self.v_gap_var = ctk.StringVar(value="30")

        ctk.CTkLabel(gap_frame, text="横:", font=ctk.CTkFont(size=10)).pack(side="left")
        self.h_gap_entry = ctk.CTkEntry(
            gap_frame, width=45, height=22, textvariable=self.h_gap_var
        )
        self.h_gap_entry.pack(side="left", padx=2)

        ctk.CTkLabel(gap_frame, text="纵:", font=ctk.CTkFont(size=10)).pack(side="left")
        self.v_gap_entry = ctk.CTkEntry(
            gap_frame, width=45, height=22, textvariable=self.v_gap_var
        )
        self.v_gap_entry.pack(side="left", padx=2)

        zoom_frame = ctk.CTkFrame(page_toolbar, fg_color="transparent")
        zoom_frame.pack(side="right", padx=5)

        ctk.CTkButton(
            zoom_frame, text="➖", width=30, height=24, command=self._zoom_out
        ).pack(side="left", padx=1)
        self.zoom_label = ctk.CTkLabel(
            zoom_frame, text="100%", width=50, font=ctk.CTkFont(size=10)
        )
        self.zoom_label.pack(side="left", padx=2)
        ctk.CTkButton(
            zoom_frame, text="➕", width=30, height=24, command=self._zoom_in
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            zoom_frame, text="🔲适应", width=50, height=24, command=self._fit_window
        ).pack(side="left", padx=(5, 0))

    def _create_tool_buttons(self, toolbar):
        tool_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_frame.pack(side="left", padx=(10, 5))

        ctk.CTkLabel(tool_frame, text="工具:").pack(side="left", padx=(0, 5))

        self.tool_var = ctk.StringVar(value="select")

        self.btn_select = ctk.CTkButton(
            tool_frame,
            text="🖐️ 移动",
            command=lambda: self._set_tool_mode("select"),
            width=70,
            height=28,
        )
        self.btn_select.pack(side="left", padx=2)

        self.btn_draw = ctk.CTkButton(
            tool_frame,
            text="✚ 绘制",
            command=lambda: self._set_tool_mode("draw"),
            width=70,
            height=28,
        )
        self.btn_draw.pack(side="left", padx=2)

    def _create_model_selector(self, toolbar):
        ctk.CTkLabel(toolbar, text="模型:").pack(side="left", padx=(10, 5))

        self.model_var = ctk.StringVar()
        all_models = self.config.get_all_models()
        model_names = [m[0] for m in all_models]

        self.model_combo = ctk.CTkComboBox(
            toolbar,
            values=model_names,
            variable=self.model_var,
            width=200,
            height=28,
            command=self._on_model_changed,
        )
        self.model_combo.pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar, text="⚙️", command=self.show_provider_manager, width=30, height=28
        ).pack(side="left", padx=2)

        default_model = self.config.get_ocr_model_id()
        if not default_model or default_model not in model_names:
            default_model = "Qwen/Qwen2-VL-72B-Instruct"
            if default_model not in model_names and model_names:
                default_model = model_names[0]
        self.model_var.set(default_model)
        self._update_provider_from_model(default_model)

    def _on_model_changed(self, value):
        self._update_provider_from_model(value)

    def _update_provider_from_model(self, model_id):
        provider = self.config.get_provider_by_model_id(model_id)
        if provider and self.config.config.ocr_model:
            self.config.config.ocr_model.provider = provider.id

    def _create_main_area(self):
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        self.paned = ttk.PanedWindow(main_frame, orient="horizontal")
        self.paned.grid(row=0, column=0, sticky="nsew")

        self.pdf_frame = ctk.CTkFrame(self.paned)
        self.paned.add(self.pdf_frame, weight=1)

        self._create_page_toolbar()

        self.pdf_canvas = tk.Canvas(self.pdf_frame, bg="#2B2B2B", highlightthickness=0)

        self.v_scrollbar = ctk.CTkScrollbar(
            self.pdf_frame, orientation="vertical", command=self.pdf_canvas.yview
        )
        self.pdf_canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.h_scrollbar = ctk.CTkScrollbar(
            self.pdf_frame, orientation="horizontal", command=self.pdf_canvas.xview
        )
        self.pdf_canvas.configure(xscrollcommand=self.h_scrollbar.set)

        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.pdf_canvas.pack(side="left", fill="both", expand=True)

        self._create_info_panel()

    def _create_info_panel(self):
        info_panel = ctk.CTkFrame(self.paned)
        self.paned.add(info_panel, weight=0)

        info_panel.configure(width=INFO_PANEL_WIDTH)
        info_panel.pack_propagate(False)

        ctk.CTkLabel(
            info_panel, text="📋 框列表", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", padx=10, pady=(10, 5))

        self.box_list_frame = ctk.CTkScrollableFrame(info_panel)
        self.box_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        prompt_frame = ctk.CTkFrame(info_panel)
        prompt_frame.pack(fill="x", padx=5, pady=(5, 0))

        self.prompt_var = ctk.StringVar(value=self.prompt_mgr.first_key() or "原文识别")
        self.prompt_combo = ctk.CTkComboBox(
            prompt_frame,
            values=self.prompt_mgr.keys(),
            variable=self.prompt_var,
            height=25,
        )
        self.prompt_combo.pack(side="left", fill="x", expand=True, padx=(5, 2), pady=3)

        ctk.CTkButton(
            prompt_frame, text="✏️", command=self.show_prompt_editor, width=30, height=25
        ).pack(side="left", padx=(0, 5), pady=3)

        ctk.CTkFrame(info_panel, height=2, fg_color="gray30").pack(
            fill="x", padx=10, pady=5
        )

        text_header = ctk.CTkFrame(info_panel, fg_color="transparent")
        text_header.pack(fill="x", padx=10, pady=(5, 3))
        ctk.CTkLabel(
            text_header, text="✏️ 识别文本", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self._textbox_font_size = 10
        ctk.CTkButton(
            text_header,
            text="A-",
            width=30,
            height=22,
            command=self._decrease_font,
            font=ctk.CTkFont(size=10),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            text_header,
            text="A+",
            width=30,
            height=22,
            command=self._increase_font,
            font=ctk.CTkFont(size=10),
        ).pack(side="right", padx=2)

        self.textbox = ctk.CTkTextbox(
            info_panel, height=80, font=("Consolas", self._textbox_font_size)
        )
        self.textbox.pack(fill="x", padx=5, pady=(25, 5))
        self.textbox.bind("<FocusOut>", lambda e: self._save_edited_text())
        self.textbox.bind("<FocusIn>", self._on_textbox_focus_in)
        self.textbox.bind("<Control-z>", lambda e: self._undo_edit())
        self.textbox.bind("<Control-y>", lambda e: self._redo_edit())
        self.textbox.bind("<KeyRelease>", lambda e: self._on_text_changed())

        threshold_frame = ctk.CTkFrame(info_panel, fg_color="transparent")
        threshold_frame.pack(fill="x", padx=10, pady=(5, 3))

        ctk.CTkLabel(threshold_frame, text="相似度:", font=ctk.CTkFont(size=10)).pack(
            side="left", padx=(0, 5)
        )

        self.similarity_var = ctk.DoubleVar(value=0.5)
        self.similarity_slider = ctk.CTkSlider(
            threshold_frame,
            from_=0.1,
            to=1.0,
            variable=self.similarity_var,
            number_of_steps=18,
            height=16,
        )
        self.similarity_slider.pack(side="left", fill="x", expand=True)

        self.similarity_label = ctk.CTkLabel(
            threshold_frame, text="0.50", width=35, font=ctk.CTkFont(size=10)
        )
        self.similarity_label.pack(side="left", padx=(5, 0))
        self.similarity_slider.configure(command=self._on_similarity_change)

        replace_mode_frame = ctk.CTkFrame(info_panel, fg_color="transparent")
        replace_mode_frame.pack(fill="x", padx=10, pady=(3, 3))

        ctk.CTkLabel(replace_mode_frame, text="替换:", font=ctk.CTkFont(size=10)).pack(
            side="left", padx=(0, 5)
        )

        self.replace_mode_var = ctk.StringVar(value="precise")

        ctk.CTkRadioButton(
            replace_mode_frame,
            text="精确文本",
            variable=self.replace_mode_var,
            value="precise",
            font=ctk.CTkFont(size=9),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkRadioButton(
            replace_mode_frame,
            text="整个文本框",
            variable=self.replace_mode_var,
            value="frame",
            font=ctk.CTkFont(size=9),
        ).pack(side="left")

        search_btn_frame = ctk.CTkFrame(info_panel, fg_color="transparent")
        search_btn_frame.pack(fill="x", padx=5, pady=3)

        self.btn_search_id = ctk.CTkButton(
            search_btn_frame,
            text="🔍 ID搜索",
            command=self.search_in_indesign,
            height=28,
            width=70,
        )
        self.btn_search_id.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_replace_id = ctk.CTkButton(
            search_btn_frame,
            text="↔️ 替换",
            command=self.replace_in_indesign,
            height=28,
            width=70,
        )
        self.btn_replace_id.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_search_replace = ctk.CTkButton(
            search_btn_frame,
            text="🔍➜✓ 查找并替换",
            command=self.search_and_replace,
            height=28,
            width=90,
        )
        self.btn_search_replace.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_replace_next = ctk.CTkButton(
            search_btn_frame,
            text="✓→ 替换并查找",
            command=self.replace_and_find_next,
            height=28,
            width=80,
            fg_color=("#2D8C4E", "#1E6B3A"),
        )
        self.btn_replace_next.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_reindex = ctk.CTkButton(
            search_btn_frame,
            text="🔄 索引",
            command=self.rebuild_index,
            height=28,
            width=50,
            fg_color=("#8B4513", "#5C3000"),
        )
        self.btn_reindex.pack(side="left")

        ctk.CTkLabel(info_panel, text="📋 搜索结果", font=ctk.CTkFont(size=11)).pack(
            fill="x", padx=10, pady=(8, 3)
        )

        self.search_result_frame = ctk.CTkScrollableFrame(info_panel, height=100)
        self.search_result_frame.pack(fill="both", expand=True, padx=5, pady=(25, 5))

        self.search_matches = []
        self.selected_match_index = None

        self.status_bar = ctk.CTkLabel(
            self, text="就绪", anchor="w", font=ctk.CTkFont(size=11), height=28
        )
        self.status_bar.pack(fill="x", padx=10, pady=(0, 5), side="bottom")

        self.search_hint = ctk.CTkLabel(
            self.search_result_frame,
            text="搜索后在右侧查看结果",
            text_color="gray50",
            font=ctk.CTkFont(size=10),
        )
        self.search_hint.pack(pady=10)

    def _create_hint_label(self):
        self.hint_label = ctk.CTkLabel(
            self.pdf_canvas,
            text="请打开 PDF 文件",
            font=ctk.CTkFont(size=16),
            text_color="gray50",
        )
        self.pdf_canvas.create_window(400, 300, window=self.hint_label, anchor="center")
