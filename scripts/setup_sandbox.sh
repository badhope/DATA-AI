#!/bin/bash
# DATA-AI 默认沙箱环境一键安装
# 用途: 新建沙箱后,执行此脚本装齐所有 DATA-AI 需要的系统包、Python 库、中文字体
# 用法: bash scripts/setup_sandbox.sh

set -e

echo "=========================================="
echo "DATA-AI 沙箱环境安装"
echo "=========================================="

# ─── 1. 系统包 ─────────────────────────────────────
echo ""
echo "[1/4] 系统包 (apt) ..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-core \
    pandoc \
    ghostscript \
    poppler-utils \
    imagemagick \
    fonts-wqy-microhei \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    ttf-mscorefonts-installer \
    2>&1 | tail -3

# ─── 2. Python 库 ─────────────────────────────────
echo ""
echo "[2/4] Python 库 (pip) ..."

# 基础(必需)
sudo pip install --quiet --no-warn-script-location \
    openpyxl \
    python-docx \
    python-pptx \
    pypdf \
    PyPDF2 \
    reportlab \
    matplotlib \
    Pillow \
    xlsxwriter \
    requests \
    2>&1 | tail -3

# 增强(可选但推荐)
sudo pip install --quiet --no-warn-script-location \
    pandas \
    PyMuPDF \
    pdfplumber \
    docxtpl \
    docxcompose \
    2>&1 | tail -3

# ─── 3. 字体缓存 ───────────────────────────────────
echo ""
echo "[3/4] 字体缓存刷新 ..."
sudo fc-cache -fv >/dev/null 2>&1
fc-list :lang=zh | wc -l | xargs -I{} echo "  ✓ 已注册中文字体: {} 个家族"

# ─── 4. 验证 ──────────────────────────────────────
echo ""
echo "[4/4] 验证 ..."
python3 -c "
mods = [
    ('openpyxl', 'Excel 读写'),
    ('docx', 'Word 读写'),
    ('pptx', 'PPT 读写'),
    ('pypdf', 'PDF 读取'),
    ('reportlab', 'PDF 生成'),
    ('matplotlib', '图表'),
    ('pandas', '数据分析'),
    ('fitz', 'PDF 编辑(PyMuPDF)'),
    ('pdfplumber', 'PDF 表格'),
]
for mod, desc in mods:
    try:
        __import__(mod.split()[0])
        print(f'  ✓ {mod:12s} ({desc})')
    except ImportError:
        print(f'  ✗ {mod:12s} 缺失')
"

clis=("libreoffice" "pandoc" "gs" "convert" "pdftotext")
for cmd in "${clis[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  ✓ CLI $cmd"
    else
        echo "  ✗ CLI $cmd 缺失"
    fi
done

echo ""
echo "=========================================="
echo "✅ DATA-AI 沙箱环境安装完成"
echo "=========================================="
