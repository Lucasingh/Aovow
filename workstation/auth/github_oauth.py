"""
GitHub OAuth 认证模块

实现桌面应用的 GitHub OAuth 2.0 授权流程：
1. 启动本地 HTTP 回调服务器
2. 打开浏览器跳转 GitHub 授权页面
3. 接收回调 → 换取 access_token → 获取用户信息

配置要求：需在 GitHub Settings > Developer settings > OAuth Apps
注册一个 OAuth App，填写：
- Homepage URL: http://localhost:8765
- Authorization callback URL: http://localhost:8765/callback
"""

import json
import logging
import os
import socket
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Callable

import requests
import urllib3

# Windows 环境下 SSL 证书可能不可用，禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ============ 打包后诊断日志（重要）============
# 打包后的 exe console=False，用户看不到 stdout/stderr。
# 这里把 OAuth 相关的所有关键步骤写到 ~/.aovow/oauth_debug.log，
# 用户遇到问题可让他们贴这个文件来定位。
def _setup_file_logger():
    try:
        log_path = Path.home() / ".aovow" / "oauth_debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # 清除已有 handler，避免重复添加
        for h in list(logger.handlers):
            logger.removeHandler(h)
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
        # 同时让 root logger 也写，方便看完整调用栈
        root = logging.getLogger()
        if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
            root.addHandler(logging.FileHandler(str(log_path), encoding="utf-8"))
    except Exception:
        pass

_setup_file_logger()
logger.info("======== OAuth 模块加载 ========")
logger.info(f"frozen={getattr(__import__('sys'), 'frozen', False)}")

# ============================================================
# GitHub OAuth 配置（替换为你的应用凭证）
# ============================================================
GITHUB_CLIENT_ID = "Ov23li1JpIteI5X71Qaf"
GITHUB_CLIENT_SECRET = "f383b75d912b61198408453706118877a161c326"
REDIRECT_URI = "http://localhost:8765/callback"
CALLBACK_PORT = 8765

# 代理配置（国内访问 github.com 需要代理）
# 设为 None 则自动检测系统代理；也可手动指定如 "http://127.0.0.1:7890"
PROXY_URL = None


def _parse_proxy_url(proxy_url: str):
    """解析代理 URL，返回 (host, port)"""
    # 去掉 scheme
    url = proxy_url.split("://", 1)[-1] if "://" in proxy_url else proxy_url
    # 取 host:port
    host, _, port = url.partition(":")
    if not port:
        port = "8080"
    return host.strip(), int(port)


def _check_proxy_reachable(proxy_url: str, timeout: float = 2.0) -> tuple[bool, str]:
    """快速检测代理端口是否可达（TCP connect 测试）。

    返回 (是否可达, 友好提示)。
    """
    try:
        host, port = _parse_proxy_url(proxy_url)
    except Exception as e:
        return False, f"代理地址格式错误: {proxy_url}"

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, ""
    except socket.timeout:
        return False, f"代理 {host}:{port} 连接超时（{timeout}s）"
    except ConnectionRefusedError:
        return False, (
            f"代理 {host}:{port} 未启动——请打开你的代理软件（Clash/v2ray 等），"
            f"点击「开启」或「Start」按钮让代理核心运行后重试登录。"
        )
    except OSError as e:
        return False, f"代理 {host}:{port} 无法连接: {e}"


