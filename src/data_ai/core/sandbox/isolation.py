"""
沙箱隔离机制模块。

本模块实现了不同级别的沙箱隔离机制，包括进程隔离、容器隔离和虚拟机隔离。

主要类:
- IsolationLevel: 隔离级别枚举
- IsolationConfig: 隔离配置
- IsolationManager: 隔离管理器
- IsolatedEnvironment: 隔离环境
"""

import json
import multiprocessing
import os
import pickle
import subprocess
import tempfile
import threading
import traceback
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class IsolationLevel(Enum):
    """
    隔离级别枚举。

    定义不同的隔离级别，从轻量到重量级。

    Attributes:
        PROCESS: 进程级隔离，使用子进程
        CONTAINER: 容器级隔离，使用 Docker 等容器技术
        VM: 虚拟机级隔离，使用完整的虚拟化
    """

    PROCESS = auto()
    CONTAINER = auto()
    VM = auto()

    def get_security_level(self) -> str:
        """获取安全级别描述。"""
        levels = {
            IsolationLevel.PROCESS: "基础",
            IsolationLevel.CONTAINER: "高级",
            IsolationLevel.VM: "最高",
        }
        return levels.get(self, "未知")

    def get_overhead(self) -> str:
        """获取性能开销描述。"""
        overheads = {
            IsolationLevel.PROCESS: "低",
            IsolationLevel.CONTAINER: "中",
            IsolationLevel.VM: "高",
        }
        return overheads.get(self, "未知")


@dataclass
class IsolationConfig:
    """
    隔离配置。

    配置隔离环境的参数。

    Attributes:
        level: 隔离级别
        name: 环境名称
        timeout: 超时时间（秒）
        memory_limit_mb: 内存限制 (MB)
        cpu_limit_percent: CPU 限制百分比
        network_enabled: 是否启用网络
        shared_paths: 共享路径列表
        environment_variables: 环境变量
        working_directory: 工作目录
        auto_cleanup: 是否自动清理
    """

    level: IsolationLevel = IsolationLevel.PROCESS
    name: str = ""
    timeout: float = 300.0
    memory_limit_mb: int = 1024
    cpu_limit_percent: float = 80.0
    network_enabled: bool = False
    shared_paths: list[str] = field(default_factory=list)
    environment_variables: dict[str, str] = field(default_factory=dict)
    working_directory: str | None = None
    auto_cleanup: bool = True

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "level": self.level.name,
            "name": self.name,
            "timeout": self.timeout,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit_percent": self.cpu_limit_percent,
            "network_enabled": self.network_enabled,
            "shared_paths": self.shared_paths,
            "environment_variables": self.environment_variables,
            "working_directory": self.working_directory,
            "auto_cleanup": self.auto_cleanup,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IsolationConfig":
        """从字典创建配置。"""
        return cls(
            level=IsolationLevel[data.get("level", "PROCESS")],
            name=data.get("name", ""),
            timeout=data.get("timeout", 300.0),
            memory_limit_mb=data.get("memory_limit_mb", 1024),
            cpu_limit_percent=data.get("cpu_limit_percent", 80.0),
            network_enabled=data.get("network_enabled", False),
            shared_paths=data.get("shared_paths", []),
            environment_variables=data.get("environment_variables", {}),
            working_directory=data.get("working_directory"),
            auto_cleanup=data.get("auto_cleanup", True),
        )


