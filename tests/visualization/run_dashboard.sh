#!/bin/bash

# 可视化仪表板启动脚本Linux版本
# 使用方法：./tests/visualization/run_dashboard.sh

echo "========================================"
echo "  日志分析 AI 助手 - 可视化仪表板"
echo "========================================"
echo ""

# 检查虚拟环境是否存在
if [ ! -d "./venv" ]; then
    echo "❌ 虚拟环境未找到，请先创建虚拟环境..."
    echo ""
    echo "执行以下命令创建虚拟环境："
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install streamlit"
    echo ""
    exit 1
fi

# 激活虚拟环境
echo "[1/3] 激活虚拟环境..."
source venv/bin/activate

# 检查 Streamlit 是否安装
echo "[2/3] 检查 Streamlit 依赖..."
streamlit_version=$(python3 -c "import streamlit; print(streamlit.__version__)" 2>&1)
if [ $? -ne 0 ]; then
    echo "⚠️  Streamlit 未安装，正在安装..."
    pip install streamlit==1.56.0
    if [ $? -ne 0 ]; then
        echo "✗ 安装失败，请手动运行：pip install streamlit"
        exit 1
    fi
    echo "✓ Streamlit 安装完成"
else
    echo "✓ Streamlit 已安装：v$streamlit_version"
fi

# 启动 Streamlit
echo "[3/3] 启动可视化仪表板..."
echo ""
echo "========================================"
echo "  ✅ 仪表板启动成功！"
echo "  🌐 访问地址：http://localhost:8501"
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 运行 Streamlit
streamlit run src/visualization/dashboard.py --server.port 8501 --server.address localhost

# 如果运行失败
if [ $? -ne 0 ]; then
    echo ""
    echo "✗ 仪表板运行失败，请检查错误信息"
    exit 1
fi