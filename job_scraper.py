import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
from urllib.parse import quote

"""
LinkedIn职位抓取器最佳实践和成功经验

1. 连接处理:
   - 使用较短的连接超时时间（30秒），避免长时间等待
   - 实现重试机制，在连接失败时自动重试，每次重试间隔递增
   - 不要设置自定义User-Agent，Bright Data不允许覆盖User-Agent头

2. 页面加载策略:
   - 使用'domcontentloaded'而非'networkidle'作为页面加载策略，大幅提高加载速度
   - 为职位卡片元素设置合理的等待时间（20秒），避免过长等待
   - 实现滚动加载更多内容的功能，确保能获取更多职位信息

3. 错误处理:
   - 使用try-except-finally结构确保资源在任何情况下都能被正确释放
   - 在出错时保存页面截图和HTML源码，便于调试
   - 对不同类型的错误实现不同的处理策略

4. 资源管理:
   - 确保page、browser和playwright实例在使用后被正确关闭
   - 使用合理的超时设置，避免资源长时间占用
   - 在finally块中进行资源清理，防止资源泄漏

5. 数据提取:
   - 使用多个选择器尝试提取数据，增强对页面结构变化的适应性
   - 在JavaScript中使用try-catch块处理单个职位卡片解析失败的情况
   - 对提取的数据进行验证，过滤掉无效数据

6. 性能优化:
   - 减少不必要的等待时间，如滚动间隔从2秒减少到1秒
   - 使用更高效的DOM选择器组合，提高元素查找效率
   - 优化重试逻辑，避免不必要的重试
"""

# 配置日志
logging.basicConfig(
    filename='job_scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Bright Data Scraping Browser 配置
SBR_WS_ENDPOINT = "wss://brd-customer-hl_afd51056-zone-scraping_browser1:klqv3xfx5yb0@brd.superproxy.io:9222"
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
    "internship": "I",
    "volunteer": "V",
    "other": "O"
}

DATE_POSTED = {
    "past_24h": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
    "any_time": ""
}

async def scrape_jobs(job_title, location, experience=None, job_type=None, date_posted=None):
    """
    从 LinkedIn 抓取职位数据
    参数:
        job_title (str): 职位名称（必填）
        location (str): 地点（必填）
        experience (str, optional): 经验级别
        job_type (str, optional): 工作类型
        date_posted (str, optional): 发布时间
    返回:
        list: 职位信息列表
    """
    logger = logging.getLogger(__name__)
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
    query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
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
                        
                        // 用于清理文本的辅助函数
                        const cleanText = (text) => {
                            if (!text) return '';
                            // 移除多余的空白字符
                            return text.replace(/\s+/g, ' ').trim();
                        };
                        
                        // 检测是否包含星号或特殊字符的辅助函数
                        const containsSpecialChars = (text) => {
                            if (!text) return false;
                            return text.includes('*') || text.includes('******');
                        };
                        
                        // 遍历所有选择器
                        for (const selector of cardSelectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                elements.forEach(element => {
                                    try {
                                        // 尝试多种选择器组合来获取职位信息
                                        const titleSelectors = [
                                            'h3', 
                                            '.base-search-card__title', 
                                            '.job-card-list__title',
                                            'h3 a',
                                            '.job-card-container__link-wrapper'
                                        ];
                                        
                                        const companySelectors = [
                                            '.base-search-card__subtitle', 
                                            '.job-card-container__company-name',
                                            '.job-card-container__primary-description',
                                            '.base-search-card__subtitle a'
                                        ];
                                        
                                        const locationSelectors = [
                                            '.job-search-card__location', 
                                            '.base-search-card__metadata', 
                                            '.job-card-container__metadata-item',
                                            '.job-card-container__metadata-wrapper'
                                        ];
                                        
                                        // 尝试所有标题选择器
                                        let titleElement = null;
                                        for (const sel of titleSelectors) {
                                            titleElement = element.querySelector(sel);
                                            if (titleElement && titleElement.innerText.trim()) break;
                                        }
                                        
                                        // 尝试所有公司选择器
                                        let companyElement = null;
                                        for (const sel of companySelectors) {
                                            companyElement = element.querySelector(sel);
                                            if (companyElement && companyElement.innerText.trim()) break;
                                        }
                                        
                                        // 尝试所有位置选择器
                                        let locationElement = null;
                                        for (const sel of locationSelectors) {
                                            locationElement = element.querySelector(sel);
                                            if (locationElement && locationElement.innerText.trim()) break;
                                        }
                                        
                                        const linkElement = element.querySelector('a');
                                        
                                        // 获取职位发布时间
                                        const timeElement = element.querySelector('time, .job-search-card__listdate, .base-search-card__metadata span:last-child');
                                        
                                        // 确保至少有标题，其他信息可以是默认值
                                        if (titleElement) {
                                            const title = cleanText(titleElement.innerText);
                                            const company = companyElement ? cleanText(companyElement.innerText) : "未知公司";
                                            const location = locationElement ? cleanText(locationElement.innerText) : "未知位置";
                                            
                                            // 如果标题包含星号或特殊字符，尝试从元素的其他属性中获取更多信息
                                            let finalTitle = title;
                                            if (containsSpecialChars(title)) {
                                                // 尝试从aria-label或title属性获取更多信息
                                                const ariaLabel = titleElement.getAttribute('aria-label');
                                                const titleAttr = titleElement.getAttribute('title');
                                                
                                                if (ariaLabel && !containsSpecialChars(ariaLabel)) {
                                                    finalTitle = cleanText(ariaLabel);
                                                } else if (titleAttr && !containsSpecialChars(titleAttr)) {
                                                    finalTitle = cleanText(titleAttr);
                                                }
                                            }
                                            
                                            const job = {
                                                title: finalTitle || "未知职位",
                                                company: containsSpecialChars(company) ? "未知公司" : company,
                                                location: containsSpecialChars(location) ? "未知位置" : location,
                                                link: linkElement ? linkElement.href : "",
                                                posted_time: timeElement ? timeElement.getAttribute('datetime') || cleanText(timeElement.innerText) : new Date().toISOString()
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
                    from datetime import datetime
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

# 测试代码
async def main():
    try:
        jobs = await scrape_jobs(
            job_title="Software Engineer",
            location="New York",
            experience="entry_level",
            job_type="full_time",
            date_posted="past_week"
        )
        for job in jobs:
            print(job)
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
