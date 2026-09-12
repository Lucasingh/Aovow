"""
安全模块

密码加密和令牌管理：
- bcrypt 密码哈希（自动加盐）
- UUID 会话令牌生成
- OAuth state 参数生成（防 CSRF）
- 输入验证
"""

import bcrypt
import uuid
import re
import secrets
from dataclasses import dataclass


# ============================================================
# 密码策略
# ============================================================
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 32
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str = ""
    error_code: str = ""


class SecurityManager:
    """安全管理器"""

    @staticmethod
    def hash_password(password: str) -> str:
        """使用 bcrypt 哈希密码"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except Exception:
            return False

    @staticmethod
    def generate_session_token() -> str:
        """生成会话令牌"""
        return f"{uuid.uuid4().hex}{secrets.token_hex(16)}"

    @staticmethod
    def generate_oauth_state() -> str:
        """生成 OAuth state 参数（防 CSRF）"""
        return secrets.token_urlsafe(32)

    # ========== 输入验证 ==========

    @staticmethod
    def validate_username(username: str) -> ValidationResult:
        """验证用户名格式"""
        if not username:
            return ValidationResult(False, "用户名不能为空", "EMPTY_USERNAME")
        if len(username) < USERNAME_MIN_LENGTH:
            return ValidationResult(
                False, f"用户名至少 {USERNAME_MIN_LENGTH} 个字符", "USERNAME_TOO_SHORT")
        if len(username) > USERNAME_MAX_LENGTH:
            return ValidationResult(
                False, f"用户名不超过 {USERNAME_MAX_LENGTH} 个字符", "USERNAME_TOO_LONG")
        if not re.match(r"^[a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*$", username):
            return ValidationResult(
                False, "用户名仅支持字母、数字、下划线和中文，不能以数字开头",
                "INVALID_USERNAME")
        return ValidationResult(True)

    @staticmethod
    def validate_password(password: str) -> ValidationResult:
        """验证密码强度"""
        if not password:
            return ValidationResult(False, "密码不能为空", "EMPTY_PASSWORD")
        if len(password) < PASSWORD_MIN_LENGTH:
            return ValidationResult(
                False, f"密码至少 {PASSWORD_MIN_LENGTH} 位", "PASSWORD_TOO_SHORT")
        if len(password) > PASSWORD_MAX_LENGTH:
            return ValidationResult(
                False, f"密码不超过 {PASSWORD_MAX_LENGTH} 位", "PASSWORD_TOO_LONG")
        if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
            return ValidationResult(
                False, "密码需包含字母和数字", "PASSWORD_TOO_WEAK")
        return ValidationResult(True)

    @staticmethod
    def validate_password_match(password: str, confirm: str) -> ValidationResult:
        """验证两次密码一致"""
        if password != confirm:
            return ValidationResult(
                False, "两次输入的密码不一致", "PASSWORD_MISMATCH")
        return ValidationResult(True)
