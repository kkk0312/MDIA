from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import os
from dotenv import load_dotenv  # 新增：加载环境变量（确保已安装python-dotenv）

# 加载环境变量（读取VOLCES_API_KEY，需在.env文件中配置）
load_dotenv()

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('volces_ark')


# 创建火山方舟专用配置（复制默认配置后覆盖关键参数）
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "volces"  # 指定火山方舟为LLM提供商（需与trading_graph.py中的判断一致）
config["backend_url"] = "https://ark.cn-beijing.volces.com/api/v3/"  # 火山方舟API地址
config["deep_think_llm"] = "你的火山方舟深度模型名称"  # 替换为实际部署的深度模型名
config["quick_think_llm"] = "你的火山方舟轻量模型名称"  # 替换为实际部署的轻量模型名
config["max_debate_rounds"] = 1  # 保持不变
config["online_tools"] = True  # 保持不变

# 初始化火山方舟版本的TradingAgentsGraph
ta = TradingAgentsGraph(debug=True, config=config)

# 执行分析（以NVDA 2024-05-10为例）
_, decision = ta.propagate("NVDA", "2024-05-10")
print("分析决策结果:", decision)
