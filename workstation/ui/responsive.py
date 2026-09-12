"""
响应式尺寸引擎

根据窗口尺寸自动计算缩放因子，提供统一的尺寸计算接口。
设计 5 档断点，确保在所有屏幕尺寸下 UI 协调一致。

断点系统:
    xs:  < 900px   (最小窗口)     scale=0.78
    sm:  900-1200  (小窗口)       scale=0.88
    md:  1200-1600 (标准桌面)     scale=1.0
    lg:  1600-2100 (大屏桌面)     scale=1.12
    xl:  > 2100px  (超大屏/4K)    scale=1.28

缩放影响: 字体大小、间距、圆角、侧边栏宽度、工具栏高度等
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Breakpoint:
    """响应式断点定义"""
    min_width: int
    max_width: int
    scale: float
    label: str


# 5 档响应式断点
BREAKPOINTS = [
    Breakpoint(0,     899,  0.78, "xs"),
    Breakpoint(900,   1199, 0.88, "sm"),
    Breakpoint(1200,  1599, 1.00, "md"),
    Breakpoint(1600,  2099, 1.12, "lg"),
    Breakpoint(2100,  99999,1.28, "xl"),
]


class ResponsiveEngine:
    """
    响应式尺寸计算引擎。

    使用方式:
        engine = ResponsiveEngine()
        engine.update(1400, 900)       # 根据窗口尺寸更新断点
        font_sm = engine.scaled(12)     # 返回缩放后的值
        sidebar_w = engine.sidebar_width()

    缩放规则: base_value * scale_factor，结果四舍五入取整。
    """

    def __init__(self):
        self._width: int = 1280
        self._height: int = 800
        self._scale: float = 1.0
        self._breakpoint_label: str = "md"
        self._dirty: bool = True
        self._update_bp()

    def update(self, width: int, height: int):
        """更新窗口尺寸并重新计算断点"""
        if width == self._width and height == self._height:
            return False  # 无变化
        self._width = width
        self._height = height
        self._update_bp()
        self._dirty = True
        return True

    def _update_bp(self):
        """根据当前宽度匹配断点"""
        for bp in BREAKPOINTS:
            if bp.min_width <= self._width <= bp.max_width:
                # 在断点范围内做平滑插值
                self._scale = self._smooth_scale(bp)
                self._breakpoint_label = bp.label
                return

    def _smooth_scale(self, bp: Breakpoint) -> float:
        """在断点范围内平滑缩放（可选，目前用固定值 + 微调）"""
        range_width = bp.max_width - bp.min_width
        if range_width <= 0:
            return bp.scale

        # 在当前断点内的比例位置
        progress = (self._width - bp.min_width) / range_width

        # 使用前后断点做线性插值
        idx = next((i for i, b in enumerate(BREAKPOINTS) if b.label == bp.label), 2)
        if idx < len(BREAKPOINTS) - 1:
            next_bp = BREAKPOINTS[idx + 1]
            return bp.scale + (next_bp.scale - bp.scale) * progress * 0.5
        return bp.scale + 0.02 * progress

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def breakpoint_label(self) -> str:
        return self._breakpoint_label

    @property
    def is_compact(self) -> bool:
        """是否为紧凑模式（小窗口）"""
        return self._breakpoint_label in ("xs", "sm")

    @property
    def is_wide(self) -> bool:
        """是否为大屏模式"""
        return self._breakpoint_label in ("lg", "xl")

    # ========== 尺寸计算方法 ==========

    def scaled(self, base_value: float) -> float:
        """按当前缩放因子计算尺寸"""
        return base_value * self._scale

    def scaled_int(self, base_value: float) -> int:
        """按当前缩放因子计算尺寸（取整）"""
        return max(1, round(base_value * self._scale))

    def scaled_str(self, base_value: float, unit: str = "px") -> str:
        """按当前缩放因子计算尺寸（返回字符串）"""
        return f"{self.scaled_int(base_value)}{unit}"

    def font_size(self, base_size: int) -> int:
        """计算字体大小（有最小限制）"""
        return max(8, self.scaled_int(base_size))

    # ========== 组件级尺寸 ==========

    def sidebar_width(self) -> int:
        return self.scaled_int(240)

    def sidebar_collapsed_width(self) -> int:
        return self.scaled_int(56)

    def toolbar_height(self) -> int:
        return self.scaled_int(44)

    def status_bar_height(self) -> int:
        return max(22, self.scaled_int(28))

    def sidebar_item_height(self) -> int:
        return self.scaled_int(40)

    def spacing(self, base: int = 8) -> int:
        return max(2, self.scaled_int(base))

    def border_radius(self, base: int = 6) -> int:
        return max(2, self.scaled_int(base))

    # ========== 尺寸字典（供 QSS 模板使用） ==========

    def get_sizes(self) -> dict:
        """返回缩放后的尺寸字典，用于 QSS 模板替换"""
        return {
            "toolbar_height":      self.toolbar_height(),
            "toolbar_icon_size":   self.scaled_int(22),
            "status_bar_height":   self.status_bar_height(),
            "sidebar_width":       self.sidebar_width(),
            "sidebar_collapsed_width": self.sidebar_collapsed_width(),
            "sidebar_item_height": self.sidebar_item_height(),
            "border_radius_sm":    self.border_radius(4),
            "border_radius_md":    self.border_radius(6),
            "border_radius_lg":    self.border_radius(10),
            "font_size_sm":        self.font_size(11),
            "font_size_md":        self.font_size(13),
            "font_size_lg":        self.font_size(15),
            "font_size_xl":        self.font_size(18),
            "spacing_xs":          self.spacing(4),
            "spacing_sm":          self.spacing(8),
            "spacing_md":          self.spacing(12),
            "spacing_lg":          self.spacing(16),
            "spacing_xl":          self.spacing(24),
        }

    def get_scale_info(self) -> dict:
        """获取当前缩放信息（用于调试/状态栏）"""
        return {
            "width": self._width,
            "height": self._height,
            "scale": round(self._scale, 2),
            "breakpoint": self._breakpoint_label,
        }


# 全局单例
_engine: ResponsiveEngine | None = None


def get_responsive_engine() -> ResponsiveEngine:
    """获取全局响应式引擎单例"""
    global _engine
    if _engine is None:
        _engine = ResponsiveEngine()
    return _engine
