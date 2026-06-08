"""
DATA-AI 浏览器自动化工具

基于 Playwright 实现浏览器自动化：
- 页面导航
- 元素交互
- 截图
- 内容提取
"""

from __future__ import annotations

from ...utils.logging import get_logger

logger = get_logger(__name__)


async def browser_navigate(url: str, wait_until: str = "load") -> dict:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until=wait_until)

            title = await page.title()

            await browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
            }
    except ImportError:
        return {
            "success": False,
            "error": "playwright not installed. Run: pip install playwright && playwright install",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def browser_click(selector: str, url: str | None = None) -> dict:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            if url:
                await page.goto(url)

            await page.click(selector)

            await browser.close()

            return {
                "success": True,
                "selector": selector,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def browser_screenshot(
    url: str,
    selector: str | None = None,
    full_page: bool = False,
) -> dict:
    try:
        import base64

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)

            if selector:
                element = await page.query_selector(selector)
                if element:
                    screenshot = await element.screenshot()
                else:
                    await browser.close()
                    return {
                        "success": False,
                        "error": f"Element not found: {selector}",
                    }
            else:
                screenshot = await page.screenshot(full_page=full_page)

            await browser.close()

            screenshot_base64 = base64.b64encode(screenshot).decode()

            return {
                "success": True,
                "url": url,
                "screenshot_base64": screenshot_base64[:100] + "...",
                "screenshot_size": len(screenshot),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def browser_extract(
    url: str,
    selector: str | None = None,
    extract_type: str = "text",
) -> dict:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url)

            result = {}

            if extract_type == "text":
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        result["content"] = await element.inner_text()
                    else:
                        result["error"] = f"Element not found: {selector}"
                else:
                    result["content"] = await page.inner_text("body")

            elif extract_type == "html":
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        result["content"] = await element.inner_html()
                    else:
                        result["error"] = f"Element not found: {selector}"
                else:
                    result["content"] = await page.content()

            elif extract_type == "links":
                links = await page.query_selector_all("a")
                result["links"] = []
                for link in links:
                    href = await link.get_attribute("href")
                    text = await link.inner_text()
                    if href:
                        result["links"].append(
                            {
                                "href": href,
                                "text": text.strip(),
                            }
                        )

            elif extract_type == "images":
                images = await page.query_selector_all("img")
                result["images"] = []
                for img in images:
                    src = await img.get_attribute("src")
                    alt = await img.get_attribute("alt")
                    if src:
                        result["images"].append(
                            {
                                "src": src,
                                "alt": alt or "",
                            }
                        )

            await browser.close()

            result["success"] = True
            result["url"] = url
            result["extract_type"] = extract_type

            return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def browser_fill(
    selector: str,
    value: str,
    url: str | None = None,
) -> dict:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            if url:
                await page.goto(url)

            await page.fill(selector, value)

            await browser.close()

            return {
                "success": True,
                "selector": selector,
                "value": value,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def register_browser_tools() -> None:
    from data_ai.core.tool.registry import get_tool_registry

    registry = get_tool_registry()

    registry.register_function(
        name="browser_navigate",
        func=browser_navigate,
        description="Navigate to a URL in the browser",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "wait_until": {"type": "string", "description": "Wait condition (load, domcontentloaded, networkidle)"},
            },
            "required": ["url"],
        },
    )

    registry.register_function(
        name="browser_click",
        func=browser_click,
        description="Click an element on the page",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the element to click"},
                "url": {"type": "string", "description": "URL to navigate to first (optional)"},
            },
            "required": ["selector"],
        },
    )

    registry.register_function(
        name="browser_screenshot",
        func=browser_screenshot,
        description="Take a screenshot of the page",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "selector": {"type": "string", "description": "CSS selector for specific element (optional)"},
                "full_page": {"type": "boolean", "description": "Take full page screenshot"},
            },
            "required": ["url"],
        },
    )

    registry.register_function(
        name="browser_extract",
        func=browser_extract,
        description="Extract content from a web page",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to extract content from"},
                "selector": {"type": "string", "description": "CSS selector for content to extract"},
                "extract_type": {"type": "string", "description": "Type of extraction (text, html, links, images)"},
            },
            "required": ["url"],
        },
    )

    registry.register_function(
        name="browser_fill",
        func=browser_fill,
        description="Fill a form field on the page",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the input field"},
                "value": {"type": "string", "description": "Value to fill"},
                "url": {"type": "string", "description": "URL to navigate to first (optional)"},
            },
            "required": ["selector", "value"],
        },
    )

    logger.info(f"已注册 {5} 个浏览器工具")
