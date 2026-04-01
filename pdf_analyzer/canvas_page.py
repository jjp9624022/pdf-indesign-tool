"""
PDF 页面画布组件
支持框编辑、拖拽、缩放
"""

import tkinter as tk
from PIL import Image, ImageTk
from .constants import (
    BOX_COLORS,
    MIN_SCALE,
    MAX_SCALE,
    WHEEL_ZOOM_STEP,
    RESIZE_HANDLE_SIZE,
    RESIZE_CURSOR_SIZE,
)


class PDFPageCanvas:
    """
    PDF 页面画布，支持框编辑和动态缩放

    坐标系统：
    - 原始坐标 (page_x, page_y): 基于 PDF 原始尺寸的坐标
    - 视图坐标 (view_x, view_y): 基于 Canvas 显示的坐标
    - 缩放比例 self.scale: view = page * scale
    """

    def __init__(self, canvas, page_image, page_width, page_height, initial_scale=1.0):
        self.canvas = canvas  # 使用外部传入的 Canvas
        self.page_image = page_image
        self.page_width = page_width  # 原始页面宽度
        self.page_height = page_height  # 原始页面高度

        # 缩放比例
        self.scale = initial_scale

        # Canvas 尺寸
        self.canvas_width = int(page_width * self.scale)
        self.canvas_height = int(page_height * self.scale)

        # 设置 scrollregion
        self.canvas.configure(
            scrollregion=(0, 0, self.canvas_width, self.canvas_height)
        )

        # 缩放图片
        self._update_image()

        # 框列表 [{'x1', 'y1', 'x2', 'y2', 'text', 'processed', ...}]
        self.boxes = []

        # 当前选中的框
        self.selected_box = None
        self.selected_box_id = None
        self.selected_boxes = []  # 多选

        # 拖拽状态
        self.drag_start = None
        self.is_dragging = False
        self.is_drawing = False
        self.draw_rect_id = None
        self.is_selecting = False
        self.select_rect_id = None

        # 工具模式
        self.tool_mode = "select"

        # 角点调整状态
        self.is_resizing = False
        self.resize_handle = None  # 'nw', 'ne', 'sw', 'se'
        self.resize_start = None  # 调整开始时的框坐标

        # 角点手柄
        self.resize_handles = {}  # {'nw': canvas_id, 'ne': canvas_id, ...}

        # 回调函数
        self.on_scale_change = None
        self.on_clear = None  # 清空回调
        self.on_box_added = None  # 添加框回调
        self.on_box_deleted = None
        self.wheel_zoom_step = WHEEL_ZOOM_STEP

        self._bind_events()

    def _draw_resize_handles(self):
        """绘制调整大小的角点手柄"""
        # 先清除旧的角点
        for handle_id in self.resize_handles.values():
            self.canvas.delete(handle_id)
        self.resize_handles = {}

        if not self.selected_box:
            return

        x1, y1 = self.to_view_coords(self.selected_box["x1"], self.selected_box["y1"])
        x2, y2 = self.to_view_coords(self.selected_box["x2"], self.selected_box["y2"])

        size = 6  # 角点大小

        # 四个角点: nw=左上, ne=右上, sw=左下, se=右下
        handles = {
            "nw": (x1, y1),
            "ne": (x2, y1),
            "sw": (x1, y2),
            "se": (x2, y2),
        }

        for key, (hx, hy) in handles.items():
            rect_id = self.canvas.create_rectangle(
                hx - size,
                hy - size,
                hx + size,
                hy + size,
                fill="#3B8ED0",
                outline="white",
                width=1,
            )
            self.resize_handles[key] = rect_id

    def _get_handle_at(self, x, y):
        """检测鼠标位置是否在某个角点上"""
        if not self.selected_box:
            return None

        x1, y1 = self.to_view_coords(self.selected_box["x1"], self.selected_box["y1"])
        x2, y2 = self.to_view_coords(self.selected_box["x2"], self.selected_box["y2"])

        check_range = 8  # 检测范围

        handles = {
            "nw": (x1, y1),
            "ne": (x2, y1),
            "sw": (x1, y2),
            "se": (x2, y2),
        }

        for key, (hx, hy) in handles.items():
            if abs(x - hx) <= check_range and abs(y - hy) <= check_range:
                return key
        return None

    def _update_cursor(self, event):
        """根据鼠标位置更新光标"""
        handle = self._get_handle_at(event.x, event.y)
        if handle:
            cursors = {
                "nw": "size_nw_se",
                "ne": "size_ne_sw",
                "sw": "size_ne_sw",
                "se": "size_nw_se",
            }
            self.canvas.configure(cursor=cursors.get(handle, ""))
        elif self.tool_mode == "draw":
            self.canvas.configure(cursor="crosshair")
        else:
            self.canvas.configure(cursor="")

        # ==================== 缩放控制 ====================
        self.on_scale_change = None
        self.on_clear = None  # 清空回调
        self.on_box_added = None  # 添加框回调 (index)
        self.wheel_zoom_step = WHEEL_ZOOM_STEP

        self._bind_events()

    # ==================== 缩放控制 ====================

    def set_tool_mode(self, mode):
        """设置工具模式"""
        self.tool_mode = mode
        self._clear_selection()
        cursor = "crosshair" if mode == "draw" else ""
        self.canvas.configure(cursor=cursor)

    def _update_image(self):
        """更新缩放后的图片"""
        scaled_image = self.page_image.resize(
            (self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS
        )
        self.tk_image = ImageTk.PhotoImage(scaled_image)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.configure(
            scrollregion=(0, 0, self.canvas_width, self.canvas_height)
        )

    def set_scale(self, new_scale):
        """设置缩放比例"""
        new_scale = max(MIN_SCALE, min(MAX_SCALE, new_scale))

        self.scale = new_scale
        self.canvas_width = int(self.page_width * self.scale)
        self.canvas_height = int(self.page_height * self.scale)
        self.canvas.configure(width=self.canvas_width, height=self.canvas_height)

        self._update_image()
        self._redraw_all_boxes()

        if self.on_scale_change:
            self.on_scale_change(new_scale)

    def zoom_in(self, delta=0.1):
        self.set_scale(self.scale + delta)

    def zoom_out(self, delta=0.1):
        self.set_scale(self.scale - delta)

    def fit_to_window(self):
        """适应窗口大小"""
        parent = self.canvas.master
        w = parent.winfo_width() if parent.winfo_width() > 1 else 800
        h = parent.winfo_height() if parent.winfo_height() > 1 else 600
        scale = min(w / self.page_width, h / self.page_height, 1.0)
        self.set_scale(scale)

    def _redraw_all_boxes(self):
        """重新绘制所有框"""
        for box in self.boxes:
            if "canvas_id" in box:
                self.canvas.delete(box["canvas_id"])
                color = (
                    BOX_COLORS["processed"]
                    if box.get("processed")
                    else BOX_COLORS["normal"]
                )
                x1, y1 = self.to_view_coords(box["x1"], box["y1"])
                x2, y2 = self.to_view_coords(box["x2"], box["y2"])
                box["canvas_id"] = self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    outline=color,
                    width=2 if color != BOX_COLORS["processed"] else 1,
                )
                if box.get("processed"):
                    self.canvas.itemconfig(box["canvas_id"], fill="", stipple="gray25")

        if self.selected_box and "canvas_id" in self.selected_box:
            self.canvas.itemconfig(
                self.selected_box["canvas_id"], outline=BOX_COLORS["selected"], width=3
            )

        # 绘制选中框的角点
        self._draw_resize_handles()

    def _draw_resize_handles(self):
        """绘制调整大小的角点手柄"""
        # 先清除旧的角点
        self._clear_resize_handles()

        if not self.selected_box:
            return

        x1, y1 = self.to_view_coords(self.selected_box["x1"], self.selected_box["y1"])
        x2, y2 = self.to_view_coords(self.selected_box["x2"], self.selected_box["y2"])

        size = RESIZE_HANDLE_SIZE

        # 四个角点
        handles = {
            "nw": (x1, y1),  # 左上
            "ne": (x2, y1),  # 右上
            "sw": (x1, y2),  # 左下
            "se": (x2, y2),  # 右下
        }

        for key, (hx, hy) in handles.items():
            # 画方块
            rect_id = self.canvas.create_rectangle(
                hx - size,
                hy - size,
                hx + size,
                hy + size,
                fill="#3B8ED0",
                outline="white",
                width=1,
            )
            self.canvas.tag_bind(
                rect_id, "<Button-1>", lambda e, h=key: self._on_handle_click(e, h)
            )
            self.resize_handles[key] = rect_id

    def _clear_resize_handles(self):
        """清除角点手柄"""
        for handle_id in self.resize_handles.values():
            self.canvas.delete(handle_id)
        self.resize_handles = {}

    def _on_handle_click(self, event, handle):
        """点击角点手柄"""
        self.is_resizing = True
        self.resize_handle = handle
        self.resize_start = {
            "x1": self.selected_box["x1"],
            "y1": self.selected_box["y1"],
            "x2": self.selected_box["x2"],
            "y2": self.selected_box["y2"],
        }
        self.drag_start = (event.x, event.y)
        # 停止普通拖拽
        self.is_dragging = False

    def _get_handle_at(self, x, y):
        """检测鼠标位置是否在某个角点上"""
        if not self.selected_box:
            return None

        x1, y1 = self.to_view_coords(self.selected_box["x1"], self.selected_box["y1"])
        x2, y2 = self.to_view_coords(self.selected_box["x2"], self.selected_box["y2"])

        check_size = RESIZE_CURSOR_SIZE

        handles = {
            "nw": (x1, y1),
            "ne": (x2, y1),
            "sw": (x1, y2),
            "se": (x2, y2),
        }

        for key, (hx, hy) in handles.items():
            if abs(x - hx) <= check_size and abs(y - hy) <= check_size:
                return key
        return None

    def _update_cursor(self, event):
        """根据鼠标位置更新光标"""
        handle = self._get_handle_at(event.x, event.y)
        if handle:
            cursors = {
                "nw": "size_nw_se",
                "ne": "size_ne_sw",
                "sw": "size_ne_sw",
                "se": "size_nw_se",
            }
            self.canvas.configure(cursor=cursors.get(handle, ""))
        elif self.tool_mode == "draw":
            self.canvas.configure(cursor="crosshair")
        else:
            self.canvas.configure(cursor="")

    # ==================== 坐标转换 ====================

    def to_page_coords(self, view_x, view_y):
        """视图坐标转原始页面坐标"""
        return (int(view_x / self.scale), int(view_y / self.scale))

    def to_view_coords(self, page_x, page_y):
        """原始页面坐标转视图坐标"""
        return (int(page_x * self.scale), int(page_y * self.scale))

    # ==================== 事件绑定 ====================

    def _bind_events(self):
        """绑定鼠标事件"""
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Delete>", self._on_delete)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<Motion>", self._on_mouse_move)  # 添加鼠标移动事件

    def _on_mousewheel(self, event):
        """鼠标滚轮缩放"""
        delta = event.delta
        if delta == 0:
            delta = 120 if event.num == 4 else -120
        if delta > 0:
            self.zoom_in(self.wheel_zoom_step)
        else:
            self.zoom_out(self.wheel_zoom_step)

    def _on_mouse_move(self, event):
        """鼠标移动 - 更新光标"""
        if not self.is_resizing and not self.is_dragging:
            self._update_cursor(event)

    def _on_handle_click(self, event, handle):
        """点击角点手柄"""
        self.is_resizing = True
        self.resize_handle = handle
        self.resize_start = {
            "x1": self.selected_box["x1"],
            "y1": self.selected_box["y1"],
            "x2": self.selected_box["x2"],
            "y2": self.selected_box["y2"],
        }
        self.drag_start = (event.x, event.y)
        self.is_dragging = False  # 停止普通拖拽

    def _on_mouse_down(self, event):
        """鼠标按下"""
        # 先检查是否点击了角点
        if self.selected_box:
            handle = self._get_handle_at(event.x, event.y)
            if handle:
                self._on_handle_click(event, handle)
                return

        clicked_box = self._get_box_at(event.x, event.y)

        if self.tool_mode == "draw":
            self.is_drawing = True
            self.drag_start = (event.x, event.y)
            self.draw_rect_id = self.canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline=BOX_COLORS["selected"],
                width=2,
            )
        else:
            if clicked_box:
                if event.state & 0x4:
                    self._toggle_select_box(clicked_box)
                else:
                    self._select_box(clicked_box)
                self.is_dragging = True
                self.drag_start = (event.x, event.y)
            else:
                self.is_selecting = True
                self.drag_start = (event.x, event.y)
                self.select_rect_id = self.canvas.create_rectangle(
                    event.x,
                    event.y,
                    event.x,
                    event.y,
                    outline="#00AAFF",
                    dash=(4, 2),
                    width=2,
                )
                self._clear_selection()

    def _on_mouse_drag(self, event):
        """鼠标拖动"""
        if self.is_resizing and self.selected_box and self.resize_handle:
            # 角点调整大小
            x_page, y_page = self.to_page_coords(event.x, event.y)
            handle = self.resize_handle
            rs = self.resize_start

            if handle == "nw":  # 左上角
                self.selected_box["x1"] = min(x_page, rs["x2"] - 10)
                self.selected_box["y1"] = min(y_page, rs["y2"] - 10)
            elif handle == "ne":  # 右上角
                self.selected_box["x2"] = max(x_page, rs["x1"] + 10)
                self.selected_box["y1"] = min(y_page, rs["y2"] - 10)
            elif handle == "sw":  # 左下角
                self.selected_box["x1"] = min(x_page, rs["x2"] - 10)
                self.selected_box["y2"] = max(y_page, rs["y1"] + 10)
            elif handle == "se":  # 右下角
                self.selected_box["x2"] = max(x_page, rs["x1"] + 10)
                self.selected_box["y2"] = max(y_page, rs["y1"] + 10)

            # 更新框和角点
            self.canvas.coords(
                self.selected_box_id,
                self.selected_box["x1"] * self.scale,
                self.selected_box["y1"] * self.scale,
                self.selected_box["x2"] * self.scale,
                self.selected_box["y2"] * self.scale,
            )
            self._draw_resize_handles()

        elif self.is_drawing and self.draw_rect_id:
            self.canvas.coords(
                self.draw_rect_id,
                self.drag_start[0],
                self.drag_start[1],
                event.x,
                event.y,
            )
        elif self.is_selecting and self.select_rect_id:
            self.canvas.coords(
                self.select_rect_id,
                self.drag_start[0],
                self.drag_start[1],
                event.x,
                event.y,
            )
        elif self.is_dragging:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            dx_page = dx / self.scale
            dy_page = dy / self.scale

            if self.selected_boxes:
                for item in self.selected_boxes:
                    box = item["box"]
                    box["x1"] += dx_page
                    box["y1"] += dy_page
                    box["x2"] += dx_page
                    box["y2"] += dy_page
                    self.canvas.coords(
                        item["canvas_id"],
                        box["x1"] * self.scale,
                        box["y1"] * self.scale,
                        box["x2"] * self.scale,
                        box["y2"] * self.scale,
                    )
            elif self.selected_box and self.selected_box_id:
                self.selected_box["x1"] += dx_page
                self.selected_box["y1"] += dy_page
                self.selected_box["x2"] += dx_page
                self.selected_box["y2"] += dy_page
                self.canvas.coords(
                    self.selected_box_id,
                    self.selected_box["x1"] * self.scale,
                    self.selected_box["y1"] * self.scale,
                    self.selected_box["x2"] * self.scale,
                    self.selected_box["y2"] * self.scale,
                )

            self.drag_start = (event.x, event.y)

    def _on_mouse_up(self, event):
        """鼠标释放"""
        # 角点调整结束
        if self.is_resizing:
            self.is_resizing = False
            self.resize_handle = None
            self.resize_start = None
            # 通知框列表更新
            if hasattr(self, "_on_boxes_changed") and self._on_boxes_changed:
                self._on_boxes_changed()
            return

        if self.is_selecting and self.select_rect_id:
            x1, y1 = self.drag_start
            x2, y2 = event.x, event.y
            self.canvas.delete(self.select_rect_id)
            self.select_rect_id = None
            x1_p, y1_p = self.to_page_coords(min(x1, x2), min(y1, y2))
            x2_p, y2_p = self.to_page_coords(max(x1, x2), max(y1, y2))
            self._select_boxes_in_region(x1_p, y1_p, x2_p, y2_p)
            self.is_selecting = False

        elif self.is_drawing:
            x1, y1 = self.drag_start
            x2, y2 = event.x, event.y
            if self.draw_rect_id:
                self.canvas.delete(self.draw_rect_id)

            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
                x1_orig, y1_orig = self.to_page_coords(min(x1, x2), min(y1, y2))
                x2_orig, y2_orig = self.to_page_coords(max(x1, x2), max(y1, y2))

                box = {
                    "x1": x1_orig,
                    "y1": y1_orig,
                    "x2": x2_orig,
                    "y2": y2_orig,
                    "text": "",
                    "processed": False,
                }
                self.boxes.append(box)
                rect_id = self.canvas.create_rectangle(
                    x1_orig * self.scale,
                    y1_orig * self.scale,
                    x2_orig * self.scale,
                    y2_orig * self.scale,
                    outline=BOX_COLORS["normal"],
                    width=2,
                )
                box["id"] = rect_id
                box["canvas_id"] = rect_id
                self._select_box(box)

                # 通知主应用有新框添加（手动绘制需要自动OCR）
                box_index = len(self.boxes) - 1
                if self.on_box_added:
                    self.on_box_added(box_index, auto_ocr=True)

        self.is_drawing = False
        self.is_dragging = False
        self.drag_start = None

    def _on_double_click(self, event):
        """双击编辑框"""
        if self.selected_box:
            self.canvas.event_generate("<<EditBox>>", when="tail")

    def _on_delete(self, event=None):
        """删除选中框"""
        self._delete_selected_boxes()

    def _on_right_click(self, event):
        """右键菜单"""
        clicked_box = self._get_box_at(event.x, event.y)
        if clicked_box:
            self._select_box(clicked_box)
            self._show_context_menu(event)

    def _show_context_menu(self, event):
        """显示右键菜单"""
        menu = tk.Menu(self.canvas, tearoff=0)
        has_selection = self.selected_box or self.selected_boxes
        has_multi = len(self.selected_boxes) > 1

        if has_selection:
            if has_multi:
                menu.add_command(
                    label=f"删除 ({len(self.selected_boxes)} 个)",
                    command=self._delete_selected_boxes,
                )
                menu.add_separator()
            else:
                menu.add_command(label="编辑内容", command=self._edit_selected_box)
                menu.add_command(label="删除", command=self._delete_selected_boxes)
                menu.add_separator()

        menu.add_command(label="拖动空白：框选多个", state="disabled")
        menu.add_command(label="Shift+点击：加选/减选", state="disabled")
        menu.add_separator()
        menu.add_command(label="清空所有", command=self._clear_all)
        menu.post(event.x_root, event.y_root)

    def _edit_selected_box(self):
        if self.selected_box:
            self.canvas.event_generate("<<EditBox>>", when="tail")

    def _clear_all(self):
        for box in self.boxes:
            if box.get("canvas_id"):
                self.canvas.delete(box["canvas_id"])
        self.boxes.clear()
        self.selected_box = None
        self.selected_box_id = None
        self._clear_resize_handles()  # 清除角点
        if self.on_clear:
            self.on_clear()

    # ==================== 框操作 ====================

    def _get_box_at(self, view_x, view_y):
        """获取指定坐标的框"""
        page_x, page_y = self.to_page_coords(view_x, view_y)
        for box in self.boxes:
            if min(box["x1"], box["x2"]) <= page_x <= max(box["x1"], box["x2"]) and min(
                box["y1"], box["y2"]
            ) <= page_y <= max(box["y1"], box["y2"]):
                return box
        return None

    def _select_box(self, box):
        if self.selected_box and self.selected_box_id:
            color = (
                BOX_COLORS["processed"]
                if self.selected_box["processed"]
                else BOX_COLORS["normal"]
            )
            self.canvas.itemconfig(self.selected_box_id, outline=color, width=2)

        self.selected_box = box
        self.selected_box_id = box["canvas_id"]
        self.canvas.itemconfig(
            self.selected_box_id, outline=BOX_COLORS["selected"], width=3
        )

        # 绘制角点
        self._draw_resize_handles()

    def _unselect_box(self):
        if self.selected_box and self.selected_box_id:
            color = (
                BOX_COLORS["processed"]
                if self.selected_box["processed"]
                else BOX_COLORS["normal"]
            )
            self.canvas.itemconfig(self.selected_box_id, outline=color, width=2)
        self.selected_box = None
        self.selected_box_id = None
        self._clear_resize_handles()  # 清除角点

    def _clear_selection(self):
        self._unselect_box()
        for item in self.selected_boxes:
            box = item["box"]
            color = (
                BOX_COLORS["processed"]
                if box.get("processed")
                else BOX_COLORS["normal"]
            )
            self.canvas.itemconfig(item["canvas_id"], outline=color, width=2)
        self.selected_boxes = []

    def _toggle_select_box(self, box):
        if not box or not box.get("canvas_id"):
            return
        for item in self.selected_boxes:
            if item["box"] == box:
                color = (
                    BOX_COLORS["processed"]
                    if box.get("processed")
                    else BOX_COLORS["normal"]
                )
                self.canvas.itemconfig(box["canvas_id"], outline=color, width=2)
                self.selected_boxes.remove(item)
                return
        self.canvas.itemconfig(
            box["canvas_id"], outline=BOX_COLORS["selected"], width=3
        )
        self.selected_boxes.append({"box": box, "canvas_id": box["canvas_id"]})

    def _select_boxes_in_region(self, x1, y1, x2, y2):
        self._clear_selection()
        for box in self.boxes:
            if not box.get("canvas_id"):
                continue
            if box["x1"] < x2 and box["x2"] > x1 and box["y1"] < y2 and box["y2"] > y1:
                self.canvas.itemconfig(
                    box["canvas_id"], outline=BOX_COLORS["selected"], width=3
                )
                self.selected_boxes.append({"box": box, "canvas_id": box["canvas_id"]})

    def _delete_selected_boxes(self):
        if not self.selected_boxes:
            if self.selected_box:
                self._delete_single_box(self.selected_box)
            return
        for item in self.selected_boxes:
            if item["canvas_id"]:
                self.canvas.delete(item["canvas_id"])
            if item["box"] in self.boxes:
                self.boxes.remove(item["box"])
        self.selected_boxes = []
        self.selected_box = None
        if self.on_box_deleted:
            self.on_box_deleted()

    def _delete_single_box(self, box):
        if box.get("canvas_id"):
            self.canvas.delete(box["canvas_id"])
        if box in self.boxes:
            self.boxes.remove(box)
        if self.selected_box == box:
            self.selected_box = None
            self.selected_box_id = None
        if self.on_box_deleted:
            self.on_box_deleted()

    def delete_box(self, index):
        if 0 <= index < len(self.boxes):
            box = self.boxes[index]
            if box.get("canvas_id"):
                self.canvas.delete(box["canvas_id"])
            self.boxes.pop(index)
            if self.selected_box == box:
                self._unselect_box()

    def clear_all_boxes(self):
        for box in self.boxes:
            if box.get("canvas_id"):
                self.canvas.delete(box["canvas_id"])
        self.boxes.clear()
        self._unselect_box()
        if self.on_clear:
            self.on_clear()

    def mark_processed(self, index, text, model_name=None):
        if 0 <= index < len(self.boxes):
            box = self.boxes[index]
            box["text"] = text
            box["processed"] = True
            box["ocr_source"] = "llm"
            if model_name:
                box["ocr_model"] = model_name
            if box.get("canvas_id"):
                self.canvas.itemconfig(
                    box["canvas_id"], outline=BOX_COLORS["processed"]
                )

    def mark_applied(self, index):
        if 0 <= index < len(self.boxes):
            box = self.boxes[index]
            box["applied_to_indesign"] = True
            if box.get("canvas_id"):
                self.canvas.itemconfig(box["canvas_id"], outline=BOX_COLORS["applied"])

    def get_boxes(self):
        return self.boxes

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)
