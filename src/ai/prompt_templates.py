"""
Prompt 模板模块
TODO: 设计 AI 分析的 Prompt 模板

开发任务:
1. 设计异常分析 Prompt 模板
2. 设计威胁分类 Prompt 模板
3. 设计处置建议 Prompt 模板
4. 优化 Prompt 以提高准确性
"""

# 异常分析 Prompt 模板
ANOMALY_ANALYSIS_PROMPT = """
你是一位资深的安全分析师。请分析以下用户异常行为：

用户：{username}
异常行为描述：{anomaly_description}

请回答：
1. 这可能是什么类型的攻击？
2. 风险等级是什么？
3. 给出分析理由。
4. 提供处置建议。

请以 JSON 格式回答。
"""

# 威胁分类 Prompt 模板
THREAT_CLASSIFICATION_PROMPT = """
根据以下日志片段，判断可能的威胁类型：

日志内容：
{log_content}

请只返回威胁类型代码。
"""

# 处置建议 Prompt 模板
SUGGESTION_GENERATION_PROMPT = """
针对以下安全威胁，提供专业的处置建议：

威胁类型：{threat_type}
威胁描述：{description}

请提供立即处置措施、短期处置措施和长期改进建议。
"""
