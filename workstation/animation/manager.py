"""
动画管理器

统一管理应用中所有动画效果，提供：
- 动画队列管理
- 预设动画模板
- 动画执行状态追踪
- 全局动画开关
"""

from typing import Optional, Callable, List
from enum import Enum

from PySide6.QtCore import (
    QObject, QPropertyAnimation, QEasingCurve, QPoint, QSize,
    QRect, QParallelAnimationGroup, QSequentialAnimationGroup,
    QAbstractAnimation, Signal, QTimer
)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect


class EasingType(Enum):
    """缓动函数类型"""
    LINEAR = QEasingCurve.Type.Linear
    IN_QUAD = QEasingCurve.Type.InQuad
    OUT_QUAD = QEasingCurve.Type.OutQuad
    IN_OUT_QUAD = QEasingCurve.Type.InOutQuad
    IN_CUBIC = QEasingCurve.Type.InCubic
    OUT_CUBIC = QEasingCurve.Type.OutCubic
    IN_OUT_CUBIC = QEasingCurve.Type.InOutCubic
    IN_QUART = QEasingCurve.Type.InQuart
    OUT_QUART = QEasingCurve.Type.OutQuart
    IN_OUT_QUART = QEasingCurve.Type.InOutQuart
    IN_EXPO = QEasingCurve.Type.InExpo
    OUT_EXPO = QEasingCurve.Type.OutExpo
    OUT_BACK = QEasingCurve.Type.OutBack


