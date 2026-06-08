"""
DATA-AI 浏览器会话管理器

提供持久化的浏览器会话：
- 会话创建/销毁/复用
- 多标签页管理
- Cookie 管理
- JS 执行
- 智能等待
- 滚动控制
- 键盘输入
- 下拉选择
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BrowserSession:
    """浏览器会话"""

    session_id: str
    browser: Any = None
    context: Any = None
    pages: dict[str, Any] = field(default_factory=dict)
    active_tab: str = "main"
    _playwright: Any = None

    @property
    def current_page(self) -> Any:
        return self.pages.get(self.active_tab)


class BrowserSessionManager:
    """
    浏览器会话管理器

    管理浏览器实例的生命周期
    """

    _instance: BrowserSessionManager | None = None

    def __new__(cls) -> BrowserSessionManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions: dict[str, BrowserSession] = {}
        return cls._instance

    async def create_session(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
    ) -> BrowserSession:
        import uuid

        from playwright.async_api import async_playwright

        session_id = f"browser_{uuid.uuid4().hex[:8]}"
        pw = await async_playwright().start()

        if browser_type == "firefox":
            browser = await pw.firefox.launch(headless=headless)
        elif browser_type == "webkit":
            browser = await pw.webkit.launch(headless=headless)
        else:
            browser = await pw.chromium.launch(headless=headless)

        context = await browser.new_context()
        page = await context.new_page()

        session = BrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            pages={"main": page},
            active_tab="main",
            _playwright=pw,
        )

        self._sessions[session_id] = session
        logger.info(f"浏览器会话已创建: {session_id}", browser_type=browser_type)

        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self._sessions.get(session_id)

    async def destroy_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            try:
                await session.browser.close()
                await session._playwright.stop()
            except Exception as e:
                logger.warning(f"关闭浏览器会话失败: {e}")
            return True
        return False

    async def destroy_all(self) -> None:
        for sid in list(self._sessions.keys()):
            await self.destroy_session(sid)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


_browser_manager: BrowserSessionManager | None = None


def get_browser_manager() -> BrowserSessionManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserSessionManager()
    return _browser_manager


async def browser_session(
    action: str,
    session_id: str | None = None,
    headless: bool = True,
) -> dict:
    manager = get_browser_manager()

    if action == "create":
        session = await manager.create_session(headless=headless)
        return {"success": True, "session_id": session.session_id}
    elif action == "list":
        sessions = manager.list_sessions()
        return {"success": True, "sessions": sessions, "count": len(sessions)}
    elif action == "destroy":
        if not session_id:
            return {"success": False, "error": "session_id required for destroy"}
        result = await manager.destroy_session(session_id)
        return {"success": result, "session_id": session_id}

    return {"success": False, "error": f"Unknown action: {action}"}


async def browser_tab(
    action: str,
    session_id: str,
    tab_id: str | None = None,
    url: str | None = None,
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session:
        return {"success": False, "error": f"Session not found: {session_id}"}

    if action == "open":
        import uuid

        new_tab_id = f"tab_{uuid.uuid4().hex[:6]}"
        new_page = await session.context.new_page()
        if url:
            await new_page.goto(url)
        session.pages[new_tab_id] = new_page
        return {"success": True, "tab_id": new_tab_id, "url": url}

    elif action == "close":
        if not tab_id or tab_id not in session.pages:
            return {"success": False, "error": f"Tab not found: {tab_id}"}
        await session.pages[tab_id].close()
        del session.pages[tab_id]
        if session.active_tab == tab_id:
            session.active_tab = list(session.pages.keys())[0] if session.pages else "main"
        return {"success": True, "closed_tab": tab_id}

    elif action == "switch":
        if not tab_id or tab_id not in session.pages:
            return {"success": False, "error": f"Tab not found: {tab_id}"}
        session.active_tab = tab_id
        return {"success": True, "active_tab": tab_id}

    elif action == "list":
        tabs = list(session.pages.keys())
        return {"success": True, "tabs": tabs, "active_tab": session.active_tab, "count": len(tabs)}

    return {"success": False, "error": f"Unknown action: {action}"}


async def browser_js(session_id: str, script: str) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session or not session.current_page:
        return {"success": False, "error": "No active browser session or page"}

    try:
        result = await session.current_page.evaluate(script)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_cookie(
    session_id: str,
    action: str,
    name: str | None = None,
    value: str | None = None,
    domain: str | None = None,
    path: str = "/",
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session:
        return {"success": False, "error": f"Session not found: {session_id}"}

    if action == "get_all":
        cookies = await session.context.cookies()
        return {"success": True, "cookies": cookies, "count": len(cookies)}

    elif action == "get":
        if not name:
            return {"success": False, "error": "Cookie name required"}
        cookies = await session.context.cookies()
        for c in cookies:
            if c.get("name") == name:
                return {"success": True, "cookie": c}
        return {"success": False, "error": f"Cookie not found: {name}"}

    elif action == "set":
        if not name or not domain:
            return {"success": False, "error": "Cookie name and domain required"}
        await session.context.add_cookies(
            [
                {
                    "name": name,
                    "value": value or "",
                    "domain": domain,
                    "path": path,
                }
            ]
        )
        return {"success": True, "name": name, "domain": domain}

    elif action == "delete":
        if not name:
            return {"success": False, "error": "Cookie name required"}
        await session.context.clear_cookies(name=name)
        return {"success": True, "deleted": name}

    return {"success": False, "error": f"Unknown action: {action}"}


async def browser_wait(
    session_id: str,
    wait_type: str,
    selector: str | None = None,
    timeout: int = 10000,
    value: str | None = None,
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session or not session.current_page:
        return {"success": False, "error": "No active browser session"}

    page = session.current_page

    try:
        if wait_type == "element":
            if not selector:
                return {"success": False, "error": "selector required for element wait"}
            await page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "wait_type": "element", "selector": selector}

        elif wait_type == "time":
            import asyncio

            await asyncio.sleep(timeout / 1000)
            return {"success": True, "wait_type": "time", "ms": timeout}

        elif wait_type == "network_idle":
            await page.wait_for_load_state("networkidle", timeout=timeout)
            return {"success": True, "wait_type": "network_idle"}

        elif wait_type == "navigation":
            await page.wait_for_load_state("load", timeout=timeout)
            return {"success": True, "wait_type": "navigation"}

        return {"success": False, "error": f"Unknown wait type: {wait_type}"}

    except Exception as e:
        return {"success": False, "error": str(e), "wait_type": wait_type}


async def browser_scroll(
    session_id: str,
    direction: str,
    amount: int = 500,
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session or not session.current_page:
        return {"success": False, "error": "No active browser session"}

    try:
        if direction == "top":
            await session.current_page.evaluate("window.scrollTo(0, 0)")
        elif direction == "bottom":
            await session.current_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction == "up":
            await session.current_page.evaluate(f"window.scrollBy(0, -{amount})")
        elif direction == "down":
            await session.current_page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            return {"success": False, "error": f"Unknown direction: {direction}"}

        return {"success": True, "direction": direction, "amount": amount}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_keyboard(
    session_id: str,
    action: str,
    selector: str | None = None,
    text: str | None = None,
    key: str | None = None,
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session or not session.current_page:
        return {"success": False, "error": "No active browser session"}

    try:
        if action == "type":
            if not selector or not text:
                return {"success": False, "error": "selector and text required for type action"}
            await session.current_page.fill(selector, text)
            return {"success": True, "action": "type", "selector": selector}

        elif action == "press":
            if not key:
                return {"success": False, "error": "key required for press action"}
            await session.current_page.keyboard.press(key)
            return {"success": True, "action": "press", "key": key}

        return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_select(
    session_id: str,
    action: str,
    selector: str,
    value: str | None = None,
    label: str | None = None,
) -> dict:
    manager = get_browser_manager()
    session = manager.get_session(session_id)
    if not session or not session.current_page:
        return {"success": False, "error": "No active browser session"}

    try:
        if action == "get_options":
            options = await session.current_page.evaluate(f"""
                () => {{
                    const select = document.querySelector('{selector}');
                    if (!select) return [];
                    return Array.from(select.options).map(opt => ({{
                        value: opt.value,
                        label: opt.text,
                        selected: opt.selected
                    }}));
                }}
            """)
            return {"success": True, "options": options, "count": len(options)}

        elif action == "select":
            if value:
                await session.current_page.select_option(selector, value=value)
            elif label:
                await session.current_page.select_option(selector, label=label)
            else:
                return {"success": False, "error": "value or label required for select action"}
            return {"success": True, "action": "select", "selector": selector}

        return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register_browser_session_tools() -> None:
    from data_ai.core.tool.registry import get_tool_registry

    registry = get_tool_registry()

    registry.register_function(
        name="browser_session",
        func=browser_session,
        description="Create, list, or destroy browser sessions",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action: create, list, destroy"},
                "session_id": {"type": "string", "description": "Session ID (for destroy)"},
                "headless": {"type": "boolean", "description": "Run headless mode"},
            },
            "required": ["action"],
        },
    )

    registry.register_function(
        name="browser_tab",
        func=browser_tab,
        description="Manage browser tabs (open, close, switch, list)",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action: open, close, switch, list"},
                "session_id": {"type": "string", "description": "Browser session ID"},
                "tab_id": {"type": "string", "description": "Tab ID (for switch/close)"},
                "url": {"type": "string", "description": "URL to open (for open action)"},
            },
            "required": ["action", "session_id"],
        },
    )

    registry.register_function(
        name="browser_js",
        func=browser_js,
        description="Execute JavaScript on the current page",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "script": {"type": "string", "description": "JavaScript code to execute"},
            },
            "required": ["session_id", "script"],
        },
    )

    registry.register_function(
        name="browser_cookie",
        func=browser_cookie,
        description="Get, set, or delete browser cookies",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "action": {"type": "string", "description": "Action: get, get_all, set, delete"},
                "name": {"type": "string", "description": "Cookie name"},
                "value": {"type": "string", "description": "Cookie value (for set)"},
                "domain": {"type": "string", "description": "Cookie domain (for set)"},
                "path": {"type": "string", "description": "Cookie path"},
            },
            "required": ["session_id", "action"],
        },
    )

    registry.register_function(
        name="browser_wait",
        func=browser_wait,
        description="Wait for elements, conditions, or time",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "wait_type": {"type": "string", "description": "Type: element, time, network_idle, navigation"},
                "selector": {"type": "string", "description": "CSS selector (for element type)"},
                "timeout": {"type": "integer", "description": "Max wait time in ms"},
                "value": {"type": "string", "description": "Text to wait for (for navigation)"},
            },
            "required": ["session_id", "wait_type"],
        },
    )

    registry.register_function(
        name="browser_scroll",
        func=browser_scroll,
        description="Scroll the page (up, down, to top, to bottom, to element)",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "direction": {"type": "string", "description": "Direction: up, down, top, bottom"},
                "amount": {"type": "integer", "description": "Scroll amount in pixels"},
            },
            "required": ["session_id", "direction"],
        },
    )

    registry.register_function(
        name="browser_keyboard",
        func=browser_keyboard,
        description="Send keyboard input or key combinations",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "action": {"type": "string", "description": "Action: type, press"},
                "selector": {"type": "string", "description": "CSS selector (for type action)"},
                "text": {"type": "string", "description": "Text to type (for type action)"},
                "key": {
                    "type": "string",
                    "description": "Key to press (for press action, e.g., Enter, Tab, Escape, Control+a)",
                },
            },
            "required": ["session_id", "action"],
        },
    )

    registry.register_function(
        name="browser_select",
        func=browser_select,
        description="Get dropdown options or select an option",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID"},
                "action": {"type": "string", "description": "Action: get_options, select"},
                "selector": {"type": "string", "description": "CSS selector for select element"},
                "value": {"type": "string", "description": "Option value to select"},
                "label": {"type": "string", "description": "Option label to select"},
            },
            "required": ["session_id", "action", "selector"],
        },
    )

    logger.info(f"已注册 {8} 个浏览器会话工具")
