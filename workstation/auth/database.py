"""
MySQL 数据库连接与操作层

特性：
- 连接池管理，避免频繁创建/销毁连接
- 所有查询使用参数化，防止 SQL 注入
- 自动重连机制
- 支持 GitHub OAuth 绑定
- 线程安全
"""

import threading
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any

import mysql.connector
from mysql.connector import pooling

logger = logging.getLogger(__name__)


# ============================================================
# 数据库配置
# ============================================================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "111111",
    "database": "aovow_workstation",
    "charset": "utf8mb4",
    "autocommit": True,
    "connect_timeout": 10,
    # 使用纯 Python 实现的 connection，避免 cext 模式要求打包
    # mysql/vendor/plugin/mysql_native_password.dll（PyInstaller 不会自动收这个目录）
    "use_pure": True,
}


class DatabaseManager:
    """数据库管理器，单例模式。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._pool: Optional[pooling.MySQLConnectionPool] = None
            self._init_database()

    def _init_database(self):
        """初始化和建表"""
        try:
            config = {k: v for k, v in DB_CONFIG.items() if k != "database"}
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()

            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS `aovow_workstation` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cursor.close()
            conn.close()

            self._pool = pooling.MySQLConnectionPool(
                pool_name="aovow_pool",
                pool_size=5,
                pool_reset_session=True,
                **DB_CONFIG,
            )
            logger.info("MySQL 连接池初始化成功")

            self._create_tables()
        except mysql.connector.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def _create_tables(self):
        """创建用户表（支持 GitHub OAuth）"""
        with self._get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `username` VARCHAR(64) NOT NULL UNIQUE,
                    `password_hash` VARCHAR(255) DEFAULT NULL,
                    `github_id` INT DEFAULT NULL COMMENT 'GitHub 用户 ID',
                    `github_username` VARCHAR(128) DEFAULT NULL COMMENT 'GitHub 用户名',
                    `github_avatar` VARCHAR(512) DEFAULT NULL COMMENT 'GitHub 头像',
                    `is_active` TINYINT(1) DEFAULT 1,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX `idx_username` (`username`),
                    INDEX `idx_github_id` (`github_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # 登录会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `sessions` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL,
                    `token` VARCHAR(255) NOT NULL UNIQUE,
                    `expires_at` DATETIME NOT NULL,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_token` (`token`),
                    INDEX `idx_user_id` (`user_id`),
                    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # 迁移：为已有数据库添加 github 字段
            self._migrate_columns(cursor)

            logger.info("数据库表创建/验证完成")

    def _migrate_columns(self, cursor):
        """为旧表添加 github 相关列（兼容已有数据）"""
        existing = set()
        cursor.execute("DESCRIBE `users`")
        for row in cursor.fetchall():
            if isinstance(row, dict):
                existing.add(row["Field"].lower())
            else:
                existing.add(row[0].lower())

        migrations = [
            ("github_id", "INT DEFAULT NULL COMMENT 'GitHub 用户 ID'"),
            ("github_username", "VARCHAR(128) DEFAULT NULL COMMENT 'GitHub 用户名'"),
            ("github_avatar", "VARCHAR(512) DEFAULT NULL COMMENT 'GitHub 头像'"),
        ]
        for col_name, col_def in migrations:
            if col_name not in existing:
                try:
                    cursor.execute(f"ALTER TABLE `users` ADD COLUMN `{col_name}` {col_def}")
                    logger.info(f"迁移：添加字段 {col_name}")
                except mysql.connector.Error as e:
                    logger.warning(f"字段迁移跳过 {col_name}: {e}")

        # 添加索引
        if "idx_github_id" not in existing:
            try:
                cursor.execute(
                    "ALTER TABLE `users` ADD INDEX `idx_github_id` (`github_id`)"
                )
            except mysql.connector.Error:
                pass

    @contextmanager
    def _get_cursor(self):
        """获取数据库游标"""
        conn = self._pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ========== 用户操作 ==========

    def create_user(self, username: str, password_hash: str = None,
                    github_id: int = None, github_username: str = None,
                    github_avatar: str = None) -> Optional[int]:
        """创建新用户（GitHub OAuth 注册时 password_hash 可为 None）"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO `users` "
                    "(`username`, `password_hash`, `github_id`, "
                    "`github_username`, `github_avatar`) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (username, password_hash, github_id,
                     github_username, github_avatar),
                )
                return cursor.lastrowid
        except mysql.connector.IntegrityError:
            return None
        except mysql.connector.Error as e:
            logger.error(f"创建用户失败: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名查询"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM `users` WHERE `username` = %s AND `is_active` = 1",
                (username,),
            )
            return cursor.fetchone()

    def get_user_by_github_id(self, github_id: int) -> Optional[Dict[str, Any]]:
        """根据 GitHub ID 查询用户"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM `users` WHERE `github_id` = %s AND `is_active` = 1",
                (github_id,),
            )
            return cursor.fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 查询"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM `users` WHERE `id` = %s AND `is_active` = 1",
                (user_id,),
            )
            return cursor.fetchone()

    def bind_github(self, user_id: int, github_id: int,
                    github_username: str, github_avatar: str = None) -> bool:
        """绑定/更新 GitHub 信息"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    "UPDATE `users` SET `github_id` = %s, "
                    "`github_username` = %s, `github_avatar` = %s "
                    "WHERE `id` = %s",
                    (github_id, github_username, github_avatar, user_id),
                )
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logger.error(f"绑定 GitHub 失败: {e}")
            return False

    def username_exists(self, username: str) -> bool:
        """检查用户名是否已存在"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM `users` WHERE `username` = %s",
                (username,),
            )
            return cursor.fetchone() is not None

    # ========== 会话管理 ==========

    def create_session(self, user_id: int, token: str,
                       expires_hours: int = 168) -> bool:
        """创建登录会话（默认7天）"""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO `sessions` (`user_id`, `token`, `expires_at`) "
                    "VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL %s HOUR))",
                    (user_id, token, expires_hours),
                )
                return True
        except mysql.connector.Error as e:
            logger.error(f"创建会话失败: {e}")
            return False

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """验证会话"""
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT u.* FROM `sessions` s "
                "JOIN `users` u ON s.`user_id` = u.`id` "
                "WHERE s.`token` = %s AND s.`expires_at` > NOW()",
                (token,),
            )
            return cursor.fetchone()

    def delete_session(self, token: str):
        """删除会话"""
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM `sessions` WHERE `token` = %s", (token,))

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM `sessions` WHERE `expires_at` < NOW()")
