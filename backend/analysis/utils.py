import streamlit as st
import os
import json
import re
import base64

# 引入官方SDK
try:
    from volcenginesdkarkruntime import Ark

    has_ark_sdk = True
except ImportError:
    has_ark_sdk = False

# 导入指定模型
from backend.analysis.config import MULTIMODAL_MODEL

# 辅助函数：从文本中提取股票代码
def extract_tickers_from_text(text):
    """提取A股股票代码（6位数字）"""
    # 定位模型报告中明确标注个股代码的部分
    start_markers = ["个股股票代码", "股票代码", "A股代码"]
    end_markers = ["公司名称", "模块分析", "总体概述", "模块划分"]

    # 尝试所有可能的起始标记
    start_idx = -1
    for marker in start_markers:
        start_idx = text.find(marker)
        if start_idx != -1:
            break

    if start_idx != -1:
        # 尝试所有可能的结束标记
        end_idx = len(text)
        for marker in end_markers:
            temp_idx = text.find(marker, start_idx)
            if temp_idx != -1:
                end_idx = temp_idx
                break

        # 提取从起始标记到结束标记之间的内容
        code_section = text[start_idx:end_idx].strip()
    else:
        # 如果没有明确标记，搜索整个文本
        code_section = text

    # 提取6位数字的A股代码
    pattern = r'\b\d{6}\b'
    tickers = re.findall(pattern, code_section)

    # 去重并返回
    return list(dict.fromkeys(tickers))


# 辅助函数：从文本中提取公司名称
def extract_companies_from_text(text):
    """提取公司名称"""
    start_markers = ["公司名称", "对应的公司名称"]
    end_markers = ["模块分析", "总体概述", "模块划分", "个股股票代码"]

    # 尝试所有可能的起始标记
    start_idx = -1
    for marker in start_markers:
        start_idx = text.find(marker)
        if start_idx != -1:
            break

    if start_idx == -1:
        return []

    # 尝试所有可能的结束标记
    end_idx = len(text)
    for marker in end_markers:
        temp_idx = text.find(marker, start_idx)
        if temp_idx != -1:
            end_idx = temp_idx
            break

    # 提取公司名称部分
    company_section = text[start_idx:end_idx].strip()

    # 提取公司名称（处理列表格式）
    companies = []
    # 按行分割
    lines = [line.strip() for line in company_section.split('\n') if line.strip()]

    for line in lines:
        # 过滤掉数字和空行
        if not line.isdigit() and len(line) > 3:
            # 移除可能的编号前缀（如1. 2. 等）
            cleaned_line = re.sub(r'^\d+\.\s*', '', line)
            # 移除可能包含的股票代码
            cleaned_line = re.sub(r'\b\d{6}\b', '', cleaned_line).strip()
            companies.append(cleaned_line)

    # 去重
    return list(dict.fromkeys(companies))


# 辅助函数：从文本中提取模块
def extract_modules_from_text(text):
    """从分析报告中提取内容模块"""
    start_markers = ["模块划分", "内容模块", "识别出的模块"]
    end_markers = ["模块分析", "总体概述", "个股股票代码", "公司名称"]

    # 尝试所有可能的起始标记
    start_idx = -1
    for marker in start_markers:
        start_idx = text.find(marker)
        if start_idx != -1:
            break

    if start_idx == -1:
        # 如果没有明确的模块划分，尝试从分析中提取
        return extract_implied_modules(text)

    # 尝试所有可能的结束标记
    end_idx = len(text)
    for marker in end_markers:
        temp_idx = text.find(marker, start_idx)
        if temp_idx != -1:
            end_idx = temp_idx
            break

    # 提取模块部分
    module_section = text[start_idx:end_idx].strip()

    # 提取模块名称
    modules = []
    # 按行分割
    lines = [line.strip() for line in module_section.split('\n') if line.strip()]

    for line in lines:
        # 跳过标记行
        if any(marker in line for marker in start_markers):
            continue
        if line.startswith('#'):
            continue

        # 移除可能的编号前缀（如1. 2. 等）
        cleaned_line = re.sub(r'^\d+\.\s*', '', line)

        if len(cleaned_line) > 2:  # 过滤过短的条目
            modules.append(cleaned_line)

    # 去重
    return list(dict.fromkeys(modules))


# 辅助函数：从文本中提取隐含的模块
def extract_implied_modules(text):
    """当没有明确模块划分时，从分析中提取隐含的模块"""
    possible_modules = [
        "行业分析", "个股分析", "市场趋势", "财务分析",
        "投资建议", "风险评估", "宏观经济", "政策分析",
        "市场情绪", "技术分析", "估值分析", "业绩预测"
    ]

    found_modules = []
    for module in possible_modules:
        if module in text:
            found_modules.append(module)

    # 如果没有找到任何模块，返回默认模块
    if not found_modules:
        return ["总体市场分析", "个股分析", "投资建议"]

    return found_modules


# 使用大模型提取步骤结构，替代正则表达式
def extract_steps_from_plan(plan_text):
    """使用大模型从执行计划文本中提取多层级步骤结构，包括步骤间依赖关系"""
    if not has_ark_sdk:
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

    # 定义期望的JSON结构，增加了依赖关系字段
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
                        "expected_output": "该步骤的预期结果",
                        "depends_on": ["1.a", "2.b"]  # 新增：依赖的步骤ID列表，为空表示无依赖
                    }
                ]
            }
        ],
        "execution_order": ["1.a", "1.b", "2.a", "..."]  # 执行顺序列表
    }

    prompt = f"""
    请分析以下执行计划文本，并将其转换为结构化的JSON数据。
    你的任务是识别出所有模块、每个模块下的步骤，每个步骤的详细信息，以及步骤之间的依赖关系。

    执行计划文本:
    {plan_text}

    依赖关系说明:
    - 如果步骤B需要使用步骤A的输出结果，则步骤B的"depends_on"应包含步骤A的ID
    - 如果步骤不需要任何其他步骤的输出，则"depends_on"应为空列表
    - 依赖关系必须严格基于执行计划中的明确说明

    请严格按照以下JSON格式返回结果，不要添加任何额外解释：
    {json.dumps(expected_format, ensure_ascii=False, indent=2)}

    注意事项:
    1. 确保JSON格式正确，可被标准JSON解析器解析
    2. "uses_tool"字段应为布尔值(true/false)
    3. "tool"字段只包含工具名，不要带有例如"工具1"之类的额外说明，不要有任何额外说明，不要有任何额外说明
    4. "parameters"字段必须使用已有信息进行构造，不允许在没有相关信息时编造参数，例如不允许编造报告日期
    5. 如果步骤不使用工具，"tool"字段应为空字符串
    6. 如果没有参数，"parameters"应为空对象
    7. "execution_order"应包含所有步骤的完整标识符，如"1.a"、"1.b"等
    8. 保留所有原始信息，不要遗漏任何模块或步骤
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

                # 转换为我们需要的步骤格式，包含依赖关系
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
                            'expected_output': step.get('expected_output', ''),
                            'depends_on': step.get('depends_on', [])  # 新增：存储依赖的步骤ID
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

# 辅助函数：生成下载链接
def get_download_link(text, filename, text_description):
    """生成下载链接"""
    b64 = base64.b64encode(text.encode()).decode()
    href = f'<a href="data:text/markdown;base64,{b64}" download="{filename}">{text_description}</a>'
    return href