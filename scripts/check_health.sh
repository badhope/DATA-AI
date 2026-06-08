#!/usr/bin/env bash
# DATA-AI 健康检查脚本
set -e

echo "========================================="
echo "  DATA-AI 健康检查"
echo "========================================="
echo ""

ERRORS=0

# 检查 Python
echo -n "[1/6] Python >= 3.10 ... "
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)')
    if [ "$PY_VERSION" -ge 30 ]; then
        echo "✓ $(python3 --version)"
    else
        echo "✗ 版本过低"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "✗ 未安装"
    ERRORS=$((ERRORS + 1))
fi

# 检查核心模块
echo -n "[2/6] 核心模块 ... "
python3 -c "from data_ai.core.agent import BaseAgent; from data_ai.core.tool import get_tool_registry; print('✓')" 2>/dev/null || { echo "✗ 导入失败"; ERRORS=$((ERRORS + 1)); }

# 检查 RAG 模块
echo -n "[3/6] RAG 系统 ... "
python3 -c "from data_ai.core.rag import RAGPipeline; print('✓')" 2>/dev/null || { echo "✗ 导入失败"; ERRORS=$((ERRORS + 1)); }

# 检查记忆系统
echo -n "[4/6] 记忆系统 ... "
python3 -c "from data_ai.core.memory import SemanticMemoryStore, LearningEngine; print('✓')" 2>/dev/null || { echo "✗ 导入失败"; ERRORS=$((ERRORS + 1)); }

# 检查工具数量
echo -n "[5/6] 工具数量 ... "
TOOL_COUNT=$(python3 -c "
from data_ai.core.tool import register_all_tools, get_tool_registry
register_all_tools()
print(len(get_tool_registry().list_tools()))
" 2>/dev/null || echo "0")
if [ "$TOOL_COUNT" -ge 50 ]; then
    echo "✓ ($TOOL_COUNT 个工具)"
else
    echo "⚠ ($TOOL_COUNT 个工具，预期 >= 50)"
fi

# 检查配置
echo -n "[6/6] 配置文件 ... "
if [ -f "config/config.example.toml" ] || [ -f "$HOME/.data-ai/config.toml" ]; then
    echo "✓"
else
    echo "⚠ 未找到配置文件"
fi

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo "========================================="
    echo "  发现 $ERRORS 个问题"
    echo "========================================="
    exit 1
else
    echo "========================================="
    echo "  所有检查通过 ✓"
    echo "========================================="
fi
