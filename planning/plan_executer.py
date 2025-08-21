import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage, HumanMessage

from tradingagents.llm_adapters import ChatDashScopeOpenAI
from planning.toolkit import stock_analysis, fund_analysis

# 工具名中-英映射
tool_name_dict = {
    "stock_analysis": "个股分析工具",
    "fund_analysis": "公募基金分析工具"
}


def analyze_step_with_model_and_tools(step, image_analysis_report):
    try:
        model = "qwen-flash-2025-07-28"
        tools = [stock_analysis, fund_analysis]

        llm = ChatDashScopeOpenAI(
            model=model,
            temperature=0.1,
            max_tokens=2000
        )

        escaped_report = image_analysis_report.replace("{", "{{").replace("}", "}}")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "user",
                    f"""
                        请根据以下当前分析步骤要求，判断是否要调用工具：

                        当前分析步骤:
                        当前分析步骤所属模块: {step.get('module', '未命名模块')}
                        当前分析步骤名称: {step.get('name', '未命名步骤')}
                        当前分析步骤内容: {step.get('content', '无内容')}
                        当前分析步骤预期输出: {step.get('expected_output', '无预期输出')}

                        可用的分析工具：
                        1. 个股股票分析工具：用于对特定股票代码进行基本面分析，提供财务指标、估值分析和投资建议。
                        2. 单个公募基金分析工具：用于对特定基金代码进行数据获取和分析。

                        请聚焦于当前分析步骤的内容，当且仅当当前分析步骤内容与提供的分析工具高度相关时，才选择调用工具。
                    """
                ),
                (
                    "user",
                    f"""
                        如果选择调用工具，则提供调用的工具名和调用参数，
                        如果不选择调用工具，则直接根据当前分析步骤所要执行的内容和文档初步分析信息生成详细的分析报告，内容应全面、深入。

                        以下文档初步分析信息作为调用参数或者分析报告的参考:
                        {escaped_report}
                    """
                ),
            ]
        )

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke({})

        if len(result.tool_calls) == 0:
            # 没有工具调用，直接使用LLM的回复
            st.write(f"**是否使用工具**: False")
            st.write(f"**状态**: 未使用工具，直接生成报告")
            report = result.content
        else:
            # 执行工具调用
            st.write(f"**是否使用工具**: True")
            st.write(
                f"**状态**: 调用工具：{', '.join([tool_name_dict.get(tc.get('name')) for tc in result.tool_calls])}")
            tool_messages = []
            for tool_call in result.tool_calls:
                tool_name = tool_call.get('name')
                tool_args = tool_call.get('args', {})
                tool_id = tool_call.get('id')

                # 找到对应的工具并执行
                tool_result = None
                for tool in tools:
                    # 安全地获取工具名称进行比较
                    current_tool_name = None
                    if hasattr(tool, 'name'):
                        current_tool_name = tool.name
                    elif hasattr(tool, '__name__'):
                        current_tool_name = tool.__name__

                    if current_tool_name == tool_name:
                        tool_result = tool.invoke(tool_args)
                        break

                if tool_result is None:
                    tool_result = f"未找到工具: {tool_name}"

                # 创建工具消息
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id
                )
                tool_messages.append(tool_message)

            # 基于工具结果生成完整分析报告
            analysis_prompt = f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。"""

            # 构建完整的消息序列
            messages = [result] + tool_messages + [HumanMessage(content=analysis_prompt)]

            # 生成最终分析报告
            final_result = llm.invoke(messages)
            report = final_result.content

        return report

    except Exception as e:
        error_msg = f"分析过程出错：{str(e)}"
        st.error(error_msg)
        return error_msg