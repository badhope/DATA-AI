import pytest

from core.app.workflow.file_runtime import bind_data_workflow_file_runtime


@pytest.fixture(autouse=True)
def _bind_workflow_file_runtime() -> None:
    bind_data_workflow_file_runtime()
