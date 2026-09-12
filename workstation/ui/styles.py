"""
全局 QSS 样式表

采用暗色主题设计，定义统一的视觉风格。
支持响应式缩放——通过传入缩放后的尺寸字典动态调整 UI。

色彩和字体不随窗口缩放，尺寸（字体大小/间距/圆角）会动态调整。
"""

# ============================================================
# 色彩系统（不缩放）— 现代深色主题，层次分明
# ============================================================
COLORS = {
    # 背景层次：从深到浅，营造空间感
    "bg_base": "#0f0f1a",          # 最底层（窗口背景）
    "bg_primary": "#161624",        # 主背景
    "bg_secondary": "#1e1e30",      # 卡片/面板背景
    "bg_tertiary": "#262640",       # 悬浮元素背景
    "bg_hover": "#2e2e4a",          # 悬停状态
    "bg_selected": "#353560",       # 选中状态

    # 文字层次
    "fg_primary": "#f0f0fa",        # 主要文字（高对比度）
    "fg_secondary": "#b8b8d4",      # 次要文字
    "fg_tertiary": "#7a7a9e",       # 辅助文字/标签
    "fg_disabled": "#4a4a68",       # 禁用文字

    # 强调色：紫蓝渐变系
    "accent": "#7c6cff",            # 主强调色
    "accent_hover": "#9080ff",      # 悬停强调
    "accent_pressed": "#6858e8",    # 按下强调
    "accent_glow": "rgba(124, 108, 255, 0.15)",  # 强调光晕

    # 语义色
    "success": "#2dd4a7",
    "warning": "#fbbf24",
    "error": "#f87171",
    "info": "#60a5fa",

    # 边框
    "border": "#2a2a44",
    "border_light": "#3a3a5c",
    "border_focus": "#7c6cff",

    # 区域背景
    "toolbar_bg": "#131322",
    "sidebar_bg": "#16162a",
    "status_bar_bg": "#10101e",
    "shadow_color": "rgba(0, 0, 0, 0.5)",
}

# ============================================================
# 默认尺寸（scale=1.0 时的基准值，数字，不带单位）
# ============================================================
DEFAULT_SIZES = {
    "toolbar_height": 44,
    "toolbar_icon_size": 22,
    "status_bar_height": 28,
    "sidebar_width": 240,
    "sidebar_collapsed_width": 56,
    "sidebar_item_height": 40,
    "border_radius_sm": 4,
    "border_radius_md": 6,
    "border_radius_lg": 10,
    "font_size_sm": 11,
    "font_size_md": 13,
    "font_size_lg": 15,
    "font_size_xl": 18,
    "spacing_xs": 4,
    "spacing_sm": 8,
    "spacing_md": 12,
    "spacing_lg": 16,
    "spacing_xl": 24,
}

# ---- 阴影（不缩放） ----
SHADOWS = {
    "panel": f"0px 2px 8px {COLORS['shadow_color']}",
    "dialog": f"0px 4px 16px {COLORS['shadow_color']}",
    "dropdown": f"0px 8px 24px {COLORS['shadow_color']}",
}

FONTS = {
    "default": "Microsoft YaHei UI",
    "code": "Cascadia Code, Consolas, monospace",
    "fallback": "Segoe UI",
}


