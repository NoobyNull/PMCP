"""
Playwright Service for PerfectMPC
Web automation, browser testing, and web scraping capabilities
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from utils.database import DatabaseManager
from utils.logger import LoggerMixin

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserType(Enum):
    """Supported browser types"""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class ActionType(Enum):
    """Browser action types"""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    EXTRACT_TEXT = "extract_text"
    EXTRACT_LINKS = "extract_links"
    WAIT_FOR_ELEMENT = "wait_for_element"
    EVALUATE_JS = "evaluate_js"


class PlaywrightService(LoggerMixin):
    """Web automation and browser testing service"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._playwright = None
        self._browsers: Dict[str, Browser] = {}
        self._contexts: Dict[str, BrowserContext] = {}
        self._pages: Dict[str, Page] = {}
        self._sessions: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize the Playwright service"""
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright not available. Install with: pip install playwright")
            raise ImportError("Playwright not installed")
        
        self.logger.info("Initializing Playwright Service")
        
        try:
            self._playwright = await async_playwright().start()
            self.logger.info("Playwright Service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the Playwright service"""
        try:
            # Close all pages
            for page in self._pages.values():
                await page.close()
            
            # Close all contexts
            for context in self._contexts.values():
                await context.close()
            
            # Close all browsers
            for browser in self._browsers.values():
                await browser.close()
            
            # Stop playwright
            if self._playwright:
                await self._playwright.stop()
            
            self.logger.info("Playwright Service shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during Playwright shutdown: {e}")
    
    async def create_browser_session(
        self, 
        session_id: str,
        browser_type: BrowserType = BrowserType.CHROMIUM,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None
    ) -> str:
        """Create a new browser session"""
        
        if not self._playwright:
            raise RuntimeError("Playwright not initialized")
        
        browser_id = f"{session_id}_{browser_type.value}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Launch browser
            if browser_type == BrowserType.CHROMIUM:
                browser = await self._playwright.chromium.launch(headless=headless)
            elif browser_type == BrowserType.FIREFOX:
                browser = await self._playwright.firefox.launch(headless=headless)
            elif browser_type == BrowserType.WEBKIT:
                browser = await self._playwright.webkit.launch(headless=headless)
            else:
                raise ValueError(f"Unsupported browser type: {browser_type}")
            
            self._browsers[browser_id] = browser
            
            # Create context
            context_options = {}
            if viewport:
                context_options["viewport"] = viewport
            
            context = await browser.new_context(**context_options)
            context_id = f"{browser_id}_context"
            self._contexts[context_id] = context
            
            # Create initial page
            page = await context.new_page()
            page_id = f"{browser_id}_page_0"
            self._pages[page_id] = page
            
            # Store session info
            self._sessions[session_id] = {
                "browser_id": browser_id,
                "context_id": context_id,
                "page_id": page_id,
                "browser_type": browser_type.value,
                "created_at": datetime.utcnow().isoformat(),
                "headless": headless
            }
            
            # Store in database
            await self.db.mongo_insert_one("playwright_sessions", {
                "session_id": session_id,
                "browser_id": browser_id,
                "browser_type": browser_type.value,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            })
            
            self.logger.info(f"Created browser session {browser_id}", 
                           session_id=session_id, browser_type=browser_type.value)
            
            return browser_id
            
        except Exception as e:
            self.logger.error(f"Failed to create browser session: {e}")
            raise
    
    async def navigate(self, session_id: str, url: str, wait_until: str = "load") -> Dict[str, Any]:
        """Navigate to a URL"""
        page = await self._get_page(session_id)
        
        try:
            response = await page.goto(url, wait_until=wait_until)
            
            result = {
                "url": url,
                "status": response.status if response else None,
                "title": await page.title(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.NAVIGATE, {"url": url}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            raise
    
    async def click_element(self, session_id: str, selector: str, timeout: int = 30000) -> Dict[str, Any]:
        """Click an element"""
        page = await self._get_page(session_id)
        
        try:
            await page.click(selector, timeout=timeout)
            
            result = {
                "selector": selector,
                "action": "clicked",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.CLICK, {"selector": selector}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Click failed: {e}")
            raise
    
    async def type_text(self, session_id: str, selector: str, text: str, delay: int = 0) -> Dict[str, Any]:
        """Type text into an element"""
        page = await self._get_page(session_id)
        
        try:
            await page.fill(selector, text)
            if delay > 0:
                await page.type(selector, text, delay=delay)
            
            result = {
                "selector": selector,
                "text_length": len(text),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.TYPE, 
                                 {"selector": selector, "text_length": len(text)}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Type failed: {e}")
            raise
    
    async def take_screenshot(self, session_id: str, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot"""
        page = await self._get_page(session_id)
        
        try:
            screenshot_id = f"screenshot_{uuid.uuid4().hex[:8]}"
            screenshot_path = f"/tmp/{screenshot_id}.png"
            
            await page.screenshot(path=screenshot_path, full_page=full_page)
            
            # Store screenshot info in database
            screenshot_info = {
                "screenshot_id": screenshot_id,
                "session_id": session_id,
                "path": screenshot_path,
                "full_page": full_page,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.db.mongo_insert_one("screenshots", screenshot_info)
            
            result = {
                "screenshot_id": screenshot_id,
                "path": screenshot_path,
                "full_page": full_page,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.SCREENSHOT, {"full_page": full_page}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            raise
    
    async def extract_text(self, session_id: str, selector: str = "body") -> Dict[str, Any]:
        """Extract text from page or element"""
        page = await self._get_page(session_id)
        
        try:
            text = await page.text_content(selector)
            
            result = {
                "selector": selector,
                "text": text,
                "text_length": len(text) if text else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.EXTRACT_TEXT, {"selector": selector}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            raise
    
    async def extract_links(self, session_id: str) -> Dict[str, Any]:
        """Extract all links from the page"""
        page = await self._get_page(session_id)
        
        try:
            links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(link => ({
                        text: link.textContent.trim(),
                        href: link.href,
                        title: link.title || null
                    }));
                }
            """)
            
            result = {
                "links": links,
                "count": len(links),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.EXTRACT_LINKS, {}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Link extraction failed: {e}")
            raise
    
    async def evaluate_javascript(self, session_id: str, script: str) -> Dict[str, Any]:
        """Evaluate JavaScript on the page"""
        page = await self._get_page(session_id)
        
        try:
            result_value = await page.evaluate(script)
            
            result = {
                "script": script,
                "result": result_value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.EVALUATE_JS, {"script": script}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"JavaScript evaluation failed: {e}")
            raise
    
    async def wait_for_element(self, session_id: str, selector: str, timeout: int = 30000) -> Dict[str, Any]:
        """Wait for an element to appear"""
        page = await self._get_page(session_id)
        
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            
            result = {
                "selector": selector,
                "found": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self._log_action(session_id, ActionType.WAIT_FOR_ELEMENT, {"selector": selector}, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Wait for element failed: {e}")
            raise
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a browser session"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session_info = self._sessions[session_id].copy()
        
        # Get current page info
        try:
            page = await self._get_page(session_id)
            session_info.update({
                "current_url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size
            })
        except Exception as e:
            self.logger.warning(f"Could not get page info: {e}")
        
        return session_info
    
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """Close a browser session"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session_info = self._sessions[session_id]
        browser_id = session_info["browser_id"]
        
        try:
            # Close browser
            if browser_id in self._browsers:
                await self._browsers[browser_id].close()
                del self._browsers[browser_id]
            
            # Clean up references
            context_id = session_info.get("context_id")
            if context_id and context_id in self._contexts:
                del self._contexts[context_id]
            
            page_id = session_info.get("page_id")
            if page_id and page_id in self._pages:
                del self._pages[page_id]
            
            del self._sessions[session_id]
            
            # Update database
            await self.db.mongo_update_one(
                "playwright_sessions",
                {"session_id": session_id},
                {"status": "closed", "closed_at": datetime.utcnow().isoformat()}
            )
            
            self.logger.info(f"Closed browser session {browser_id}", session_id=session_id)
            
            return {"session_id": session_id, "status": "closed"}
            
        except Exception as e:
            self.logger.error(f"Failed to close session: {e}")
            raise
    
    # Private helper methods
    async def _get_page(self, session_id: str) -> Page:
        """Get the page for a session"""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        page_id = self._sessions[session_id]["page_id"]
        if page_id not in self._pages:
            raise ValueError(f"Page {page_id} not found")
        
        return self._pages[page_id]
    
    async def _log_action(self, session_id: str, action_type: ActionType, params: Dict, result: Dict):
        """Log a browser action"""
        try:
            action_log = {
                "session_id": session_id,
                "action_type": action_type.value,
                "parameters": params,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.db.mongo_insert_one("playwright_actions", action_log)
            
        except Exception as e:
            self.logger.warning(f"Failed to log action: {e}")
