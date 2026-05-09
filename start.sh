#!/bin/bash
# 安牛后端启动脚本

cd "$(dirname "$0")"

echo "🐮 启动安牛后端服务..."
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
echo "✅ Python 版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -q -r backend/requirements.txt

# 启动服务
echo ""
echo "🚀 启动服务: http://localhost:8000"
echo "📖 API文档: http://localhost:8000/docs"
echo ""

python3 -m backend.app
