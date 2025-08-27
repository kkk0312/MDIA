import streamlit as st
import os
import datetime

import json
import base64

import io

# 引入官方SDK
try:
    from volcenginesdkarkruntime import Ark

    has_ark_sdk = True
except ImportError:
    has_ark_sdk = False

# 导入工具执行器
from backend.tools.tool_executor import ToolExecutor

# 导入辅助函数
from backend.analysis.utils import extract_tickers_from_text, extract_companies_from_text, extract_modules_from_text, extract_steps_from_plan

# 导入指定模型
from backend.analysis.config import MULTIMODAL_MODEL


# 多模态文档解析函数 - 第一阶段：分析文档并划分为多个模块
def analyze_document_with_multimodal(document, doc_type="image"):
    """
    使用指定的多模态模型分析图片、PDF文档或网页截图
    提供完整文档分析报告，将内容分为多个模块，并提取个股股票代码
    """
    # 检查是否安装了必要的SDK
    if not has_ark_sdk:
        st.error("volcenginesdkarkruntime not installed. Please install it to use multimodal features.")
        return {"tickers": [], "companies": [], "report": "", "modules": []}

    # 获取API密钥
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        st.error("API key not configured. Please set ARK_API_KEY environment variable.")
        return {"tickers": [], "companies": [], "report": "", "modules": []}

    try:
        # 初始化客户端
        client = Ark(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize SDK client: {str(e)}")
        return {"tickers": [], "companies": [], "report": "", "modules": []}

    try:
        all_tickers = []
        all_companies = []
        all_reports = []
        modules = []

        # 处理PDF文档
        if doc_type == "pdf" and document:
            total_pages = len(document)
            st.info(f"开始分析PDF文档，共 {total_pages} 页...")

            # 为每一页创建进度条
            progress_bar = st.progress(0)

            for i, page_data in enumerate(document):
                page_num = page_data['page_number']
                image = page_data['image']
                img_bytes = page_data['bytes']

                # 更新进度
                progress = (i + 1) / total_pages
                progress_bar.progress(progress, text=f"分析第 {page_num}/{total_pages} 页")

                # 显示当前页图片预览
                with st.expander(f"查看第 {page_num} 页内容", expanded=False):
                    st.image(image, caption=f"PDF第 {page_num} 页", use_container_width=True)

                # 将图片转换为base64编码
                img_str = base64.b64encode(img_bytes).decode()
                image_url = f"data:image/png;base64,{img_str}"

                # 构建提示词，要求完整分析同时专门提取个股股票代码
                prompt = f"""
                请全面分析这张PDF第 {page_num} 页的内容，包括所有财务信息、图表、表格、文本内容和市场数据。

                您的任务是：
                1. 详细解析本页内容，识别所有相关的信息
                2. 将内容划分为有逻辑的模块（例如：行业分析、个股分析、市场趋势等），最多分三个模块，最多只能分为三个模块，必须遵守这条规则
                3. 为每个模块提供详细分析
                4. 不要分析UI界面的交互逻辑，只需要分析内容和数据就行。不要分析UI界面，只需要分析内容和数据就行。不要分析任何与数据和内容无关的东西，不要分析网页界面中的任何模块，是要针对金融领域的内容和数据进行分析。必须遵守这条规则
                5. 必须要提取所有的数据和内容，任何数据都不能省略，必须要保留所有的数据。但是不要分析UI界面中的任何像按钮、筛选、下拉框这些东西。必须遵守这条规则
                6. 如果有数据表必须要保留全部数据，不能有任何省略。但是不要分析UI界面中的任何像按钮、筛选、下拉框这些东西。必须遵守这条规则

                请按以下结构组织您的回答：
                - 总体概述：本页内容的简要总结
                - 模块划分：列出识别出的内容模块
                - 模块分析：对每个模块进行详细分析
                """

                # 按照官方参考代码格式构建消息
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]

                # 发送请求到API
                with st.spinner(f"使用 {MULTIMODAL_MODEL} 分析第 {page_num} 页..."):
                    try:
                        resp = client.chat.completions.create(
                            model=MULTIMODAL_MODEL,
                            messages=messages
                        )

                        # 提取模型返回的内容
                        if resp.choices and len(resp.choices) > 0:
                            report = resp.choices[0].message.content
                            all_reports.append(f"## 第 {page_num} 页分析\n{report}")

                            # 从模型响应中提取股票代码和公司信息
                            page_tickers = extract_tickers_from_text(report)
                            page_companies = extract_companies_from_text(report)
                            page_modules = extract_modules_from_text(report)

                            # 添加到总列表
                            all_tickers.extend(page_tickers)
                            all_companies.extend(page_companies)
                            modules.extend(page_modules)

                            st.success(f"第 {page_num} 页分析完成")
                        else:
                            st.warning(f"第 {page_num} 页未返回有效响应")
                            all_reports.append(f"## 第 {page_num} 页分析\n未返回有效响应")

                    except Exception as e:
                        st.error(f"第 {page_num} 页分析失败: {str(e)}")
                        all_reports.append(f"## 第 {page_num} 页分析\n分析失败: {str(e)}")

            # 合并所有报告
            full_report = "\n\n".join(all_reports)

            # 去重处理
            unique_tickers = list(dict.fromkeys(all_tickers))
            # 处理公司名称列表，使其与股票代码列表长度匹配
            unique_companies = []
            seen = set()
            for ticker, company in zip(all_tickers, all_companies):
                if ticker not in seen:
                    seen.add(ticker)
                    unique_companies.append(company)

            # 去重模块
            unique_modules = []
            seen_modules = set()
            for module in modules:
                if module not in seen_modules:
                    seen_modules.add(module)
                    unique_modules.append(module)

            # 保存到会话状态
            st.session_state.image_analysis_report = full_report
            st.session_state.extracted_tickers = unique_tickers
            st.session_state.extracted_companies = unique_companies
            st.session_state.pdf_analysis_completed = True
            st.session_state.image_analysis_completed = True
            st.session_state.web_analysis_completed = False

            # 更新任务进度
            st.session_state.task_progress['stage'] = 'document_analysis'
            st.session_state.task_progress['modules'] = unique_modules
            # 标记当前阶段为已完成
            if 'document_analysis' not in st.session_state.task_progress['completed_stages']:
                st.session_state.task_progress['completed_stages'].append('document_analysis')

            # 如果有提取到股票，默认选择第一个
            if unique_tickers:
                st.session_state.selected_ticker_from_image = unique_tickers[0]

            return {
                "tickers": unique_tickers,
                "companies": unique_companies,
                "report": full_report,
                "modules": unique_modules
            }

        # 处理图片文件或网页截图
        elif doc_type in ["image", "web"] and document:
            # 显示图片预览
            st.image(document, caption="网页截图" if doc_type == "web" else "上传的图片", use_container_width=True,
                     output_format="PNG")

            # 将图片转换为base64编码
            buffered = io.BytesIO()
            document.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            image_url = f"data:image/png;base64,{img_str}"

            # 根据文档类型调整提示词
            content_type = "网页" if doc_type == "web" else "图片"

            prompt = f"""
            请全面分析这张{content_type}中的内容，包括所有财务信息、图表、表格、文本内容和市场数据。

            您的任务是：
            1. 详细解析{content_type}内容，识别所有相关的信息
            2. 将内容划分为有逻辑的模块（例如：行业分析、个股分析、市场趋势等）
            3. 为每个模块提供详细分析
            4. 不要分析UI界面的交互逻辑，只需要分析内容和数据就行。不要分析UI界面，只需要分析内容和数据就行。不要分析任何与数据和内容无关的东西，不要分析网页界面中的任何模块，是要针对金融领域的内容和数据进行分析。必须遵守这条规则
            5. 必须要提取所有的数据和内容，任何数据都不能省略，必须要保留所有的数据。但是不要分析UI界面中的任何像按钮、筛选、下拉框这些东西。必须遵守这条规则
            6. 如果有数据表必须要保留全部数据，不能有任何省略。但是不要分析UI界面中的任何像按钮、筛选、下拉框这些东西。必须遵守这条规则

            请按以下结构组织您的回答：
            - 总体概述：{content_type}内容的简要总结
            - 模块划分：列出识别出的内容模块
            - 模块分析：对每个模块进行详细分析

            """

            # 按照官方参考代码格式构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]

            # 发送请求到API
            with st.spinner(f"使用 {MULTIMODAL_MODEL} 多模态模型分析{content_type}中..."):
                try:
                    resp = client.chat.completions.create(
                        model=MULTIMODAL_MODEL,
                        messages=messages
                    )

                    # 提取模型返回的内容
                    if resp.choices and len(resp.choices) > 0:
                        report = resp.choices[0].message.content
                        st.success(f"{content_type}分析成功完成")

                        # 从模型响应中提取股票代码、公司信息和模块
                        extracted_tickers = extract_tickers_from_text(report)
                        extracted_tickers = list(dict.fromkeys(extracted_tickers))

                        extracted_companies = extract_companies_from_text(report)
                        if len(extracted_companies) > len(extracted_tickers):
                            extracted_companies = extracted_companies[:len(extracted_tickers)]
                        elif len(extracted_companies) < len(extracted_tickers):
                            extracted_companies += ["未知公司"] * (len(extracted_tickers) - len(extracted_companies))

                        modules = extract_modules_from_text(report)
                        unique_modules = list(dict.fromkeys(modules))

                        # 保存到会话状态
                        st.session_state.image_analysis_report = report
                        st.session_state.extracted_tickers = extracted_tickers
                        st.session_state.extracted_companies = extracted_companies

                        # 根据文档类型设置相应的完成状态
                        if doc_type == "web":
                            st.session_state.web_analysis_completed = True
                            st.session_state.image_analysis_completed = False
                            st.session_state.pdf_analysis_completed = False
                        else:
                            st.session_state.image_analysis_completed = True
                            st.session_state.pdf_analysis_completed = False
                            st.session_state.web_analysis_completed = False

                        # 更新任务进度
                        st.session_state.task_progress['stage'] = 'document_analysis'
                        st.session_state.task_progress['modules'] = unique_modules
                        # 标记当前阶段为已完成
                        if 'document_analysis' not in st.session_state.task_progress['completed_stages']:
                            st.session_state.task_progress['completed_stages'].append('document_analysis')

                        # 如果有提取到股票，默认选择第一个
                        if extracted_tickers:
                            st.session_state.selected_ticker_from_image = extracted_tickers[0]

                        return {
                            "tickers": extracted_tickers,
                            "companies": extracted_companies,
                            "report": report,
                            "modules": unique_modules
                        }
                    else:
                        st.warning(f"{content_type}模型未返回有效响应。")
                        return {"tickers": [], "companies": [], "report": "", "modules": []}

                except Exception as e:
                    st.error(f"API请求失败: {str(e)}")
                    return {"tickers": [], "companies": [], "report": "", "modules": []}

        else:
            st.warning("未提供有效的文档进行分析")
            return {"tickers": [], "companies": [], "report": "", "modules": []}

    except Exception as e:
        st.error(f"文档分析错误: {str(e)}")
        return {"tickers": [], "companies": [], "report": "", "modules": []}


