"""
系统性能监测装置（AWTF 双轨制版本）

实时显示：
- CPU / 内存 / 磁盘 / 网络 总览卡片（CPU/内存数据来自 AWTF sysinfo 模块）
- 迷你折线图（CPU/内存最近 60 秒趋势，原生 QPainter 绘制）
- Top 进程表（按 CPU 或内存排序，可切换）
- 刷新频率可调（1s / 2s / 5s / 10s）

AWTF 集成：
1. @tool 函数 perf_monitor 采集系统快照（数据全来自 awtf.sysinfo，JSON 安全），
   可命令行运行：
   python -m awtf run perf_monitor --discover workstation/tools/perf_monitor_tool.py
2. GUI 的 CPU/内存同样来自 awtf.sysinfo；磁盘/网络 I/O 速率与进程表
   是"实时监测"特有能力（sysinfo 定位是信息快照），保留 psutil 采集。

实现要点：
- 独立 QTimer 采集，主线程内绘制
- 折线图用 QPainter 画，不依赖 PySide6-Charts（减小打包体积）
- 全程不使用 os.system，仅用跨平台 API（AWTF sysinfo / psutil / Qt）
"""

from __future__ import annotations

# ========== AWTF 函数工具 ==========
# 让这个文件同时也是 AWTF 的工具模块，可以被 python -m awtf run 发现
import sys as _sys
from pathlib import Path as _Path

# 让 awtf 可被导入（引导真包父目录：editable finder 会被 cwd namespace 抢占）
_awtf_root = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _awtf_root.is_dir() and str(_awtf_root) not in _sys.path:
    _sys.path.insert(0, str(_awtf_root))

from awtf import Parameter, ToolContext, tool  # type: ignore
from awtf import sysinfo as _sysinfo  # noqa: E402


@tool(
    name="perf_monitor",
    description="系统性能快照 —— CPU/内存/磁盘/网络/OS/运行时 一键采集（数据来自 awtf.sysinfo）",
    tags=["perf", "system", "monitor"],
    parameters=[
        Parameter("probe_connectivity", bool, default=False,
                  description="是否探测外网连通性（发一次真实请求）"),
    ],
)
def perf_monitor(ctx: ToolContext, probe_connectivity: bool = False) -> dict:
    """采集系统性能快照。

    Args:
        probe_connectivity: 是否探测外网连通性（默认 False 保持轻量）。
    """
    from awtf.sysinfo import collect_system_info

    info = collect_system_info(probe_connectivity=probe_connectivity)
    hw = info["hardware"]
    summary = {
        "cpu_usage_percent": hw["cpu"]["usage_percent"],
        "cpu_model": hw["cpu"]["model"],
        "cpu_logical_cores": hw["cpu"]["logical_cores"],
        "memory_usage_percent": hw["memory"]["usage_percent"],
        "memory_total": hw["memory"]["total"],
        "disk_total": hw["disk"]["total"],
        "os": f"{info['os']['system']} {info['os']['release']}",
        "ip": info["network"]["ip"],
    }
    ctx.info("perf_monitor: cpu=%s%% mem=%s%%",
             summary["cpu_usage_percent"], summary["memory_usage_percent"])
    return {"summary": summary, "detail": info}


# ========== 工作站 GUI 工具 ==========
import psutil
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QFrame, QScrollArea, QSizePolicy, QHeaderView
)

from workstation.tools.base_tool import BaseTool


# 历史长度
_HISTORY_LEN = 60


# ==============================================================
# 迷你折线图（纯 QPainter）
# ==============================================================

