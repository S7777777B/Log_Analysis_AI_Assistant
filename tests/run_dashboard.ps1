# 可视化仪表板启动脚本
# 使用方法：.\tests\run_dashboard.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  日志分析 AI 助手 - 可视化仪表板" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境是否存在
if (-not (Test-Path ".\venv")) {
    Write-Host "❌ 虚拟环境未找到，请先创建虚拟环境..." -ForegroundColor Red
    Write-Host ""
    Write-Host "执行以下命令创建虚拟环境：" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "  pip install streamlit" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# 激活虚拟环境
Write-Host "[1/3] 激活虚拟环境..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# 检查 Streamlit 是否安装
Write-Host "[2/3] 检查 Streamlit 依赖..." -ForegroundColor Yellow
try {
    $streamlitVersion = python -c "import streamlit; print(streamlit.__version__)" 2>&1
    Write-Host "✓ Streamlit 已安装：v$streamlitVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Streamlit 未安装，正在安装..." -ForegroundColor Yellow
    pip install streamlit
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 安装失败，请手动运行：pip install streamlit" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Streamlit 安装完成" -ForegroundColor Green
}

# 启动 Streamlit
Write-Host "[3/3] 启动可视化仪表板..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ 仪表板启动成功！" -ForegroundColor Green
Write-Host "  🌐 访问地址：http://localhost:8501" -ForegroundColor Cyan
Write-Host "  按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 运行 Streamlit
streamlit run src\visualization\dashboard.py --server.port 8501 --server.address localhost

# 如果运行失败
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ 仪表板运行失败，请检查错误信息" -ForegroundColor Red
    exit 1
}
