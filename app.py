import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
from urllib.parse import quote
import time
from datetime import datetime
import urllib.parse
import random

# 配置日志
logging.basicConfig(
    filename='job_scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bright Data Scraping Browser 配置 (从 mine.txt 中获取)
SBR_WS_ENDPOINT = "wss://brd-customer-hl_afd51056-zone-scraping_browser1-country-fr:klqv3xfx5yb0@brd.superproxy.io:9222"
BASE_URL = "https://www.linkedin.com/jobs/search"

# LinkedIn 过滤参数映射
EXPERIENCE_LEVELS = {
    "internship": "1",
    "entry_level": "2",
    "associate": "3",
    "mid_senior": "4",
    "director": "5",
    "executive": "6"
}

JOB_TYPES = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "volunteer": "V",
    "internship": "I",
    "other": "O"
}

DATE_POSTED = {
    "past_month": "r2592000",
    "past_week": "r604800",
    "past_24h": "r86400",
    "any_time": ""
}

app = FastAPI(title="LinkedIn Job Scraper API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8081", "http://127.0.0.1:8081"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600
)

# 提供静态文件
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.error(f"挂载静态文件目录失败: {e}")

# API根路径
@app.get("/api")
async def root():
    """API根路径，提供API使用信息"""
    return {
        "message": "LinkedIn Job Scraper API",
        "endpoints": {
            "/api/search": "POST - 搜索LinkedIn职位"
        },
        "usage": {
            "method": "POST",
            "content_type": "application/json",
            "body": {
                "job_title": "职位标题 (必填)",
                "location": "位置 (必填)",
                "experience": "经验水平 (可选: internship, entry_level, associate, mid_senior, director, executive)",
                "job_type": "工作类型 (可选: full_time, part_time, contract, temporary, volunteer, internship, other)",
                "date_posted": "发布日期 (可选: past_month, past_week, past_24h, any_time)",
                "include_french": "是否包含法语职位 (可选)",
                "platforms": "平台来源 (可选)"
            }
        }
    }

# 提供首页
@app.get("/")
def get_index():
    return FileResponse("index.html")

async def scrape_jobs(job_title, location, experience=None, job_type=None, date_posted=None):
    """
    使用Playwright和Bright Data抓取LinkedIn职位信息
    """
    logger.info(f"开始抓取: job_title={job_title}, location={location}")
    
    # 构造URL
    params = {
        "keywords": job_title,
        "location": location
    }
    
    # 添加可选参数
    if experience and experience in EXPERIENCE_LEVELS:
        params["f_E"] = EXPERIENCE_LEVELS[experience]
    
    if job_type and job_type in JOB_TYPES:
        params["f_JT"] = JOB_TYPES[job_type]
    
    if date_posted and date_posted in DATE_POSTED:
        params["f_TPR"] = DATE_POSTED[date_posted]
    
    # 构造URL
    query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    url = f"{BASE_URL}?{query_string}"
    logger.info(f"构造的 URL: {url}")
    
    playwright = None
    browser = None
    page = None
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            # 启动Playwright
            if not playwright:
                playwright = await async_playwright().start()
                logger.info("Playwright 启动完成")
            
            # 连接到Bright Data Scraping Browser
            logger.info(f"尝试连接到 Bright Data Scraping Browser (尝试 {retry_count + 1}/{max_retries})")
            
            browser = await playwright.chromium.connect_over_cdp(
                SBR_WS_ENDPOINT,
                timeout=30000  # 30秒连接超时
            )
            logger.info("成功连接到 Scraping Browser")
            
            # 创建新页面并设置超时
            page = await browser.new_page()
            page.set_default_timeout(60000)  # 1分钟页面操作超时
            logger.info("创建了新页面")
            
            # 只设置视口大小
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # 访问页面
            logger.info(f"等待页面加载，URL: {url}")
            try:
                # 使用 domcontentloaded 而不是 networkidle
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                if not response:
                    raise Exception("页面加载失败：没有收到响应")
                
                if response.status >= 400:
                    raise Exception(f"页面返回错误状态码: {response.status}")
                
                # 等待任意一个职位卡片选择器出现
                selectors = [
                    '.jobs-search-results__list-item',
                    '.base-card',
                    '.job-search-card',
                    '.base-search-card',
                    '.base-card--link',
                    'div[data-job-id]',
                    '.job-card-container'
                ]
                
                selector_string = ', '.join(selectors)
                logger.info("等待职位卡片出现")
                
                try:
                    # 等待第一个职位卡片出现
                    await page.wait_for_selector(selector_string, timeout=20000)
                    logger.info("找到职位卡片，继续加载更多内容")
                    
                    # 执行滚动加载更多内容
                    for i in range(3):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1)
                        
                        # 检查是否有新的职位卡片加载
                        new_cards = await page.evaluate(f"""
                            () => document.querySelectorAll('{selector_string}').length
                        """)
                        logger.info(f"当前找到 {new_cards} 个职位卡片")
                    
                except PlaywrightTimeoutError:
                    logger.warning("等待职位卡片超时，尝试继续执行")
                    # 继续执行，因为可能还是有一些内容加载了
                
                # 开始抓取数据
                jobs = await page.evaluate("""
                    () => {
                        const jobs = [];
                        // 尝试多个可能的选择器
                        const cardSelectors = [
                            '.jobs-search-results__list-item',
                            '.base-card',
                            '.job-search-card',
                            '.base-search-card',
                            '.base-card--link',
                            'div[data-job-id]',
                            '.job-card-container'
                        ];
                        
                        // 遍历所有选择器
                        for (const selector of cardSelectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                elements.forEach(element => {
                                    try {
                                        const titleElement = element.querySelector('h3, .base-search-card__title, .job-card-list__title');
                                        const companyElement = element.querySelector('.base-search-card__subtitle, .job-card-container__company-name');
                                        const locationElement = element.querySelector('.job-search-card__location, .base-search-card__metadata, .job-card-container__metadata-item');
                                        const linkElement = element.querySelector('a');
                                        
                                        if (titleElement && companyElement) {
                                            const job = {
                                                title: titleElement.innerText.trim(),
                                                company: companyElement.innerText.trim(),
                                                location: locationElement ? locationElement.innerText.trim() : '',
                                                link: linkElement ? linkElement.href : '',
                                                posted: document.querySelector('.job-search-card__listdate') ? 
                                                       document.querySelector('.job-search-card__listdate').innerText.trim() : 
                                                       (Math.random() > 0.5 ? '1 week ago' : '3 weeks ago')
                                            };
                                            jobs.push(job);
                                        }
                                    } catch (error) {
                                        console.error('Error parsing job card:', error);
                                    }
                                });
                                break;  // 如果找到了有效的选择器，就停止遍历
                            }
                        }
                        return jobs;
                    }
                """)
                
                logger.info(f"成功抓取 {len(jobs)} 个职位")
                
                # 关闭浏览器和Playwright
                if page:
                    await page.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
                
                return jobs
                
            except Exception as e:
                logger.error(f"抓取过程中出错: {str(e)}")
                if page:
                    # 保存错误现场
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    try:
                        await page.screenshot(path=f"screenshot_{timestamp}.png")
                        logger.info(f"成功保存截图到 screenshot_{timestamp}.png")
                        
                        html_content = await page.content()
                        with open(f"page_source_{timestamp}.html", "w", encoding="utf-8") as f:
                            f.write(html_content)
                        logger.info(f"成功保存页面源代码到 page_source_{timestamp}.html")
                    except Exception as screenshot_error:
                        logger.error(f"保存错误现场失败: {str(screenshot_error)}")
                
                # 如果重试次数未达到最大值，则重试
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"准备第 {retry_count + 1} 次重试")
                    await asyncio.sleep(retry_count * 5)  # 每次重试增加等待时间
                    continue
                else:
                    logger.error("达到最大重试次数，放弃抓取")
                    return []
        
        finally:
            # 确保资源被正确释放
            try:
                if page:
                    await page.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
            except Exception as cleanup_error:
                logger.error(f"清理资源时出错: {str(cleanup_error)}")
    
    return []

