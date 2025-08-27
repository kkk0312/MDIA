import streamlit as st
import time

from PIL import Image
import io

# PDF处理相关库
from pdf2image import convert_from_bytes

# 网页截图相关库
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def convert_pdf_to_images(pdf_file):
    """将PDF文件转换为图片列表"""
    try:
        # 使用pdf2image将PDF转换为图片
        with st.spinner("正在将PDF转换为图片..."):
            # 转换PDF的每一页为图片
            pages = convert_from_bytes(pdf_file.read(), 300)  # 300 DPI保证清晰度

            # 存储图片的字节流
            image_list = []
            for i, page in enumerate(pages):
                # 将PIL图像转换为字节流
                img_byte_arr = io.BytesIO()
                page.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()

                # 存储图片和页码信息
                image_list.append({
                    'image': page,
                    'bytes': img_byte_arr,
                    'page_number': i + 1
                })

                # 显示进度
                progress = (i + 1) / len(pages)
                st.progress(progress, text=f"转换第 {i + 1}/{len(pages)} 页")

            st.success(f"PDF转换完成，共 {len(image_list)} 页")
            return image_list
    except Exception as e:
        st.error(f"PDF转换失败: {str(e)}")
        return []


def capture_screenshot(url):
    """使用Selenium捕获完整网页截图"""
    try:
        # 配置Chrome浏览器选项
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # 无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # 禁用自动化控制特征，避免被网站检测
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # 初始化WebDriver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # 执行JavaScript以隐藏自动化控制特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        # 打开目标URL
        with st.spinner(f"正在加载网页: {url}"):
            driver.get(url)

            # 等待页面加载完成
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 等待额外时间确保JavaScript渲染完成
            time.sleep(3)

        # 获取页面总高度和视口高度
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")

        st.info(f"网页高度: {total_height}px，正在截取完整网页...")

        # 计算需要滚动的次数
        num_scrolls = (total_height + viewport_height - 1) // viewport_height
        screenshots = []

        # 截取每个视口的截图
        for i in range(num_scrolls):
            # 滚动到当前位置
            scroll_position = i * viewport_height
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            time.sleep(1)  # 等待页面稳定

            # 截取当前视口
            screenshot = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))
            screenshots.append(img)

            # 显示进度
            progress = (i + 1) / num_scrolls
            st.progress(progress, text=f"截取网页部分 {i + 1}/{num_scrolls}")

        # 关闭浏览器
        driver.quit()

        # 拼接所有截图
        if not screenshots:
            st.error("未能捕获到网页截图")
            return None

        # 创建完整截图的画布
        full_image = Image.new('RGB', (screenshots[0].width, total_height))

        # 拼接各个部分
        y_offset = 0
        for img in screenshots:
            full_image.paste(img, (0, y_offset))
            y_offset += img.height

            # 防止超出总高度
            if y_offset > total_height:
                break

        # 裁剪到精确的总高度
        full_image = full_image.crop((0, 0, full_image.width, total_height))

        st.success("网页截图已完成")
        return full_image

    except Exception as e:
        st.error(f"网页截图失败: {str(e)}")
        return None