# 生成执行计划 - 第二阶段
def generate_execution_plan(document_report, modules):
    """根据初步分析报告和模块生成详细的多层级执行计划，明确步骤间依赖关系"""
    if not has_ark_sdk:
        return "volcenginesdkarkruntime not installed. Cannot generate execution plan."

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return "API key not configured. Cannot generate execution plan."

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return f"Failed to initialize SDK client: {str(e)}"

    tool_executor = ToolExecutor()
    AVAILABLE_TOOLS = ToolExecutor.generate_available_tools(tool_executor)

    # 改进的提示词：明确要求标注步骤间依赖关系
    prompt = f"""
    根据以下文档分析报告和识别出的内容模块，为接下来的深度解析生成详细的多层级执行计划。
    执行计划应具有视觉吸引力，层次分明，易于阅读和理解。
    绝对强制要求：计划中不需要验证信息准确性与完整性和一致性什么的，步骤中不允许出现对信息准确性、完整性和一致性的验证。不允许出现任何验证计划，不允许验证，不需要验证任何数据和内容
    {AVAILABLE_TOOLS}

    文档分析报告:
    {document_report}

    识别出的内容模块:
    {', '.join(modules)}

    您的任务是:
    1. 为每个模块设计1-2个详细的分析步骤，形成清晰的层级结构
    2. 绝对强制要求：计划中不需要验证信息准确性与完整性和一致性什么的，步骤中不允许出现对信息准确性、完整性和一致性的验证。不允许出现任何验证计划，不允许验证，不需要验证任何数据和内容
    3. 每个步骤必须有明确的目标和预期输出
    4. 明确每个步骤是否需要使用工具，如需要，说明工具名称和参数
    5. 使用的工具必须是工具列表中存在的工具，严格禁止使用工具列表中不存在的工具
    6. 使用的工具必须和内容相关，不允许在不存在工具参数的时候使用工具
    7. 必须严格基于报告生成工具调用参数，绝对不允许编造参数
    8. 绝对强制要求：计划中不需要验证信息准确性与完整性，步骤中不允许出现对信息准确性和完整性的验证
    9. 如果工具和当前步骤高度相关，但工具所需必要参数难以从报告中提取，则不选择调用该工具
       - 当前日期为 {str(datetime.date.today())}
       - 如果工具需要日期参数但报告中未明确指出报告日期，则对于需要给出单个日期的工具选择当前日期作为输入参数，对于需要给出范围日期的工具选择最近一周作为输入参数，绝对不允许自行假设日期参数
    10. 确保计划逻辑清晰，按合理顺序排列
    11. **关键要求：明确步骤间依赖关系**  
       - 如果步骤B需要使用步骤A的输出结果，则必须在步骤B中注明“依赖步骤：A的ID”  
       - 例如：步骤1.b依赖步骤1.a的结果，则在步骤1.b中添加“依赖步骤：1.a”  
    12. 使用清晰的标题和格式，使计划易于阅读和理解
    13. 绝对强制要求：必须基于真实的内容设计计划，不允许任何假设或编造！
    14. 每个步骤只能选择一个工具调用
    15. 计划中不需要验证信息准确性与完整性。不允许出现任何验证计划，不允许验证，不需要验证任何数据和内容
    16. 计划主要应该是解决文档分析中对文档内容分析为什么，怎么做的问题
    17. 工具参数即使有默认值也必须要显式给出参数值  

    执行计划必须采用以下严格格式，使用数字和字母编号区分模块和步骤：
    # 总体分析目标
    [简要描述整体分析目标]

    # 模块分析计划
    ## 1. [模块名称1]
       ### a. 步骤1: [步骤名称]
          - 分析内容: [详细描述需要分析的内容]
          - 使用工具: [是/否，如果是，说明工具名称]
          - 参数: [如使用工具，列出所需参数]
          - 预期输出: [描述该步骤的预期结果]
          - 依赖步骤: [如果有依赖，填写依赖的步骤ID，如"1.a"；无依赖则填"无"]
       ### b. 步骤2: [步骤名称]
          - 分析内容: [详细描述需要分析的内容]
          - 使用工具: [是/否，如果是，说明工具名称]
          - 参数: [如使用工具，列出所需参数]
          - 预期输出: [描述该步骤的预期结果]
          - 依赖步骤: [如果有依赖，填写依赖的步骤ID，如"1.a"；无依赖则填"无"]
       ...
    ## 2. [模块名称2]
       ### a. 步骤1: [步骤名称]
          - 分析内容: [详细描述需要分析的内容]
          - 使用工具: [是/否，如果是，说明工具名称]
          - 参数: [如使用工具，列出所需参数]
          - 预期输出: [描述该步骤的预期结果]
          - 依赖步骤: [如果有依赖，填写依赖的步骤ID，如"1.b"；无依赖则填"无"]
       ...

    # 计划执行顺序
    [说明模块和步骤的执行顺序，如：1.a → 1.b → 2.a → ...]
    """

    try:
        with st.spinner(f"使用 {MULTIMODAL_MODEL} 生成执行计划中..."):
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
                plan = resp.choices[0].message.content
                st.session_state.execution_plan = plan
                st.session_state.task_progress['stage'] = 'plan_generation'
                if 'plan_generation' not in st.session_state.task_progress['completed_stages']:
                    st.session_state.task_progress['completed_stages'].append('plan_generation')

                # 解析计划步骤并更新任务进度
                steps = extract_steps_from_plan(plan)
                st.session_state.task_progress['steps'] = steps
                st.session_state.task_progress['total_steps'] = len(steps)
                st.session_state.task_progress['current_step'] = 0
                st.session_state.task_progress['completed_steps'] = 0

                return plan
            else:
                return "模型未返回有效响应，无法生成执行计划"

    except Exception as e:
        return f"生成执行计划失败: {str(e)}"