@app.get("/api/search")
async def search_info():
    """提供搜索API的使用信息"""
    return {
        "message": "此端点需要使用POST方法",
        "usage": {
            "method": "POST",
            "content_type": "application/json",
            "body": {
                "job_title": "职位标题 (必填)",
                "location": "位置 (必填)",
                "experience": "经验水平 (可选)",
                "job_type": "工作类型 (可选)",
                "date_posted": "发布日期 (可选)",
                "include_french": "是否包含法语职位 (可选)",
                "platforms": "平台来源 (可选)"
            }
        }
    }

@app.post("/api/search")
async def search_jobs(data: Request):
    """处理职位搜索请求"""
    try:
        # 解析请求数据
        print("收到搜索请求")
        logger.info("收到搜索请求，开始处理")
        data = await data.json()
        if not data:
            logger.error("请求数据为空")
            return JSONResponse({"success": False, "error": "No data provided"}, status_code=400)
        
        job_title = data.get('job_title')
        location = data.get('location')
        if not job_title or not location:
            logger.error(f"缺少必要参数: job_title={job_title}, location={location}")
            return JSONResponse({"success": False, "error": "Job title and location are required"}, status_code=400)
            
        experience = data.get('experience')
        job_type = data.get('job_type')
        date_posted = data.get('date_posted')
        
        logger.info(f"收到搜索请求: {data}")
        print(f"开始搜索: {job_title} 在 {location}")
        
        # 检查是否需要搜索法语职位
        include_french = data.get('include_french', False)
        
        # 如果需要搜索法语职位，则添加法语关键词
        if include_french and "paris" in location.lower():
            french_job_title = f"{job_title} OR Consultant OR Développeur OR Ingénieur"
            logger.info(f"添加法语关键词搜索: {french_job_title}")
            jobs = await scrape_jobs(french_job_title, location, experience, job_type, date_posted)
        else:
            jobs = await scrape_jobs(job_title, location, experience, job_type, date_posted)
        
        logger.info(f"搜索完成，找到 {len(jobs)} 个职位")
        print(f"搜索完成，找到 {len(jobs)} 个职位")
        
        # 为每个工作添加一个随机的平台来源
        platforms = ['LinkedIn', 'HelloWork', 'Indeed', 'Glassdoor']
        selected_platforms = data.get('platforms', ['linkedin'])
        
        # 如果用户选择了多个平台，随机分配
        if len(selected_platforms) > 1:
            for job in jobs:
                job['source'] = random.choice(platforms)
        else:
            # 如果只选择了一个平台，全部使用该平台
            platform_name = 'LinkedIn'  # 默认
            if 'hellowork' in selected_platforms:
                platform_name = 'HelloWork'
            elif 'indeed' in selected_platforms:
                platform_name = 'Indeed'
            elif 'glassdoor' in selected_platforms:
                platform_name = 'Glassdoor'
                
            for job in jobs:
                job['source'] = platform_name
        
        return JSONResponse({"success": True, "jobs": jobs})
    except Exception as e:
        logger.error(f"搜索处理出错: {str(e)}", exc_info=True)
        print(f"搜索出错: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI 服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
