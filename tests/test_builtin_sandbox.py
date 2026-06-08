"""
DATA-AI Sandbox System Tests

Test LocalSandbox, SandboxManager, SandboxConfig, ExecutionResult
"""

import sys
from pathlib import Path

import pytest

# Ensure src is on path
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sandbox_config():
    """Create a SandboxConfig with short timeout for tests."""
    from data_ai.sandbox import SandboxConfig

    return SandboxConfig(timeout=10, max_memory_mb=256)


@pytest.fixture
async def local_sandbox(sandbox_config):
    """Create and set up a LocalSandbox, tear down after test."""
    from data_ai.sandbox import LocalSandbox

    sb = LocalSandbox(config=sandbox_config)
    await sb.create()
    yield sb
    await sb.destroy()


# ─── SandboxConfig Tests ─────────────────────────────────────────────────────


class TestSandboxConfig:
    """SandboxConfig dataclass tests."""

    def test_default_config(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig()
        assert config.timeout == 30
        assert config.max_memory_mb == 512
        assert config.max_cpu_percent == 80
        assert config.max_file_size_mb == 10
        assert config.max_output_size_kb == 100
        assert isinstance(config.allowed_commands, list)
        assert "python" in config.allowed_commands
        assert config.network_enabled is False

    def test_custom_config(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig(timeout=5, max_memory_mb=128)
        assert config.timeout == 5
        assert config.max_memory_mb == 128


# ─── ExecutionResult Tests ───────────────────────────────────────────────────


class TestExecutionResult:
    """ExecutionResult dataclass tests."""

    def test_success_result(self):
        from data_ai.sandbox import ExecutionResult

        result = ExecutionResult(
            success=True,
            stdout="hello",
            stderr="",
            exit_code=0,
            execution_time_ms=100.0,
            sandbox_id="test_123",
        )
        assert result.success is True
        assert result.stdout == "hello"
        assert result.exit_code == 0
        assert result.error is None

    def test_failure_result(self):
        from data_ai.sandbox import ExecutionResult

        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="command not found",
            exit_code=127,
            execution_time_ms=50.0,
            sandbox_id="test_456",
            error="command not found",
        )
        assert result.success is False
        assert result.error == "command not found"


# ─── LocalSandbox Tests ──────────────────────────────────────────────────────


class TestLocalSandbox:
    """LocalSandbox integration tests."""

    @pytest.mark.asyncio
    async def test_create_sandbox(self, sandbox_config):
        from data_ai.sandbox import LocalSandbox, SandboxStatus

        sb = LocalSandbox(config=sandbox_config)
        assert sb.status == SandboxStatus.CREATED
        await sb.create()
        assert sb.status == SandboxStatus.RUNNING
        assert sb.working_dir is not None
        assert sb.working_dir.exists()
        await sb.destroy()
        assert sb.status == SandboxStatus.STOPPED

    @pytest.mark.asyncio
    async def test_execute_code_python(self, local_sandbox):
        result = await local_sandbox.execute_code("print('hello from sandbox')")
        assert result.success is True
        assert "hello from sandbox" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_code_python_error(self, local_sandbox):
        result = await local_sandbox.execute_code("1 / 0")
        assert result.success is False
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_execute_code_unsupported_language(self, local_sandbox):
        result = await local_sandbox.execute_code("echo hi", language="cobol")
        assert result.success is False
        assert "Unsupported language" in result.stderr

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, local_sandbox):
        content = "Hello, sandbox world!"
        written = await local_sandbox.write_file("test.txt", content)
        assert written is True

        read_content = await local_sandbox.read_file("test.txt")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, local_sandbox):
        result = await local_sandbox.read_file("nonexistent.txt")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_files(self, local_sandbox):
        await local_sandbox.write_file("a.txt", "a")
        await local_sandbox.write_file("b.txt", "b")

        files = await local_sandbox.list_files(".")
        assert len(files) >= 2
        names = [f["name"] for f in files]
        assert "a.txt" in names
        assert "b.txt" in names

    @pytest.mark.asyncio
    async def test_execute_command(self, local_sandbox):
        result = await local_sandbox.execute("echo hello")
        assert result.success is True
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sandbox_config):
        from data_ai.sandbox import LocalSandbox, SandboxConfig

        config = SandboxConfig(timeout=1)
        sb = LocalSandbox(config=config)
        await sb.create()

        from data_ai.utils.exceptions import SandboxTimeoutError

        # 跨平台长命令: ``ping -n 11 127.0.0.1`` 在 Win 上 ~10s,
        # ``sleep 10`` 在 Unix 上 10s. timeout=1 应当触发.
        import sys as _sys
        if _sys.platform == "win32":
            cmd = "ping -n 11 127.0.0.1 > NUL"
        else:
            cmd = "sleep 10"
        with pytest.raises(SandboxTimeoutError):
            await sb.execute(cmd)

        await sb.destroy()

    @pytest.mark.asyncio
    async def test_command_validation_dangerous(self, local_sandbox):
        """Dangerous commands should fail (error caught internally, returns failure result)."""
        result = await local_sandbox.execute("rm -rf /")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_destroy_sandbox(self, local_sandbox):
        assert local_sandbox.working_dir is not None
        await local_sandbox.destroy()
        assert local_sandbox.status.value == "stopped"


# ─── SandboxManager Tests ────────────────────────────────────────────────────


class TestSandboxManager:
    """SandboxManager singleton tests."""

    @pytest.mark.asyncio
    async def test_create_and_destroy_sandbox(self):
        from data_ai.sandbox import SandboxManager, SandboxType

        mgr = SandboxManager()
        sb = await mgr.create_sandbox(SandboxType.LOCAL)
        assert sb.sandbox_id in [s["id"] for s in mgr.list_sandboxes()]

        destroyed = await mgr.destroy_sandbox(sb.sandbox_id)
        assert destroyed is True
        assert sb.sandbox_id not in [s["id"] for s in mgr.list_sandboxes()]

    @pytest.mark.asyncio
    async def test_get_sandbox(self):
        from data_ai.sandbox import SandboxManager, SandboxType

        mgr = SandboxManager()
        sb = await mgr.create_sandbox(SandboxType.LOCAL)
        fetched = mgr.get_sandbox(sb.sandbox_id)
        assert fetched is sb
        await mgr.destroy_sandbox(sb.sandbox_id)

    @pytest.mark.asyncio
    async def test_destroy_nonexistent(self):
        from data_ai.sandbox import SandboxManager

        mgr = SandboxManager()
        result = await mgr.destroy_sandbox("nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_sandboxes(self):
        from data_ai.sandbox import SandboxManager, SandboxType

        mgr = SandboxManager()
        initial_count = len(mgr.list_sandboxes())

        await mgr.create_sandbox(SandboxType.LOCAL)
        await mgr.create_sandbox(SandboxType.LOCAL)

        assert len(mgr.list_sandboxes()) == initial_count + 2

        await mgr.destroy_all()
        assert len(mgr.list_sandboxes()) == 0