# 新增：验证工具输出是否符合步骤要求
def validate_tool_output(step, tool_output):
    """使用大模型验证工具输出是否符合步骤要求"""
    if not has_ark_sdk:
        return {"matches": False, "reason": "volcenginesdkarkruntime not installed"}

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return {"matches": False, "reason": "API key not configured"}

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return {"matches": False, "reason": f"Failed to initialize SDK client: {str(e)}"}

    prompt = f"""
    请判断以下工具执行结果是否符合步骤要求：

    步骤信息：
    - 步骤名称: {step.get('name', '未命名步骤')}
    - 分析内容: {step.get('content', '无内容')}
    - 预期输出: {step.get('expected_output', '无预期输出')}
    - 使用工具: {step.get('tool', '无工具')}
    - 请求参数: {json.dumps(step.get('parameters', {}), ensure_ascii=False)}

    工具执行结果：
    {tool_output}

    您的判断标准：
    1. 工具返回的数据是否能够满足该步骤的分析需求
    2. 返回的数据是否与请求参数相关
    3. 数据是否完整到可以基于此进行下一步分析

    请返回一个JSON对象，包含：
    - "matches": 布尔值，表示结果是否符合要求
    - "reason": 字符串，说明判断理由
    - "missing_info": 字符串数组，列出缺失的关键信息（如无缺失则为空数组）
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
            result_text = resp.choices[0].message.content
            # 清理可能的格式问题
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()

            return json.loads(result_text)
        else:
            return {
                "matches": False,
                "reason": "模型未返回有效响应",
                "missing_info": []
            }

    except json.JSONDecodeError as e:
        return {
            "matches": False,
            "reason": f"解析验证结果失败: {str(e)}",
            "missing_info": []
        }
    except Exception as e:
        return {
            "matches": False,
            "reason": f"验证工具输出失败: {str(e)}",
            "missing_info": []
        }


# 新增：根据工具输出调整步骤
def adjust_step_based_on_output(current_step, tool_output, validation_result, all_steps, completed_steps):
    """根据工具输出和验证结果调整步骤"""
    if not has_ark_sdk:
        return None, "volcenginesdkarkruntime not installed"

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return None, "API key not configured"

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return None, f"Failed to initialize SDK client: {str(e)}"

    tool_executor = ToolExecutor()
    AVAILABLE_TOOLS = ToolExecutor.generate_available_tools(tool_executor)

    # 收集已完成步骤的信息
    completed_steps_info = []
    for step in completed_steps:
        completed_steps_info.append({
            "step_id": step.get('full_step_id', ''),
            "name": step.get('name', ''),
            "tool": step.get('tool', ''),
            "output_summary": f"{str(step.get('tool_output', ''))[:200]}..."
        })

    prompt = f"""
    由于工具执行结果不符合预期，需要重新设计当前步骤。
    绝对强制要求：新步骤必须基于已获取的数据来设计步骤计划，不允许再要求获取其他数据。例如之前工具返回的数据是实时数据，没有近一个月或者近一年的数据，那就必须调整步骤为要求获取实时数据的步骤。而不是继续要求获取历史数据。

    {AVAILABLE_TOOLS}

    当前步骤信息：
    - 步骤ID: {current_step.get('full_step_id', '未知')}
    - 步骤名称: {current_step.get('name', '未命名步骤')}
    - 所属模块: {current_step.get('module', '未分类模块')}
    - 原分析内容: {current_step.get('content', '无内容')}
    - 原使用工具: {current_step.get('tool', '无工具')}
    - 原请求参数: {json.dumps(current_step.get('parameters', {}), ensure_ascii=False)}
    - 原预期输出: {current_step.get('expected_output', '无预期输出')}

    工具实际执行结果：
    {tool_output}

    验证结果：
    - 是否符合预期: {'是' if validation_result.get('matches', False) else '否'}
    - 原因: {validation_result.get('reason', '无')}
    - 缺失信息: {', '.join(validation_result.get('missing_info', [])) or '无'}

    已完成的步骤：
    {json.dumps(completed_steps_info, ensure_ascii=False, indent=2)}

    您的任务：
    1. 基于实际工具输出和已完成步骤的结果，重新设计当前步骤
    2. 绝对强制要求：新步骤必须基于已获取的数据来设计步骤计划，不允许再要求获取其他数据。例如之前工具返回的数据是实时数据，没有近一个月或者近一年的数据，那就必须调整步骤为要求获取实时数据的步骤。而不是继续要求获取历史数据。
    3. 调整使用的工具或参数，确保能够获得有效的分析结果
    4. 保持与其他步骤的依赖关系，但可以适当调整
    5. 必须使用工具列表中存在的工具，参数必须基于已有信息
    6. 工具参数即使有默认值也必须要显示给出参数值
    7. 当前日期为 {str(datetime.date.today())}
    8. 每个步骤只能选择一个工具调用，不允许使用多个工具

    请返回一个JSON对象，包含调整后的步骤信息：
    {{
        "name": "新步骤名称",
        "content": "新的分析内容",
        "uses_tool": true/false,
        "tool": "工具名称（如果使用工具）",
        "parameters": {{
            "参数名称1": "参数值1",
            "参数名称2": "参数值2"
        }},
        "expected_output": "调整后的预期输出",
        "depends_on": ["依赖的步骤ID列表"]
    }}
    """

    try:
        with st.spinner(f"使用 {MULTIMODAL_MODEL} 调整分析步骤..."):
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
                result_text = resp.choices[0].message.content
                # 清理可能的格式问题
                result_text = result_text.strip()
                if result_text.startswith('```json'):
                    result_text = result_text[7:-3].strip()
                elif result_text.startswith('```'):
                    result_text = result_text[3:-3].strip()

                adjusted_step = json.loads(result_text)
                # 保留模块和ID信息
                adjusted_step['module'] = current_step.get('module', '未分类模块')
                adjusted_step['module_id'] = current_step.get('module_id', '')
                adjusted_step['step_id'] = current_step.get('step_id', '')
                adjusted_step['full_step_id'] = current_step.get('full_step_id', '')

                return adjusted_step, "步骤调整成功"
            else:
                return None, "模型未返回有效响应，无法调整步骤"

    except json.JSONDecodeError as e:
        return None, f"解析调整结果失败: {str(e)}"
    except Exception as e:
        return None, f"调整步骤失败: {str(e)}"


# 执行计划 - 第三阶段
def execute_plan(plan, progress_callback=None):
    # 初始化工具执行器
    if st.session_state.tool_executor is None:
        st.session_state.tool_executor = ToolExecutor()
    tool_executor = st.session_state.tool_executor

    """按照执行计划执行分析步骤，仅向模型传递必要的前置步骤信息"""
    if not plan:
        return []

    # 提取计划中的步骤
    steps = st.session_state.task_progress.get('steps', [])
    if not steps:
        steps = extract_steps_from_plan(plan)
        st.session_state.task_progress['steps'] = steps
        st.session_state.task_progress['total_steps'] = len(steps)
        st.session_state.task_progress['current_step'] = 0
        st.session_state.task_progress['completed_steps'] = 0

    # 如果所有步骤都已完成，返回
    if st.session_state.task_progress['current_step'] >= st.session_state.task_progress['total_steps']:
        if 'plan_execution' not in st.session_state.task_progress['completed_stages']:
            st.session_state.task_progress['completed_stages'].append('plan_execution')
        return st.session_state.task_progress.get('execution_reports', [])

    # 执行当前步骤
    execution_reports = st.session_state.task_progress.get('execution_reports', [])
    current_step_idx = st.session_state.task_progress['current_step']
    step = steps[current_step_idx]
    step_name = step.get('name', f"步骤 {current_step_idx + 1}")
    module_name = step.get('module', "未分类模块")

    if progress_callback:
        progress_callback(f"正在执行 {module_name} - {step_name}", current_step_idx, len(steps))

    # 收集依赖的步骤信息（仅用于模型分析）
    dependencies = []
    if step.get('depends_on', []):
        # 查找所有已完成的步骤报告
        completed_reports = [r for r in execution_reports if r['status'] == 'completed']

        # 为每个依赖的步骤ID查找对应的报告
        for dep_step_id in step['depends_on']:
            # 查找对应的步骤
            dep_step = next((s for s in steps if s['full_step_id'] == dep_step_id), None)
            if dep_step:
                # 查找该步骤的报告
                dep_report = next(
                    (r for r in completed_reports if r['step'] == steps.index(dep_step) + 1),
                    None
                )
                if dep_report:
                    dependencies.append({
                        'step_id': dep_step_id,
                        'step_name': dep_step['name'],
                        'report': dep_report['report'],
                        'tool_output': dep_report.get('tool_output', None)
                    })

    # 显示当前执行步骤和依赖信息
    with st.expander(f"🔄 正在执行 [{module_name}]: {step_name}", expanded=True):
        st.write(f"**分析内容**: {step.get('content', '未指定')}")
        st.write(f"**是否使用工具**: {step.get('uses_tool', '否')}")

        # 显示依赖信息
        if dependencies:
            with st.expander("查看依赖的前置步骤信息", expanded=False):
                for dep in dependencies:
                    st.markdown(f"**来自步骤 {dep['step_id']}: {dep['step_name']} 的信息:**")
                    st.markdown(dep['report'])

        try:
            # 准备传递给模型的依赖信息
            dependency_context = "\n\n".join([
                f"来自步骤 {dep['step_id']} ({dep['step_name']}) 的信息:\n{dep['report']}"
                for dep in dependencies
            ])

            tool_output = None
            if step.get('uses_tool', False):
                # 执行工具时不传递依赖信息，只使用原始参数
                tool_output = tool_executor.execute(
                    tool_name=step.get('tool', ''),
                    parameters=step.get('parameters', {}),
                )

                # 显示工具输出
                st.info("工具执行完成，正在验证结果...")
                with st.expander("查看工具原始输出", expanded=False):
                    st.code(tool_output)

                # 验证工具输出是否符合预期
                validation_result = validate_tool_output(step, tool_output)

                # 显示验证结果
                if validation_result.get('matches', False):
                    st.success(f"✅ 工具输出符合步骤要求: {validation_result.get('reason', '')}")
                else:
                    st.warning(f"⚠️ 工具输出不符合预期: {validation_result.get('reason', '')}")
                    if validation_result.get('missing_info', []):
                        st.info(f"缺失信息: {', '.join(validation_result.get('missing_info', []))}")

                    # 尝试调整步骤
                    st.info("正在尝试调整步骤...")
                    completed_steps = steps[:current_step_idx]  # 获取已完成的步骤
                    adjusted_step, adjust_msg = adjust_step_based_on_output(
                        step, tool_output, validation_result, steps, completed_steps
                    )

                    if adjusted_step:
                        st.success(f"步骤已调整: {adjust_msg}")
                        # 更新当前步骤为调整后的步骤
                        steps[current_step_idx] = adjusted_step
                        st.session_state.task_progress['steps'] = steps

                        # 重新执行调整后的步骤
                        with st.expander("查看调整后的步骤", expanded=True):
                            st.json(adjusted_step)

                        # 使用调整后的步骤重新执行工具调用
                        if adjusted_step.get('uses_tool', False):
                            tool_output = tool_executor.execute(
                                tool_name=adjusted_step.get('tool', ''),
                                parameters=adjusted_step.get('parameters', {}),
                            )
                            st.info("使用调整后的参数重新执行工具...")
                            with st.expander("查看调整后工具的原始输出", expanded=False):
                                st.code(tool_output)
                        else:
                            st.info("调整后的步骤不使用工具，直接进行分析...")
                    else:
                        st.error(f"无法调整步骤: {adjust_msg}，将基于现有结果继续分析")

                # 将工具输出和依赖信息一起输入大模型生成报告
                report_text = analyze_step_with_model(step, tool_output=tool_output, dependencies=dependencies)
            else:
                # 直接调用模型进行分析，传递依赖信息
                st.info("正在进行文本分析...")
                report_text = analyze_step_with_model(step, dependencies=dependencies)

            # 更新执行报告
            step_report = {
                'step': current_step_idx + 1,
                'module': module_name,
                'name': step_name,
                'report': report_text,
                'status': 'completed',
                'tool_output': tool_output if step.get('uses_tool', False) else None,
                'validation_result': validation_result if step.get('uses_tool', False) else None
            }

            if current_step_idx < len(execution_reports):
                execution_reports[current_step_idx] = step_report
            else:
                execution_reports.append(step_report)

            # 更新会话状态
            st.session_state.task_progress['completed_steps'] = current_step_idx + 1
            st.session_state.task_progress['current_step'] = current_step_idx + 1
            st.session_state.task_progress['execution_reports'] = execution_reports

            st.success(f"✅ {module_name} - {step_name} 执行完成")

        except Exception as e:
            error_msg = f"步骤 {current_step_idx + 1} 执行失败: {str(e)}"
            if current_step_idx < len(execution_reports):
                execution_reports[current_step_idx] = {
                    'step': current_step_idx + 1,
                    'module': module_name,
                    'name': step_name,
                    'report': error_msg,
                    'status': 'failed'
                }
            else:
                execution_reports.append({
                    'step': current_step_idx + 1,
                    'module': module_name,
                    'name': step_name,
                    'report': error_msg,
                    'status': 'failed'
                })

            st.session_state.task_progress['execution_reports'] = execution_reports
            st.error(error_msg)

    # 更新任务进度状态
    st.session_state.task_progress['stage'] = 'plan_execution'
    st.rerun()

    return execution_reports


# 使用模型分析单个步骤
def analyze_step_with_model(step, tool_output=None, dependencies=None):
    """使用模型分析单个步骤，接收工具输出和依赖信息"""
    if not has_ark_sdk:
        return "volcenginesdkarkruntime not installed. Cannot analyze step."

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return "API key not configured. Cannot analyze step."

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return f"Failed to initialize SDK client: {str(e)}"

    # 基础提示信息
    prompt_parts = [
        "请根据以下分析步骤要求，进行详细分析并生成报告：",
        f"\n分析步骤:",
        f"模块: {step.get('module', '未命名模块')}",
        f"名称: {step.get('name', '未命名步骤')}",
        f"内容: {step.get('content', '无内容')}",
        f"预期输出: {step.get('expected_output', '无预期输出')}",
        f"\n文档初步分析信息:",
        f"{st.session_state.image_analysis_report}..."
    ]

    # 添加依赖信息（仅模型使用）
    if dependencies and len(dependencies) > 0:
        prompt_parts.append("\n相关前置步骤信息:")
        for i, dep in enumerate(dependencies):
            prompt_parts.append(f"步骤 {dep['step_id']} ({dep['step_name']}) 的分析结果:")
            prompt_parts.append(f"{dep['report']}")

    # 如果有工具输出，添加到提示中
    if tool_output:
        prompt_parts.extend([
            "\n工具执行结果:",
            f"{tool_output}",
            "\n请基于上述工具执行结果、前置步骤信息和分析步骤要求，生成分析报告。"
        ])
    else:
        prompt_parts.append("\n请基于前置步骤信息（如有时）和分析步骤要求，提供详细分析报告。")

    # 合并所有提示部分
    prompt = "\n".join(prompt_parts)

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


# 生成最终综合报告 - 第四阶段
def generate_final_synthesis_report():
    """整合所有分析报告生成最终综合报告"""
    if not has_ark_sdk:
        return "volcenginesdkarkruntime not installed. Cannot generate synthesis report."

    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        return "API key not configured. Cannot generate synthesis report."

    try:
        client = Ark(api_key=api_key)
    except Exception as e:
        return f"Failed to initialize SDK client: {str(e)}"

    # 收集所有报告
    document_report = st.session_state.get('image_analysis_report', '')
    execution_plan = st.session_state.get('execution_plan', '')
    execution_reports = st.session_state.task_progress.get('execution_reports', [])

    # 构建执行报告文本
    execution_reports_text = ""
    for report in execution_reports:
        execution_reports_text += f"## 步骤 {report['step']} [{report['module']}]: {report['name']}\n{report['report']}\n\n"

    prompt = f"""
    作为资深金融分析师，请将以下所有分析内容整合成一份全面、深入的最终综合报告：

    1. 文档初步分析报告：
    {document_report}

    2. 执行计划：
    {execution_plan}

    3. 各步骤执行结果：
    {execution_reports_text}

    您的最终综合报告应：
    - 保留所有之前分析报告的关键内容
    - 按逻辑顺序组织，结构清晰
    - 增加更深入的分析和见解
    - 使用专业的术语，同时保持可读性
    - 要保证所有数据绝对真实准确，存在缺失数据不允许说缺失数据，而是应该改变分析策略，不分析没有数据的这部分
    """

    try:
        with st.spinner(f"使用 {MULTIMODAL_MODEL} 生成最终综合报告中..."):
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
                final_report = resp.choices[0].message.content
                st.session_state.final_synthesis_report = final_report
                st.session_state.task_progress['stage'] = 'final_report'
                # 标记当前阶段为已完成
                if 'final_report' not in st.session_state.task_progress['completed_stages']:
                    st.session_state.task_progress['completed_stages'].append('final_report')
                return final_report
            else:
                return "模型未返回有效响应，无法生成综合报告"

    except Exception as e:
        return f"生成综合报告失败: {str(e)}"

# 改进任务进度显示，增加模块分组
def display_task_progress():
    """显示当前任务进度和流程，确保进度条实时更新"""
    task_progress = st.session_state.task_progress

    st.markdown("### 📝 分析任务流程")

    # 显示总体进度
    stages = [
        {'id': 'initial', 'name': '初始化'},
        {'id': 'document_analysis', 'name': '文档解析'},
        {'id': 'plan_generation', 'name': '生成执行计划'},
        {'id': 'plan_execution', 'name': '执行计划'},
        {'id': 'final_report', 'name': '生成最终报告'}
    ]

    # 计算总体进度百分比
    current_stage_idx = next((i for i, s in enumerate(stages) if s['id'] == task_progress['stage']), 0)
    overall_progress = (current_stage_idx / (len(stages) - 1)) if len(stages) > 1 else 0

    st.progress(overall_progress, text=f"当前阶段: {stages[current_stage_idx]['name']}")

    # 显示阶段状态 - 根据已完成的阶段列表来显示✅
    cols = st.columns(len(stages))
    for i, stage in enumerate(stages):
        with cols[i]:
            if stage['id'] in task_progress['completed_stages']:
                status = "✅"
            elif stage['id'] == task_progress['stage']:
                status = "🔄"
            else:
                status = "⏸️"
            st.markdown(f"{status} {stage['name']}")

    st.markdown("---")

    # 根据当前阶段显示详细信息
    if task_progress['stage'] == 'document_analysis' and 'modules' in task_progress:
        st.markdown("### 🔍 文档解析结果 - 识别的模块")
        modules = task_progress['modules']
        for i, module in enumerate(modules):
            st.markdown(f"{i + 1}. {module}")

        if st.button("📋 生成执行计划"):
            with st.spinner("正在生成执行计划..."):
                plan = generate_execution_plan(
                    st.session_state.image_analysis_report,
                    modules
                )
                # 确保当前阶段被标记为已完成
                if 'document_analysis' not in st.session_state.task_progress['completed_stages']:
                    st.session_state.task_progress['completed_stages'].append('document_analysis')
                st.success("执行计划生成完成")
                st.rerun()

    elif task_progress['stage'] == 'plan_generation' and st.session_state.execution_plan:
        st.markdown("### 📋 执行计划")
        with st.expander("查看详细执行计划", expanded=False):
            st.code(st.session_state.execution_plan, language="markdown")

        if st.button("▶️ 开始执行计划"):
            st.session_state.task_progress['stage'] = 'plan_execution'
            st.session_state.task_progress['current_step'] = 0
            st.session_state.task_progress['completed_steps'] = 0
            # 确保当前阶段被标记为已完成
            if 'plan_generation' not in st.session_state.task_progress['completed_stages']:
                st.session_state.task_progress['completed_stages'].append('plan_generation')
            st.rerun()

    elif task_progress['stage'] == 'plan_execution':
        st.markdown("### ▶️ 计划执行进度")
        # 添加折叠面板显示执行计划
        with st.expander("📋 查看执行计划", expanded=False):
            st.markdown(st.session_state.execution_plan)

        total_steps = task_progress['total_steps']
        completed_steps = task_progress['completed_steps']
        current_step = task_progress['current_step']

        # 实时更新的进度条
        if total_steps > 0:
            progress = completed_steps / total_steps if total_steps > 0 else 0
            progress_bar = st.progress(progress, text=f"已完成 {completed_steps}/{total_steps} 步")

            # 按模块分组显示步骤列表
            steps = task_progress['steps']
            modules = list(dict.fromkeys(step['module'] for step in steps))  # 去重且保持顺序

            # 遍历有序模块列表
            for module in modules:
                module_steps = [s for s in steps if s['module'] == module]
                with st.expander(
                        f"📦 {module} ({sum(1 for s in module_steps if steps.index(s) < completed_steps)}/{len(module_steps)})",
                        expanded=True
                ):
                    # 按步骤在原始计划中的顺序显示
                    for step in module_steps:
                        step_index = steps.index(step)  # 保持原始步骤顺序
                        # 明确区分已完成、正在执行和未开始的步骤
                        if step_index < completed_steps:
                            step_status = "✅"
                            step_class = "completed"
                        elif step_index == current_step and completed_steps < total_steps:
                            step_status = "🔄"
                            step_class = "active"
                        else:
                            step_status = "⏸️"
                            step_class = ""

                        st.markdown(f"""
                        <div class="task-step {step_class}">
                            <strong>{step_status} 步骤 {step_index + 1}: {step['name']}</strong>
                            <p>分析内容: {step['content'][:100]}{'...' if len(step['content']) > 100 else ''}</p>
                            <p>使用工具: {'是 - ' + step['tool'] if step['uses_tool'] else '否'}</p>
                        </div>
                        """, unsafe_allow_html=True)

            # 执行步骤的逻辑，每次只执行一个步骤
            if completed_steps < total_steps:
                # 检查是否需要执行下一步
                if current_step == completed_steps:
                    # 显示当前执行的步骤信息
                    current_step_data = steps[current_step] if current_step < len(steps) else None
                    if current_step_data:
                        with st.spinner(f"正在执行步骤 {current_step + 1}/{total_steps}: {current_step_data['name']}"):
                            # 执行单步并立即更新状态
                            execute_plan(st.session_state.execution_plan)
                else:
                    # 同步状态，防止不一致
                    st.session_state.task_progress['current_step'] = completed_steps
                    st.rerun()
            elif completed_steps >= total_steps:
                # 关键修复：步骤完成后立即标记阶段为已完成
                if 'plan_execution' not in st.session_state.task_progress['completed_stages']:
                    st.session_state.task_progress['completed_stages'].append('plan_execution')
                    # 强制刷新以更新UI状态
                    st.rerun()
                st.success("所有计划步骤执行完成！")
                if st.button("📊 生成最终综合报告"):
                    with st.spinner("正在生成最终综合报告..."):
                        final_report = generate_final_synthesis_report()
                        # 确保当前阶段被标记为已完成
                        if 'plan_execution' not in st.session_state.task_progress['completed_stages']:
                            st.session_state.task_progress['completed_stages'].append('plan_execution')
                        st.success("最终综合报告生成完成")
                        st.rerun()

    elif task_progress['stage'] == 'final_report' and st.session_state.final_synthesis_report:
        st.markdown("### 📊 最终综合报告")
        with st.expander("📋 查看执行计划", expanded=False):
            st.markdown(st.session_state.execution_plan)
        with st.expander("查看最终综合报告", expanded=True):
            st.markdown(st.session_state.final_synthesis_report)

        st.success("🎉 所有分析任务已完成！")
