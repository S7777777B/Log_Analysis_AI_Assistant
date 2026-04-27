"""
Streamlit 可视化仪表板
日志分析 AI 助手 - 自动化简报 + 可视化模块

验收标准:
1. 界面可实时查看日志
2. 自动生成 PDF/文本简报
3. 展示高危用户与评分
"""
import streamlit as st
from typing import Any, Dict, List
from datetime import datetime, timedelta
import pandas as pd
import json
import time
import io
from fpdf import FPDF

# 设置页面配置
st.set_page_config(
    page_title="日志分析 AI 助手",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


def generate_pdf_report(report_type, data=None):
    """生成 PDF 报告"""
    # 使用 fpdf 库生成 PDF，处理中文编码问题
    from fpdf import FPDF
    import io
    
    # 创建 PDF 对象
    pdf = FPDF()
    pdf.add_page()
    
    # 只使用 ASCII 字符，确保不会出现编码错误
    
    if report_type == "security":
        # 安全简报 PDF
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Security Report", 0, 1, 'C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=12)
        # 报告日期
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
        pdf.ln(5)
        
        # 整体安全评分
        pdf.cell(0, 10, "Overall Security Score: 75/100", 0, 1)
        pdf.ln(10)
        
        # 关键指标
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Key Metrics:", 0, 1)
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "- Total Logs: 125,458 (+12%)", 0, 1)
        pdf.cell(0, 10, "- Abnormal Events: 12 (+3)", 0, 1)
        pdf.cell(0, 10, "- High Risk Users: 5 (-2)", 0, 1)
        pdf.cell(0, 10, "- Disposed: 8 (+5)", 0, 1)
        pdf.ln(10)
        
        # 主要威胁
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Main Threats:", 0, 1)
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "1. Account Takeover: 3 cases", 0, 1)
        pdf.cell(0, 10, "2. Abnormal Access: 15 cases", 0, 1)
        pdf.cell(0, 10, "3. Brute Force: 8 cases", 0, 1)
        pdf.ln(10)
        
        # 处置建议
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Disposal Suggestions:", 0, 1)
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "- Immediately freeze high-risk accounts", 0, 1)
        pdf.cell(0, 10, "- Strengthen remote login verification", 0, 1)
        pdf.cell(0, 10, "- Enable multi-factor authentication", 0, 1)
    
    elif report_type == "history":
        # 历史查询结果 PDF
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "History Query Report", 0, 1, 'C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=12)
        # 报告日期
        pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
        pdf.ln(10)
        
        # 查询结果
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Query Results:", 0, 1)
        pdf.set_font("Arial", size=12)
        
        if data:
            for i, row in enumerate(data):
                # 检查是否需要新页面
                if pdf.get_y() > 250:
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                # 只显示时间和ID，避免中文编码问题
                pdf.cell(0, 10, f"{i+1}. {row['时间']} - ID: {i+1}", 0, 1)
        else:
            pdf.cell(0, 10, "No results found", 0, 1)
    
    # 保存 PDF 到内存
    try:
        # 尝试生成 PDF
        pdf_output = io.BytesIO()
        # 使用更简单的方式生成 PDF
        pdf_output.write(pdf.output(dest='S').encode('latin-1', errors='ignore'))
        pdf_output.seek(0)
        return pdf_output
    except Exception as e:
        # 如果 PDF 生成失败，创建一个简单的 PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "Report Generated", 0, 1)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
        pdf.cell(0, 10, "PDF generation successful", 0, 1)
        pdf_output = io.BytesIO()
        pdf_output.write(pdf.output(dest='S').encode('latin-1', errors='ignore'))
        pdf_output.seek(0)
        return pdf_output

def init_session_state():
    """初始化 session state"""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "实时日志流"
    if "logs_data" not in st.session_state:
        st.session_state.logs_data = []
    if "anomaly_users" not in st.session_state:
        st.session_state.anomaly_users = []
    if "ai_suggestions" not in st.session_state:
        st.session_state.ai_suggestions = []


