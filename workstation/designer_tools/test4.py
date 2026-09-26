"""自动生成的工具：test4（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="test4",
    description='test04',
    tags=["designer"],
    category='通用',
    parameters=[
        # 无参数
    ],
)
def test4(ctx: ToolContext):
    """test04"""
    # 在这里写你的工具逻辑
    ctx.info("工具运行")
    return {"result": "你好，世界！"}


class Test4Tool(DesignerToolBase):
    tool_id = "test4"
    name = 'test4'
    icon = '🧩'
    category = '通用'
    description = 'test04'
    _func = test4

    def build_custom_widget(self):
        from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                        QLabel, QLineEdit, QPushButton,
                                        QTextEdit, QMessageBox)
        from PySide6.QtCore import Qt
        
        
        def create_ui():
            """
            在这里构建你的专属界面（函数体，返回 QWidget）
            """
            # 创建根容器
            w = QWidget()
            w.setWindowTitle("PySide6 界面示例")
            w.resize(480, 360)
        
            # 主布局（垂直）
            lay = QVBoxLayout(w)
        
            # ---- 顶部标题 ----
            title = QLabel("欢迎使用 PySide6")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
            lay.addWidget(title)
        
            # ---- 输入区域（水平布局）----
            input_layout = QHBoxLayout()
            input_label = QLabel("请输入内容:")
            input_edit = QLineEdit()
            input_edit.setPlaceholderText("在这里输入一些文字...")
            input_layout.addWidget(input_label)
            input_layout.addWidget(input_edit)
            lay.addLayout(input_layout)
        
            # ---- 日志输出区 ----
            log_edit = QTextEdit()
            log_edit.setReadOnly(True)
            log_edit.setPlaceholderText("操作记录会显示在这里...")
            lay.addWidget(log_edit)
        
            # ---- 按钮区域（水平布局）----
            button_layout = QHBoxLayout()
            greet_btn = QPushButton("打招呼")
            clear_btn = QPushButton("清空记录")
            button_layout.addWidget(greet_btn)
            button_layout.addWidget(clear_btn)
            lay.addLayout(button_layout)
        
            # ---- 事件处理 ----
            def on_greet():
                text = input_edit.text().strip()
                if not text:
                    QMessageBox.warning(w, "提示", "请先输入内容！")
                    return
                log_edit.append(f"你好，{text}！")
                input_edit.clear()
        
            def on_clear():
                log_edit.clear()
                log_edit.append("记录已清空。")
        
            greet_btn.clicked.connect(on_greet)
            clear_btn.clicked.connect(on_clear)
        
            return w
