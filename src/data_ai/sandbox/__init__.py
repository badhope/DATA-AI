"""
DATA-AI 沙箱执行引擎

提供安全的代码执行环境：
- 本地沙箱：轻量级隔离执行
- Docker 沙箱：完整容器隔离
- 远程沙箱：远程服务器执行
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import (
    SandboxException,
    SandboxResourceLimitError,
    SandboxSecurityError,
    SandboxTimeoutError,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SandboxType(Enum):
    """沙箱类型"""

    LOCAL = "local"
    DOCKER = "docker"
    REMOTE = "remote"


class SandboxStatus(Enum):
    """沙箱状态"""

    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SandboxConfig:
    """沙箱配置"""

    timeout: int = 30  # 执行超时（秒）
    max_memory_mb: int = 512  # 最大内存（MB）
    max_cpu_percent: int = 80  # 最大 CPU 使用率
    max_file_size_mb: int = 10  # 最大文件大小（MB）
    max_output_size_kb: int = 100  # 最大输出大小（KB）
    allowed_commands: list[str] = field(default_factory=lambda: ["python", "pip", "node", "npm", "bash", "git"])
    allowed_paths: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    network_enabled: bool = False  # 是否允许网络访问
    working_dir: str | None = None  # 工作目录


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    sandbox_id: str
    resource_usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseSandbox(ABC):
    """沙箱基类"""

    sandbox_type: SandboxType = SandboxType.LOCAL

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self.sandbox_id = self._generate_id()
        self.status = SandboxStatus.CREATED
        self.working_dir: Path | None = None
        self.logger = get_logger(f"sandbox.{self.sandbox_type.value}")

    def _generate_id(self) -> str:
        import uuid

        return f"{self.sandbox_type.value}_{uuid.uuid4().hex[:8]}"

    @abstractmethod
    async def create(self) -> None:
        """创建沙箱环境"""
        pass

    @abstractmethod
    async def execute(
        self,
        command: str,
        stdin: str | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """执行命令"""
        pass

    @abstractmethod
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
    ) -> ExecutionResult:
        """执行代码"""
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str) -> bool:
        """写入文件"""
        pass

    @abstractmethod
    async def read_file(self, path: str) -> str | None:
        """读取文件"""
        pass

    @abstractmethod
    async def list_files(self, path: str = ".") -> list[dict[str, Any]]:
        """列出文件"""
        pass

    @abstractmethod
    async def destroy(self) -> None:
        """销毁沙箱"""
        pass

    async def create_snapshot(self, name: str) -> bool:
        """创建快照

        子类应覆盖此方法以提供特定实现。本地沙箱通过 zip 打包工作目录实现，
        Docker 沙箱通过 ``docker commit`` 提交为镜像。
        """
        self.logger.warning(
            "当前沙箱类型不支持快照",
            sandbox_id=self.sandbox_id,
            name=name,
            sandbox_type=self.sandbox_type.value,
        )
        return False

    async def restore_snapshot(self, name: str) -> bool:
        """恢复快照

        子类应覆盖此方法。本地沙箱从 zip 解压恢复，Docker 沙箱从镜像重建容器。
        """
        self.logger.warning(
            "当前沙箱类型不支持快照恢复",
            sandbox_id=self.sandbox_id,
            name=name,
            sandbox_type=self.sandbox_type.value,
        )
        return False

    def is_running(self) -> bool:
        """检查是否运行中"""
        return self.status == SandboxStatus.RUNNING


class LocalSandbox(BaseSandbox):
    """
    本地沙箱

    轻量级隔离执行，适用于：
    - 快速验证
    - 简单脚本执行
    - 无需完整隔离的场景
    """

    sandbox_type = SandboxType.LOCAL

    def __init__(self, config: SandboxConfig | None = None):
        super().__init__(config)
        self._temp_dir: Path | None = None
        self._snapshots: dict[str, str] = {}

    async def create(self) -> None:
        """创建本地沙箱环境"""
        # 创建临时工作目录
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"data_ai_sandbox_{self.sandbox_id}_"))
        self.working_dir = self._temp_dir
        self.status = SandboxStatus.RUNNING

        self.logger.info(
            "本地沙箱已创建",
            sandbox_id=self.sandbox_id,
            working_dir=str(self.working_dir),
        )

    async def execute(
        self,
        command: str,
        stdin: str | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """执行命令"""
        if not self.is_running():
            raise SandboxException("Sandbox not running")

        start_time = time.time()
        exec_timeout = timeout or self.config.timeout

        try:
            # 安全检查
            self._validate_command(command)

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                cwd=self.working_dir,
                env={**os.environ, **self.config.env_vars},
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode() if stdin else None),
                    timeout=exec_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise SandboxTimeoutError(
                    f"Command timed out after {exec_timeout}s",
                    sandbox_id=self.sandbox_id,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # 输出大小限制
            max_output = self.config.max_output_size_kb * 1024
            if len(stdout) > max_output:
                stdout = stdout[:max_output] + "\n... [output truncated]"
            if len(stderr) > max_output:
                stderr = stderr[:max_output] + "\n... [output truncated]"

            execution_time_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=proc.returncode or 0,
                execution_time_ms=execution_time_ms,
                sandbox_id=self.sandbox_id,
            )

        except SandboxTimeoutError:
            raise
        except Exception as e:
            self.logger.error(f"执行失败: {e}", sandbox_id=self.sandbox_id)
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_id=self.sandbox_id,
                error=str(e),
            )

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
    ) -> ExecutionResult:
        """执行代码"""
        # 根据语言选择执行器
        language_config = {
            "python": {"ext": ".py", "cmd": "python"},
            "javascript": {"ext": ".js", "cmd": "node"},
            "bash": {"ext": ".sh", "cmd": "bash"},
            "go": {"ext": ".go", "cmd": "go run"},
            "rust": {"ext": ".rs", "cmd": "rustc"},
        }

        if language not in language_config:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1,
                execution_time_ms=0,
                sandbox_id=self.sandbox_id,
                error=f"Unsupported language: {language}",
            )

        config = language_config[language]
        file_path = self.working_dir / f"code{config['ext']}"

        # 写入代码文件
        await self.write_file(str(file_path), code)

        # 执行
        command = f"{config['cmd']} {file_path}"
        return await self.execute(command, timeout=timeout)

    async def write_file(self, path: str, content: str) -> bool:
        """写入文件"""
        try:
            file_path = self.working_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 文件大小检查
            if len(content) > self.config.max_file_size_mb * 1024 * 1024:
                raise SandboxResourceLimitError(
                    f"File size exceeds limit ({self.config.max_file_size_mb}MB)",
                    sandbox_id=self.sandbox_id,
                )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        except Exception as e:
            self.logger.error(f"写入文件失败: {e}", sandbox_id=self.sandbox_id)
            return False

    async def read_file(self, path: str) -> str | None:
        """读取文件"""
        try:
            file_path = self.working_dir / path
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"读取文件失败: {e}", sandbox_id=self.sandbox_id)
            return None

    async def list_files(self, path: str = ".") -> list[dict[str, Any]]:
        """列出文件"""
        try:
            dir_path = self.working_dir / path
            files = []
            for item in dir_path.iterdir():
                files.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                        "modified": item.stat().st_mtime,
                    }
                )
            return files
        except Exception as e:
            self.logger.error(f"列出文件失败: {e}", sandbox_id=self.sandbox_id)
            return []

    async def destroy(self) -> None:
        """销毁沙箱"""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

        self.status = SandboxStatus.STOPPED
        self.logger.info("本地沙箱已销毁", sandbox_id=self.sandbox_id)

    async def create_snapshot(self, name: str) -> bool:
        """创建本地沙箱文件系统快照

        把工作目录的内容打包到一个 zip 文件里，存到 ``<parent>/.snapshots/<name>.zip``。
        """
        if not self._temp_dir or not self._temp_dir.exists():
            self.logger.error("沙箱未运行，无法创建快照", sandbox_id=self.sandbox_id)
            return False

        try:
            snapshot_root = self._temp_dir.parent / ".snapshots"
            snapshot_root.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshot_root / f"{name}.zip"

            if snapshot_path.exists():
                snapshot_path.unlink()

            import zipfile

            with zipfile.ZipFile(str(snapshot_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for item in self._temp_dir.rglob("*"):
                    if item.is_file():
                        arcname = str(item.relative_to(self._temp_dir))
                        zf.write(str(item), arcname)

            self._snapshots[name] = str(snapshot_path)
            self.logger.info(
                "本地快照已创建",
                sandbox_id=self.sandbox_id,
                name=name,
                path=str(snapshot_path),
                size=snapshot_path.stat().st_size,
            )
            return True
        except Exception as e:
            self.logger.error(
                "创建本地快照失败",
                sandbox_id=self.sandbox_id,
                name=name,
                error=str(e),
            )
            return False

    async def restore_snapshot(self, name: str) -> bool:
        """从快照恢复本地沙箱文件系统

        清空当前工作目录中的所有文件，然后从 zip 快照中解压回原位。
        """
        if not self._temp_dir or not self._temp_dir.exists():
            self.logger.error("沙箱未运行，无法恢复快照", sandbox_id=self.sandbox_id)
            return False

        snapshot_path = Path(self._snapshots.get(name, "")) if getattr(self, "_snapshots", None) else None
        if snapshot_path is None or not str(snapshot_path):
            snapshot_path = self._temp_dir.parent / ".snapshots" / f"{name}.zip"

        if not snapshot_path.exists():
            self.logger.error(
                "快照不存在",
                sandbox_id=self.sandbox_id,
                name=name,
                path=str(snapshot_path),
            )
            return False

        try:
            import shutil as _sh
            import zipfile

            for item in self._temp_dir.iterdir():
                if item.name == ".snapshots":
                    continue
                if item.is_dir():
                    _sh.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

            with zipfile.ZipFile(str(snapshot_path), "r") as zf:
                zf.extractall(str(self._temp_dir))

            self.logger.info(
                "本地快照已恢复",
                sandbox_id=self.sandbox_id,
                name=name,
                path=str(snapshot_path),
            )
            return True
        except Exception as e:
            self.logger.error(
                "恢复本地快照失败",
                sandbox_id=self.sandbox_id,
                name=name,
                error=str(e),
            )
            return False

    def _validate_command(self, command: str) -> None:
        """验证命令安全性"""
        # 危险命令检查
        dangerous_patterns = [
            "rm -rf /",
            "mkfs",
            "dd if=",
            "> /dev/sd",
            ":(){ :|:& };:",
            "chmod 777",
            "chown root",
        ]

        for pattern in dangerous_patterns:
            if pattern in command:
                raise SandboxSecurityError(
                    f"Dangerous command detected: {pattern}",
                    sandbox_id=self.sandbox_id,
                )


class DockerSandbox(BaseSandbox):
    """
    Docker 沙箱

    完整容器隔离，适用于：
    - 复杂依赖项目
    - 需要完整系统环境
    - 高安全性要求
    """

    sandbox_type = SandboxType.DOCKER

    def __init__(
        self,
        config: SandboxConfig | None = None,
        image: str = "python:3.11-slim",
    ):
        super().__init__(config)
        self.image = image
        self._container_id: str | None = None
        self._snapshots: dict[str, bool] = {}

    async def create(self) -> None:
        """创建 Docker 容器"""
        try:
            # 检查 Docker 是否可用
            result = await asyncio.create_subprocess_exec(
                "docker",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()

            if result.returncode != 0:
                raise SandboxException("Docker not available")

            # 创建容器
            cmd = [
                "docker",
                "create",
                "--interactive",
                "--rm",
                f"--memory={self.config.max_memory_mb}m",
                f"--cpus={self.config.max_cpu_percent / 100}",
                "--network=none" if not self.config.network_enabled else "--network=bridge",
                "-w",
                "/workspace",
                self.image,
                "/bin/bash",
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise SandboxException(f"Failed to create container: {stderr.decode()}")

            self._container_id = stdout.decode().strip()
            self.status = SandboxStatus.RUNNING

            self.logger.info(
                "Docker沙箱已创建",
                sandbox_id=self.sandbox_id,
                container_id=self._container_id,
                image=self.image,
            )

        except FileNotFoundError:
            raise SandboxException("Docker not installed")

    async def execute(
        self,
        command: str,
        stdin: str | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在容器中执行命令"""
        if not self._container_id:
            raise SandboxException("Container not created")

        start_time = time.time()
        exec_timeout = timeout or self.config.timeout

        try:
            cmd = [
                "docker",
                "exec",
                self._container_id,
                "/bin/bash",
                "-c",
                command,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=exec_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise SandboxTimeoutError(
                    f"Command timed out after {exec_timeout}s",
                    sandbox_id=self.sandbox_id,
                )

            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_id=self.sandbox_id,
            )

        except SandboxTimeoutError:
            raise
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_id=self.sandbox_id,
                error=str(e),
            )

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
    ) -> ExecutionResult:
        """执行代码"""
        # 写入代码到容器
        await self.write_file(f"/workspace/code.{language}", code)

        language_cmd = {
            "python": "python /workspace/code.py",
            "javascript": "node /workspace/code.js",
            "bash": "bash /workspace/code.sh",
        }

        if language not in language_cmd:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1,
                execution_time_ms=0,
                sandbox_id=self.sandbox_id,
            )

        return await self.execute(language_cmd[language], timeout=timeout)

    async def write_file(self, path: str, content: str) -> bool:
        """写入文件到容器"""
        if not self._container_id:
            return False

        try:
            # 使用 docker cp
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(content)
                temp_file = f.name

            cmd = ["docker", "cp", temp_file, f"{self._container_id}:{path}"]
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()

            os.unlink(temp_file)
            return proc.returncode == 0
        except Exception as e:
            self.logger.error(f"写入文件失败: {e}")
            return False

    async def read_file(self, path: str) -> str | None:
        """从容器读取文件"""
        if not self._container_id:
            return None

        try:
            cmd = ["docker", "exec", self._container_id, "cat", path]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return stdout.decode("utf-8")
            return None
        except Exception:
            return None

    async def list_files(self, path: str = ".") -> list[dict[str, Any]]:
        """列出容器中的文件"""
        if not self._container_id:
            return []

        try:
            cmd = ["docker", "exec", self._container_id, "ls", "-la", path]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            # 解析 ls 输出
            files = []
            for line in stdout.decode().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 9:
                        files.append(
                            {
                                "name": parts[-1],
                                "type": "directory" if line.startswith("d") else "file",
                                "size": parts[4],
                            }
                        )
            return files
        except Exception:
            return []

    async def destroy(self) -> None:
        """销毁容器"""
        if self._container_id:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "docker",
                    "rm",
                    "-f",
                    self._container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            except Exception:
                pass

        self.status = SandboxStatus.STOPPED
        self.logger.info("Docker沙箱已销毁", sandbox_id=self.sandbox_id)

    async def create_snapshot(self, name: str) -> bool:
        """创建容器快照（镜像）"""
        if not self._container_id:
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "commit",
                self._container_id,
                name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                self._snapshots[name] = True
                self.logger.info(
                    "Docker 快照已创建",
                    sandbox_id=self.sandbox_id,
                    name=name,
                    container_id=self._container_id,
                )
            return proc.returncode == 0
        except Exception as e:
            self.logger.error(
                "创建 Docker 快照失败",
                sandbox_id=self.sandbox_id,
                name=name,
                error=str(e),
            )
            return False

    async def restore_snapshot(self, name: str) -> bool:
        """从镜像恢复容器：销毁当前容器并用指定镜像重启一个新容器

        注意：当前容器内未持久化的进程/内存状态会丢失，但镜像层（文件系统）会被恢复。
        """
        if not self._container_id:
            self.logger.error("容器未创建，无法恢复快照", sandbox_id=self.sandbox_id)
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "image",
                "inspect",
                name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                self.logger.error(
                    "快照镜像不存在",
                    sandbox_id=self.sandbox_id,
                    name=name,
                )
                return False

            current_id = self._container_id
            cmd = [
                "docker",
                "run",
                "--interactive",
                "--rm",
                "-d",
                f"--memory={self.config.max_memory_mb}m",
                f"--cpus={self.config.max_cpu_percent / 100}",
                "--network=none" if not self.config.network_enabled else "--network=bridge",
                "-w",
                "/workspace",
                "--name",
                f"{self.sandbox_id}_restored",
                name,
                "/bin/bash",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                self.logger.error(
                    "从快照启动容器失败",
                    sandbox_id=self.sandbox_id,
                    name=name,
                    stderr=stderr.decode("utf-8", errors="replace"),
                )
                return False

            kill_proc = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                current_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await kill_proc.communicate()

            self._container_id = stdout.decode().strip()
            self.status = SandboxStatus.RUNNING
            self.logger.info(
                "Docker 快照已恢复",
                sandbox_id=self.sandbox_id,
                name=name,
                new_container_id=self._container_id,
            )
            return True
        except Exception as e:
            self.logger.error(
                "恢复 Docker 快照失败",
                sandbox_id=self.sandbox_id,
                name=name,
                error=str(e),
            )
            return False


class SandboxManager:
    """
    沙箱管理器

    统一管理所有沙箱实例
    """

    _instance: SandboxManager | None = None

    def __new__(cls) -> SandboxManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sandboxes: dict[str, BaseSandbox] = {}
        return cls._instance

    async def create_sandbox(
        self,
        sandbox_type: SandboxType = SandboxType.LOCAL,
        config: SandboxConfig | None = None,
        **kwargs,
    ) -> BaseSandbox:
        """创建沙箱"""
        if sandbox_type == SandboxType.LOCAL:
            sandbox = LocalSandbox(config)
        elif sandbox_type == SandboxType.DOCKER:
            sandbox = DockerSandbox(config, **kwargs)
        else:
            raise SandboxException(f"Unsupported sandbox type: {sandbox_type}")

        await sandbox.create()
        self._sandboxes[sandbox.sandbox_id] = sandbox

        logger.info(
            "沙箱已创建",
            sandbox_id=sandbox.sandbox_id,
            type=sandbox_type.value,
        )

        return sandbox

    def get_sandbox(self, sandbox_id: str) -> BaseSandbox | None:
        """获取沙箱"""
        return self._sandboxes.get(sandbox_id)

    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            await sandbox.destroy()
            return True
        return False

    async def destroy_all(self) -> None:
        """销毁所有沙箱"""
        for sandbox_id in list(self._sandboxes.keys()):
            await self.destroy_sandbox(sandbox_id)

    def list_sandboxes(self) -> list[dict[str, Any]]:
        """列出所有沙箱"""
        return [
            {
                "id": s.sandbox_id,
                "type": s.sandbox_type.value,
                "status": s.status.value,
            }
            for s in self._sandboxes.values()
        ]


# 全局管理器
_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    """获取全局沙箱管理器"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager
