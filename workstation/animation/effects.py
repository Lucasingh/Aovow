"""
预设动画效果

提供常用的组合动画效果，方便各模块直接调用。
"""

from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup


class AnimationEffects:
    """静态动画效果工厂"""

    @staticmethod
    def button_hover(button: QWidget, enter: bool, duration: int = 150):
        """按钮悬停缩放效果"""
        target = 1.03 if enter else 1.0
        anim = QPropertyAnimation(button, b"transform")
        # 使用 graphics effect 实现缩放
        button.setGraphicsEffect(None)  # 简化：在 QSS 中使用 :hover 伪类
        # 这里主要通过 QSS 实现，保留占位以供扩展

    @staticmethod
    def pulse(widget: QWidget, duration: int = 600, loops: int = 3):
        """脉冲闪烁效果（用于通知/提醒）"""
        effect = widget.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.5, 0.5)
        anim.setEndValue(1.0)
        anim.setLoopCount(loops)
        anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.InOutSine))
        anim.start()
        return anim

    @staticmethod
    def shake(widget: QWidget, duration: int = 300, intensity: int = 5):
        """抖动效果（用于输入验证失败）"""
        original_pos = widget.pos()
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(duration)
        anim.setLoopCount(2)
        anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutElastic))

        x = original_pos.x()
        y = original_pos.y()
        anim.setKeyValueAt(0.0, widget.pos())
        anim.setKeyValueAt(0.25, widget.pos() - type(widget.pos())(intensity, 0))
        anim.setKeyValueAt(0.5, widget.pos() + type(widget.pos())(intensity, 0))
        anim.setKeyValueAt(0.75, widget.pos() - type(widget.pos())(intensity // 2, 0))
        anim.setKeyValueAt(1.0, original_pos)

        anim.finished.connect(lambda: widget.move(original_pos))
        anim.start()
        return anim

    @staticmethod
    def spin_in(widget: QWidget, duration: int = 400):
        """旋转进入效果"""
        widget.setVisible(False)
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        opacity_anim = QPropertyAnimation(effect, b"opacity")
        opacity_anim.setDuration(duration)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))

        group = QParallelAnimationGroup()
        group.addAnimation(opacity_anim)
        widget.setVisible(True)
        group.start()
        return group
