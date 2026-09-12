"""
登录注册工具 — GitHub OAuth 版

集成到 Aovow Workstation 框架：
1. GitHub OAuth 浏览器授权登录/注册
2. 用户名密码登录
3. 注册表单（自动填充 GitHub 用户名）
4. 会话管理（记住登录状态）

OAuth 流程：
    点击 GitHub 登录 → 打开浏览器授权 → 本地服务器接收回调
    → 已绑定: 自动登录 / 未绑定: 跳转注册页
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QStackedWidget, QCheckBox,
    QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QCursor

from workstation.tools.base_tool import BaseTool
from workstation.auth.database import DatabaseManager
from workstation.auth.security import SecurityManager
from workstation.auth.session import SessionManager
from workstation.auth.github_oauth import GithubOAuthServer, _CallbackHandler
from workstation.core.signals import SignalBus
from workstation.ui.responsive import get_responsive_engine


class _OAuthWorker(QThread):
    """后台线程：交换 GitHub token + 获取用户信息

    注意：不能用 `finished` 作为信号名，会与 QThread 内置的 finished 信号冲突。
    """
    result_ready = Signal(object)  # {"ok": bool, "user": dict|None, "error": str}

    def __init__(self, server: GithubOAuthServer, code: str):
        super().__init__()
        self._server = server
        self._code = code

    def run(self):
        try:
            access_token = self._server._exchange_code(self._code)
            if not access_token:
                self.result_ready.emit({
                    "ok": False, "user": None,
                    "error": self._server.last_error or "换取 access_token 失败",
                })
                return
            github_user = self._server._fetch_user_info(access_token)
            if github_user:
                self.result_ready.emit({"ok": True, "user": github_user, "error": ""})
            else:
                self.result_ready.emit({
                    "ok": False, "user": None,
                    "error": self._server.last_error or "获取用户信息失败",
                })
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"OAuth worker 异常: {e}")
            self.result_ready.emit({"ok": False, "user": None, "error": str(e)})


class LoginTool(BaseTool):
    """登录注册工具"""

    tool_id = "auth_login"
    name = "用户中心"
    icon = "👤"
    category = "系统"
    description = "用户注册与登录管理"

    def __init__(self):
        self._widget: QWidget | None = None
        self._db = DatabaseManager()
        self._security = SecurityManager()
        self._session_mgr = SessionManager()
        self._signals = SignalBus()
        self._stack: QStackedWidget | None = None
        self._r = get_responsive_engine()
        self._session_token: str = ""
        self._current_user: dict | None = None

        # GitHub OAuth 状态
        self._oauth_server: GithubOAuthServer | None = None
        self._oauth_github_user: dict | None = None
        self._oauth_poll_timer: QTimer | None = None
        self._oauth_worker: _OAuthWorker | None = None
        self._oauth_timeout_timer: QTimer | None = None

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_ui()
        return self._widget

    def _build_ui(self) -> QWidget:
        self._r = get_responsive_engine()
        container = QWidget()
        container.setObjectName("toolContainer")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        root = QVBoxLayout(container)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        margin = self._r.spacing(40)
        root.setContentsMargins(margin, margin, margin, margin)

        title_fs = self._r.font_size(22)
        title = QLabel("用户中心")
        title.setStyleSheet(f"font-size: {title_fs}px; font-weight: bold; color: #e4e4f0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        root.addSpacing(self._r.spacing(24))

        self._stack = QStackedWidget()
        self._stack.setMaximumWidth(self._r.scaled_int(420))

        self._stack.addWidget(self._build_main_page())            # 0: 主页
        self._stack.addWidget(self._build_register_page())         # 1: 注册
        self._stack.addWidget(self._build_password_login_page())   # 2: 密码登录
        self._stack.addWidget(self._build_logged_in_page())        # 3: 已登录
        self._stack.addWidget(self._build_oauth_loading_page())    # 4: OAuth 等待中

        root.addWidget(self._stack, 0, Qt.AlignmentFlag.AlignCenter)
        root.addStretch()

        scroll.setWidget(container)
        return scroll

    # ========== 页面 0: 主页 ==========
    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        card = self._make_card()
        card_layout = QVBoxLayout(card)

        subtitle = QLabel("快速登录")
        sub_fs = self._r.font_size(15)
        subtitle.setStyleSheet(f"font-size: {sub_fs}px; font-weight: bold; color: #e4e4f0;")
        card_layout.addWidget(subtitle)

        desc = QLabel("使用 GitHub 账号一键登录，首次使用自动注册")
        desc_fs = self._r.font_size(12)
        desc.setStyleSheet(f"color: #a0a0c0; font-size: {desc_fs}px; margin-bottom: 8px;")
        card_layout.addWidget(desc)

        btn_github = QPushButton("🐙  GitHub 登录")
        btn_fs = self._r.font_size(14)
        btn_pad = self._r.spacing(12)
        btn_github.setStyleSheet(
            f"QPushButton {{ background: #24292e; color: #ffffff; "
            f"border: none; border-radius: 8px; padding: {btn_pad}px; "
            f"font-size: {btn_fs}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #2f363d; }}"
            f"QPushButton:pressed {{ background: #1b1f23; }}"
        )
        btn_github.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_github.clicked.connect(self._start_github_oauth)
        card_layout.addWidget(btn_github)
        layout.addWidget(card)

        sep_label = QLabel("———— 或 ————")
        sep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep_fs = self._r.font_size(12)
        sep_label.setStyleSheet(f"color: #6b6b8a; font-size: {sep_fs}px;")
        layout.addWidget(sep_label)

        card2 = self._make_card()
        card2_layout = QVBoxLayout(card2)

        btn_pwd_login = QPushButton("🔑  使用用户名密码登录")
        pwd_btn_fs = self._r.font_size(14)
        pwd_btn_pad = self._r.spacing(12)
        btn_pwd_login.setStyleSheet(
            f"QPushButton {{ background: transparent; color: #a0a0c0; "
            f"border: 1px solid #3a3a5c; border-radius: 8px; "
            f"padding: {pwd_btn_pad}px; font-size: {pwd_btn_fs}px; }}"
            f"QPushButton:hover {{ background: #35355a; color: #e4e4f0; border-color: #4a4a6e; }}"
        )
        btn_pwd_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_pwd_login.clicked.connect(lambda: self._stack.setCurrentIndex(2))
        card2_layout.addWidget(btn_pwd_login)
        layout.addWidget(card2)

        return page

    # ========== 页面 1: GitHub 注册页 ==========
    def _build_register_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        back = QPushButton("← 返回")
        back.setStyleSheet(
            "QPushButton { background: transparent; color: #a0a0c0; border: none; "
            "font-size: 12px; text-align: left; }"
            "QPushButton:hover { color: #e4e4f0; }"
        )
        back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back.clicked.connect(self._on_register_back)
        layout.addWidget(back)

        title = QLabel("完成注册")
        title_fs = self._r.font_size(18)
        title.setStyleSheet(f"font-size: {title_fs}px; font-weight: bold; color: #e4e4f0;")
        layout.addWidget(title)

        self._reg_hint = QLabel("")
        self._reg_hint.setStyleSheet("color: #a0a0c0; font-size: 12px; margin-bottom: 8px;")
        self._reg_hint.setWordWrap(True)
        layout.addWidget(self._reg_hint)

        layout.addWidget(self._make_label("用户名"))
        self._reg_username = QLineEdit()
        self._reg_username.setPlaceholderText("3-20位，支持字母/数字/下划线/中文")
        self._reg_username.setStyleSheet(self._input_style())
        layout.addWidget(self._reg_username)

        self._reg_user_error = QLabel("")
        self._reg_user_error.setStyleSheet("color: #ff5c5c; font-size: 11px;")
        self._reg_user_error.hide()
        layout.addWidget(self._reg_user_error)

        layout.addWidget(self._make_label("密码"))
        self._reg_password = QLineEdit()
        self._reg_password.setPlaceholderText("6-32位，需包含字母和数字")
        self._reg_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_password.setStyleSheet(self._input_style())
        layout.addWidget(self._reg_password)

        self._reg_pwd_error = QLabel("")
        self._reg_pwd_error.setStyleSheet("color: #ff5c5c; font-size: 11px;")
        self._reg_pwd_error.hide()
        layout.addWidget(self._reg_pwd_error)

        layout.addWidget(self._make_label("确认密码"))
        self._reg_confirm = QLineEdit()
        self._reg_confirm.setPlaceholderText("请再次输入密码")
        self._reg_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_confirm.setStyleSheet(self._input_style())
        layout.addWidget(self._reg_confirm)

        self._reg_confirm_error = QLabel("")
        self._reg_confirm_error.setStyleSheet("color: #ff5c5c; font-size: 11px;")
        self._reg_confirm_error.hide()
        layout.addWidget(self._reg_confirm_error)

        layout.addSpacing(8)

        self._btn_register = QPushButton("注册并登录")
        self._style_primary_btn(self._btn_register)
        self._btn_register.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_register.clicked.connect(self._do_register)
        layout.addWidget(self._btn_register)
        layout.addStretch()
        return page

    # ========== 页面 2: 密码登录页 ==========
    def _build_password_login_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        back = QPushButton("← 返回")
        back.setStyleSheet(
            "QPushButton { background: transparent; color: #a0a0c0; border: none; "
            "font-size: 12px; text-align: left; }"
            "QPushButton:hover { color: #e4e4f0; }"
        )
        back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(back)

        title = QLabel("用户登录")
        title_fs = self._r.font_size(18)
        title.setStyleSheet(f"font-size: {title_fs}px; font-weight: bold; color: #e4e4f0;")
        layout.addWidget(title)

        layout.addWidget(self._make_label("用户名"))
        self._login_username = QLineEdit()
        self._login_username.setPlaceholderText("请输入用户名")
        self._login_username.setStyleSheet(self._input_style())
        layout.addWidget(self._login_username)

        layout.addWidget(self._make_label("密码"))
        self._login_password = QLineEdit()
        self._login_password.setPlaceholderText("请输入密码")
        self._login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_password.setStyleSheet(self._input_style())
        self._login_password.returnPressed.connect(self._do_password_login)
        layout.addWidget(self._login_password)

        self._remember_cb = QCheckBox("保持登录状态（7天有效）")
        self._remember_cb.setStyleSheet("QCheckBox { color: #a0a0c0; font-size: 12px; }")
        self._remember_cb.setChecked(True)
        layout.addWidget(self._remember_cb)

        self._login_error = QLabel("")
        self._login_error.setStyleSheet("color: #ff5c5c; font-size: 12px;")
        self._login_error.setWordWrap(True)
        self._login_error.hide()
        layout.addWidget(self._login_error)

        btn_login = QPushButton("登  录")
        self._style_primary_btn(btn_login)
        btn_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_login.clicked.connect(self._do_password_login)
        layout.addWidget(btn_login)
        layout.addStretch()
        return page

    # ========== 页面 3: 已登录页 ==========
    def _build_logged_in_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self._logged_avatar = QLabel("🐙")
        self._logged_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logged_avatar.setStyleSheet("font-size: 48px;")
        layout.addWidget(self._logged_avatar)

        self._logged_user_label = QLabel("")
        self._logged_user_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e4e4f0;")
        self._logged_user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._logged_user_label)

        self._logged_detail_label = QLabel("")
        self._logged_detail_label.setStyleSheet("color: #a0a0c0; font-size: 12px;")
        self._logged_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._logged_detail_label)

        layout.addSpacing(16)

        btn_logout = QPushButton("退出登录")
        btn_logout.setStyleSheet(
            "QPushButton { background: transparent; color: #ff5c5c; "
            "border: 1px solid #3a3a5c; border-radius: 8px; "
            "padding: 10px 24px; font-size: 13px; }"
            "QPushButton:hover { background: #35355a; border-color: #ff5c5c; }"
        )
        btn_logout.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_logout.clicked.connect(self._do_logout)
        layout.addWidget(btn_logout, 0, Qt.AlignmentFlag.AlignCenter)
        return page

    # ========== 页面 4: OAuth 等待中 ==========
    def _build_oauth_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        icon = QLabel("🐙")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 56px;")
        layout.addWidget(icon)

        self._oauth_status = QLabel("正在打开浏览器进行 GitHub 授权...")
        self._oauth_status.setStyleSheet(
            "font-size: 14px; color: #e4e4f0; font-weight: bold;")
        self._oauth_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._oauth_status)

        self._oauth_elapsed = QLabel("")
        self._oauth_elapsed.setStyleSheet("color: #6b6b8a; font-size: 12px;")
        self._oauth_elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._oauth_elapsed)

        layout.addSpacing(16)

        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet(
            "QPushButton { background: transparent; color: #a0a0c0; "
            "border: 1px solid #3a3a5c; border-radius: 8px; padding: 8px 32px; "
            "font-size: 13px; }"
            "QPushButton:hover { background: #35355a; color: #e4e4f0; }"
        )
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cancel.clicked.connect(self._cancel_oauth)
        layout.addWidget(btn_cancel, 0, Qt.AlignmentFlag.AlignCenter)
        return page

    # ========== GitHub OAuth 流程 ==========

    def _start_github_oauth(self):
        """启动 GitHub OAuth 授权"""
        self._oauth_github_user = None

        # 切换到加载页面
        self._stack.setCurrentIndex(4)
        self._oauth_status.setText("正在打开浏览器进行 GitHub 授权...")
        self._oauth_elapsed.setText("请在新打开的浏览器页面中点击授权")

        # 启动 OAuth 服务器
        try:
            self._oauth_server = GithubOAuthServer()
            self._oauth_server.start()

            import webbrowser
            auth_url = self._oauth_server.get_auth_url()
            webbrowser.open(auth_url)

            # 用 QTimer 轮询回调结果（不阻塞 UI 线程）
            self._oauth_poll_timer = QTimer()
            self._oauth_poll_timer.setInterval(500)
            self._poll_start_time = __import__("time").time()
            self._oauth_poll_timer.timeout.connect(self._poll_oauth_callback)
            self._oauth_poll_timer.start()
        except Exception as e:
            self._oauth_status.setText(f"启动失败: {e}")
            self._oauth_elapsed.setText("请检查网络连接后重试")

    def _poll_oauth_callback(self):
        """轮询 OAuth 回调（UI 线程安全）"""
        elapsed = int(__import__("time").time() - self._poll_start_time)
        self._oauth_elapsed.setText(f"等待授权中... ({elapsed}s / 120s)")

        # 检查是否超时
        if elapsed > 120:
            self._stop_oauth()
            self._oauth_status.setText("授权超时")
            self._oauth_elapsed.setText("请检查网络连接后重试")
            return

        # 检查是否有回调
        if _CallbackHandler.received_code is None:
            return

        # 回调已收到！停止轮询，启动后台线程处理 token 交换
        self._oauth_poll_timer.stop()
        self._oauth_elapsed.setText("授权成功，正在获取用户信息...")

        import logging
        logging.getLogger(__name__).info("收到 GitHub 回调，启动 token 交换线程")

        code = _CallbackHandler.received_code
        self._oauth_worker = _OAuthWorker(self._oauth_server, code)
        self._oauth_worker.result_ready.connect(self._on_oauth_finished)
        # 线程结束后自动清理
        self._oauth_worker.finished.connect(self._oauth_worker.deleteLater)
        self._oauth_worker.start()

        # 启动超时保护（60秒，覆盖两次网络请求的 connect+read 超时）
        self._oauth_timeout_timer = QTimer()
        self._oauth_timeout_timer.setSingleShot(True)
        self._oauth_timeout_timer.setInterval(60000)
        self._oauth_timeout_timer.timeout.connect(self._on_oauth_timeout)
        self._oauth_timeout_timer.start()

    def _on_oauth_timeout(self):
        """OAuth token 交换超时保护"""
        import logging
        logging.getLogger(__name__).warning("OAuth token 交换超时")
        if self._oauth_worker and self._oauth_worker.isRunning():
            self._oauth_worker.terminate()
            self._oauth_worker.wait(2000)
        self._stop_oauth()
        self._oauth_status.setText("获取用户信息超时")
        self._oauth_elapsed.setText("请检查网络连接后重试")

    def _on_oauth_finished(self, result: dict):
        """OAuth 后台任务完成回调（UI 线程）"""
        # 停掉超时计时器
        if hasattr(self, "_oauth_timeout_timer") and self._oauth_timeout_timer:
            self._oauth_timeout_timer.stop()
            self._oauth_timeout_timer = None

        import logging
        logging.getLogger(__name__).info(f"OAuth 完成: {result}")

        # 先处理 UI 逻辑，最后再停服务器（避免任何潜在阻塞影响 UI 响应）
        github_user = result.get("user") if result.get("ok") else None
        if github_user is None:
            error = result.get("error") or "GitHub 授权失败"
            self._stop_oauth()
            self._oauth_status.setText("GitHub 授权失败")
            self._oauth_elapsed.setWordWrap(True)
            self._oauth_elapsed.setText(
                f"{error}\n请检查网络或代理设置（可写入 ~/.aovow/settings.yaml 的 oauth.proxy）")
            return

        self._oauth_github_user = github_user

        # 检查是否已绑定
        existing = self._db.get_user_by_github_id(github_user["github_id"])
        if existing:
            self._login_user(existing)
        else:
            self._goto_github_register(github_user)

        # UI 已更新，最后清理服务器
        self._stop_oauth()

    def _goto_github_register(self, github_user: dict):
        """跳转到 GitHub 注册页"""
        gh_username = github_user.get("github_username", "")
        self._reg_hint.setText(
            f"已通过 GitHub 验证 (@{gh_username})，请设置本地账号信息")
        self._reg_username.setText(gh_username)
        self._reg_password.clear()
        self._reg_confirm.clear()
        self._reg_user_error.hide()
        self._reg_pwd_error.hide()
        self._reg_confirm_error.hide()
        self._stack.setCurrentIndex(1)

    def _stop_oauth(self):
        """停止 OAuth 服务器和轮询"""
        if self._oauth_poll_timer:
            self._oauth_poll_timer.stop()
            self._oauth_poll_timer = None
        if self._oauth_server:
            self._oauth_server.stop()
            self._oauth_server = None

    def _cancel_oauth(self):
        """取消 OAuth"""
        self._stop_oauth()
        self._stack.setCurrentIndex(0)

    def _on_register_back(self):
        """注册页返回 — 如果是 GitHub 注册则清理状态"""
        self._oauth_github_user = None
        self._stack.setCurrentIndex(0)

    # ========== 注册 ==========

    def _do_register(self):
        """执行注册"""
        username = self._reg_username.text().strip()
        password = self._reg_password.text()
        confirm = self._reg_confirm.text()

        self._reg_user_error.hide()
        self._reg_pwd_error.hide()
        self._reg_confirm_error.hide()

        has_error = False
        for field, validator in [
            (self._reg_user_error, self._security.validate_username(username)),
            (self._reg_pwd_error, self._security.validate_password(password)),
        ]:
            if not validator.valid:
                field.setText(validator.message)
                field.show()
                has_error = True

        if password != confirm:
            self._reg_confirm_error.setText("两次输入的密码不一致")
            self._reg_confirm_error.show()
            has_error = True

        if has_error:
            return

        if self._db.username_exists(username):
            self._reg_user_error.setText("用户名已被注册")
            self._reg_user_error.show()
            return

        password_hash = self._security.hash_password(password)

        github_info = self._oauth_github_user or {}
        user_id = self._db.create_user(
            username=username,
            password_hash=password_hash,
            github_id=github_info.get("github_id"),
            github_username=github_info.get("github_username"),
            github_avatar=github_info.get("avatar_url"),
        )

        if user_id is None:
            QMessageBox.critical(self.widget, "错误", "注册失败，请稍后重试")
            return

        user = self._db.get_user_by_id(user_id)
        if user:
            self._show_success("注册成功！")
            self._login_user(user)

    # ========== 密码登录 ==========

    def _do_password_login(self):
        """用户名密码登录"""
        username = self._login_username.text().strip()
        password = self._login_password.text()

        if not username or not password:
            self._login_error.setText("请输入用户名和密码")
            self._login_error.show()
            return

        user = self._db.get_user_by_username(username)
        if user is None:
            self._login_error.setText("用户名不存在或账号已被禁用")
            self._login_error.show()
            return

        if not user.get("password_hash"):
            self._login_error.setText("该账号未设置密码，请使用 GitHub 登录")
            self._login_error.show()
            return

        if not self._security.verify_password(password, user["password_hash"]):
            self._login_error.setText("密码错误，请重试")
            self._login_error.show()
            return

        self._login_error.hide()
        self._login_user(user, remember=self._remember_cb.isChecked())

    # ========== 登录/登出 ==========

    def _login_user(self, user: dict, remember: bool = True):
        """执行登录"""
        self._current_user = user

        if remember:
            token = self._security.generate_session_token()
            self._db.create_session(user["id"], token)
            self._session_token = token

        # 更新登录页面信息
        if user.get("github_username"):
            self._logged_avatar.setText("🐙")
        else:
            self._logged_avatar.setText("👤")

        self._logged_user_label.setText(f"欢迎，{user['username']}")

        detail_parts = []
        if user.get("github_username"):
            detail_parts.append(f"已绑定 GitHub @{user['github_username']}")
        created = str(user.get("created_at", ""))
        if len(created) > 10:
            created = created[:10]
        detail_parts.append(f"注册于 {created}")
        self._logged_detail_label.setText(" | ".join(detail_parts))

        self._stack.setCurrentIndex(3)

        # 同步全局会话状态 + 广播登录信号（供其他工具感知登录态）
        self._session_mgr.login(user, token=self._session_token)
        self._signals.user_logged_in.emit(user)

    def _do_logout(self):
        if self._session_token:
            self._db.delete_session(self._session_token)
            self._session_token = ""
        self._current_user = None
        self._stack.setCurrentIndex(0)

        # 同步全局会话状态 + 广播登出信号
        self._session_mgr.logout()
        self._signals.user_logged_out.emit()

    # ========== 辅助方法 ==========

    def _make_card(self) -> QFrame:
        return self._make_card_styled()

    def _make_card_styled(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #252536; border: 1px solid #3a3a5c; "
            "border-radius: 12px; padding: 20px; }")
        return card

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #a0a0c0; font-size: 12px; font-weight: bold;")
        return lbl

    def _input_style(self) -> str:
        return (
            "QLineEdit { background: #1e1e2e; color: #e4e4f0; "
            "border: 1px solid #3a3a5c; border-radius: 8px; "
            "padding: 10px 14px; font-size: 13px; }"
            "QLineEdit:focus { border-color: #6c5ce7; }"
        )

    def _style_primary_btn(self, btn: QPushButton):
        btn.setStyleSheet(
            "QPushButton { background: #6c5ce7; color: #ffffff; "
            "border: none; border-radius: 8px; padding: 12px; "
            "font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #7d6ff0; }"
            "QPushButton:pressed { background: #5a4bd1; }"
        )

    def _show_success(self, msg: str):
        QMessageBox.information(self.widget, "成功", msg)
