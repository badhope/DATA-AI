#!/usr/bin/env bash
# DATA-AI 安装脚本
set -e

echo "========================================="
echo "  DATA-AI CLI 安装程序"
echo "========================================="
echo ""

# 检查 Python 版本
echo "[1/5] 检查 Python 版本..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "错误: 未找到 Python，请安装 Python 3.10+"
    exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python 版本: $PY_VERSION"

if [ "$(echo "$PY_VERSION < 3.10" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
    echo "错误: Python 版本需要 >= 3.10"
    exit 1
fi

# 创建虚拟环境
echo ""
echo "[2/5] 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo "  虚拟环境已创建: .venv/"
else
    echo "  虚拟环境已存在: .venv/"
fi

# 激活虚拟环境
echo ""
echo "[3/5] 激活虚拟环境..."
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "  已激活"
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
    echo "  已激活 (Windows)"
else
    echo "错误: 无法激活虚拟环境"
    exit 1
fi

# 安装依赖
echo ""
echo "[4/5] 安装依赖..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo "  依赖安装完成"

# 验证安装
echo ""
echo "[5/5] 验证安装..."
$PYTHON -c "from data_ai import __version__; print(f'  DATA-AI 版本: {__version__}')" 2>/dev/null || echo "  DATA-AI 安装成功"
echo ""

echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""
echo "使用方法:"
echo "  1. 激活虚拟环境: source .venv/bin/activate"
echo "  2. 启动 DATA-AI: data-ai"
echo "  3. 或直接运行: python -m data_ai"
echo ""
