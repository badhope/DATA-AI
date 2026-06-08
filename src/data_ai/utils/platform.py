"""
DATA-AI 跨平台适配模块

处理 Windows/Linux/macOS 之间的差异。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .logging import get_logger

logger = get_logger(__name__)


class OSType(Enum):
    """操作系统类型枚举

    标识代码运行的操作系统平台。
    """

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@dataclass
class PlatformInfo:
    """平台信息"""

    os_type: OSType
    os_name: str
    os_version: str
    architecture: str
    python_version: str
    is_64bit: bool
    home_dir: str
    config_dir: str
    data_dir: str
    cache_dir: str
    shell: str


def get_os_type() -> OSType:
    """获取操作系统类型"""
    system = platform.system().lower()
    if system == "windows":
        return OSType.WINDOWS
    elif system == "linux":
        return OSType.LINUX
    elif system == "darwin":
        return OSType.MACOS
    return OSType.UNKNOWN


def get_platform_info() -> PlatformInfo:
    """获取平台信息"""
    os_type = get_os_type()

    # 确定数据目录
    home = Path.home()
    if os_type == OSType.WINDOWS:
        config_dir = os.environ.get("APPDATA", str(home / "AppData" / "Roaming")) + "/data-ai"
        data_dir = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")) + "/data-ai"
        cache_dir = str(home / "AppData" / "Local" / "data-ai" / "cache")
        shell = "powershell"
    elif os_type == OSType.MACOS:
        config_dir = str(home / "Library" / "Application Support" / "data-ai")
        data_dir = str(home / "Library" / "Application Support" / "data-ai")
        cache_dir = str(home / "Library" / "Caches" / "data-ai")
        shell = "zsh"
    else:
        config_dir = str(home / ".config" / "data-ai")
        data_dir = str(home / ".local" / "share" / "data-ai")
        cache_dir = str(home / ".cache" / "data-ai")
        shell = "bash"

    return PlatformInfo(
        os_type=os_type,
        os_name=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        is_64bit=sys.maxsize > 2**32,
        home_dir=str(home),
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        shell=shell,
    )


def ensure_directories() -> PlatformInfo:
    """确保所有必要目录存在"""
    info = get_platform_info()
    for dir_path in [info.config_dir, info.data_dir, info.cache_dir]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    return info


def get_config_path(filename: str = "config.toml") -> str:
    """获取配置文件路径"""
    info = get_platform_info()
    return str(Path(info.config_dir) / filename)


def get_data_path(filename: str = "") -> str:
    """获取数据文件路径"""
    info = get_platform_info()
    if filename:
        return str(Path(info.data_dir) / filename)
    return info.data_dir


def get_cache_path(filename: str = "") -> str:
    """获取缓存文件路径"""
    info = get_platform_info()
    if filename:
        return str(Path(info.cache_dir) / filename)
    return info.cache_dir


def open_file(path: str) -> bool:
    """用系统默认程序打开文件"""
    try:
        os_type = get_os_type()
        if os_type == OSType.WINDOWS:
            os.startfile(path)
        elif os_type == OSType.MACOS:
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except Exception as e:
        logger.error(f"打开文件失败: {e}")
        return False


def open_terminal(command: str = "") -> bool:
    """在新的终端窗口中执行命令"""
    try:
        os_type = get_os_type()
        if os_type == OSType.WINDOWS:
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", command])
        elif os_type == OSType.MACOS:
            subprocess.Popen(["open", "-a", "Terminal.app"])
        else:
            # Linux: 尝试常见终端
            terminals = [
                ["gnome-terminal", "--", "bash", "-c", command],
                ["konsole", "-e", "bash", "-c", command],
                ["xfce4-terminal", "-e", f"bash -c '{command}'"],
                ["xterm", "-e", "bash", "-c", command],
            ]
            for term_cmd in terminals:
                try:
                    subprocess.Popen(term_cmd)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception as e:
        logger.error(f"打开终端失败: {e}")
        return False


def get_editor_command() -> list[str]:
    """获取系统默认编辑器命令"""
    editor = os.environ.get("EDITOR", "")
    if editor:
        return editor.split()

    os_type = get_os_type()
    if os_type == OSType.WINDOWS:
        return ["notepad"]
    elif os_type == OSType.MACOS:
        return ["open", "-a", "TextEdit"]
    else:
        for cmd in ["nano", "vim", "vi"]:
            if shutil.which(cmd):
                return [cmd]
        return ["vi"]


def check_command_exists(command: str) -> bool:
    """检查命令是否存在"""
    return shutil.which(command) is not None


def get_available_shells() -> list[str]:
    """获取可用的 Shell"""
    shells = []
    for shell in ["bash", "zsh", "fish", "sh"]:
        if check_command_exists(shell):
            shells.append(shell)

    os_type = get_os_type()
    if os_type == OSType.WINDOWS:
        if check_command_exists("powershell"):
            shells.append("powershell")
        if check_command_exists("cmd"):
            shells.append("cmd")

    return shells


def get_system_info() -> dict[str, str]:
    """获取系统信息摘要"""
    info = get_platform_info()
    return {
        "os": info.os_name,
        "os_type": info.os_type.value,
        "version": info.os_version,
        "architecture": info.architecture,
        "python": info.python_version,
        "64bit": str(info.is_64bit),
        "shell": info.shell,
        "config_dir": info.config_dir,
        "data_dir": info.data_dir,
    }