def build_stylesheet(sizes: dict = None) -> str:
    """
    构建全局 QSS 样式表。

    Args:
        sizes: 缩放后的尺寸字典（值是 int，不含单位）。
               为 None 时使用默认尺寸。

    Returns:
        完整的 QSS 字符串
    """
    s = sizes or DEFAULT_SIZES.copy()

    # 转换为带 px 单位的字符串（QSS 需要）
    px = {k: f"{v}px" for k, v in s.items()}
    c = COLORS

    return f"""
    /* ========== 全局默认 ========== */
    * {{
        font-family: "{FONTS['default']}", "{FONTS['fallback']}";
        outline: none;
    }}

    QMainWindow {{
        background-color: {c['bg_base']};
    }}

    /* ========== 滚动条 — 极简风格 ========== */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 4px 2px 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border_light']};
        border-radius: 3px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0 4px 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border_light']};
        border-radius: 3px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* ========== 工具提示 ========== */
    QToolTip {{
        background-color: {c['bg_tertiary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border_light']};
        border-radius: {px['border_radius_sm']};
        padding: {px['spacing_xs']} {px['spacing_sm']};
        font-size: {px['font_size_sm']};
    }}

    /* ========== 菜单 ========== */
    QMenu {{
        background-color: {c['bg_secondary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border_light']};
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_xs']};
    }}
    QMenu::item {{
        padding: {px['spacing_sm']} {px['spacing_xl']} {px['spacing_sm']} {px['spacing_md']};
        border-radius: {px['border_radius_sm']};
        margin: 2px {px['spacing_xs']};
    }}
    QMenu::item:selected {{
        background-color: {c['accent']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c['border']};
        margin: {px['spacing_xs']} {px['spacing_sm']};
    }}

    /* ========== 按钮 ========== */
    QPushButton {{
        background-color: {c['bg_tertiary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_sm']} {px['spacing_lg']};
        font-size: {px['font_size_md']};
        min-height: 28px;
    }}
    QPushButton:hover {{
        background-color: {c['bg_hover']};
        border-color: {c['border_light']};
    }}
    QPushButton:pressed {{
        background-color: {c['bg_selected']};
        border-color: {c['accent']};
    }}
    QPushButton:disabled {{
        background-color: {c['bg_secondary']};
        color: {c['fg_disabled']};
        border-color: transparent;
    }}

    QPushButton#primaryBtn {{
        background-color: {c['accent']};
        color: #ffffff;
        border: none;
        font-weight: bold;
    }}
    QPushButton#primaryBtn:hover {{ background-color: {c['accent_hover']}; }}
    QPushButton#primaryBtn:pressed {{ background-color: {c['accent_pressed']}; }}

    QPushButton#toolBtn {{
        background: transparent;
        border: none;
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_xs']};
        min-width: 32px;
        min-height: 32px;
        font-size: {px['font_size_lg']};
        color: {c['fg_secondary']};
    }}
    QPushButton#toolBtn:hover {{
        background-color: {c['bg_hover']};
        color: {c['fg_primary']};
    }}
    QPushButton#toolBtn:pressed {{ background-color: {c['bg_selected']}; }}

    /* ========== 输入框 ========== */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {c['bg_primary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_sm']} {px['spacing_sm']};
        font-size: {px['font_size_md']};
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {c['border_focus']};
        background-color: {c['bg_secondary']};
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
        background-color: {c['bg_primary']};
        color: {c['fg_disabled']};
    }}

    /* ========== 标签页 ========== */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_md']};
        background-color: {c['bg_secondary']};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c['fg_secondary']};
        border: 1px solid transparent;
        border-bottom: 2px solid transparent;
        padding: {px['spacing_sm']} {px['spacing_lg']};
        margin-right: 2px;
        font-size: {px['font_size_md']};
        border-top-left-radius: {px['border_radius_sm']};
        border-top-right-radius: {px['border_radius_sm']};
    }}
    QTabBar::tab:hover {{
        background-color: {c['bg_hover']};
        color: {c['fg_primary']};
    }}
    QTabBar::tab:selected {{
        background-color: {c['bg_secondary']};
        color: {c['accent']};
        border-bottom: 2px solid {c['accent']};
    }}

    /* ========== 组合框/下拉 ========== */
    QComboBox {{
        background-color: {c['bg_primary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_sm']} {px['spacing_md']};
        font-size: {px['font_size_md']};
        min-height: 20px;
    }}
    QComboBox:hover {{ border-color: {c['border_light']}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ image: none; border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_secondary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border_light']};
        border-radius: {px['border_radius_md']};
        padding: {px['spacing_xs']};
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: {px['spacing_sm']} {px['spacing_md']};
        border-radius: {px['border_radius_sm']};
        min-height: 24px;
    }}
    QComboBox QAbstractItemView::item:hover {{ background-color: {c['bg_hover']}; }}

    /* ========== 复选框/单选框 ========== */
    QCheckBox, QRadioButton {{
        color: {c['fg_primary']};
        spacing: {px['spacing_sm']};
        font-size: {px['font_size_md']};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 2px solid {c['border_light']};
        border-radius: {px['border_radius_sm']};
        background-color: {c['bg_primary']};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {c['accent']};
    }}

    /* ========== 滑条 ========== */
    QSlider::groove:horizontal {{
        height: 4px; background: {c['border']}; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 16px; height: 16px; margin: -6px 0;
        background: {c['accent']}; border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{ background: {c['accent_hover']}; }}
    QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}

    /* ========== 进度条 ========== */
    QProgressBar {{
        background-color: {c['bg_primary']};
        border: none;
        border-radius: {px['border_radius_sm']};
        height: 6px;
        text-align: center;
        font-size: {px['font_size_sm']};
        color: {c['fg_secondary']};
    }}
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: {px['border_radius_sm']};
    }}

    /* ========== 列表控件 ========== */
    QListWidget, QTreeWidget, QTableWidget {{
        background-color: {c['bg_secondary']};
        color: {c['fg_primary']};
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_md']};
        font-size: {px['font_size_md']};
        outline: none;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: {px['spacing_sm']} {px['spacing_sm']};
        border-radius: {px['border_radius_sm']};
        margin: 1px {px['spacing_xs']};
    }}
    QListWidget::item:hover, QTreeWidget::item:hover {{ background-color: {c['bg_hover']}; }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {c['bg_selected']};
        color: {c['fg_primary']};
    }}
    QHeaderView::section {{
        background-color: {c['bg_tertiary']};
        color: {c['fg_secondary']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: {px['spacing_sm']} {px['spacing_sm']};
        font-size: {px['font_size_sm']};
        font-weight: bold;
    }}

    /* ========== 分组框 ========== */
    QGroupBox {{
        color: {c['fg_primary']};
        font-size: {px['font_size_lg']};
        font-weight: bold;
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_lg']};
        margin-top: 20px;
        padding: {px['spacing_lg']};
        padding-top: {px['spacing_xl']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {px['spacing_lg']};
        padding: 0 {px['spacing_sm']};
    }}

    /* ========== 状态栏 ========== */
    QStatusBar {{
        background-color: {c['status_bar_bg']};
        color: {c['fg_secondary']};
        border-top: 1px solid {c['border']};
        font-size: {px['font_size_sm']};
        padding: 2px {px['spacing_sm']};
    }}
    QStatusBar QLabel {{
        color: {c['fg_tertiary']};
    }}
    QStatusBar QLabel#perfLabel {{
        color: {c['fg_secondary']};
    }}

    /* ========== 工具栏 ========== */
    QToolBar {{
        background-color: {c['toolbar_bg']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: {px['spacing_xs']} {px['spacing_sm']};
        spacing: {px['spacing_sm']};
    }}

    /* ========== Dock 控件 ========== */
    QDockWidget {{
        color: {c['fg_primary']};
        titlebar-close-icon: none;
    }}
    QDockWidget::title {{
        background-color: {c['bg_tertiary']};
        padding: {px['spacing_sm']} {px['spacing_md']};
        border-bottom: 1px solid {c['border']};
    }}

    /* ========== 卡片效果样式 ========== */
    QFrame#cardFrame {{
        background-color: {c['bg_secondary']};
        border: 1px solid {c['border']};
        border-radius: {px['border_radius_lg']};
    }}

    /* ========== 侧边栏 — 现代导航设计 ========== */
    QFrame#sidebarFrame {{
        background-color: {c['sidebar_bg']};
        border: none;
        border-right: 1px solid {c['border']};
    }}

    QPushButton#sidebarItem {{
        background: transparent;
        color: {c['fg_secondary']};
        border: none;
        border-radius: {px['border_radius_md']};
        text-align: left;
        padding: 0 {px['spacing_md']};
        height: {px['sidebar_item_height']};
        font-size: {px['font_size_sm']};
        margin: 2px {px['spacing_sm']};
    }}
    QPushButton#sidebarItem:hover {{
        background-color: {c['bg_hover']};
        color: {c['fg_primary']};
    }}
    QPushButton#sidebarItem:checked {{
        background-color: {c['accent_glow']};
        color: {c['accent']};
        font-weight: bold;
        border-left: 3px solid {c['accent']};
    }}

    QLabel#sidebarCategory {{
        color: {c['fg_tertiary']};
        font-size: 10px;
        font-weight: bold;
        padding: {px['spacing_md']} {px['spacing_lg']} {px['spacing_xs']} {px['spacing_lg']};
        letter-spacing: 1.5px;
    }}

    QLabel#sidebarHeader {{
        color: {c['fg_primary']};
        font-size: {px['font_size_lg']};
        font-weight: bold;
        padding: {px['spacing_md']} {px['spacing_lg']};
    }}

    /* ========== 内容区域 ========== */
    QFrame#contentFrame {{
        background-color: {c['bg_primary']};
        border: none;
    }}

    /* ========== 空白状态 ========== */
    QLabel#emptyStateTitle {{
        color: {c['fg_primary']};
        font-size: {px['font_size_xl']};
        font-weight: bold;
    }}
    QLabel#emptyStateSubtitle {{
        color: {c['fg_secondary']};
        font-size: {px['font_size_md']};
    }}

    /* ========== 标题标签 ========== */
    QLabel#pageTitle {{
        color: {c['fg_primary']};
        font-size: {px['font_size_lg']};
        font-weight: bold;
    }}

    /* ========== 分割面板 ========== */
    QSplitter::handle {{
        background-color: {c['border']};
        width: 1px;
    }}
    QSplitter::handle:hover {{
        background-color: {c['accent']};
    }}

    /* ========== 工具特定样式占位 ========== */
    QWidget#toolContainer {{
        background-color: {c['bg_primary']};
    }}
    """