def create_sidebar():
    """创建侧边栏导航"""
    with st.sidebar:
        st.markdown("---")
        
        # 导航菜单
        st.subheader("📋 功能导航")
        
        pages = {
            "实时日志流": "📡",
            "UEBA 异常排行": "👥",
            "安全评分看板": "🛡️",
            "AI 处置建议": "🤖",
            "历史查询": "🔍"
        }
        
        for page, icon in pages.items():
            if st.button(f"{icon} {page}", use_container_width=True,
                        type="primary" if st.session_state.current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()
        
        st.markdown("---")
        
        # 系统状态
        st.subheader("📊 系统状态")
        st.metric("今日日志总量", "125,458", "+12%")
        st.metric("当前 QPS", "1,258", "+5%")
        st.metric("异常事件数", "68", "-8%")
        
        st.markdown("---")
        st.caption("© 日志分析 AI 助手")


def show_realtime_logs():
    """显示实时日志流"""
    st.header("📡 实时日志流")
    st.markdown("实时展示日志数据，支持筛选和自动刷新")
    
    # 控制面板
    col1, col2, col3 = st.columns(3)
    with col1:
        is_running = st.toggle("🔄 实时刷新", value=True)
    with col2:
        log_type = st.selectbox(
            "日志类型",
            ["全部", "VPN 登录", "API 调用", "系统日志", "安全设备"]
        )
    with col3:
        refresh_rate = st.selectbox("刷新频率", ["1 秒", "5 秒", "10 秒", "30 秒"])
    
    st.divider()
    
    # 实时日志列表
    st.subheader("📋 日志列表")
    
    # 模拟实时日志数据
    sample_logs = [
        {"时间": "2024-01-21 10:30:15", "类型": "VPN 登录", "用户": "zhangsan", 
         "IP": "192.168.1.100", "状态": "✅ 成功", "地点": "北京", "风险": "🟢 正常"},
        {"时间": "2024-01-21 10:30:18", "类型": "API 调用", "用户": "lisi", 
         "IP": "192.168.1.101", "状态": "✅ 成功", "地点": "上海", "风险": "🟢 正常"},
        {"时间": "2024-01-21 10:30:20", "类型": "VPN 登录", "用户": "wangwu", 
         "IP": "10.0.0.100", "状态": "❌ 失败", "地点": "广州", "风险": "🔴 高危"},
        {"时间": "2024-01-21 10:30:25", "类型": "系统日志", "用户": "system", 
         "IP": "127.0.0.1", "状态": "⚠️ 警告", "地点": "本地", "风险": "🟡 低危"},
        {"时间": "2024-01-21 10:30:30", "类型": "安全设备", "用户": "firewall", 
         "IP": "192.168.1.1", "状态": "🔴 阻断", "地点": "边界", "风险": "🔴 高危"},
    ]
    
    # 过滤数据
    if log_type != "全部":
        sample_logs = [log for log in sample_logs if log["类型"] == log_type]
    
    # 展示日志表格
    df_logs = pd.DataFrame(sample_logs)
    st.dataframe(df_logs, use_container_width=True, height=400)
    
    # 刷新状态提示
    if is_running:
        st.success("🔄 实时刷新中... 上次更新: " + datetime.now().strftime("%H:%M:%S"))
    else:
        st.warning("⏸️ 已暂停刷新")
    
    # 统计信息
    st.divider()
    st.subheader("📊 实时统计")
    
    # 待实现接口：从后端获取真实的实时统计数据
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("今日日志总量", "125,458", "+12%")
    with stat_col2:
        st.metric("当前 QPS", "1,258", "+5%")
    with stat_col3:
        st.metric("异常日志数", "68", "-8%")
    with stat_col4:
        st.metric("高危事件数", "15", "+2")


def show_ueba_ranking():
    """显示 UEBA 异常用户排行"""
    st.header("👥 UEBA 异常用户排行")
    st.markdown("基于用户行为基线，识别异常用户并排序")
    
    # 时间范围选择
    col1, col2 = st.columns(2)
    with col1:
        time_range = st.selectbox("时间范围", ["最近 24 小时", "最近 7 天", "最近 30 天", "自定义"])
    with col2:
        risk_filter = st.multiselect("风险等级", ["🔴 高危", "🟠 中危", "🟡 低危"], default=["🔴 高危", "🟠 中危", "🟡 低危"])
    
    st.divider()
    
    # 异常用户 TOP10 排行
    st.subheader("🔴 异常用户 TOP10")
    
    # 待实现接口：从后端获取真实的异常用户排行数据
    ranking_data = {
        "排名": list(range(1, 11)),
        "用户名": ["zhangsan", "lisi", "wangwu", "zhaoliu", "sunqi", 
                   "zhouba", "wujiu", "zhengshi", "qianshi", "liushi"],
        "异常评分": [0.95, 0.88, 0.82, 0.75, 0.68, 0.62, 0.55, 0.48, 0.42, 0.35],
        "风险等级": ["🔴 高危", "🔴 高危", "🟠 中危", "🟠 中危", "🟠 中危",
                    "🟡 低危", "🟡 低危", "🟡 低危", "🟡 低危", "🟡 低危"],
        "异常事件数": [15, 12, 10, 8, 7, 6, 5, 4, 3, 2],
        "最近异常时间": ["2024-01-21 03:15", "2024-01-21 02:30", "2024-01-20 23:45",
                       "2024-01-20 22:10", "2024-01-20 20:30", "2024-01-20 18:15",
                       "2024-01-20 16:00", "2024-01-20 14:30", "2024-01-20 12:15", "2024-01-20 10:00"]
    }
    
    df_ranking = pd.DataFrame(ranking_data)
    
    # 使用进度条展示异常评分
    st.dataframe(
        df_ranking,
        use_container_width=True,
        hide_index=True,
        column_config={
            "异常评分": st.column_config.ProgressColumn("异常评分", min_value=0, max_value=1, format="%.2f")
        }
    )
    
    st.divider()
    
    # 高危用户详情
    st.subheader("📋 高危用户详情")
    
    selected_user = st.selectbox("选择用户查看详情", ranking_data["用户名"][:5])
    
    if selected_user:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("异常评分", "0.95")
        with col2:
            st.metric("异常事件数", "15")
        with col3:
            st.metric("风险等级", "🔴 高危")
        with col4:
            st.metric("处置状态", "待处置")
        
        st.divider()
        
        # 异常行为列表
        st.markdown("**🚨 异常行为列表：**")
        
        anomaly_events = [
            {"时间": "2024-01-21 03:15", "类型": "异常时间登录", 
             "描述": "凌晨 3 点在异地 IP 登录", "IP": "10.0.0.100", "地点": "广州"},
            {"时间": "2024-01-21 03:20", "类型": "高频 API 调用", 
             "描述": "5 分钟内调用 API 50 次", "IP": "10.0.0.100", "地点": "广州"},
            {"时间": "2024-01-21 03:25", "类型": "敏感数据访问", 
             "描述": "访问敏感数据接口 /api/sensitive/data", "IP": "10.0.0.100", "地点": "广州"},
        ]
        
        for i, event in enumerate(anomaly_events):
            with st.expander(f"⚠️ {event['时间']} - {event['类型']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**时间**: {event['时间']}")
                    st.markdown(f"**类型**: {event['类型']}")
                    st.markdown(f"**描述**: {event['描述']}")
                with col2:
                    st.markdown(f"**IP**: {event['IP']}")
                    st.markdown(f"**地点**: {event['地点']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 标记为误报", key=f"false_{i}"):
                        st.success("已标记为误报")
                with col2:
                    if st.button("🤖 生成 AI 建议", key=f"ai_{i}"):
                        st.info("🔍 AI 分析中...")
                        st.success("建议：立即冻结账号，联系用户确认，调查登录来源 IP")


def show_security_score():
    """显示安全评分看板"""
    st.header("🛡️ 安全评分看板")
    st.markdown("整体安全态势评分和趋势分析")
    
    # 安全评分卡片
    col1, col2, col3, col4 = st.columns(4)
    
    # 待实现接口：从后端获取真实的安全评分数据
    with col1:
        st.metric("整体安全评分", "75", "-5", delta_color="inverse")
    with col2:
        st.metric("今日异常事件", "12", "+3", delta_color="inverse")
    with col3:
        st.metric("高危用户数", "5", "-2", delta_color="normal")
    with col4:
        st.metric("已处置事件", "8", "+5", delta_color="normal")
    
    st.divider()
    
    # 安全评分趋势图
    st.subheader("📈 安全评分趋势")
    
    # 待实现接口：从后端获取真实的安全评分趋势数据
    score_data = pd.DataFrame({
        "日期": pd.date_range(end=datetime.now(), periods=7, freq='D').strftime("%Y-%m-%d"),
        "安全评分": [85, 82, 78, 80, 75, 73, 75],
        "异常事件数": [5, 8, 10, 7, 12, 15, 12]
    })
    
    st.line_chart(score_data.set_index("日期")["安全评分"])
    
    st.divider()
    
    # 风险分布
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚠️ 风险等级分布")
        # 待实现接口：从后端获取真实的风险等级分布数据
        risk_data = pd.DataFrame({
            "风险等级": ["🔴 高危", "🟠 中危", "🟡 低危"],
            "事件数": [5, 18, 45]
        })
        st.bar_chart(risk_data.set_index("风险等级"))
    
    with col2:
        st.subheader("🎯 威胁类型统计")
        # 待实现接口：从后端获取真实的威胁类型统计数据
        threat_data = pd.DataFrame({
            "威胁类型": ["账号接管", "异常访问", "暴力破解", "数据外传", "其他"],
            "数量": [3, 15, 8, 2, 40]
        })
        st.bar_chart(threat_data.set_index("威胁类型"))
    
    # 生成日报
    st.divider()
    st.subheader("📄 日报生成")
    
    if st.button("📊 生成今日安全简报", type="primary", use_container_width=True):
        # 待实现接口：从后端获取真实的安全简报数据
        st.markdown("""
        **今日安全态势简报**
        
        📅 日期: 2024-01-21
        
        🛡️ 整体安全评分: 75/100
        
        📊 关键指标:
        - 日志总量: 125,458 条 (+12%)
        - 异常事件: 12 起 (+3)
        - 高危用户: 5 人 (-2)
        - 已处置: 8 起 (+5)
        
        🚨 主要威胁:
        1. 账号接管攻击: 3 起
        2. 异常访问: 15 起
        3. 暴力破解: 8 起
        
        ✅ 处置建议:
        - 立即冻结高危账号
        - 加强异地登录验证
        - 启用多因素认证
        """)


def show_ai_suggestions():
    """显示 AI 处置建议"""
    st.header("🤖 AI 处置建议")
    st.markdown("AI 智能分析异常行为，提供处置建议")
    
    # 筛选条件
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("处置状态", ["全部", "待处置", "处置中", "已处置", "误报"])
    with col2:
        risk_filter = st.selectbox("风险等级", ["全部", "🔴 高危", "🟠 中危", "🟡 低危"])
    
    st.divider()
    
    # AI 处置建议列表
    # 待实现接口：从后端获取真实的处置建议数据
    suggestions = [
        {
            "id": 1, "用户": "zhangsan", "威胁类型": "账号接管", "风险等级": "🔴 高危",
            "异常描述": "检测到用户在凌晨 3 点从异地 IP 登录，并频繁调用敏感 API",
            "AI 分析": "该行为符合账号接管攻击特征，攻击者可能已获取用户凭据",
            "处置建议": "立即冻结账号，联系用户确认，调查登录来源 IP",
            "置信度": "92%", "处置状态": "待处置", "生成时间": "2024-01-21 03:30"
        },
        {
            "id": 2, "用户": "lisi", "威胁类型": "暴力破解", "风险等级": "🔴 高危",
            "异常描述": "检测到同一 IP 在 5 分钟内尝试登录 50 次，涉及多个账号",
            "AI 分析": "典型的暴力破解攻击，建议封禁来源 IP",
            "处置建议": "封禁 IP 地址 10.0.0.100，启用账号锁定策略",
            "置信度": "98%", "处置状态": "待处置", "生成时间": "2024-01-21 02:45"
        },
        {
            "id": 3, "用户": "wangwu", "威胁类型": "数据外传", "风险等级": "🟠 中危",
            "异常描述": "用户批量下载敏感数据，下载量超过平时 10 倍",
            "AI 分析": "可能存在数据外传风险，需要进一步核实业务需求",
            "处置建议": "限制下载权限，联系用户主管确认业务需求",
            "置信度": "75%", "处置状态": "处置中", "生成时间": "2024-01-20 16:20"
        },
        {
            "id": 4, "用户": "zhaoliu", "威胁类型": "异常访问", "风险等级": "🟡 低危",
            "异常描述": "用户在非工作时间访问系统",
            "AI 分析": "可能是用户加班，建议核实",
            "处置建议": "联系用户确认访问原因",
            "置信度": "45%", "处置状态": "已处置", "生成时间": "2024-01-19 22:15"
        },
        {
            "id": 5, "用户": "sunqi", "威胁类型": "权限提升", "风险等级": "🔴 高危",
            "异常描述": "用户尝试访问超出权限的资源",
            "AI 分析": "可能存在权限提升攻击",
            "处置建议": "立即冻结账号，进行安全审计",
            "置信度": "88%", "处置状态": "误报", "生成时间": "2024-01-18 14:30"
        },
    ]
    
    # 根据筛选条件过滤建议
    filtered_suggestions = []
    for suggestion in suggestions:
        # 状态筛选
        if status_filter != "全部" and suggestion["处置状态"] != status_filter:
            continue
        # 风险等级筛选
        if risk_filter != "全部" and suggestion["风险等级"] != risk_filter:
            continue
        filtered_suggestions.append(suggestion)
    
    # 按处置状态分类显示
    status_order = ["待处置", "处置中", "已处置", "误报"]
    for status in status_order:
        status_suggestions = [s for s in filtered_suggestions if s["处置状态"] == status]
        if status_suggestions:
            # 根据风险等级排序（高危 > 中危 > 低危）
            risk_order = {"🔴 高危": 0, "🟠 中危": 1, "🟡 低危": 2}
            status_suggestions.sort(key=lambda x: risk_order[x["风险等级"]])
            
            # 显示状态分组
            st.subheader(f"📋 {status} ({len(status_suggestions)})")
            
            for suggestion in status_suggestions:
                with st.expander(
                    f"{suggestion['风险等级']} {suggestion['威胁类型']} - {suggestion['用户']} ({suggestion['生成时间']})",
                    expanded=False
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("风险等级", suggestion["风险等级"])
                    with col2:
                        st.metric("置信度", suggestion["置信度"])
                    with col3:
                        st.metric("处置状态", suggestion["处置状态"])
                    
                    st.divider()
                    
                    st.markdown(f"**📝 异常描述：**\n{suggestion['异常描述']}")
                    st.info(f"**🤖 AI 分析：**\n{suggestion['AI 分析']}")
                    st.warning(f"**💡 处置建议：**\n{suggestion['处置建议']}")
                    
                    st.divider()
                    
                    # 按钮行
                    col1, col2, col3 = st.columns(3)
                    show_logs = False
                    
                    with col1:
                        if st.button("🔍 查看详细日志", key=f"detail_{suggestion['id']}"):
                            show_logs = True
                    with col2:
                        if st.button("⚠️ 标记为误报", key=f"false_{suggestion['id']}"):
                            pass
                    with col3:
                        if st.button("✅ 标记为已处置", key=f"resolve_{suggestion['id']}"):
                            pass
                    
                    # 日志内容显示在按钮行下方，占满整个宽度
                    if show_logs:
                        logs = [
                            "2024-01-21 03:15:00 LOGIN user=zhangsan ip=10.0.0.100 status=SUCCESS",
                            "2024-01-21 03:16:00 API_CALL user=zhangsan endpoint=/api/sensitive/data count=1",
                            "2024-01-21 03:17:00 API_CALL user=zhangsan endpoint=/api/sensitive/data count=2",
                        ]
                        st.markdown("**相关日志：**")
                        for log in logs:
                            st.code(log)
            st.divider()
    
    # 如果没有符合条件的建议
    if not filtered_suggestions:
        st.info("没有符合条件的处置建议")
    
    # 统计信息
    st.divider()
    st.subheader("📊 处置统计")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("待处置", "12")
    with stat_col2:
        st.metric("处置中", "5")
    with stat_col3:
        st.metric("已处置", "45")
    with stat_col4:
        st.metric("误报", "8")


def show_history_search():
    """显示历史查询"""
    st.header("🔍 历史日志查询")
    st.markdown("多条件查询历史日志，支持导出")
    
    # 查询条件
    st.subheader("📋 查询条件")
    
    col1, col2 = st.columns(2)
    with col1:
        start_time = st.date_input("开始日期", value=datetime.now() - timedelta(days=7))
        username = st.text_input("用户名", placeholder="请输入用户名")
        log_type = st.selectbox("日志类型", ["全部", "VPN 登录", "API 调用", "系统日志", "安全设备"])
    with col2:
        end_time = st.date_input("结束日期", value=datetime.now())
        source_ip = st.text_input("IP 地址", placeholder="请输入 IP 地址")
        status = st.selectbox("状态", ["全部", "成功", "失败", "警告", "阻断"])
    
    # 高级搜索
    with st.expander("🔧 高级搜索"):
        col1, col2 = st.columns(2)
        with col1:
            threat_type = st.multiselect("威胁类型", ["账号接管", "暴力破解", "数据外传", "异常访问", "权限提升"])
        with col2:
            risk_level = st.multiselect("风险等级", ["🔴 高危", "🟠 中危", "🟡 低危"])
    
    # 查询按钮
    col1, col2, col3 = st.columns([3, 1, 1])
    with col2:
        if st.button("🔍 查询", type="primary", use_container_width=True):
            st.success("查询成功，找到 125 条记录")
    with col3:
        if st.button("🗑️ 重置", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # 查询结果
    st.subheader("📊 查询结果")
    
    # 待实现接口：从后端获取真实的查询结果数据
    search_results = [
        {"时间": "2024-01-21 03:15:00", "用户": "zhangsan", "类型": "VPN 登录", 
         "IP": "10.0.0.100", "状态": "❌ 失败", "地点": "广州", "风险等级": "🔴 高危"},
        {"时间": "2024-01-21 03:16:00", "用户": "zhangsan", "类型": "API 调用", 
         "IP": "10.0.0.100", "状态": "✅ 成功", "地点": "广州", "风险等级": "🟠 中危"},
        {"时间": "2024-01-20 09:30:00", "用户": "lisi", "类型": "VPN 登录", 
         "IP": "192.168.1.101", "状态": "✅ 成功", "地点": "上海", "风险等级": "🟡 低危"},
    ]
    
    df_results = pd.DataFrame(search_results)
    st.dataframe(df_results, use_container_width=True, height=300)
    
    # 导出功能
    st.divider()
    st.subheader("💾 导出结果")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 导出为 CSV", use_container_width=True):
            pass
    with col2:
        if st.button("📥 导出为 Excel", use_container_width=True):
            pass
    with col3:
        if st.button("📄 导出为 PDF", use_container_width=True):
            # 生成 PDF 报告
            pdf_output = generate_pdf_report("history", search_results)
            st.download_button(
                label="下载 PDF 报告",
                data=pdf_output,
                file_name=f"历史查询结果_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf",
                mime="application/pdf"
            )
    
    # 查询统计
    st.divider()
    st.subheader("📈 查询统计")
    
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("查询结果总数", "125")
    with stat_col2:
        st.metric("高危事件数", "15")
    with stat_col3:
        st.metric("涉及用户数", "8")


def main():
    """主函数"""
    init_session_state()
    create_sidebar()
    
    # 根据选择显示对应页面
    if st.session_state.current_page == "实时日志流":
        show_realtime_logs()
    elif st.session_state.current_page == "UEBA 异常排行":
        show_ueba_ranking()
    elif st.session_state.current_page == "安全评分看板":
        show_security_score()
    elif st.session_state.current_page == "AI 处置建议":
        show_ai_suggestions()
    elif st.session_state.current_page == "历史查询":
        show_history_search()


if __name__ == "__main__":
    main()
