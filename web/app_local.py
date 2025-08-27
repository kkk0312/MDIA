import streamlit as st
import sys
from pathlib import Path
from dotenv import load_dotenv
import base64

# 导入自定义组件
from components.header import render_header
from utils.smart_session_manager import get_persistent_analysis_id

# 导入后端核心函数
from backend.analysis.core import analyze_document_with_multimodal, display_task_progress

# 导入多模态预处理函数
from backend.analysis.modal_process import convert_pdf_to_images, capture_screenshot

# 导入辅助函数
from backend.analysis.utils import get_download_link

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 引入日志模块
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('web')

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

# 设置页面配置
st.set_page_config(
    page_title="多模态文档洞察分析平台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

current_dir = Path(__file__).parent
logo_path = current_dir / "decoration.gif"
with open(logo_path, "rb") as image_file:
    decoration_path = base64.b64encode(image_file.read()).decode()

# 自定义CSS样式
st.markdown(f"""
<style>

    /* 隐藏Streamlit顶部工具栏和Deploy按钮 - 多种选择器确保兼容性 */
    .stAppToolbar {{
        display: none !important;
    }}

    header[data-testid="stHeader"] {{
        display: none !important;
    }}

    .stDeployButton {{
        display: none !important;
    }}

    /* 新版本Streamlit的Deploy按钮选择器 */
    [data-testid="stToolbar"] {{
        display: none !important;
    }}

    [data-testid="stDecoration"] {{
        display: none !important;
    }}

    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}

    /* 隐藏整个顶部区域 */
    .stApp > header {{
        display: none !important;
    }}

    .stApp > div[data-testid="stToolbar"] {{
        display: none !important;
    }}

    /* 隐藏主菜单按钮 */
    #MainMenu {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* 隐藏页脚 */
    footer {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* 隐藏"Made with Streamlit"标识 */
    .viewerBadge_container__1QSob {{
        display: none !important;
    }}

    /* 隐藏所有可能的工具栏元素 */
    div[data-testid="stToolbar"] {{
        display: none !important;
    }}

    /* 隐藏右上角的所有按钮 */
    .stApp > div > div > div > div > section > div {{
        padding-top: 0 !important;
    }}

    /* 应用样式 */
    .main-header {{
    background-image: url("data:image/gif;base64,{decoration_path}");
    background-size: cover;
    background-position: center;
    padding: 1rem;
    border-radius: 10px;
    margin-bottom: 2rem;
    color: white;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-top: -100px;
    padding-top: 0;
}}

    .metric-card {{
    /* 金属渐变背景（银灰→亮银→银灰） */
    background: linear-gradient(
        135deg,
        #e0e5ec 0%,
        #ffffff 40%,
        #d0d9e4 60%,
        #e0e5ec 100%
    );

    /* 让渐变更“拉丝” */
    background-size: 120% 120%;
    animation: metalShine 6s linear infinite;

    /* 内阴影营造厚度 */
    box-shadow:
        inset 1px 1px 2px rgba(255,255,255,0.7),   /* 高光 */
        inset -1px -1px 2px rgba(0,0,0,0.2);     /* 暗部 */

    padding: 1rem;
    border-radius: 10px;
    border-left: 4px solid #1f77b4;
    margin: 0.5rem 0;
}}

/* 缓慢移动渐变，制造光泽流动 */
@keyframes metalShine {{
    0%   {{ background-position: 0% 50%; }}
    50%  {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}

    .analysis-section {{
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }}

    .success-box {{
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }}

    .warning-box {{
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }}

    .error-box {{
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }}

    /* 图片、PDF和网页分析区域样式 */
    .document-analysis-container {{
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
    }}

    .document-preview {{
        max-width: 100%;
        border-radius: 5px;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}

    /* PDF页面导航样式 */
    .pdf-navigation {{
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 1rem 0;
        gap: 1rem;
    }}

    .pdf-page-indicator {{
        font-weight: bold;
        color: #1f77b4;
    }}

    /* 任务流程样式 */
    .task-step {{
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }}

    .task-step.active {{
        background: #e3f2fd;
        border-left-color: #2196f3;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }}

    .task-step.completed {{
        border-left-color: #4caf50;
    }}

    .task-step.failed {{
        border-left-color: #f44336;
    }}

    /* 执行计划样式优化 */
    .execution-plan-container {{
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
    }}

    .plan-module {{
        background-color: white;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}

    .plan-module-title {{
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #eee;
    }}

    .plan-step {{
        margin-left: 1rem;
        margin-bottom: 1rem;
        padding-left: 0.8rem;
        border-left: 2px solid #3498db;
    }}

    .plan-step-title {{
        font-weight: 500;
        color: #34495e;
        margin-bottom: 0.3rem;
    }}

    .plan-step-details {{
        font-size: 0.9rem;
        color: #7f8c8d;
        margin-bottom: 0.3rem;
    }}
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """初始化会话状态，添加多模态相关状态变量"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'last_analysis_time' not in st.session_state:
        st.session_state.last_analysis_time = None
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None
    if 'form_config' not in st.session_state:
        st.session_state.form_config = None

    # 多模态分析相关状态变量
    if 'image_analysis_report' not in st.session_state:
        st.session_state.image_analysis_report = ""
    if 'extracted_tickers' not in st.session_state:
        st.session_state.extracted_tickers = []
    if 'extracted_companies' not in st.session_state:
        st.session_state.extracted_companies = []
    if 'final_synthesis_report' not in st.session_state:
        st.session_state.final_synthesis_report = ""
    if 'selected_ticker_from_image' not in st.session_state:
        st.session_state.selected_ticker_from_image = None
    if 'image_analysis_completed' not in st.session_state:
        st.session_state.image_analysis_completed = False

    # 新增任务流程相关状态
    if 'task_progress' not in st.session_state:
        st.session_state.task_progress = {
            'stage': 'initial',  # initial, document_analysis, plan_generation, plan_execution, final_report
            'completed_stages': [],  # 新增：跟踪已完成的阶段
            'steps': [],
            'current_step': 0,
            'completed_steps': 0,
            'total_steps': 0,
            'execution_reports': []
        }
    if 'execution_plan' not in st.session_state:
        st.session_state.execution_plan = ""
    if 'module_analysis_reports' not in st.session_state:
        st.session_state.module_analysis_reports = {}

    # PDF分析相关状态变量
    if 'pdf_pages' not in st.session_state:
        st.session_state.pdf_pages = []  # 存储PDF转换的图片
    if 'current_pdf_page' not in st.session_state:
        st.session_state.current_pdf_page = 0  # 当前显示的PDF页码
    if 'pdf_analysis_reports' not in st.session_state:
        st.session_state.pdf_analysis_reports = []  # 存储每一页的分析报告
    if 'pdf_analysis_completed' not in st.session_state:
        st.session_state.pdf_analysis_completed = False  # PDF整体分析是否完成

    # 网页截图相关状态变量
    if 'web_screenshot' not in st.session_state:
        st.session_state.web_screenshot = None  # 存储网页截图
    if 'web_analysis_completed' not in st.session_state:
        st.session_state.web_analysis_completed = False  # 网页分析是否完成

    # 模型配置相关状态
    if 'llm_config' not in st.session_state:
        st.session_state.llm_config = {
            'llm_provider': 'dashscope',
            'llm_model': 'qwen-plus'
        }

    # 工具相关状态
    if 'tool_executor' not in st.session_state:
        st.session_state.tool_executor = None

    # 尝试从最新完成的分析中恢复结果
    if not st.session_state.analysis_results:
        try:
            from utils.async_progress_tracker import get_latest_analysis_id, get_progress_by_id
            from utils.analysis_runner import format_analysis_results

            latest_id = get_latest_analysis_id()
            if latest_id:
                progress_data = get_progress_by_id(latest_id)
                if (progress_data and
                        progress_data.get('status') == 'completed' and
                        'raw_results' in progress_data):

                    # 恢复分析结果
                    raw_results = progress_data['raw_results']
                    formatted_results = format_analysis_results(raw_results)

                    if formatted_results:
                        st.session_state.analysis_results = formatted_results
                        st.session_state.current_analysis_id = latest_id
                        # 检查分析状态
                        analysis_status = progress_data.get('status', 'completed')
                        st.session_state.analysis_running = (analysis_status == 'running')
                        # 恢复股票信息
                        if 'stock_symbol' in raw_results:
                            st.session_state.last_stock_symbol = raw_results.get('stock_symbol', '')
                        if 'market_type' in raw_results:
                            st.session_state.last_market_type = raw_results.get('market_type', '')
                        logger.info(f"📊 [结果恢复] 从分析 {latest_id} 恢复结果，状态: {analysis_status}")

        except Exception as e:
            logger.warning(f"⚠️ [结果恢复] 恢复失败: {e}")

    # 使用cookie管理器恢复分析ID（优先级：session state > cookie > Redis/文件）
    try:
        persistent_analysis_id = get_persistent_analysis_id()
        if persistent_analysis_id:
            # 使用线程检测来检查分析状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(persistent_analysis_id)

            # 只在状态变化时记录日志，避免重复
            current_session_status = st.session_state.get('last_logged_status')
            if current_session_status != actual_status:
                logger.info(f"📊 [状态检查] 分析 {persistent_analysis_id} 实际状态: {actual_status}")
                st.session_state.last_logged_status = actual_status

            if actual_status == 'running':
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = persistent_analysis_id
            elif actual_status in ['completed', 'failed']:
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = persistent_analysis_id
            else:  # not_found
                logger.warning(f"📊 [状态检查] 分析 {persistent_analysis_id} 未找到，清理状态")
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = None
    except Exception as e:
        # 如果恢复失败，保持默认值
        logger.warning(f"⚠️ [状态恢复] 恢复分析状态失败: {e}")
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None

    # 恢复表单配置
    try:
        from utils.smart_session_manager import smart_session_manager
        session_data = smart_session_manager.load_analysis_state()

        if session_data and 'form_config' in session_data:
            st.session_state.form_config = session_data['form_config']
            # 只在没有分析运行时记录日志，避免重复
            if not st.session_state.get('analysis_running', False):
                logger.info("📊 [配置恢复] 表单配置已恢复")
    except Exception as e:
        logger.warning(f"⚠️ [配置恢复] 表单配置恢复失败: {e}")
    if 'initial' not in st.session_state.task_progress['completed_stages']:
        st.session_state.task_progress['completed_stages'].append('initial')


def main():
    """主应用程序"""
    import datetime
    import base64
    from PIL import Image
    import streamlit as st

    from backend.analysis.core import MULTIMODAL_MODEL

    # 初始化会话状态
    initialize_session_state()

    # 自定义CSS - 调整侧边栏宽度
    st.markdown("""
    <style>
    /* 调整侧边栏宽度为260px，避免标题挤压 */
    section[data-testid="stSidebar"] {
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
    }

    /* 隐藏侧边栏的隐藏按钮 - 更全面的选择器 */
    button[kind="header"],
    button[data-testid="collapsedControl"],
    .css-1d391kg,
    .css-1rs6os,
    .css-17eq0hr,
    .css-1lcbmhc,
    .css-1y4p8pa,
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"],
    [data-testid="collapsedControl"],
    .stSidebar button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* 其他CSS样式保持不变... */
    section[data-testid="stSidebar"] > div:first-child > button[kind="header"],
    section[data-testid="stSidebar"] > div:first-child > div > button[kind="header"],
    section[data-testid="stSidebar"] .css-1lcbmhc > button[kind="header"],
    section[data-testid="stSidebar"] .css-1y4p8pa > button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    .main .block-container,
    section.main .block-container,
    div.main .block-container,
    .stApp .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
        max-width: none !important;
        width: calc(100% - 16px) !important;
    }

    .stApp > div {
        overflow-x: auto !important;
    }

    .element-container {
        margin-right: 8px !important;
    }

    .sidebar .sidebar-content {
        padding: 0.5rem 0.3rem !important;
    }

    section[data-testid="stSidebar"] .element-container {
        margin-bottom: 0.5rem !important;
    }

    section[data-testid="stSidebar"] hr {
        margin: 0.8rem 0 !important;
    }

    section[data-testid="stSidebar"] h1 {
        font-size: 1.2rem !important;
        line-height: 1.3 !important;
        margin-bottom: 1rem !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    section[data-testid="stSidebar"] .stSelectbox > div > div {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }

    section[data-testid="stSidebar"] .stSelectbox > div > div {
        min-width: 220px !important;
        width: 100% !important;
    }

    .main {
        padding-right: 8px !important;
    }

    .stApp {
        margin-right: 0 !important;
        padding-right: 8px !important;
    }

    .streamlit-expanderContent {
        padding-right: 8px !important;
        margin-right: 8px !important;
    }

    .main .block-container {
        overflow-x: visible !important;
    }

    .stApp,
    .stApp > div,
    .stApp > div > div,
    .main,
    .main > div,
    .main > div > div,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewContainer"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    div[data-testid="column"],
    .css-1d391kg,
    .css-1r6slb0,
    .css-12oz5g7,
    .css-1lcbmhc {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    .main .block-container {
        width: calc(100vw - 276px) !important;
        max-width: calc(100vw - 276px) !important;
    }

    div[data-testid="column"]:last-child {
        background-color: #f8f9fa !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin-left: 8px !important;
        border: 1px solid #e9ecef !important;
    }

    div[data-testid="column"]:last-child .streamlit-expanderHeader {
        background-color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #dee2e6 !important;
        font-weight: 500 !important;
    }

    div[data-testid="column"]:last-child .stMarkdown {
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }

    div[data-testid="column"]:last-child h1 {
        font-size: 1.3rem !important;
        color: #495057 !important;
        margin-bottom: 1rem !important;
    }
    </style>

    <script>
    // JavaScript来强制隐藏侧边栏按钮
    function hideSidebarButtons() {
        const selectors = [
            'button[kind="header"]',
            'button[data-testid="collapsedControl"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            '[data-testid="collapsedControl"]',
            '.css-1d391kg',
            '.css-1rs6os',
            '.css-17eq0hr',
            '.css-1lcbmhc button',
            '.css-1y4p8pa button'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
            });
        });
    }

    document.addEventListener('DOMContentLoaded', hideSidebarButtons);
    setInterval(hideSidebarButtons, 1000);

    function forceOptimalPadding() {
        const selectors = [
            '.main .block-container',
            '.stApp',
            '.stApp > div',
            '.main',
            '.main > div',
            'div[data-testid="stAppViewContainer"]',
            'section[data-testid="stMain"]',
            'div[data-testid="column"]'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.paddingLeft = '8px';
                el.style.paddingRight = '8px';
                el.style.marginLeft = '0px';
                el.style.marginRight = '0px';
            });
        });

        const mainContainer = document.querySelector('.main .block-container');
        if (mainContainer) {
            mainContainer.style.width = 'calc(100vw - 276px)';
            mainContainer.style.maxWidth = 'calc(100vw - 276px)';
        }
    }

    document.addEventListener('DOMContentLoaded', forceOptimalPadding);
    setInterval(forceOptimalPadding, 500);
    </script>
    """, unsafe_allow_html=True)

    # 渲染页面头部
    render_header()

    # 页面导航 - 保留logo和标题
    current_dir = Path(__file__).parent
    logo_path = current_dir / "logo.gif"
    with open(logo_path, "rb") as f:
        contents = f.read()
    data_url = base64.b64encode(contents).decode("utf-8")
    st.sidebar.markdown(
        f'<img src="data:image/gif;base64,{data_url}" width="150" style="display: block; margin: 0 auto;">',
        unsafe_allow_html=True,
    )
    st.sidebar.title("💡 多模态文档洞察分析")
    st.sidebar.markdown("---")

    # 初始化历史记录会话状态
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    if 'current_analysis' not in st.session_state:
        st.session_state.current_analysis = None
    if 'analysis_counter' not in st.session_state:
        st.session_state.analysis_counter = 0

    # 生成唯一分析ID
    def generate_analysis_id():
        st.session_state.analysis_counter += 1
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"analysis_{timestamp}_{st.session_state.analysis_counter}"

    # 上方：开启新分析
    st.sidebar.subheader("📝 分析管理")
    if st.sidebar.button("🚀 开启新分析", use_container_width=True):
        # 生成新分析ID
        analysis_id = generate_analysis_id()

        # 创建新分析记录
        new_analysis = {
            "id": analysis_id,
            "title": f"分析 #{st.session_state.analysis_counter}",
            "status": "进行中",
            "start_time": datetime.datetime.now(),
            "end_time": None,
            "type": None,  # 图片/PDF/网页
            "file_name": None,
            "url": None,
            "results": None
        }

        # 保存当前分析并添加到历史记录
        st.session_state.current_analysis = new_analysis
        st.session_state.analysis_history.append(new_analysis)

        # 重置分析相关状态
        st.session_state.image_analysis_completed = False
        st.session_state.pdf_analysis_completed = False
        st.session_state.web_analysis_completed = False
        st.session_state.image_analysis_report = ""
        st.session_state.extracted_tickers = []
        st.session_state.extracted_companies = []
        st.session_state.pdf_pages = []
        st.session_state.current_pdf_page = 0
        st.session_state.pdf_analysis_reports = []
        st.session_state.web_screenshot = None
        st.session_state.final_synthesis_report = ""

        # 重置任务进度
        st.session_state.task_progress = {
            'stage': 'initial',
            'completed_stages': ['initial'],
            'steps': [],
            'current_step': 0,
            'completed_steps': 0,
            'total_steps': 0,
            'execution_reports': []
        }

        st.session_state.execution_plan = ""
        st.rerun()

    # 下方：历史分析记录
    st.sidebar.markdown("---")
    st.sidebar.subheader("📜 历史分析记录")

    # 显示空状态提示
    if not st.session_state.analysis_history:
        st.sidebar.info("暂无历史分析记录，点击上方按钮开始新分析")
    else:
        # 按时间倒序显示历史记录
        for analysis in reversed(st.session_state.analysis_history):
            with st.sidebar.expander(
                    f"{analysis['title']} "
                    f"[{analysis['status']}] "
                    f"{analysis['start_time'].strftime('%m-%d %H:%M')}",
                    expanded=False
            ):
                # 显示分析基本信息
                st.markdown(f"**开始时间:** {analysis['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")

                if analysis['end_time']:
                    st.markdown(f"**结束时间:** {analysis['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")

                if analysis['type'] == 'file':
                    st.markdown(f"**分析文件:** {analysis['file_name']}")
                elif analysis['type'] == 'web':
                    st.markdown(f"**分析网页:** {analysis['url']}")

                # 操作按钮
                col_view, col_rename, col_delete = st.columns(3)

                with col_view:
                    if st.button("查看", key=f"view_{analysis['id']}", use_container_width=True):
                        # 加载选中的历史分析
                        st.session_state.current_analysis = analysis
                        st.rerun()

                with col_rename:
                    if st.button("重命名", key=f"rename_{analysis['id']}", use_container_width=True):
                        new_title = st.text_input(
                            "输入新标题",
                            value=analysis['title'],
                            key=f"rename_input_{analysis['id']}"
                        )
                        if new_title and new_title != analysis['title']:
                            analysis['title'] = new_title
                            st.success("标题已更新")
                            st.rerun()

                with col_delete:
                    if st.button("删除", key=f"delete_{analysis['id']}", use_container_width=True):
                        # 从历史记录中移除
                        st.session_state.analysis_history = [
                            a for a in st.session_state.analysis_history
                            if a['id'] != analysis['id']
                        ]
                        # 如果删除的是当前分析，重置当前分析
                        if (st.session_state.current_analysis and
                                st.session_state.current_analysis['id'] == analysis['id']):
                            st.session_state.current_analysis = None
                        st.success("记录已删除")
                        st.rerun()

    # 检查是否有当前活跃的分析
    if not st.session_state.current_analysis:
        st.info("请从左侧边栏点击「开启新分析」按钮开始一个新的分析任务，或选择历史分析记录查看详情。")
        return

    # 主内容区域 - 固定分为两列，右侧始终显示使用指南
    col1, col2 = st.columns([2, 1])  # 2:1比例，使用指南占三分之一

    with col1:
        # 显示当前分析标题
        st.header(f"当前分析: {st.session_state.current_analysis['title']}")

        # 多模态文档分析区域（支持图片、PDF和网页截图）
        st.subheader("🖼️ 文档分析 (多模态)")
        with st.container():
            # 网页分析部分
            st.subheader("🌐 网页分析")
            url_input = st.text_input(
                "输入网页URL",
                placeholder="例如: https://finance.yahoo.com/quote/AAPL",
                help="输入包含股票信息的网页URL，系统将自动截取完整网页并分析"
            )

            col_url1, col_url2 = st.columns(2)
            with col_url1:
                if st.button("📸 截取网页截图", disabled=not url_input):
                    # 更新当前分析信息
                    st.session_state.current_analysis['type'] = 'web'
                    st.session_state.current_analysis['url'] = url_input
                    st.session_state.current_analysis['status'] = "处理中"

                    # 重置相关状态
                    st.session_state.web_screenshot = None
                    st.session_state.web_analysis_completed = False
                    st.session_state.image_analysis_completed = False
                    st.session_state.pdf_analysis_completed = False
                    st.session_state.image_analysis_report = ""
                    st.session_state.extracted_tickers = []
                    st.session_state.extracted_companies = []
                    # 重置任务进度
                    st.session_state.task_progress = {
                        'stage': 'initial',
                        'completed_stages': ['initial'],  # 保留初始化阶段
                        'steps': [],
                        'current_step': 0,
                        'completed_steps': 0,
                        'total_steps': 0,
                        'execution_reports': []
                    }

                    # 截取网页截图
                    screenshot = capture_screenshot(url_input)
                    if screenshot:
                        st.session_state.web_screenshot = screenshot

                        extracted_info = analyze_document_with_multimodal(
                            document=screenshot,
                            doc_type="web"
                        )

                        # 更新分析状态
                        if st.session_state.web_analysis_completed:
                            st.session_state.current_analysis['status'] = "已完成"
                            st.session_state.current_analysis['end_time'] = datetime.datetime.now()
                            st.session_state.current_analysis['results'] = {
                                'type': 'web',
                                'has_report': bool(st.session_state.image_analysis_report)
                            }

            with col_url2:
                if st.button("🔄 重新分析网页", disabled=not st.session_state.web_screenshot):
                    # 更新当前分析状态
                    st.session_state.current_analysis['status'] = "处理中"

                    # 重置任务进度
                    st.session_state.task_progress = {
                        'stage': 'initial',
                        'completed_stages': ['initial'],  # 保留初始化阶段
                        'steps': [],
                        'current_step': 0,
                        'completed_steps': 0,
                        'total_steps': 0,
                        'execution_reports': []
                    }

                    # 重新分析已有的网页截图
                    extracted_info = analyze_document_with_multimodal(
                        document=st.session_state.web_screenshot,
                        doc_type="web"
                    )

                    # 更新分析状态
                    if st.session_state.web_analysis_completed:
                        st.session_state.current_analysis['status'] = "已完成"
                        st.session_state.current_analysis['end_time'] = datetime.datetime.now()

            # 显示已有的网页截图
            if st.session_state.web_screenshot and not st.session_state.web_analysis_completed:
                st.image(
                    st.session_state.web_screenshot,
                    caption="网页截图预览",
                    use_container_width=True
                )
                if st.button("📊 分析网页截图", key="analyze_web_screenshot"):
                    # 更新当前分析状态
                    st.session_state.current_analysis['status'] = "处理中"

                    # 重置任务进度
                    st.session_state.task_progress = {
                        'stage': 'initial',
                        'completed_stages': ['initial'],  # 保留初始化阶段
                        'steps': [],
                        'current_step': 0,
                        'completed_steps': 0,
                        'total_steps': 0,
                        'execution_reports': []
                    }

                    extracted_info = analyze_document_with_multimodal(
                        document=st.session_state.web_screenshot,
                        doc_type="web"
                    )

                    # 更新分析状态
                    if st.session_state.web_analysis_completed:
                        st.session_state.current_analysis['status'] = "已完成"
                        st.session_state.current_analysis['end_time'] = datetime.datetime.now()

            # 文件上传部分
            st.subheader("📂 文件上传 (图片/PDF)")
            uploaded_file = st.file_uploader(
                "上传包含股票信息的文档（图片或PDF格式）",
                type=["jpg", "jpeg", "png", "pdf"]
            )

            # 处理上传的文档
            if uploaded_file is not None:
                # 更新当前分析信息
                st.session_state.current_analysis['type'] = 'file'
                st.session_state.current_analysis['file_name'] = uploaded_file.name
                st.session_state.current_analysis['status'] = "处理中"

                # 检查文件类型
                file_extension = uploaded_file.name.split('.')[-1].lower()

                # 重置相关状态（如果上传了新文件）
                if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
                    st.session_state.last_uploaded_file = uploaded_file.name
                    st.session_state.image_analysis_completed = False
                    st.session_state.pdf_analysis_completed = False
                    st.session_state.web_analysis_completed = False
                    st.session_state.image_analysis_report = ""
                    st.session_state.extracted_tickers = []
                    st.session_state.extracted_companies = []
                    st.session_state.pdf_pages = []
                    st.session_state.current_pdf_page = 0
                    st.session_state.pdf_analysis_reports = []
                    st.session_state.web_screenshot = None
                    st.session_state.tool_executor = None
                    # 重置任务进度
                    st.session_state.task_progress = {
                        'stage': 'initial',
                        'completed_stages': ['initial'],  # 保留初始化阶段
                        'steps': [],
                        'current_step': 0,
                        'completed_steps': 0,
                        'total_steps': 0,
                        'execution_reports': []
                    }

                # 处理PDF文件
                if file_extension == 'pdf' and not st.session_state.pdf_analysis_completed:
                    # 转换PDF为图片
                    if not st.session_state.pdf_pages:
                        pdf_pages = convert_pdf_to_images(uploaded_file)
                        st.session_state.pdf_pages = pdf_pages

                    # 如果转换成功，进行分析
                    if st.session_state.pdf_pages and not st.session_state.pdf_analysis_completed:
                        extracted_info = analyze_document_with_multimodal(
                            document=st.session_state.pdf_pages,
                            doc_type="pdf"
                        )

                        # 更新分析状态
                        if st.session_state.pdf_analysis_completed:
                            st.session_state.current_analysis['status'] = "已完成"
                            st.session_state.current_analysis['end_time'] = datetime.datetime.now()
                            st.session_state.current_analysis['results'] = {
                                'type': 'pdf',
                                'page_count': len(st.session_state.pdf_pages),
                                'has_report': bool(st.session_state.image_analysis_report)
                            }

                # 处理图片文件
                elif file_extension in ['jpg', 'jpeg', 'png'] and not st.session_state.image_analysis_completed:
                    try:
                        image = Image.open(uploaded_file)
                        # 使用指定的多模态模型分析图片
                        extracted_info = analyze_document_with_multimodal(
                            document=image,
                            doc_type="image"
                        )

                        # 更新分析状态
                        if st.session_state.image_analysis_completed:
                            st.session_state.current_analysis['status'] = "已完成"
                            st.session_state.current_analysis['end_time'] = datetime.datetime.now()
                            st.session_state.current_analysis['results'] = {
                                'type': 'image',
                                'has_report': bool(st.session_state.image_analysis_report)
                            }
                    except Exception as e:
                        st.error(f"图片处理错误: {str(e)}")
                        logger.error(f"图片处理错误: {str(e)}")
                        # 更新分析状态为失败
                        st.session_state.current_analysis['status'] = "失败"

            # 显示文档分析结果（如果已完成）
            if st.session_state.image_analysis_completed or st.session_state.pdf_analysis_completed or st.session_state.web_analysis_completed:
                # 显示PDF预览和导航（如果是PDF文件）
                if st.session_state.pdf_analysis_completed and st.session_state.pdf_pages:
                    total_pages = len(st.session_state.pdf_pages)

                    st.markdown("### PDF预览与导航")

                    # 页面导航控制
                    col_prev, col_page, col_next = st.columns([1, 2, 1])

                    with col_prev:
                        if st.button("上一页", disabled=st.session_state.current_pdf_page == 0):
                            st.session_state.current_pdf_page -= 1

                    with col_page:
                        st.markdown(f"**第 {st.session_state.current_pdf_page + 1}/{total_pages} 页**")

                    with col_next:
                        if st.button("下一页", disabled=st.session_state.current_pdf_page == total_pages - 1):
                            st.session_state.current_pdf_page += 1

                    # 显示当前页
                    current_page = st.session_state.pdf_pages[st.session_state.current_pdf_page]
                    st.image(
                        current_page['image'],
                        caption=f"PDF第 {current_page['page_number']} 页",
                        use_container_width=True
                    )

                # 显示网页截图（如果是网页分析）
                if st.session_state.web_analysis_completed and st.session_state.web_screenshot:
                    st.markdown("### 网页截图")
                    with st.expander("查看完整网页截图", expanded=False):
                        st.image(
                            st.session_state.web_screenshot,
                            caption="分析的网页截图",
                            use_container_width=True
                        )

                # 显示文档分析报告
                if st.session_state.image_analysis_report:
                    st.markdown("### 文档分析报告")
                    with st.expander("查看完整文档分析报告", expanded=False):
                        st.markdown(st.session_state.image_analysis_report)

            # 显示使用的模型信息
            st.info(f"使用的多模态模型: {MULTIMODAL_MODEL}")

        st.markdown("---")

        # 显示任务流程进度
        display_task_progress()

    # 右侧始终渲染使用指南，不再受按钮控制
    with col2:
        st.markdown("### ℹ️ 使用指南")

        # 快速开始指南
        with st.expander("🎯 快速开始", expanded=True):
            st.markdown("""
            ### 📋 操作步骤
            1. 上传文档（图片/PDF）或输入网页URL
            2. 系统将自动分析文档内容
            3. 查看生成的执行计划
            4. 执行分析计划，系统将自动调用必要的工具
            5. 查看最终综合报告
            """)

        # 分析流程说明
        with st.expander("🔄 分析流程详解", expanded=False):
            st.markdown("""
            ### 🔍 四阶段分析流程
            1. **文档解析**：系统分析上传的文档内容，提取关键信息
            2. **生成执行计划**：根据文档内容创建详细的分析步骤和工具调用计划
            3. **执行计划**：按步骤执行分析，自动调用股票分析等工具
            4. **生成最终报告**：整合所有分析结果，生成专业的综合报告
            """)

        # 执行计划分析报告
        with st.expander("🛠️ 执行计划分析报告", expanded=False):
            execution_reports = st.session_state.task_progress.get('execution_reports', [])

            if not execution_reports:
                st.info("尚未执行任何分析步骤，完成执行计划后将显示各步骤报告")
            else:
                st.markdown(f"共 {len(execution_reports)} 个步骤，点击展开查看详情：")
                for report in execution_reports:
                    status = "✅" if report['status'] == 'completed' else "❌"
                    with st.expander(f"{status} 步骤 {report['step']} [{report['module']}]: {report['name']}",
                                     expanded=False):
                        st.markdown(report['report'])

        # 报告下载
        with st.expander("❓ 报告下载", expanded=False):
            # 检查是否有可下载的报告
            has_reports = (
                    st.session_state.image_analysis_report or
                    st.session_state.execution_plan or
                    st.session_state.execution_plan or
                    st.session_state.task_progress.get('execution_reports') or
                    st.session_state.final_synthesis_report
            )

            if not has_reports:
                st.info("尚未生成任何报告，完成分析流程后可下载报告")
            else:
                # 生成时间戳用于文件名
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

                # 文档分析报告下载
                if st.session_state.image_analysis_report:
                    doc_report_text = f"# 文档分析报告\n\n{st.session_state.image_analysis_report}"
                    st.markdown(
                        get_download_link(
                            doc_report_text,
                            f"document_analysis_report_{timestamp}.md",
                            "📄 下载文档分析报告"
                        ),
                        unsafe_allow_html=True
                    )

                # 执行计划下载
                if st.session_state.execution_plan:
                    plan_text = f"# 执行计划\n\n{st.session_state.execution_plan}"
                    st.markdown(
                        get_download_link(
                            plan_text,
                            f"execution_plan_{timestamp}.md",
                            "📋 下载执行计划"
                        ),
                        unsafe_allow_html=True
                    )

                # 执行步骤报告下载
                execution_reports = st.session_state.task_progress.get('execution_reports', [])
                if execution_reports:
                    steps_report = "# 执行步骤报告\n\n"
                    for report in execution_reports:
                        steps_report += f"## 步骤 {report['step']} [{report['module']}]: {report['name']}\n\n{report['report']}\n\n"

                    st.markdown(
                        get_download_link(
                            steps_report,
                            f"execution_steps_report_{timestamp}.md",
                            "📝 下载执行步骤报告"
                        ),
                        unsafe_allow_html=True
                    )

                # 最终综合报告下载
                if st.session_state.final_synthesis_report:
                    final_report_text = f"# 最终综合报告\n\n{st.session_state.final_synthesis_report}"
                    st.markdown(
                        get_download_link(
                            final_report_text,
                            f"final_synthesis_report_{timestamp}.md",
                            "📊 下载最终综合报告"
                        ),
                        unsafe_allow_html=True
                    )

                # 完整报告包下载
                full_report = "# 完整分析报告包\n\n"
                full_report += "## 1. 文档分析报告\n\n"
                full_report += f"{st.session_state.image_analysis_report or '无文档分析报告'}\n\n"
                full_report += "## 2. 执行计划\n\n"
                full_report += f"{st.session_state.execution_plan or '无执行计划'}\n\n"
                full_report += "## 3. 执行步骤报告\n\n"
                for report in execution_reports:
                    full_report += f"### 步骤 {report['step']} [{report['module']}]: {report['name']}\n\n{report['report']}\n\n"
                full_report += "## 4. 最终综合报告\n\n"
                full_report += f"{st.session_state.final_synthesis_report or '无最终综合报告'}\n\n"

                st.markdown(
                    get_download_link(
                        full_report,
                        f"full_analysis_report_{timestamp}.md",
                        "📦 下载完整报告包（包含所有报告）"
                    ),
                    unsafe_allow_html=True
                )

        # 风险提示
        st.warning("""
        ⚠️ **警告**

        - 本系统提供的分析结果仅供参考，不构成任何投资建议
        - AI分析存在局限性，据此操作造成的任何损失，本系统不承担责任
        """)

    # 显示系统状态
    if st.session_state.last_analysis_time:
        st.info(f"🕒 上次分析时间: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()