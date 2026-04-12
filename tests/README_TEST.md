# 可视化模块测试说明

## 📋 测试环境准备

### 1. 创建虚拟环境
```powershell
# 在项目根目录下执行
python -m venv venv
```

### 2. 激活虚拟环境
```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# 如果 PowerShell 执行策略限制，使用以下命令：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. 安装依赖
```powershell
pip install streamlit
```

### 4. 验证安装
```powershell
python -c "import streamlit; print('Streamlit version:', streamlit.__version__)"
```

---

## 🧪 测试方法

### 方法 1: 使用启动脚本（推荐）
```powershell
.\tests\run_dashboard.ps1
```

这个脚本会自动：
- 检查虚拟环境
- 激活虚拟环境
- 检查 Streamlit 是否安装
- 启动可视化仪表板

### 方法 2: 直接运行
```powershell
streamlit run src\visualization\dashboard.py
```

### 方法 3: 指定端口运行
```powershell
streamlit run src\visualization\dashboard.py --server.port 8501
```

---

## ✅ 测试内容

### 1. 功能测试

#### 实时日志流页面
- [ ] 页面加载正常
- [ ] 实时刷新开关工作正常
- [ ] 日志类型筛选功能正常
- [ ] 刷新频率选择功能正常
- [ ] 日志列表展示正常
- [ ] 实时统计信息显示正常

#### UEBA 异常用户排行页面
- [ ] 页面加载正常
- [ ] 时间范围选择器工作正常
- [ ] TOP10 排行榜展示正常
- [ ] 异常评分进度条显示正常
- [ ] 用户详情查看功能正常
- [ ] 处置操作按钮响应正常

#### 安全评分看板页面
- [ ] 页面加载正常
- [ ] 4 个关键指标显示正常
- [ ] 安全评分趋势图显示正常
- [ ] 风险等级分布表格正常
- [ ] 威胁类型统计表格正常

#### AI 处置建议页面
- [ ] 页面加载正常
- [ ] 筛选条件工作正常
- [ ] 处置建议卡片展示正常
- [ ] AI 分析结果显示正常
- [ ] 处置操作按钮响应正常

#### 历史查询页面
- [ ] 页面加载正常
- [ ] 查询条件输入正常
- [ ] 高级搜索功能正常
- [ ] 查询结果展示正常
- [ ] 导出按钮响应正常

### 2. 交互测试
- [ ] 侧边栏导航切换正常
- [ ] 所有按钮点击响应正常
- [ ] 下拉选择框工作正常
- [ ] 可折叠区域展开/收起正常
- [ ] 数据刷新正常

---

## 🐛 已知问题

### 环境问题
1. **PowerShell 执行策略限制**
   - 错误信息：`cannot be loaded because running scripts is disabled on this system`
   - 解决方法：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

2. **Streamlit 模块未找到**
   - 错误信息：`No module named 'streamlit'`
   - 解决方法：确保虚拟环境已激活，然后运行 `pip install streamlit`

### 功能待完善
1. **实时刷新机制** - 需要使用 JavaScript 或定时任务实现
2. **数据源对接** - 目前使用模拟数据，需要对接 Kafka 和 ClickHouse
3. **导出功能** - CSV/Excel 导出功能待实现
4. **用户认证** - 登录和权限控制待实现

---

## 📊 测试结果记录

### 测试日期：___________
### 测试人员：___________

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 实时日志流 | ⬜ 待测试 | |
| UEBA 异常排行 | ⬜ 待测试 | |
| 安全评分看板 | ⬜ 待测试 | |
| AI 处置建议 | ⬜ 待测试 | |
| 历史查询 | ⬜ 待测试 | |
| 导航切换 | ⬜ 待测试 | |
| 交互功能 | ⬜ 待测试 | |

### 总体评价
- [ ] 通过
- [ ] 部分通过
- [ ] 未通过

### 问题记录
```
在此记录测试中发现的问题...
```

---

## 📚 相关文档

- [可视化模块文档](../src/visualization/README.md)
- [开发报告](./.trae/visualization-report.md)
- [任务清单](./.trae/task-checklist.md)
- [AI 开发记录](./.trae/AI_development.md)

---

**更新时间**: 2026-03-21  
**版本**: v1.0.0