class MiniLineChart(QWidget):
    """迷你折线图：画一条曲线 + 底部刻度线"""

    def __init__(self, height: int = 80, parent=None):
        super().__init__(parent)
        self._height = height
        self.setFixedHeight(height)
        self.setMinimumWidth(200)
        self._series: list[float] = []
        self._color = QColor("#6c5ce7")
        self._label = ""
        self._unit = ""

    def set_data(self, series: list[float], label: str = "", unit: str = "%",
                 color: str = "#6c5ce7"):
        self._series = list(series)
        self._label = label
        self._unit = unit
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        pad = 4
        chart_h = h - pad * 2

        # 背景
        painter.fillRect(0, 0, w, h, QColor("#1a1a2e"))
        # 底部基线
        pen = QPen(QColor("#2a2a44"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(pad, h - pad, w - pad, h - pad)

        if not self._series:
            return

        # 归一化：0 ~ 100
        values = [min(v, 100.0) for v in self._series]
        n = len(values)
        if n < 2:
            return

        # 折线
        pen = QPen(self._color)
        pen.setWidth(2)
        painter.setPen(pen)
        points = []
        x_step = (w - pad * 2) / (n - 1)
        for i, v in enumerate(values):
            x = pad + i * x_step
            y = h - pad - (v / 100.0) * (chart_h - pen.width())
            points.append(QPointF(x, y))
        painter.drawPolyline(points)

        # 数值标签（最右侧当前值）
        current = values[-1]
        painter.setPen(self._color)
        font = QFont()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(w - 80, 0, 76, 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{current:.1f}{self._unit}",
        )


# ==============================================================
# 指标卡片
# ==============================================================

class MetricCard(QFrame):
    """单个指标大卡片"""

    def __init__(self, label: str, color: str = "#6c5ce7"):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #3a3a5c; "
            "border-radius: 12px; }")

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(6)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #7a7a9e; font-size: 12px;")
        v.addWidget(self._label)

        self._value = QLabel("--")
        self._value.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: 900;")
        v.addWidget(self._value)

        self._chart = MiniLineChart(height=70)
        self._chart._color = QColor(color)
        v.addWidget(self._chart)

    def update_data(self, value: float, series: list[float], unit: str = "%"):
        self._value.setText(f"{value:.1f}{unit}")
        self._chart.set_data(series, self._label.text(), unit,
                             self._chart._color.name())


# ==============================================================
# 主面板
# ==============================================================

class PerfPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 历史数据
        self._cpu_sys: list[float] = []
        self._mem_sys: list[float] = []

        self._build_ui()

        # 刷新定时器（延迟启动，等激活后才开始刷）
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._interval_ms = 2000

        # 首次采集预热
        psutil.cpu_percent(interval=None)
        psutil.virtual_memory()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(16)

        # 标题 + 控制条
        top = QHBoxLayout()
        top.setSpacing(12)

        title = QLabel("📊 系统性能监测")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #e4e4f0;")
        top.addWidget(title)
        top.addStretch()

        hint = QLabel("刷新频率：")
        hint.setStyleSheet("color: #7a7a9e; font-size: 12px;")
        top.addWidget(hint)

        self._freq = QComboBox()
        self._freq.addItems(["1s", "2s", "5s", "10s"])
        self._freq.setCurrentText("2s")
        self._freq.setStyleSheet(
            "QComboBox { background: #2a2a44; color: #e4e4f0; "
            "border: 1px solid #3a3a5c; border-radius: 6px; padding: 4px 10px; min-width: 70px; }")
        self._freq.currentTextChanged.connect(self._on_freq_changed)
        top.addWidget(self._freq)

        self._status = QLabel("● 运行中")
        self._status.setStyleSheet("color: #2dd4a7; font-size: 12px;")
        top.addWidget(self._status)

        root.addLayout(top)

        # 四个卡片
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        self._card_cpu = MetricCard("CPU", color="#fbbf24")
        self._card_mem = MetricCard("内存", color="#6c5ce7")
        self._card_disk = MetricCard("磁盘 I/O", color="#2dd4a7")
        self._card_net = MetricCard("网络 I/O", color="#f472b6")

        for c in (self._card_cpu, self._card_mem,
                  self._card_disk, self._card_net):
            cards_row.addWidget(c, 1)
        root.addLayout(cards_row)

        # 进程 Top 表
        root.addSpacing(6)
        root.addWidget(self._build_proc_section(), 1)

    def _build_proc_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #3a3a5c; border-radius: 12px; }")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel("⚡ 进程 Top（前 10，按 CPU 排序）")
        title.setStyleSheet("color: #e4e4f0; font-size: 14px; font-weight: bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._sort = QComboBox()
        self._sort.addItems(["CPU", "内存"])
        self._sort.setStyleSheet(
            "QComboBox { background: #2a2a44; color: #e4e4f0; "
            "border: 1px solid #3a3a5c; border-radius: 6px; padding: 3px 10px; min-width: 70px; }")
        self._sort.currentTextChanged.connect(lambda _: self._tick())
        hdr.addWidget(QLabel("排序："))
        hdr.itemAt(hdr.count() - 1).widget().setStyleSheet(
            "color: #7a7a9e; font-size: 12px;")
        hdr.addWidget(self._sort)

        v.addLayout(hdr)

        # 表头
        self._proc_header = QLabel(
            f"{'名称':<22} {'PID':>6} {'用户':<14} {'CPU%':>7} {'内存MB':>8}")
        self._proc_header.setStyleSheet(
            "color: #7a7a9e; font-family: 'Consolas','Courier New',monospace; "
            "font-size: 11px; padding: 4px 4px 2px 4px;")
        v.addWidget(self._proc_header)

        # 内容
        self._proc_label = QLabel("加载中...")
        self._proc_label.setStyleSheet(
            "color: #c0c0e0; font-family: 'Consolas','Courier New',monospace; font-size: 12px;")
        v.addWidget(self._proc_label, 1)

        return wrap

    # ---------- 数据 ----------

    def _on_freq_changed(self, text: str):
        ms = int(text.rstrip("s")) * 1000
        self._interval_ms = ms
        if self._timer.isActive():
            self._timer.start(ms)

    def start(self):
        """激活时开始采集"""
        self._cpu_sys.clear()
        self._mem_sys.clear()
        self._tick()          # 立即刷一次
        self._timer.start(self._interval_ms)

    def stop(self):
        """停用时停止"""
        self._timer.stop()

    def _tick(self):
        try:
            # CPU / 内存：数据来自 AWTF sysinfo 模块（跨平台、零依赖）
            cpu = _sysinfo.cpu_info()["usage_percent"]
            if cpu is None:  # 标准库降级路径不提供瞬时使用率
                cpu = 0.0
            mem_p = _sysinfo.memory_info()["usage_percent"]

            # 平滑追加
            self._cpu_sys.append(cpu)
            self._mem_sys.append(mem_p)
            if len(self._cpu_sys) > _HISTORY_LEN:
                self._cpu_sys.pop(0)
            if len(self._mem_sys) > _HISTORY_LEN:
                self._mem_sys.pop(0)

            # 磁盘 / 网络 I/O（实时速率 = 本次累计 - 上次累计，psutil 提供）
            disk = psutil.disk_io_counters()
            net = psutil.net_io_counters()
            disk_mb_s = self._rate("disk", (disk.read_bytes + disk.write_bytes) / (1024 * 1024))
            net_mb_s = self._rate("net", (net.bytes_sent + net.bytes_recv) / (1024 * 1024))

            self._card_cpu.update_data(cpu, self._cpu_sys)
            self._card_mem.update_data(mem_p, self._mem_sys)
            self._card_disk.update_data(
                disk_mb_s, self._io_history("disk", disk_mb_s), unit=" MB/s")
            self._card_net.update_data(
                net_mb_s, self._io_history("net", net_mb_s), unit=" MB/s")

            # 进程 Top
            self._refresh_procs()

        except Exception as e:
            self._status.setText(f"● 错误: {e}")
            self._status.setStyleSheet("color: #f87171; font-size: 12px;")

    # 计算 I/O 速率（每秒累计变化量）
    def _rate(self, tag: str, current_mb: float) -> float:
        key = f"_last_{tag}"
        last = getattr(self, key, None)
        interval_s = self._interval_ms / 1000.0
        val = (current_mb - last) / interval_s if last is not None else 0.0
        setattr(self, key, current_mb)
        return max(0.0, val)

    # 给 I/O 卡片维护一份 60 长度的历史（共享频率、独立列表）
    def _io_history(self, tag: str, cur: float) -> list[float]:
        key = f"_hist_{tag}"
        hist: list[float] = getattr(self, key, [])
        hist.append(cur)
        if len(hist) > _HISTORY_LEN:
            hist.pop(0)
        setattr(self, key, hist)
        return hist

    def _refresh_procs(self):
        sort_key = "cpu" if self._sort.currentText() == "CPU" else "memory"
        # 取前 30 个再排序，psutil.process_iter 取全量有点重
        items = []
        for p in psutil.process_iter(["name", "pid", "username", "cpu_percent", "memory_info"]):
            try:
                info = p.info
                mb = (info.get("memory_info").rss / (1024 * 1024)) if info.get("memory_info") else 0.0
                items.append({
                    "name": (info.get("name") or "")[:20],
                    "pid": info["pid"],
                    "user": (info.get("username") or "")[:12],
                    "cpu": info.get("cpu_percent") or 0.0,
                    "mem_mb": round(mb, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        items.sort(key=lambda x: x["cpu"] if sort_key == "cpu" else x["mem_mb"],
                   reverse=True)
        top = items[:10]
        lines = []
        for r in top:
            lines.append(
                f"{r['name']:<22} {r['pid']:>6} {r['user']:<14} "
                f"{r['cpu']:>7.1f} {r['mem_mb']:>8.1f}"
            )
        self._proc_label.setText("\n".join(lines))


# ==============================================================
# 工具入口
# ==============================================================

class PerfMonitorTool(BaseTool):
    """系统性能监测装置"""

    tool_id = "perf_monitor"
    name = "性能监测"
    icon = "📊"
    category = "测试"
    description = "CPU/内存/磁盘/网络 实时监测 + 进程 Top"

    def __init__(self):
        self._widget: QWidget | None = None

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = PerfPanel()
        return self._widget

    def on_activate(self):
        if isinstance(self._widget, PerfPanel):
            self._widget.start()

    def on_deactivate(self):
        if isinstance(self._widget, PerfPanel):
            self._widget.stop()