class IsolationError(Exception):
    """隔离相关错误。"""

    def __init__(self, message: str, code: str = "ISOLATION_ERROR", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


class IsolatedEnvironment(ABC):
    """
    隔离环境抽象基类。

    定义隔离环境的通用接口。
    """

    def __init__(self, config: IsolationConfig) -> None:
        """
        初始化隔离环境。

        Args:
            config: 隔离配置
        """
        self.config = config
        self.env_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.is_active = False
        self._result_queue: multiprocessing.Queue | None = None

    @abstractmethod
    def create(self) -> None:
        """
        创建隔离环境。

        Raises:
            IsolationError: 如果创建失败
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """
        销毁隔离环境。

        Raises:
            IsolationError: 如果销毁失败
        """
        pass

    @abstractmethod
    def execute(self, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        在隔离环境中执行代码。

        Args:
            code: 要执行的代码（字符串或可调用对象）
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """
        获取环境状态。

        Returns:
            状态信息字典
        """
        pass

    def communicate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        与隔离环境通信。

        Args:
            message: 要发送的消息

        Returns:
            响应消息
        """
        # 默认实现，子类可以覆盖
        return {"status": "error", "message": "Communication not implemented"}


class ProcessIsolatedEnvironment(IsolatedEnvironment):
    """
    进程级隔离环境。

    使用子进程实现隔离，适用于轻量级隔离需求。
    """

    def __init__(self, config: IsolationConfig) -> None:
        """初始化进程隔离环境。"""
        super().__init__(config)
        self._process: multiprocessing.Process | None = None
        self._result_queue = multiprocessing.Queue()
        self._work_dir: str | None = None

    def create(self) -> None:
        """创建进程隔离环境。"""
        if self.is_active:
            return

        # 创建工作目录
        if self.config.working_directory:
            self._work_dir = self.config.working_directory
        else:
            self._work_dir = tempfile.mkdtemp(prefix=f"sandbox_{self.env_id}_")

        os.makedirs(self._work_dir, exist_ok=True)
        self.is_active = True

    def destroy(self) -> None:
        """销毁进程隔离环境。"""
        if not self.is_active:
            return

        # 终止进程
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5.0)
            if self._process.is_alive():
                self._process.kill()

        # 清理工作目录
        if self.config.auto_cleanup and self._work_dir:
            try:
                import shutil

                shutil.rmtree(self._work_dir, ignore_errors=True)
            except Exception:
                pass

        self.is_active = False

    def execute(self, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        在子进程中执行代码。

        Args:
            code: 要执行的代码
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        if not self.is_active:
            raise IsolationError("Environment not created", code="ENV_NOT_CREATED")

        # 准备执行参数
        exec_data = {
            "code": code,
            "args": args,
            "kwargs": kwargs,
            "work_dir": self._work_dir,
            "env_vars": self.config.environment_variables,
        }

        # 创建结果队列
        result_queue = multiprocessing.Queue()

        # 创建并启动进程
        self._process = multiprocessing.Process(target=self._run_in_process, args=(exec_data, result_queue))
        self._process.start()

        # 等待结果
        try:
            result = result_queue.get(timeout=self.config.timeout)
            self._process.join(timeout=1.0)
        except Exception as e:
            # 超时或错误
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1.0)

            return False, None, "", f"Execution failed: {e}"

        return (
            result.get("success", False),
            result.get("return_value"),
            result.get("stdout", ""),
            result.get("stderr", ""),
        )

    @staticmethod
    def _run_in_process(exec_data: dict[str, Any], result_queue: multiprocessing.Queue) -> None:
        """
        在子进程中运行代码。

        Args:
            exec_data: 执行数据
            result_queue: 结果队列
        """
        import io
        from contextlib import redirect_stderr, redirect_stdout

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = {
            "success": False,
            "return_value": None,
            "stdout": "",
            "stderr": "",
        }

        try:
            # 设置工作目录
            if exec_data.get("work_dir"):
                os.chdir(exec_data["work_dir"])

            # 设置环境变量
            for key, value in exec_data.get("env_vars", {}).items():
                os.environ[key] = value

            code = exec_data["code"]
            args = exec_data.get("args", ())
            kwargs = exec_data.get("kwargs", {})

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                if isinstance(code, str):
                    # 执行代码字符串
                    local_vars = {}
                    exec(code, {}, local_vars)
                    result["return_value"] = local_vars.get("__return__")
                elif callable(code):
                    # 执行可调用对象
                    result["return_value"] = code(*args, **kwargs)
                else:
                    raise ValueError("Code must be string or callable")

            result["success"] = True

        except Exception as e:
            result["stderr"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

        finally:
            result["stdout"] = stdout_capture.getvalue()
            result["stderr"] = result.get("stderr", "") + stderr_capture.getvalue()

            try:
                result_queue.put(result)
            except Exception:
                pass

    def get_status(self) -> dict[str, Any]:
        """获取环境状态。"""
        return {
            "env_id": self.env_id,
            "level": self.config.level.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "work_directory": self._work_dir,
            "process_alive": self._process.is_alive() if self._process else False,
        }


class ContainerIsolatedEnvironment(IsolatedEnvironment):
    """
    容器级隔离环境。

    使用 Docker 容器实现隔离，适用于需要更强隔离的场景。
    """

    def __init__(self, config: IsolationConfig) -> None:
        """初始化容器隔离环境。"""
        super().__init__(config)
        self._container_id: str | None = None
        self._image: str = "python:3.10-slim"
        self._docker_available: bool | None = None

    def _check_docker(self) -> bool:
        """检查 Docker 是否可用。"""
        if self._docker_available is not None:
            return self._docker_available

        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
            self._docker_available = result.returncode == 0
        except Exception:
            self._docker_available = False

        return self._docker_available

    def create(self) -> None:
        """创建容器隔离环境。"""
        if self.is_active:
            return

        if not self._check_docker():
            raise IsolationError("Docker is not available", code="DOCKER_NOT_AVAILABLE")

        try:
            # 构建容器创建命令
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                f"sandbox_{self.env_id}",
                "--memory",
                f"{self.config.memory_limit_mb}m",
                "--cpus",
                str(self.config.cpu_limit_percent / 100),
            ]

            # 网络设置
            if not self.config.network_enabled:
                cmd.append("--network=none")

            # 共享路径
            for path in self.config.shared_paths:
                if os.path.exists(path):
                    cmd.extend(["-v", f"{path}:{path}"])

            # 工作目录
            if self.config.working_directory:
                cmd.extend(["-w", self.config.working_directory])

            # 环境变量
            for key, value in self.config.environment_variables.items():
                cmd.extend(["-e", f"{key}={value}"])

            # 镜像
            cmd.append(self._image)

            # 保持容器运行
            cmd.extend(["tail", "-f", "/dev/null"])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                raise IsolationError(f"Failed to create container: {result.stderr}", code="CONTAINER_CREATE_FAILED")

            self._container_id = result.stdout.strip()
            self.is_active = True

        except subprocess.TimeoutExpired:
            raise IsolationError("Container creation timed out", code="CONTAINER_TIMEOUT")
        except Exception as e:
            raise IsolationError(f"Failed to create container: {e}", code="CONTAINER_ERROR")

    def destroy(self) -> None:
        """销毁容器隔离环境。"""
        if not self.is_active or not self._container_id:
            return

        try:
            # 停止容器
            subprocess.run(["docker", "stop", self._container_id], capture_output=True, timeout=30)

            # 删除容器
            subprocess.run(["docker", "rm", "-f", self._container_id], capture_output=True, timeout=30)

        except Exception:
            pass

        self._container_id = None
        self.is_active = False

    def execute(self, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        在容器中执行代码。

        Args:
            code: 要执行的代码
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        if not self.is_active or not self._container_id:
            raise IsolationError("Container not created", code="CONTAINER_NOT_CREATED")

        # 序列化代码和参数
        if callable(code):
            # 对于可调用对象，需要序列化
            code_str = f"""
import pickle
import sys

code = pickle.loads({pickle.dumps(code)!r})
args = {args!r}
kwargs = {kwargs!r}

try:
    result = code(*args, **kwargs)
    print("RESULT:", pickle.dumps(result).hex())
except Exception as e:
    print("ERROR:", str(e), file=sys.stderr)
"""
        else:
            code_str = code

        # 创建临时脚本文件
        script_path = f"/tmp/exec_{uuid.uuid4().hex}.py"

        try:
            # 将脚本复制到容器
            subprocess.run(
                ["docker", "exec", "-i", self._container_id, "bash", "-c", f"cat > {script_path}"],
                input=code_str.encode(),
                capture_output=True,
                timeout=10,
            )

            # 执行脚本
            result = subprocess.run(
                ["docker", "exec", self._container_id, "python", script_path],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )

            stdout = result.stdout
            stderr = result.stderr
            success = result.returncode == 0

            # 解析结果
            return_value = None
            if "RESULT:" in stdout:
                try:
                    result_hex = stdout.split("RESULT:")[-1].strip().split()[0]
                    return_value = pickle.loads(bytes.fromhex(result_hex))
                except Exception:
                    pass

            return success, return_value, stdout, stderr

        except subprocess.TimeoutExpired:
            return False, None, "", "Execution timed out"
        except Exception as e:
            return False, None, "", str(e)
        finally:
            # 清理脚本文件
            try:
                subprocess.run(
                    ["docker", "exec", self._container_id, "rm", "-f", script_path], capture_output=True, timeout=5
                )
            except Exception:
                pass

    def get_status(self) -> dict[str, Any]:
        """获取容器状态。"""
        status = {
            "env_id": self.env_id,
            "level": self.config.level.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "container_id": self._container_id,
            "docker_available": self._docker_available,
        }

        if self._container_id:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Status}}", self._container_id],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                status["container_status"] = result.stdout.strip()
            except Exception:
                status["container_status"] = "unknown"

        return status

    def communicate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        与容器通信。

        Args:
            message: 消息内容

        Returns:
            响应消息
        """
        if not self.is_active or not self._container_id:
            return {"status": "error", "message": "Container not active"}

        # 将消息写入容器
        try:
            msg_json = json.dumps(message)
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    self._container_id,
                    "bash",
                    "-c",
                    f"echo '{msg_json}' > /tmp/comm_{self.env_id}.json",
                ],
                capture_output=True,
                timeout=10,
            )

            return {"status": "success", "message": "Message sent"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class VMIsolatedEnvironment(IsolatedEnvironment):
    """
    虚拟机级隔离环境。

    使用虚拟机实现最强隔离，适用于最高安全要求的场景。
    注意：此实现为框架设计，实际使用需要配置虚拟化管理工具。
    """

    def __init__(self, config: IsolationConfig) -> None:
        """初始化虚拟机隔离环境。"""
        super().__init__(config)
        self._vm_id: str | None = None
        self._vm_ip: str | None = None
        self._ssh_key_path: str | None = None

    def create(self) -> None:
        """创建虚拟机隔离环境。"""
        if self.is_active:
            return

        # 注意：这是框架实现，实际需要配置虚拟化管理工具
        # 如 libvirt, VMware, 或云服务 API

        raise IsolationError(
            "VM isolation requires virtualization infrastructure configuration. "
            "Please implement VM creation using libvirt, VMware, or cloud APIs.",
            code="VM_NOT_CONFIGURED",
            details={
                "suggested_tools": ["libvirt", "VMware vSphere API", "AWS EC2", "Azure VM"],
                "config": self.config.to_dict(),
            },
        )

    def destroy(self) -> None:
        """销毁虚拟机隔离环境。"""
        # 框架实现
        self._vm_id = None
        self._vm_ip = None
        self.is_active = False

    def execute(self, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        在虚拟机中执行代码。

        Args:
            code: 要执行的代码
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        if not self.is_active:
            raise IsolationError("VM not created", code="VM_NOT_CREATED")

        # 框架实现 - 需要通过 SSH 执行
        raise IsolationError("VM execution requires SSH configuration", code="VM_SSH_NOT_CONFIGURED")

    def get_status(self) -> dict[str, Any]:
        """获取虚拟机状态。"""
        return {
            "env_id": self.env_id,
            "level": self.config.level.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "vm_id": self._vm_id,
            "vm_ip": self._vm_ip,
        }


class IsolationManager:
    """
    隔离管理器。

    管理多个隔离环境的创建、执行和销毁。

    Attributes:
        environments: 环境字典

    Example:
        >>> manager = IsolationManager()
        >>> env = manager.create_isolated_environment(
        ...     IsolationConfig(level=IsolationLevel.PROCESS)
        ... )
        >>> success, result, stdout, stderr = env.execute("print('hello')")
        >>> manager.destroy_environment(env.env_id)
    """

    def __init__(self, max_environments: int = 10) -> None:
        """
        初始化隔离管理器。

        Args:
            max_environments: 最大环境数量
        """
        self.environments: dict[str, IsolatedEnvironment] = {}
        self.max_environments = max_environments
        self._lock = threading.RLock()

    def create_isolated_environment(self, config: IsolationConfig | None = None) -> IsolatedEnvironment:
        """
        创建隔离环境。

        Args:
            config: 隔离配置

        Returns:
            创建的隔离环境

        Raises:
            IsolationError: 如果创建失败或达到最大数量
        """
        config = config or IsolationConfig()

        with self._lock:
            if len(self.environments) >= self.max_environments:
                raise IsolationError(f"Maximum environments ({self.max_environments}) reached", code="MAX_ENVIRONMENTS")

            # 根据隔离级别创建环境
            if config.level == IsolationLevel.PROCESS:
                env = ProcessIsolatedEnvironment(config)
            elif config.level == IsolationLevel.CONTAINER:
                env = ContainerIsolatedEnvironment(config)
            elif config.level == IsolationLevel.VM:
                env = VMIsolatedEnvironment(config)
            else:
                raise IsolationError(f"Unknown isolation level: {config.level}", code="UNKNOWN_LEVEL")

            # 创建环境
            env.create()
            self.environments[env.env_id] = env

            return env

    def destroy_environment(self, env_id: str) -> bool:
        """
        销毁隔离环境。

        Args:
            env_id: 环境 ID

        Returns:
            如果销毁成功返回 True
        """
        with self._lock:
            if env_id not in self.environments:
                return False

            env = self.environments.pop(env_id)
            env.destroy()
            return True

    def get_environment(self, env_id: str) -> IsolatedEnvironment | None:
        """
        获取隔离环境。

        Args:
            env_id: 环境 ID

        Returns:
            隔离环境实例，如果不存在返回 None
        """
        return self.environments.get(env_id)

    def communicate(self, env_id: str, message: dict[str, Any]) -> dict[str, Any]:
        """
        与隔离环境通信。

        Args:
            env_id: 环境 ID
            message: 消息内容

        Returns:
            响应消息
        """
        env = self.get_environment(env_id)
        if env is None:
            return {"status": "error", "message": "Environment not found"}

        return env.communicate(message)

    def execute_in_environment(self, env_id: str, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        在指定环境中执行代码。

        Args:
            env_id: 环境 ID
            code: 要执行的代码
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        env = self.get_environment(env_id)
        if env is None:
            raise IsolationError(f"Environment {env_id} not found", code="ENV_NOT_FOUND")

        return env.execute(code, *args, **kwargs)

    def list_environments(self) -> list[dict[str, Any]]:
        """
        列出所有环境。

        Returns:
            环境状态列表
        """
        with self._lock:
            return [env.get_status() for env in self.environments.values()]

    def cleanup_all(self) -> int:
        """
        清理所有环境。

        Returns:
            清理的环境数量
        """
        count = 0
        with self._lock:
            for env_id in list(self.environments.keys()):
                try:
                    self.destroy_environment(env_id)
                    count += 1
                except Exception:
                    pass
        return count

    def get_statistics(self) -> dict[str, Any]:
        """
        获取管理器统计信息。

        Returns:
            统计信息字典
        """
        with self._lock:
            by_level = {}
            for env in self.environments.values():
                level = env.config.level.name
                by_level[level] = by_level.get(level, 0) + 1

            return {
                "total_environments": len(self.environments),
                "max_environments": self.max_environments,
                "by_level": by_level,
            }

    def __enter__(self) -> "IsolationManager":
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出。"""
        self.cleanup_all()