def _get_proxies() -> tuple[Optional[dict], bool, str]:
    """返回 (代理字典, 是否为显式配置, 代理地址字符串)。

    优先级：
    1. PROXY_URL 常量
    2. 环境变量 AOVOW_HTTPS_PROXY / HTTPS_PROXY / HTTP_PROXY
    3. ~/.aovow/settings.yaml 中的 oauth.proxy / proxy
    4. 系统代理自动检测（Windows 设置 > 网络 > 代理）
    """
    if PROXY_URL:
        return {"http": PROXY_URL, "https": PROXY_URL}, True, PROXY_URL

    env_proxy = (
        os.environ.get("AOVOW_HTTPS_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    if env_proxy:
        return {"http": env_proxy, "https": env_proxy}, True, env_proxy

    try:
        import yaml
        _cfg = Path.home() / ".aovow" / "settings.yaml"
        if _cfg.exists():
            _data = yaml.safe_load(_cfg.read_text(encoding="utf-8")) or {}
            _oauth = _data.get("oauth", {}) or {}
            cfg_proxy = _oauth.get("proxy") or _data.get("proxy")
            if cfg_proxy:
                return {"http": cfg_proxy, "https": cfg_proxy}, True, cfg_proxy
    except Exception:
        pass

    proxies = urllib.request.getproxies()
    if proxies.get("http") or proxies.get("https"):
        system_proxy = proxies.get("https") or proxies.get("http")
        return proxies, False, system_proxy or "system"
    return None, False, ""


class _CallbackHandler(BaseHTTPRequestHandler):
    """本地回调服务器请求处理器"""

    # 类变量，由 GithubOAuthServer 设置
    received_code: Optional[str] = None
    received_state: Optional[str] = None
    error_message: Optional[str] = None

    def do_GET(self):
        """处理 GitHub 回调"""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/callback":
            query = urllib.parse.parse_qs(parsed.query)
            error = query.get("error", [None])[0]

            if error:
                _CallbackHandler.error_message = query.get(
                    "error_description", [error])[0]
                self._send_html("授权被取消", "#ff5c5c",
                                f"错误：{_CallbackHandler.error_message}")
            else:
                _CallbackHandler.received_code = query.get("code", [None])[0]
                _CallbackHandler.received_state = query.get("state", [None])[0]
                self._send_html("授权成功！", "#00d68f",
                                "GitHub 授权已通过，请返回应用继续操作。")
        elif parsed.path == "/health":
            self._send_html("服务就绪", "#6c5ce7",
                            "回调服务器运行正常，请在新标签页完成 OAuth 授权。")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def _send_html(self, title: str, color: str, message: str):
        """返回响应页面"""
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title><style>
body {{ background:#1e1e2e; color:#e4e4f0; display:flex; 
align-items:center; justify-content:center; height:100vh; 
font-family:-apple-system,BlinkMacSystemFont,sans-serif; }}
.card {{ background:#252536; border:1px solid #3a3a5c; border-radius:16px;
padding:40px 60px; text-align:center; }}
h2 {{ color:{color}; }} p {{ color:#a0a0c0; margin-top:16px; }}
</style></head><body><div class="card">
<h2>{title}</h2><p>{message}</p></div></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        """静默服务器日志"""
        logger.debug(f"OAuth Server: {format % args}")


class GithubOAuthServer:
    """
    GitHub OAuth 本地回调服务器。

    使用方式:
        server = GithubOAuthServer()
        auth_url = server.get_auth_url()
        webbrowser.open(auth_url)
        github_user = server.wait_for_callback(timeout=120)
        if github_user:
            # 登录/注册
        server.stop()
    """

    def __init__(self, port: int = CALLBACK_PORT):
        self._port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[dict] = None
        self._state = SecurityManager.generate_oauth_state()
        self.last_error: str = ""  # 最近一次失败原因（供 UI 展示）

        # 代理预检：启动时检测显式配置的代理是否可达
        # 不可达时自动降级为直连（或系统代理），不强制卡死
        self._proxies, self._proxy_explicit, self._proxy_address = _get_proxies()
        if self._proxy_explicit and self._proxy_address:
            ok, hint = _check_proxy_reachable(self._proxy_address)
            if ok:
                logger.info(f"显式代理 {self._proxy_address} 可达，将使用代理")
            else:
                logger.warning(
                    f"显式代理 {self._proxy_address} 不可达（{hint[:60]}...），"
                    f"自动降级为系统环境（系统代理/直连）")
                self._proxies = None
                self._proxy_explicit = False
                self._proxy_address = ""
        else:
            logger.info("未配置显式代理，使用系统环境（系统代理/直连）")

    def get_auth_url(self) -> str:
        """生成 GitHub OAuth 授权 URL"""
        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "user:email",
            "state": self._state,
        }
        return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"

    def start(self):
        """启动本地 HTTP 服务器"""
        _CallbackHandler.received_code = None
        _CallbackHandler.received_state = None
        _CallbackHandler.error_message = None

        self._server = HTTPServer(("127.0.0.1", self._port), _CallbackHandler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True)
        self._thread.start()
        logger.info(f"OAuth 回调服务器已启动: {REDIRECT_URI}")

    def wait_for_callback(self, timeout: int = 120) -> Optional[dict]:
        """
        等待 GitHub 回调（最多 timeout 秒）。

        Returns:
            GitHub 用户信息字典，失败返回 None
        """
        elapsed = 0
        while _CallbackHandler.received_code is None and \
              _CallbackHandler.error_message is None and \
              elapsed < timeout:
            event = threading.Event()
            event.wait(0.5)
            elapsed += 0.5

        if _CallbackHandler.error_message:
            logger.warning(f"GitHub OAuth 错误: {_CallbackHandler.error_message}")
            return None

        if _CallbackHandler.received_code is None:
            logger.warning("GitHub OAuth 超时")
            return None

        code = _CallbackHandler.received_code

        # 交换 access_token
        access_token = self._exchange_code(code)
        if not access_token:
            return None

        # 获取用户信息
        return self._fetch_user_info(access_token)

    def stop(self):
        """停止服务器（在独立线程中执行，避免阻塞 UI 线程）"""
        if self._server:
            server = self._server
            self._server = None
            self._thread = None
            # 在独立线程中执行 shutdown（会阻塞直到 serve_forever 退出）
            # 但因为是 daemon 线程，不影响主程序
            def _shutdown():
                try:
                    server.shutdown()
                    server.server_close()
                except Exception:
                    pass
            threading.Thread(target=_shutdown, daemon=True).start()

    def _classify_request_error(self, exception: Exception) -> str:
        """把 requests 异常转为用户可理解的中文提示。"""
        msg = str(exception)
        if "ProxyError" in msg or "Unable to connect to proxy" in msg:
            return (
                f"代理 {self._proxy_address or '(系统代理)'} 连接失败——"
                f"请在系统网络设置关闭代理或开启代理软件后重试登录。"
            )
        if "NameResolutionError" in msg or "getaddrinfo failed" in msg:
            return (
                f"DNS 无法解析 github.com——可能是网络不通或被墙，"
                f"请检查网络连接。"
            )
        if "ConnectTimeout" in msg or "ReadTimeout" in msg:
            return f"连接超时：{msg[:120]}...（请检查网络）"
        if "SSLError" in msg:
            return f"SSL 证书错误: {msg[:80]}"
        return f"网络请求失败: {msg[:160]}"

    def _exchange_code(self, code: str) -> Optional[str]:
        """用 authorization code 换取 access_token"""
        import time as _time
        logger.info(f"[OAuth] _exchange_code 开始 code={code[:20]}... proxies={self._proxies}")
        t0 = _time.time()
        try:
            resp = requests.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers={"Accept": "application/json"},
                timeout=(10, 15),
                verify=False,
                proxies=self._proxies,
            )
            data = resp.json()
            logger.info(f"[OAuth] _exchange_code status={resp.status_code} 耗时={_time.time()-t0:.2f}s body_keys={list(data.keys())}")
            if "error" in data:
                self.last_error = data.get("error_description", data.get("error", "未知错误"))
                logger.error(f"[OAuth] _exchange_code GitHub 返回错误: {self.last_error}")
                return None
            token = data.get("access_token")
            logger.info(f"[OAuth] _exchange_code 成功！token 长度={len(token) if token else 0}")
            return token
        except Exception as e:
            self.last_error = self._classify_request_error(e)
            logger.error(f"[OAuth] _exchange_code 异常 耗时={_time.time()-t0:.2f}s 错误={e}")
            return None

    def _fetch_user_info(self, access_token: str) -> Optional[dict]:
        """用 access_token 获取 GitHub 用户信息"""
        import time as _time
        logger.info(f"[OAuth] _fetch_user_info 开始 token={access_token[:10]}... proxies={self._proxies}")
        t0 = _time.time()
        try:
            resp = requests.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=(10, 15),
                verify=False,
                proxies=self._proxies,
            )
            logger.info(f"[OAuth] _fetch_user_info status={resp.status_code} 耗时={_time.time()-t0:.2f}s")
            if resp.status_code != 200:
                self.last_error = f"获取用户信息失败: HTTP {resp.status_code}"
                logger.error(f"[OAuth] _fetch_user_info {self.last_error} body={resp.text[:100]}")
                return None

            user = resp.json()
            info = {
                "github_id": user.get("id"),
                "github_username": user.get("login"),
                "avatar_url": user.get("avatar_url"),
                "name": user.get("name") or user.get("login"),
                "email": user.get("email"),
            }
            logger.info(f"[OAuth] _fetch_user_info 成功！username={info['github_username']}")
            return info
        except Exception as e:
            self.last_error = self._classify_request_error(e)
            logger.error(f"[OAuth] _fetch_user_info 异常 耗时={_time.time()-t0:.2f}s 错误={e}")
            return None

    @property
    def state(self) -> str:
        return self._state


# 导入放在最后避免循环依赖
from workstation.auth.security import SecurityManager
