#!/bin/bash

# 项目设置脚本 - Linux版本
# 使用方法：./setup_project.sh

set -e

echo "========================================"
echo "  日志分析 AI 助手 - 项目设置脚本"
echo "========================================"
echo ""

# 检查 Python 环境
echo "[1/6] 检查 Python 环境..."
python3 --version

# 检查 Python 版本是否满足要求
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.9"

if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
    echo "❌ Python 版本过低，需要 3.9 或更高版本"
    exit 1
fi
echo "✓ Python 版本满足要求: $PYTHON_VERSION"

# 检查虚拟环境是否存在
if [ ! -d "./venv" ]; then
    echo ""
    echo "[2/6] 创建虚拟环境..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "✗ 创建虚拟环境失败"
        exit 1
    fi
    echo "✓ 虚拟环境创建成功"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "[3/6] 激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo ""
echo "[4/6] 升级 pip..."
pip install --upgrade pip

# 安装项目依赖
echo ""
echo "[5/6] 安装项目依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "✗ 安装依赖失败"
        exit 1
    fi
    echo "✓ 依赖安装完成"
else
    echo "⚠️  requirements.txt 文件未找到"
    echo "尝试安装基本依赖..."
    pip install streamlit==1.56.0
    if [ $? -ne 0 ]; then
        echo "✗ 安装基本依赖失败"
        exit 1
    fi
    echo "✓ 基本依赖安装完成"
fi

# 检查环境变量配置
echo ""
echo "[6/6] 检查环境变量配置..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "复制环境变量配置文件..."
        cp .env.example .env
        echo "✓ 环境变量配置文件已复制，请根据需要修改 .env 文件"
    else
        echo "⚠️  .env.example 文件未找到"
        echo "请手动创建 .env 文件并配置必要的参数"
    fi
else
    echo "✓ 环境变量配置文件已存在"
fi

echo ""
echo "========================================"
echo "  ✅ 项目设置完成！"
echo ""
echo "  接下来可以执行以下命令："
echo "  1. 运行主程序: python -m src.main"
echo "  2. 启动可视化仪表板: streamlit run src/visualization/dashboard.py"
echo "  3. 运行测试: pytest tests/ -v"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 提示用户选择要运行的命令
echo "请选择要执行的操作："
echo "1. 运行主程序"
echo "2. 启动可视化仪表板"
echo "3. 退出"

read -p "请输入选项 (1-3): " choice

echo ""

case $choice in
    1)
        echo "启动主程序..."
        python -m src.main
        ;;
    2)
        echo "启动可视化仪表板..."
        streamlit run src/visualization/dashboard.py --server.port 8501 --server.address localhost
        ;;
    3)
        echo "退出脚本"
        exit 0
        ;;
    *)
        echo "无效选项，退出脚本"
        exit 1
        ;;
esac