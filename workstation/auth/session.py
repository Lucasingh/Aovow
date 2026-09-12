"""
全局会话管理器

单例模式，持有当前登录用户状态，供所有模块查询。
LoginTool 在登录/登出时更新此状态，其他工具（如 AI-Native）
通过 is_logged_in 判断是否允许使用受保护功能。

设计理由：登录态原先仅存于 LoginTool 实例内部，其他工具无法感知，
导致未登录用户也能调用 AI 等需登录功能。SessionManager 提供全局入口。
"""

import threading
from typing import Optional, Dict, Any


class SessionManager:
    """全局会话管理器（线程安全单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._current_user: Optional[Dict[str, Any]] = None
                    cls._instance._token: str = ""
        return cls._instance

    # ========== 状态查询 ==========

    @property
    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self._current_user is not None

    @property
    def current_user(self) -> Optional[Dict[str, Any]]:
        """当前登录用户字典（含 id/username/github_username 等）"""
        return self._current_user

    @property
    def username(self) -> str:
        """当前用户名（未登录返回空串）"""
        return self._current_user.get("username", "") if self._current_user else ""

    @property
    def user_id(self) -> Optional[int]:
        """当前用户 ID"""
        if self._current_user:
            return self._current_user.get("id")
        return None

    @property
    def token(self) -> str:
        """当前会话令牌"""
        return self._token

    # ========== 状态变更 ==========

    def login(self, user: Dict[str, Any], token: str = ""):
        """设置登录状态"""
        self._current_user = user
        self._token = token

    def logout(self):
        """清除登录状态"""
        self._current_user = None
        self._token = ""

    def __repr__(self):
        if self.is_logged_in:
            return f"<SessionManager: logged_in as {self.username}>"
        return "<SessionManager: anonymous>"
