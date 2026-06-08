"""
pytest 启动脚本 - 在 Python 进程启动时过滤第三方库警告
用法: python run_tests.py tests/                  (走本脚本, 自动过滤 UserWarning)
或者直接设置: PYTHONWARNINGS=ignore::UserWarning python -m pytest tests/
"""
import subprocess
import sys
import os

env = os.environ.copy()
env['PYTHONWARNINGS'] = 'ignore::UserWarning'

result = subprocess.run(
    [sys.executable, '-m', 'pytest'] + sys.argv[1:],
    env=env,
    cwd=os.getcwd(),
)
sys.exit(result.returncode)
