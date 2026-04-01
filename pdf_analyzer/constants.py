"""
常量配置
"""

import customtkinter as ctk

# 外观设置
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 框颜色配置
BOX_COLORS = {
    "selected": "#3B8ED0",
    "normal": "#FF6B6B",
    "hover": "#FFE66D",
    "processed": "#4ECDC4",
    "applied": "#8B5CF6",
}

# 角点调整配置
RESIZE_HANDLE_SIZE = 8  # 角点大小（像素）
RESIZE_CURSOR_SIZE = 6  # 检测范围扩展

# 缩放配置
MIN_SCALE = 0.1
MAX_SCALE = 5.0
WHEEL_ZOOM_STEP = 0.1
DEFAULT_ZOOM_STEP = 0.1

# UI配置
INFO_PANEL_WIDTH = 280
MAIN_WINDOW_SIZE = "1200x800"
