"""
PDF 分析主应用
"""

import customtkinter as ctk

from .constants import MAIN_WINDOW_SIZE
from .prompt_manager import PromptManager
from .components.ui_builder import UIBuilder
from .components.pdf_controller import PDFController
from .components.ocr_handler import OCRHandler
from .components.box_manager import BoxManager
from .components.indesign_handler import InDesignHandler
from config_manager import ConfigManager
from text_editor import TextEditorMixin

try:
    from indesign_client import InDesignClient

    INDESIGN_AVAILABLE = True
except ImportError:
    INDESIGN_AVAILABLE = False


class PDFAnalyzerApp(
    ctk.CTk,
    TextEditorMixin,
    UIBuilder,
    PDFController,
    OCRHandler,
    BoxManager,
    InDesignHandler,
):
    def __init__(self):
        super().__init__()

        self.title("PDF 版面分析工具")
        self.geometry(MAIN_WINDOW_SIZE)

        self.current_pdf = None
        self.current_page = 0
        self.total_pages = 0
        self.page_images = {}
        self.all_boxes = {}

        self.pdf_canvas = None
        self.page_canvas = None

        self.indesign_client = InDesignClient() if INDESIGN_AVAILABLE else None
        self.indesign_connected = False
        self.indesign_matches = []

        self.config = ConfigManager()
        self.prompt_mgr = PromptManager()

        self._init_text_editor()
        self._create_ui()

    def _decrease_font(self):
        if self._textbox_font_size > 8:
            self._textbox_font_size -= 1
            self.textbox.configure(font=("Consolas", self._textbox_font_size))

    def _increase_font(self):
        if self._textbox_font_size < 20:
            self._textbox_font_size += 1
            self.textbox.configure(font=("Consolas", self._textbox_font_size))

    def _save_edited_text(self):
        if self.page_canvas and self.page_canvas.selected_box:
            edited_text = self.textbox.get("1.0", "end-1c")
            if edited_text:
                edited_text = edited_text.replace("\n", "\r")
            self.page_canvas.selected_box["text"] = edited_text
            self._update_box_list()

    def _on_text_changed(self):
        pass

    def _on_similarity_change(self, value):
        self.similarity_label.configure(text=f"{value:.2f}")

    def show_prompt_editor(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("编辑 Prompt")
        dialog.geometry("700x550")
        dialog.transient(self)
        dialog.grab_set()

        top_frame = ctk.CTkFrame(dialog)
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top_frame, text="选择 Prompt:", anchor="w").pack(
            side="left", padx=5
        )

        self._editor_prompt_var = ctk.StringVar(value=self.prompt_var.get())
        prompt_combo = ctk.CTkComboBox(
            top_frame,
            values=self.prompt_mgr.keys(),
            variable=self._editor_prompt_var,
            command=lambda v: self._load_prompt_to_editor(v),
            width=150,
        )
        prompt_combo.pack(side="left", padx=5)

        ctk.CTkButton(
            top_frame, text="➕ 新建", command=self._new_prompt, width=80
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            dialog, text="Prompt 内容:", anchor="w", font=ctk.CTkFont(weight="bold")
        ).pack(fill="x", padx=10, pady=(5, 5))

        self._prompt_textbox = ctk.CTkTextbox(dialog, font=("Consolas", 11))
        self._prompt_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        self._prompt_textbox.insert(
            "1.0", self.prompt_mgr.get(self.prompt_var.get(), "")
        )

        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            btn_frame,
            text="💾 保存",
            command=lambda: self._save_prompt(dialog),
            width=100,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="❌ 删除",
            command=lambda: self._delete_prompt(dialog),
            width=100,
        ).pack(side="left", padx=5)

        ctk.CTkButton(btn_frame, text="关闭", command=dialog.destroy, width=100).pack(
            side="right", padx=5
        )

        self._prompt_dialog = dialog

    def _load_prompt_to_editor(self, prompt_key: str):
        self._editor_prompt_var.set(prompt_key)
        self._prompt_textbox.delete("1.0", "end")
        self._prompt_textbox.insert("1.0", self.prompt_mgr.get(prompt_key, ""))

    def _new_prompt(self):
        dialog = ctk.CTkInputDialog(text="输入新 Prompt 名称:", title="新建 Prompt")
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip()
            if name not in self.prompt_mgr.get_all():
                self.prompt_mgr.add(name, "请输入你的 Prompt 内容...")
                self.prompt_combo.configure(values=self.prompt_mgr.keys())
                self._prompt_textbox.delete("1.0", "end")
                self._prompt_textbox.insert("1.0", self.prompt_mgr.get(name))
                self._editor_prompt_var.set(name)
            else:
                from tkinter import messagebox

                messagebox.showwarning("提示", "该名称已存在")

    def _save_prompt(self, dialog):
        name = self._editor_prompt_var.get()
        content = self._prompt_textbox.get("1.0", "end-1c")

        if name and content:
            self.prompt_mgr.update(name, content)
            self.prompt_combo.configure(values=self.prompt_mgr.keys())
            from tkinter import messagebox

            messagebox.showinfo("提示", f"已保存 Prompt: {name}")

    def _delete_prompt(self, dialog):
        name = self._editor_prompt_var.get()

        if self.prompt_mgr.count() <= 1:
            from tkinter import messagebox

            messagebox.showwarning("提示", "至少保留一个 Prompt")
            return

        from tkinter import messagebox

        if messagebox.askyesno("确认", f"确定删除 Prompt '{name}'?"):
            self.prompt_mgr.delete(name)
            self.prompt_combo.configure(values=self.prompt_mgr.keys())
            first_key = self.prompt_mgr.first_key()
            self._editor_prompt_var.set(first_key)
            self._prompt_textbox.delete("1.0", "end")
            self._prompt_textbox.insert("1.0", self.prompt_mgr.get(first_key))
            self.prompt_var.set(first_key)
            messagebox.showinfo("提示", f"已删除 Prompt: {name}")

    def show_provider_manager(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("供应商管理")
        dialog.geometry("650x500")
        dialog.transient(self)
        dialog.grab_set()

        top_btn = ctk.CTkFrame(dialog, fg_color="transparent")
        top_btn.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            top_btn,
            text="➕ 添加供应商",
            command=lambda: self._add_provider_dialog(dialog),
            width=120,
        ).pack(side="left", padx=5)

        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        for provider in self.config.config.providers:
            self._render_provider_card(scroll, provider, dialog)

    def _render_provider_card(self, parent, provider, dialog):
        card = ctk.CTkFrame(parent, corner_radius=8)
        card.pack(fill="x", padx=5, pady=5)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header, text=provider.name, font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=f"({provider.id})",
            text_color="gray50",
            font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(5, 0))

        ctk.CTkButton(
            header,
            text="✏️",
            width=30,
            height=22,
            command=lambda p=provider, d=dialog: self._edit_provider_dialog(p, d),
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            header,
            text="✕",
            width=30,
            height=22,
            fg_color="red",
            command=lambda pid=provider.id, d=dialog: self._remove_provider(pid, d),
        ).pack(side="right", padx=2)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=10, pady=2)

        key_display = provider.api_key[:8] + "..." if provider.api_key else "(未设置)"
        ctk.CTkLabel(
            info,
            text=f"API Key: {key_display}",
            font=ctk.CTkFont(size=9),
            text_color="gray60",
        ).pack(anchor="w")

        if provider.base_url:
            ctk.CTkLabel(
                info,
                text=f"Base URL: {provider.base_url}",
                font=ctk.CTkFont(size=9),
                text_color="gray60",
            ).pack(anchor="w")

        models_frame = ctk.CTkFrame(card, fg_color="transparent")
        models_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(
            models_frame,
            text=f"模型 ({len(provider.models)}):",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="w")

        for m in provider.models:
            row = ctk.CTkFrame(models_frame, fg_color="transparent")
            row.pack(fill="x")

            ctk.CTkLabel(
                row,
                text=f"• {m['name']}",
                font=ctk.CTkFont(size=9),
                width=180,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=m["model_id"], font=ctk.CTkFont(size=8), text_color="gray50"
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                row,
                text="✕",
                width=22,
                height=18,
                fg_color="gray40",
                command=lambda pid=provider.id,
                mid=m["model_id"],
                d=dialog: self._remove_model(pid, mid, d),
            ).pack(side="right")

        ctk.CTkButton(
            models_frame,
            text="+ 添加模型",
            width=80,
            height=20,
            command=lambda pid=provider.id, d=dialog: self._add_model_dialog(pid, d),
        ).pack(anchor="w", pady=(5, 0))

    def _add_provider_dialog(self, parent_dialog):
        dialog = ctk.CTkInputDialog(text="供应商 ID (如 openai):", title="添加供应商")
        pid = dialog.get_input()
        if not pid or not pid.strip():
            return
        pid = pid.strip()

        dialog2 = ctk.CTkInputDialog(text="供应商名称 (如 OpenAI):", title="添加供应商")
        name = dialog2.get_input()
        if not name or not name.strip():
            return
        name = name.strip()

        self.config.add_provider(pid, name)
        self._refresh_provider_manager(parent_dialog)
        self._refresh_model_combo()

    def _remove_provider(self, provider_id, parent_dialog):
        from tkinter import messagebox

        if messagebox.askyesno("确认", f"确定删除供应商 '{provider_id}'?"):
            self.config.remove_provider(provider_id)
            self._refresh_provider_manager(parent_dialog)
            self._refresh_model_combo()

    def _edit_provider_dialog(self, provider, parent_dialog):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"编辑 {provider.name}")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="API Key:").pack(anchor="w", padx=10, pady=(10, 2))
        key_entry = ctk.CTkEntry(dialog, width=350)
        key_entry.pack(padx=10, pady=2)
        key_entry.insert(0, provider.api_key)

        ctk.CTkLabel(dialog, text="Base URL (可选):").pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        url_entry = ctk.CTkEntry(dialog, width=350)
        url_entry.pack(padx=10, pady=2)
        url_entry.insert(0, provider.base_url)

        def save():
            self.config.update_provider(
                provider.id, api_key=key_entry.get(), base_url=url_entry.get()
            )
            self._refresh_provider_manager(parent_dialog)
            dialog.destroy()

        ctk.CTkButton(dialog, text="💾 保存", command=save, width=100).pack(pady=15)

    def _add_model_dialog(self, provider_id, parent_dialog):
        dialog = ctk.CTkInputDialog(text="模型 ID:", title="添加模型")
        model_id = dialog.get_input()
        if not model_id or not model_id.strip():
            return
        model_id = model_id.strip()

        dialog2 = ctk.CTkInputDialog(text="模型名称:", title="添加模型")
        name = dialog2.get_input()
        if not name or not name.strip():
            return
        name = name.strip()

        self.config.add_model_to_provider(provider_id, model_id, name)
        self._refresh_provider_manager(parent_dialog)
        self._refresh_model_combo()

    def _remove_model(self, provider_id, model_id, parent_dialog):
        from tkinter import messagebox

        if messagebox.askyesno("确认", f"确定删除模型 '{model_id}'?"):
            self.config.remove_model_from_provider(provider_id, model_id)
            self._refresh_provider_manager(parent_dialog)
            self._refresh_model_combo()

    def _refresh_provider_manager(self, parent_dialog):
        for w in parent_dialog.winfo_children():
            if isinstance(w, ctk.CTkScrollableFrame):
                for child in w.winfo_children():
                    child.destroy()
                for provider in self.config.config.providers:
                    self._render_provider_card(w, provider, parent_dialog)
                break

    def _refresh_model_combo(self):
        all_models = self.config.get_all_models()
        model_names = [m[0] for m in all_models]
        self.model_combo.configure(values=model_names)
