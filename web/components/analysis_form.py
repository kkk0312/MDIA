"""
分析表单组件
"""

import streamlit as st
import datetime

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')


def render_analysis_form():
    """渲染简化版股票分析表单（固定A股、基本面分析师、1级研究深度）"""

    st.subheader("📋 分析配置")

    # 获取缓存的表单配置（确保不为None）
    cached_config = st.session_state.get('form_config') or {}

    # 调试信息（只在没有分析运行时记录，避免重复）
    if not st.session_state.get('analysis_running', False):
        if cached_config:
            logger.info(f"📊 [配置恢复] 使用缓存配置: {cached_config}")
        else:
            logger.info("📊 [配置恢复] 使用默认配置")

    # 创建表单
    with st.form("analysis_form", clear_on_submit=False):

        # 在表单开始时保存当前配置（用于检测变化）
        initial_config = cached_config.copy() if cached_config else {}

        # 固定为A股市场，不允许用户选择
        market_type = "A股"
        st.info(f"市场类型: {market_type}")

        # A股股票代码输入
        cached_stock = cached_config.get('stock_symbol', '') if cached_config else ''
        stock_symbol = st.text_input(
            "股票代码 📈",
            value=cached_stock,
            placeholder="输入A股代码，如 000001, 600519，然后按回车确认",
            help="输入要分析的A股代码，如 000001(平安银行), 600519(贵州茅台)，输入完成后请按回车键确认",
            autocomplete="off"
        ).strip()

        logger.debug(f"🔍 [FORM DEBUG] A股text_input返回值: '{stock_symbol}'")

        # 分析日期
        analysis_date = st.date_input(
            "分析日期 📅",
            value=datetime.date.today(),
            help="选择分析的基准日期"
        )

        # 固定使用基本面分析师，不显示选择框
        st.info("分析师: 基本面分析师 (固定)")

        # 固定研究深度为1级快速分析，不显示选择器
        st.info("研究深度: 1级 - 快速分析 (固定)")

        # 高级选项
        with st.expander("🔧 高级选项"):
            include_sentiment = st.checkbox(
                "包含情绪分析",
                value=True,
                help="是否包含市场情绪和投资者情绪分析"
            )

            include_risk_assessment = st.checkbox(
                "包含风险评估",
                value=True,
                help="是否包含详细的风险因素评估"
            )

            custom_prompt = st.text_area(
                "自定义分析要求",
                placeholder="输入特定的分析要求或关注点...",
                help="可以输入特定的分析要求，AI会在分析中重点关注"
            )

        # 显示输入状态提示
        if not stock_symbol:
            st.info("💡 请在上方输入股票代码，输入完成后按回车键确认")
        else:
            st.success(f"✅ 已输入股票代码: {stock_symbol}")

        # 添加JavaScript来改善用户体验
        st.markdown("""
        <script>
        // 监听输入框的变化，提供更好的用户反馈
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input[type="text"]');
            inputs.forEach(input => {
                input.addEventListener('input', function() {
                    if (this.value.trim()) {
                        this.style.borderColor = '#00ff00';
                        this.title = '按回车键确认输入';
                    } else {
                        this.style.borderColor = '';
                        this.title = '';
                    }
                });
            });
        });
        </script>
        """, unsafe_allow_html=True)

        # 在提交按钮前检测配置变化并保存
        current_config = {
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'research_depth': 1,  # 固定为1级
            'selected_analysts': ['fundamentals'],  # 固定为基本面分析师
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }

        # 如果配置发生变化，立即保存（即使没有提交）
        if current_config != initial_config:
            st.session_state.form_config = current_config
            try:
                from utils.smart_session_manager import smart_session_manager
                current_analysis_id = st.session_state.get('current_analysis_id', 'form_config_only')
                smart_session_manager.save_analysis_state(
                    analysis_id=current_analysis_id,
                    status=st.session_state.get('analysis_running', False) and 'running' or 'idle',
                    stock_symbol=stock_symbol,
                    market_type=market_type,
                    form_config=current_config
                )
                logger.debug(f"📊 [配置自动保存] 表单配置已更新")
            except Exception as e:
                logger.warning(f"⚠️ [配置自动保存] 保存失败: {e}")

        # 提交按钮
        submitted = st.form_submit_button(
            "🚀 开始分析",
            type="primary",
            use_container_width=True
        )

    # 只有在提交时才返回数据
    if submitted and stock_symbol:  # 确保有股票代码才提交
        # 添加详细日志
        logger.debug(f"🔍 [FORM DEBUG] ===== 分析表单提交 =====")
        logger.debug(f"🔍 [FORM DEBUG] 用户输入的股票代码: '{stock_symbol}'")
        logger.debug(f"🔍 [FORM DEBUG] 市场类型: '{market_type}'")
        logger.debug(f"🔍 [FORM DEBUG] 分析日期: '{analysis_date}'")
        logger.debug(f"🔍 [FORM DEBUG] 选择的分析师: ['fundamentals']")
        logger.debug(f"🔍 [FORM DEBUG] 研究深度: 1")

        form_data = {
            'submitted': True,
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'analysis_date': str(analysis_date),
            'analysts': ['fundamentals'],  # 固定使用基本面分析师
            'research_depth': 1,  # 固定为1级快速分析
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }

        # 保存表单配置到缓存和持久化存储
        form_config = {
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'research_depth': 1,
            'selected_analysts': ['fundamentals'],
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }
        st.session_state.form_config = form_config

        # 保存到持久化存储
        try:
            from utils.smart_session_manager import smart_session_manager
            # 获取当前分析ID（如果有的话）
            current_analysis_id = st.session_state.get('current_analysis_id', 'form_config_only')
            smart_session_manager.save_analysis_state(
                analysis_id=current_analysis_id,
                status=st.session_state.get('analysis_running', False) and 'running' or 'idle',
                stock_symbol=stock_symbol,
                market_type=market_type,
                form_config=form_config
            )
        except Exception as e:
            logger.warning(f"⚠️ [配置持久化] 保存失败: {e}")

        logger.info(f"📊 [配置缓存] 表单配置已保存: {form_config}")

        logger.debug(f"🔍 [FORM DEBUG] 返回的表单数据: {form_data}")
        logger.debug(f"🔍 [FORM DEBUG] ===== 表单提交结束 =====")

        return form_data
    elif submitted and not stock_symbol:
        # 用户点击了提交但没有输入股票代码
        logger.error(f"🔍 [FORM DEBUG] 提交失败：股票代码为空")
        st.error("❌ 请输入股票代码后再提交")
        return {'submitted': False}
    else:
        return {'submitted': False}
