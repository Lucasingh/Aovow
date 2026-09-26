"""
运行环境信息：Python 解释器、环境变量（安全子集）、工作目录、用户身份。

环境变量只暴露白名单（PATH、HOME/USERPROFILE 等），**绝不输出任何凭据类变量**
（API_KEY / PASSWORD / TOKEN / SECRET 等），避免误把敏感信息打进报告。
"""

from __future__ import annotations

import getpass
import os
import sys
from typing import Any, Dict

# 允许暴露的环境变量白名单
_ENV_WHITELIST = {
    "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
    "HOMEDRIVE", "HOMEPATH", "SYSTEMROOT", "USER", "USERNAME", "LANG",
    "LC_ALL", "SHELL", "TERM", "PWD", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "TZ", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV", "JAVA_HOME", "GOPATH", "RUSTUP_HOME", "CARGO_HOME",
}

# 敏感变量名关键字：匹配到就绝不输出
_SECRET_KEYWORDS = ("KEY", "PASSWORD", "PASSWD", "TOKEN", "SECRET", "CREDENTIAL", "AUTH")


def runtime_info() -> Dict[str, Any]:
    """获取运行环境信息。

    Returns:
        字典：python（版本/可执行/前缀/平台）、env（白名单环境变量）、
        cwd、user、pid、cpu_bits。
    """
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in _ENV_WHITELIST or (
            upper.startswith(("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"))
        ):
            if not any(secret in upper for secret in _SECRET_KEYWORDS):
                env[key] = value

    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""

    return {
        "python": {
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "executable": sys.executable,
            "prefix": sys.prefix,
            "platform": sys.platform,
            "implementation": sys.implementation.name,
            "maxsize_bits": sys.maxsize.bit_length(),
        },
        "env": env,
        "cwd": os.getcwd(),
        "user": user,
        "pid": os.getpid(),
    }
