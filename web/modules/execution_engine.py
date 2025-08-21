import re
import json
import datetime
from typing import List, Dict, Any, Optional
import streamlit as st

# 引入必要的库和模块
from volcenginesdkarkruntime import Ark
import os
from web.utils.api_checker import check_api_keys
from web.utils.analysis_runner import run_stock_analysis

# 多模态模型配置
MULTIMODAL_MODEL = "doubao-seed-1-6-flash-250715"


class Tool:
    """工具基类，所有工具都应继承此类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具，返回结果"""
        raise NotImplementedError("子类必须实现run方法")


class StockAnalysisTool(Tool):
    """个股股票分析工具"""

    def __init__(self):
        super().__init__(
            name="个股股票分析工具",
            description="用于对特定A股股票代码进行基本面分析，提供财务指标、估值分析和投资建议。"
        )

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行股票分析

        参数:
            parameters: 包含股票代码等参数的字典，至少需要 'stock_code' 键

        返回:
            分析报告的字符串
        """
        # 提取股票代码
        stock_code = parameters.get('stock_code')
        if not stock_code:
            return "错误：缺少股票代码参数"

        # 验证股票代码格式（6位数字）
        if not re.match(r'^\d{6}$', str(stock_code)):
            return f"错误：无效的A股股票代码格式 '{stock_code}'，必须是6位数字"

        # 获取LLM配置
        llm_provider = st.session_state.llm_config.get('llm_provider', 'dashscope')
        llm_model = st.session_state.llm_config.get('llm_model', 'qwen-turbo-2025-04-28')

        try:
            # 执行股票分析
            analysis_result = run_stock_analysis(
                stock_symbol=str(stock_code),
                analysis_date=str(datetime.date.today()),
                analysts=['fundamentals'],
                research_depth=1,
                llm_provider=llm_provider,
                llm_model=llm_model,
                market_type='A股'
            )

            # 构建分析报告
            raw_reports = []
            if 'state' in analysis_result:
                state = analysis_result['state']
                report_types = [
                    'market_report', 'fundamentals_report',
                    'sentiment_report', 'news_report',
                    'risk_assessment', 'investment_plan'
                ]
                for report_type in report_types:
                    if report_type in state:
                        raw_reports.append(
                            f"#### {report_type.replace('_', ' ').title()}\n{state[report_type]}"
                        )

            decision_reasoning = ""
            if 'decision' in analysis_result and 'reasoning' in analysis_result['decision']:
                decision_reasoning = f"#### 核心决策结论\n{analysis_result['decision']['reasoning']}"

            full_raw_report = "\n\n".join(raw_reports + [decision_reasoning])
            return full_raw_report if full_raw_report else "无分析结果"

        except Exception as e:
            return f"股票分析失败: {str(e)}"


class ToolManager:
    """工具管理器，负责注册和调用工具"""

    def __init__(self):
        self.tools = {}
        # 确保logger已初始化
        self._ensure_logger_initialized()
        # 注册默认工具
        self.register_tool(StockAnalysisTool())

    def _ensure_logger_initialized(self):
        """确保日志记录器已初始化"""
        if 'logger' not in st.session_state:
            from tradingagents.utils.logging_manager import get_logger
            st.session_state.logger = get_logger('web')

    def register_tool(self, tool: Tool) -> None:
        """注册工具"""
        # 确保logger已初始化
        self._ensure_logger_initialized()
        self.tools[tool.name] = tool
        st.session_state.logger.info(f"已注册工具: {tool.name}")

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """获取工具实例"""
        return self.tools.get(tool_name)

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有可用工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools.values()
        ]

    def get_available_tools_text(self) -> str:
        """获取可用工具的文本描述"""
        tools_text = "目前可用的分析工具：\n"
        for i, tool in enumerate(self.tools.values(), 1):
            tools_text += f"{i}. {tool.name}：{tool.description}\n"
        return tools_text


def analyze_step_with_model(step: Dict[str, Any]) -> str:
    """使用模型分析单个步骤"""
    # 检查是否安装了必要的SDK
    try:
        from volcenginesdkarkruntime import Ark
    except ImportError:
        return "volcenginesdkarkruntime not installed. Cannot analyze step."

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return "API key not configured. Cannot analyze step."

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return f"Failed to initialize SDK client: {str(e)}"

    # 获取文档初步分析信息
    document_report = st.session_state.get('image_analysis_report', '')

    prompt = f"""
    请根据以下分析步骤要求，进行详细分析并生成报告：

    分析步骤:
    模块: {step.get('module', '未命名模块')}
    名称: {step.get('name', '未命名步骤')}
    内容: {step.get('content', '无内容')}
    预期输出: {step.get('expected_output', '无预期输出')}

    文档初步分析信息:
    {document_report[:500]}...  # 限制长度，避免提示词过长

    请提供详细的分析报告，内容应全面、深入，并符合预期输出要求。
    """

    try:
        resp = client.chat.completions.create(
            model=MULTIMODAL_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        )

        if resp.choices and len(resp.choices) > 0:
            return resp.choices[0].message.content
        else:
            return "模型未返回有效响应，无法完成此步骤分析"

    except Exception as e:
        return f"分析步骤失败: {str(e)}"


def extract_steps_from_plan(plan_text: str) -> List[Dict[str, Any]]:
    """从执行计划文本中提取多层级步骤结构，返回结构化数据"""
    # 检查是否安装了必要的SDK
    try:
        from volcenginesdkarkruntime import Ark
    except ImportError:
        st.error("volcenginesdkarkruntime 未安装，无法提取步骤结构")
        return []

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        st.error("API key 未配置，无法提取步骤结构")
        return []

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        st.error(f"初始化 SDK 客户端失败: {str(e)}，无法提取步骤结构")
        return []

    # 定义期望的JSON结构
    expected_format = {
        "overall_goal": "总体分析目标的简要描述",
        "modules": [
            {
                "module_id": "模块编号，如1",
                "module_name": "模块名称",
                "steps": [
                    {
                        "step_id": "步骤编号，如a",
                        "step_name": "步骤名称",
                        "content": "分析内容的详细描述",
                        "uses_tool": "布尔值，true或false",
                        "tool": "工具名称，如果uses_tool为true",
                        "parameters": {
                            "参数名称1": "参数值1",
                            "参数名称2": "参数值2"
                        },
                        "expected_output": "该步骤的预期结果"
                    }
                ]
            }
        ],
        "execution_order": ["1.a", "1.b", "2.a", "..."]  # 执行顺序列表
    }

    prompt = f"""
    请分析以下执行计划文本，并将其转换为结构化的JSON数据。
    你的任务是识别出所有模块、每个模块下的步骤，以及每个步骤的详细信息。

    执行计划文本:
    {plan_text}

    请严格按照以下JSON格式返回结果，不要添加任何额外解释：
    {json.dumps(expected_format, ensure_ascii=False, indent=2)}

    注意事项:
    1. 确保JSON格式正确，可被标准JSON解析器解析
    2. "uses_tool"字段应为布尔值(true/false)
    3. 如果步骤不使用工具，"tool"字段应为空字符串
    4. 如果没有参数，"parameters"应为空对象
    5. "execution_order"应包含所有步骤的完整标识符，如"1.a"、"1.b"等
    6. 保留所有原始信息，不要遗漏任何模块或步骤
    """

    try:
        with st.spinner(f"使用 {MULTIMODAL_MODEL} 解析执行计划步骤中..."):
            resp = client.chat.completions.create(
                model=MULTIMODAL_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ]
            )

            if resp.choices and len(resp.choices) > 0:
                json_str = resp.choices[0].message.content

                # 清理可能的格式问题
                json_str = json_str.strip()
                # 移除可能的代码块标记
                if json_str.startswith('```json'):
                    json_str = json_str[7:-3].strip()
                elif json_str.startswith('```'):
                    json_str = json_str[3:-3].strip()

                # 解析JSON
                plan_data = json.loads(json_str)

                # 转换为我们需要的步骤格式
                steps = []
                for module in plan_data.get('modules', []):
                    module_id = module.get('module_id', '')
                    module_name = module.get('module_name', f"模块 {module_id}")

                    for step in module.get('steps', []):
                        step_id = step.get('step_id', '')
                        full_step_id = f"{module_id}.{step_id}"

                        steps.append({
                            'module': module_name,
                            'module_id': module_id,
                            'step_id': step_id,
                            'full_step_id': full_step_id,
                            'name': step.get('step_name', f"步骤 {full_step_id}"),
                            'content': step.get('content', ''),
                            'uses_tool': step.get('uses_tool', False),
                            'tool': step.get('tool', ''),
                            'parameters': step.get('parameters', {}),
                            'expected_output': step.get('expected_output', '')
                        })

                # 根据执行顺序排序步骤
                execution_order = plan_data.get('execution_order', [])
                if execution_order and steps:
                    # 创建步骤ID到步骤的映射
                    step_map = {step['full_step_id']: step for step in steps}
                    # 按执行顺序重新排列步骤
                    ordered_steps = []
                    for step_id in execution_order:
                        if step_id in step_map:
                            ordered_steps.append(step_map[step_id])
                            del step_map[step_id]
                    # 添加剩余未在执行顺序中出现的步骤
                    ordered_steps.extend(step_map.values())
                    return ordered_steps

                return steps
            else:
                st.error("模型未返回有效响应，无法提取步骤")
                return []

    except json.JSONDecodeError as e:
        st.error(f"解析步骤JSON失败: {str(e)}")
        return []
    except Exception as e:
        st.error(f"提取步骤失败: {str(e)}")
        return []


def execute_step(step: Dict[str, Any], tool_manager: ToolManager) -> str:
    """执行单个步骤并返回结果"""
    step_name = step.get('name', "未命名步骤")
    module_name = step.get('module', "未分类模块")

    try:
        if step.get('uses_tool', False):
            tool_name = step.get('tool', '')
            parameters = step.get('parameters', {})

            # 获取工具实例
            tool = tool_manager.get_tool(tool_name)
            if not tool:
                return f"错误：未找到工具 '{tool_name}'，无法执行此步骤"

            # 执行工具
            return tool.run(parameters)
        else:
            # 不需要使用工具，直接调用模型进行分析
            return analyze_step_with_model(step)

    except Exception as e:
        return f"步骤执行失败: {str(e)}"


def execute_next_step(tool_manager: ToolManager, progress_callback=None) -> None:
    """执行计划中的下一步并更新进度状态"""
    # 获取当前任务进度
    task_progress = st.session_state.task_progress

    # 提取计划中的步骤
    steps = task_progress.get('steps', [])
    if not steps:
        st.error("没有可执行的步骤")
        return

    # 获取当前状态
    current_step = task_progress['current_step']
    total_steps = task_progress['total_steps']

    # 如果所有步骤都已完成，返回
    if current_step >= total_steps:
        # 标记当前阶段为已完成
        if 'plan_execution' not in task_progress['completed_stages']:
            task_progress['completed_stages'].append('plan_execution')
        return

    # 执行当前步骤
    execution_reports = task_progress.get('execution_reports', [])
    step = steps[current_step]
    step_name = step.get('name', f"步骤 {current_step + 1}")
    module_name = step.get('module', "未分类模块")

    if progress_callback:
        progress_callback(f"正在执行 {module_name} - {step_name}", current_step, total_steps)

    # 执行步骤
    report_text = execute_step(step, tool_manager)

    # 更新执行报告
    if current_step < len(execution_reports):
        execution_reports[current_step] = {
            'step': current_step + 1,
            'module': module_name,
            'name': step_name,
            'report': report_text,
            'status': 'completed' if "错误：" not in report_text else 'failed'
        }
    else:
        execution_reports.append({
            'step': current_step + 1,
            'module': module_name,
            'name': step_name,
            'report': report_text,
            'status': 'completed' if "错误：" not in report_text else 'failed'
        })

    # 更新会话状态
    task_progress['completed_steps'] = current_step + 1
    task_progress['current_step'] = current_step + 1
    task_progress['execution_reports'] = execution_reports
    st.session_state.task_progress = task_progress