def create_isolation_context(level: IsolationLevel = IsolationLevel.PROCESS, **kwargs) -> "IsolationContext":
    """
    创建隔离上下文的便捷函数。

    Args:
        level: 隔离级别
        **kwargs: 配置参数

    Returns:
        隔离上下文
    """
    config = IsolationConfig(level=level, **kwargs)
    return IsolationContext(config)


class IsolationContext:
    """
    隔离上下文管理器。

    提供便捷的隔离环境使用方式。

    Example:
        >>> with IsolationContext(IsolationConfig()) as ctx:
        ...     success, result, stdout, stderr = ctx.execute("print('hello')")
    """

    def __init__(self, config: IsolationConfig) -> None:
        """
        初始化隔离上下文。

        Args:
            config: 隔离配置
        """
        self.config = config
        self.manager = IsolationManager()
        self.env: IsolatedEnvironment | None = None

    def __enter__(self) -> "IsolationContext":
        """进入上下文。"""
        self.env = self.manager.create_isolated_environment(self.config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文。"""
        if self.env:
            self.manager.destroy_environment(self.env.env_id)

    def execute(self, code: str | Callable, *args, **kwargs) -> tuple[bool, Any, str, str]:
        """
        执行代码。

        Args:
            code: 要执行的代码
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (成功标志, 返回值, 标准输出, 标准错误) 元组
        """
        if self.env is None:
            raise IsolationError("Environment not initialized", code="ENV_NOT_INITIALIZED")
        return self.env.execute(code, *args, **kwargs)

    def get_status(self) -> dict[str, Any]:
        """获取环境状态。"""
        if self.env is None:
            return {"status": "not_initialized"}
        return self.env.get_status()