class AnimationManager(QObject):
    """
    动画管理器。

    提供统一接口创建和管理各类 UI 动画，
    包括淡入淡出、滑动、缩放、宽度变化等。

    使用方式:
        mgr = AnimationManager()
        mgr.fade_in(widget)
        mgr.slide_in(widget, direction="left")
    """

    animation_completed = Signal(str)
    """动画完成信号，携带动画标识"""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._enabled = True
        self._active_animations: List[QAbstractAnimation] = []
        self._default_duration = 250  # ms
        self._default_easing = EasingType.OUT_CUBIC

    # ========== 全局控制 ==========

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def stop_all(self):
        """停止所有活跃动画"""
        for anim in self._active_animations[:]:
            anim.stop()
        self._active_animations.clear()

    # ========== 透明度动画 ==========

    def fade_in(self, widget: QWidget, duration: int = None,
                easing: EasingType = None, callback: Callable = None):
        """淡入效果：透明度 0 → 1"""
        self._ensure_opacity_effect(widget)
        self._animate_opacity(widget, 0.0, 1.0, duration, easing, callback)

    def fade_out(self, widget: QWidget, duration: int = None,
                 easing: EasingType = None, callback: Callable = None):
        """淡出效果：透明度 1 → 0"""
        self._ensure_opacity_effect(widget)
        self._animate_opacity(widget, self.get_opacity(widget), 0.0, duration, easing, callback)

    def fade_to(self, widget: QWidget, target_opacity: float,
                duration: int = None, easing: EasingType = None,
                callback: Callable = None):
        """渐变到指定透明度"""
        self._ensure_opacity_effect(widget)
        current = self.get_opacity(widget)
        self._animate_opacity(widget, current, target_opacity, duration, easing, callback)

    # ========== 几何动画 ==========

    def slide_in(self, widget: QWidget, direction: str = "left",
                 distance: int = None, duration: int = None,
                 easing: EasingType = None, callback: Callable = None):
        """
        滑入效果。

        Args:
            widget: 目标控件
            direction: 方向 "left" | "right" | "top" | "bottom"
            distance: 滑动距离，None=控件自身宽度/高度
            duration: 动画时长
        """
        if direction == "left":
            self._slide_horizontal(widget, -distance, 0, duration, easing, callback)
        elif direction == "right":
            self._slide_horizontal(widget, distance if distance else widget.width(), 0, duration, easing, callback)
        elif direction == "top":
            self._slide_vertical(widget, -distance, 0, duration, easing, callback)
        elif direction == "bottom":
            self._slide_vertical(widget, distance if distance else widget.height(), 0, duration, easing, callback)

    def slide_out(self, widget: QWidget, direction: str = "right",
                  distance: int = None, duration: int = None,
                  easing: EasingType = None, callback: Callable = None):
        """滑出效果"""
        if direction == "left":
            self._slide_horizontal(widget, 0, -distance, duration, easing, callback)
        elif direction == "right":
            self._slide_horizontal(widget, 0, distance if distance else widget.width(), duration, easing, callback)
        elif direction == "top":
            self._slide_vertical(widget, 0, -distance, duration, easing, callback)
        elif direction == "bottom":
            self._slide_vertical(widget, 0, distance if distance else widget.height(), duration, easing, callback)

    def expand_width(self, widget: QWidget, target_width: int,
                     duration: int = None, easing: EasingType = None,
                     callback: Callable = None):
        """宽度变化动画（用于侧边栏展开/收起）"""
        self._animate_property(widget, b"maximumWidth", widget.width(),
                               target_width, duration, easing, callback)

    # ========== 页面切换动画 ==========

    def page_transition(self, current_widget: QWidget, next_widget: QWidget,
                        direction: str = "right", duration: int = None,
                        callback: Callable = None):
        """
        页面切换动画：当前页滑出 + 新页滑入。

        Args:
            direction: 滑动方向，"right"=向左滑
        """
        dur = duration or 300

        group = QParallelAnimationGroup(self)

        # 当前页淡出 + 滑出
        self._ensure_opacity_effect(current_widget)
        fade_out = self._create_opacity_anim(current_widget, 1.0, 0.0, dur)
        fade_out.setEasingCurve(QEasingCurve(EasingType.OUT_CUBIC.value))

        # 新页淡入 + 滑入
        self._ensure_opacity_effect(next_widget)
        self.set_opacity(next_widget, 0.0)
        next_widget.show()
        fade_in_anim = self._create_opacity_anim(next_widget, 0.0, 1.0, dur)
        fade_in_anim.setEasingCurve(QEasingCurve(EasingType.OUT_CUBIC.value))

        group.addAnimation(fade_out)
        group.addAnimation(fade_in_anim)

        def on_finish():
            current_widget.hide()
            self.set_opacity(current_widget, 1.0)
            if callback:
                callback()

        group.finished.connect(on_finish)
        self._track_and_start(group, f"page_transition_{id(current_widget)}")

    # ========== 内部方法 ==========

    def _ensure_opacity_effect(self, widget: QWidget):
        """确保控件有透明度效果对象"""
        if not hasattr(widget, '_opacity_effect') or widget._opacity_effect is None:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(1.0)
            widget.setGraphicsEffect(effect)
            widget._opacity_effect = effect

    def get_opacity(self, widget: QWidget) -> float:
        """获取控件当前透明度"""
        if hasattr(widget, '_opacity_effect') and widget._opacity_effect:
            return widget._opacity_effect.opacity()
        return 1.0

    def set_opacity(self, widget: QWidget, opacity: float):
        """设置控件透明度"""
        self._ensure_opacity_effect(widget)
        widget._opacity_effect.setOpacity(max(0.0, min(1.0, opacity)))

    def _animate_opacity(self, widget: QWidget, start: float, end: float,
                         duration: int = None, easing: EasingType = None,
                         callback: Callable = None):
        anim = self._create_opacity_anim(widget, start, end, duration, easing, callback)
        self._track_and_start(anim, f"opacity_{id(widget)}")

    def _create_opacity_anim(self, widget: QWidget, start: float, end: float,
                             duration: int = None, easing: EasingType = None,
                             callback: Callable = None) -> QPropertyAnimation:
        """创建透明度动画（返回动画对象，不自动启动）"""
        self._ensure_opacity_effect(widget)
        anim = QPropertyAnimation(widget._opacity_effect, b"opacity", self)
        anim.setDuration(duration or self._default_duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve((easing or self._default_easing).value))
        if callback:
            anim.finished.connect(callback)
        return anim

    def _animate_property(self, target: QObject, property_name: bytes,
                          start_val, end_val,
                          duration: int = None, easing: EasingType = None,
                          callback: Callable = None):
        """通用属性动画"""
        if not self._enabled:
            target.setProperty(property_name, end_val)
            if callback:
                callback()
            return

        anim = QPropertyAnimation(target, property_name, self)
        anim.setDuration(duration or self._default_duration)
        anim.setStartValue(start_val)
        anim.setEndValue(end_val)
        anim.setEasingCurve(QEasingCurve((easing or self._default_easing).value))
        if callback:
            anim.finished.connect(callback)
        self._track_and_start(anim, f"prop_{property_name.decode()}_{id(target)}")

    def _slide_horizontal(self, widget: QWidget, start_offset: int,
                          end_offset: int, duration: int = None,
                          easing: EasingType = None, callback: Callable = None):
        """水平滑动"""
        if not self._enabled:
            widget.move(widget.x() + end_offset, widget.y())
            if callback:
                callback()
            return

        start_pos = widget.pos() + QPoint(start_offset or -widget.width(), 0)
        end_pos = widget.pos() + QPoint(end_offset or 0, 0)

        anim = QPropertyAnimation(widget, b"pos", self)
        anim.setDuration(duration or self._default_duration)
        anim.setStartValue(start_pos)
        anim.setEndValue(end_pos)
        anim.setEasingCurve(QEasingCurve((easing or self._default_easing).value))
        if callback:
            anim.finished.connect(callback)
        self._track_and_start(anim, f"slide_h_{id(widget)}")

    def _slide_vertical(self, widget: QWidget, start_offset: int,
                        end_offset: int, duration: int = None,
                        easing: EasingType = None, callback: Callable = None):
        """垂直滑动"""
        if not self._enabled:
            widget.move(widget.x(), widget.y() + end_offset)
            if callback:
                callback()
            return

        start_pos = widget.pos() + QPoint(0, start_offset or -widget.height())
        end_pos = widget.pos() + QPoint(0, end_offset or 0)

        anim = QPropertyAnimation(widget, b"pos", self)
        anim.setDuration(duration or self._default_duration)
        anim.setStartValue(start_pos)
        anim.setEndValue(end_pos)
        anim.setEasingCurve(QEasingCurve((easing or self._default_easing).value))
        if callback:
            anim.finished.connect(callback)
        self._track_and_start(anim, f"slide_v_{id(widget)}")

    def _track_and_start(self, anim: QAbstractAnimation, anim_id: str):
        """追踪并启动动画"""
        # 清理已完成的动画
        self._active_animations = [a for a in self._active_animations
                                   if a.state() == QAbstractAnimation.State.Running]
        self._active_animations.append(anim)

        def on_finished():
            self.animation_completed.emit(anim_id)
            if anim in self._active_animations:
                self._active_animations.remove(anim)

        anim.finished.connect(on_finished)
        anim.start()
