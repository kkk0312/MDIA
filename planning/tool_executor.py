import re
import datetime
import inspect
from docstring_parser import parse
from typing import List, Optional, Dict, Callable

from web.utils.analysis_runner import run_stock_analysis
import streamlit as st


class ToolExecutor:
    """工具执行器，用于管理和执行各种分析工具"""

    def __init__(self):
        """初始化工具执行器，注册所有可用工具"""
        # 工具注册表，键为工具名称，值为对应的执行方法
        self.tools = {
            '个股股票分析工具': self.execute_stock_analysis_tool
            # 在这里添加新工具，格式: '工具名称': 执行方法
        }

    def get_available_tools(self):
        """获取所有可用工具的列表"""
        return list(self.tools.keys())

    @staticmethod
    def get_tool_metadata(tool_func):
        """提取工具函数的元信息（名称、描述、参数列表）"""
        # 1. 基础信息：函数名和 docstring 摘要
        tool_name = tool_func.__name__
        docstring = inspect.getdoc(tool_func) or ""
        parsed_doc = parse(docstring)  # 解析docstring
        tool_description = parsed_doc.short_description or "无描述"

        # 2. 提取参数信息：结合函数签名和docstring参数描述
        sig = inspect.signature(tool_func)  # 获取函数签名
        parameters = []
        for param_name, param in sig.parameters.items():
            # 从签名中获取参数类型、默认值
            param_type = param.annotation.__name__ if param.annotation != inspect.Parameter.empty else "未指定"
            default_value = param.default if param.default != inspect.Parameter.empty else "必填"

            # 从docstring中获取参数描述（适配Google风格的Args）
            param_desc = ""
            for doc_param in parsed_doc.params:
                if doc_param.arg_name == param_name:
                    param_desc = doc_param.description or "无描述"
                    break

            parameters.append({
                "name": param_name,
                "type": param_type,
                "default": default_value,
                "description": param_desc
            })

        return {
            "name": tool_name,
            "description": tool_description,
            "parameters": parameters
        }

    def generate_available_tools(self):
        """生成包含参数信息的可用工具列表"""
        # 修复：获取工具函数而不是工具名称字符串
        tool_list = []

        # 枚举所有工具（名称和对应的函数）
        for idx, (tool_display_name, tool_func) in enumerate(self.tools.items(), 1):
            metadata = ToolExecutor.get_tool_metadata(tool_func)
            # 格式化工具基本信息
            tool_info = [
                f"{idx}. 工具名称：{tool_display_name}",  # 使用显示名称
                f"   工具描述：{metadata['description']}",
                "   参数列表："
            ]
            # 格式化参数信息
            for param in metadata["parameters"]:
                param_line = (
                    f"   - {param['name']}（类型：{param['type']}，"
                    f"默认值：{param['default']}）：{param['description']}"
                )
                tool_info.append(param_line)
            tool_list.append("\n".join(tool_info))

        return "# 可用工具列表（含参数说明）\n" + "\n\n".join(tool_list)

    def execute(self, tool_name, parameters, step_content, progress_callback=None):
        """
        执行指定的工具

        Args:
            tool_name: 工具名称
            parameters: 工具参数
            step_content: 步骤内容（作为参数提取的备选来源）
            progress_callback: 进度回调函数

        Returns:
            工具执行结果报告
        """
        if tool_name not in self.tools:
            return f"错误：未知工具 '{tool_name}'，无法执行。可用工具：{', '.join(self.get_available_tools())}"

        # 调用对应的工具执行方法
        try:
            return self.tools[tool_name](parameters, step_content, progress_callback)
        except Exception as e:
            return f"执行工具 '{tool_name}' 时发生错误: {str(e)}"

    def _extract_stock_symbols(self, parameters: Dict, step_content: str) -> List[str]:
        """从参数或步骤文本中提取6位数字的股票代码"""
        candidates = []
        # 1. 从parameters中提取（优先）
        if isinstance(parameters, dict) and "stock_symbols" in parameters:
            param_value = parameters["stock_symbols"]
            if isinstance(param_value, list):
                candidates.extend([str(code) for code in param_value])
            else:
                candidates.append(str(param_value))  # 支持单个代码的情况

        # 2. 从step_content中提取（补充）
        if not candidates and step_content:
            candidates.append(step_content)

        # 3. 过滤有效代码（6位数字）
        valid_codes = list(set(re.findall(r"\b\d{6}\b", ",".join(candidates))))  # 去重+匹配6位数字
        return sorted(valid_codes)  # 排序后返回

    def execute_stock_analysis_tool(
            self,
            parameters: Dict[str, List[str]],
            step_content: str,
            progress_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        个股股票分析工具，支持批量分析股票。

        Args:
            parameters: 工具参数字典，推荐包含键 "stock_symbols"，值为股票代码列表（如 ["600000", "600036"]）
            step_content: 步骤描述文本，若parameters中无股票代码，将从文本中提取6位数字代码
            progress_callback: 进度回调函数，接收两个参数：进度信息（str）和进度值（0-1的float）

        Returns:
            整合后的股票分析报告，包含每只股票的市场、基本面等分析内容
        """
        # 提取股票代码
        stock_symbols = self._extract_stock_symbols(parameters, step_content)
        if not stock_symbols:
            return "错误：未找到有效的A股股票代码（需为6位数字），无法执行分析。"

        # 获取LLM配置
        llm_provider = st.session_state.llm_config.get('llm_provider', 'dashscope')
        llm_model = st.session_state.llm_config.get('llm_model', 'qwen-plus')

        all_analysis = []
        total = len(stock_symbols)

        for i, code in enumerate(stock_symbols, 1):
            # 进度反馈
            if progress_callback:
                progress = i / total
                progress_callback(f"正在分析股票 {code}（{i}/{total}）", progress)

            try:
                # 执行股票分析
                analysis_result = run_stock_analysis(
                    stock_symbol=code,
                    analysis_date=str(datetime.date.today()),
                    analysts=['fundamentals'],
                    research_depth=1,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    market_type='A股',
                )
            except Exception as e:
                all_analysis.append(f"### 个股分析: {code}\n分析失败：{str(e)}")
                continue

            # 处理分析结果
            raw_reports = []
            if 'state' in analysis_result:
                state = analysis_result['state']
                report_types = [
                    'market_report', 'fundamentals_report',
                    'sentiment_report', 'news_report',
                ]
                for report_type in report_types:
                    if report_type in state:
                        raw_reports.append(
                            f"#### {report_type.replace('_', ' ').title()}\n{state[report_type]}")

            # 添加决策推理
            decision_reasoning = ""
            if 'decision' in analysis_result and 'reasoning' in analysis_result['decision']:
                decision_reasoning = f"#### 核心决策结论\n{analysis_result['decision']['reasoning']}"

            # 整合报告
            full_raw_report = "\n\n".join(raw_reports + [decision_reasoning])
            all_analysis.append(
                f"### 个股分析: {code}\n{full_raw_report if full_raw_report else '无分析结果'}")

        return "\n\n".join(all_analysis)

    # 示例：添加新工具的方法
    # def execute_industry_analysis_tool(self, parameters, step_content, progress_callback=None):
    #     """行业分析工具实现"""
    #     # 实现工具逻辑
    #     industry = parameters.get('行业名称', '未知行业')
    #     return f"### 行业分析: {industry}\n这里是行业分析的具体内容..."
