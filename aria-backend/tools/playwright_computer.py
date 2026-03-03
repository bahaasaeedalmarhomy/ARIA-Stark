import asyncio
import re
from typing import Literal, Optional

from google.adk.tools.computer_use.base_computer import BaseComputer, ComputerEnvironment, ComputerState

# Pre-compiled CAPTCHA detection pattern (M1: compiled once at module level)
_CAPTCHA_RE = re.compile(
    r"captcha|recaptcha|hcaptcha|cf-challenge|challenge-form|turnstile",
    re.IGNORECASE,
)

# Playwright launch args required for containerized environments:
# --no-sandbox: required because Docker containers run as root
# --disable-dev-shm-usage: Cloud Run /dev/shm is limited (64MB); prevents crashes
PLAYWRIGHT_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]

# Default screen size for Playwright browser (1280x800 is a common portrait viewport)
DEFAULT_SCREEN_WIDTH = 1280
DEFAULT_SCREEN_HEIGHT = 800


class BargeInException(Exception):
    """Raised when the session cancel flag is set mid-execution."""
    pass


async def launch_chromium():
    """
    Launch a Chromium browser instance with Cloud Run-compatible settings.
    Returns (playwright, browser) tuple.
    """
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(args=PLAYWRIGHT_LAUNCH_ARGS)
    return playwright, browser


async def smoketest_playwright():
    """
    Minimal smoke test verifying Playwright Chromium can launch inside the container.
    Called during startup validation.
    """
    playwright, browser = await launch_chromium()
    await browser.close()
    await playwright.stop()
    return True


class PlaywrightComputer(BaseComputer):
    """
    BaseComputer implementation backed by a Playwright browser.

    Implements the full BaseComputer interface required by ComputerUseToolset.
    Wraps Playwright async API for browser control.

    All action methods check the session cancel flag both BEFORE and AFTER
    every await call to support barge-in cancellation (BargeInException pattern).

    Story 3.1: Wired into ComputerUseToolset. Per-session lifecycle (start/stop)
    managed in Stories 3.2+.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._playwright = None
        self.browser = None
        self.page = None

    async def initialize(self) -> None:
        """Initialize the Playwright browser. Called by ComputerUseToolset before first use."""
        await self.start()

    async def start(self) -> None:
        """Launch Chromium and create a new page."""
        self._playwright, self.browser = await launch_chromium()
        self.page = await self.browser.new_page()
        await self.page.set_viewport_size(
            {"width": DEFAULT_SCREEN_WIDTH, "height": DEFAULT_SCREEN_HEIGHT}
        )

    async def stop(self) -> None:
        """Close page, browser, and Playwright instance."""
        if self.page:
            await self.page.close()
            self.page = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def close(self) -> None:
        """Cleanup resources — called by ComputerUseToolset on shutdown."""
        await self.stop()

    def _check_cancel(self) -> None:
        """Check session cancel flag and raise BargeInException if set."""
        from services.session_service import get_cancel_flag
        if get_cancel_flag(self.session_id).is_set():
            raise BargeInException(f"Barge-in detected for session {self.session_id}")

    async def _current_screenshot(self) -> bytes:
        """Capture a PNG screenshot of the current viewport."""
        if not self.page:
            return b""
        return await self.page.screenshot(full_page=False)

    async def _state(self) -> ComputerState:
        """Build the current ComputerState (screenshot + URL)."""
        screenshot = await self._current_screenshot()
        url = self.page.url if self.page else None
        return ComputerState(screenshot=screenshot, url=url)

    # ──────────────────────────── BaseComputer interface ──────────────────────

    async def screen_size(self) -> tuple[int, int]:
        """Returns the (width, height) of the browser viewport."""
        return (DEFAULT_SCREEN_WIDTH, DEFAULT_SCREEN_HEIGHT)

    async def environment(self) -> ComputerEnvironment:
        """Returns ENVIRONMENT_BROWSER — we always operate in a web browser."""
        return ComputerEnvironment.ENVIRONMENT_BROWSER

    async def current_state(self) -> ComputerState:
        """Returns the current browser state (screenshot + URL)."""
        self._check_cancel()
        state = await self._state()
        self._check_cancel()
        return state

    async def open_web_browser(self) -> ComputerState:
        """Open web browser. No-op if already started; navigates to blank page."""
        self._check_cancel()
        if not self.page:
            await self.start()
        await self.page.goto("about:blank")
        state = await self._state()
        self._check_cancel()
        return state

    async def navigate(self, url: str) -> ComputerState:
        """Navigate to a URL using networkidle wait with 15 000ms timeout."""
        self._check_cancel()
        await self.page.goto(url, wait_until="networkidle", timeout=15_000)
        state = await self._state()
        self._check_cancel()
        return state

    async def click_at(self, x: int, y: int) -> ComputerState:
        """Click at viewport-absolute coordinates (x, y)."""
        self._check_cancel()
        await self.page.mouse.click(x, y)
        state = await self._state()
        self._check_cancel()
        return state

    async def hover_at(self, x: int, y: int) -> ComputerState:
        """Hover at viewport-absolute coordinates (x, y)."""
        self._check_cancel()
        await self.page.mouse.move(x, y)
        state = await self._state()
        self._check_cancel()
        return state

    async def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool = True,
        clear_before_typing: bool = True,
    ) -> ComputerState:
        """Click at (x, y) then type text; optionally press Enter after."""
        self._check_cancel()
        await self.page.mouse.click(x, y)
        self._check_cancel()
        if clear_before_typing:
            await self.page.keyboard.press("Control+a")
            self._check_cancel()
        await self.page.keyboard.type(text, delay=30)
        self._check_cancel()
        if press_enter:
            await self.page.keyboard.press("Enter")
        state = await self._state()
        self._check_cancel()
        return state

    async def scroll_document(
        self, direction: Literal["up", "down", "left", "right"]
    ) -> ComputerState:
        """Scroll the whole page in the given direction by ~500px."""
        self._check_cancel()
        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = 500
        elif direction == "up":
            delta_y = -500
        elif direction == "right":
            delta_x = 500
        elif direction == "left":
            delta_x = -500
        await self.page.mouse.wheel(delta_x, delta_y)
        state = await self._state()
        self._check_cancel()
        return state

    async def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int,
    ) -> ComputerState:
        """Scroll at coordinates (x, y) by `magnitude` pixels in `direction`."""
        self._check_cancel()
        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = magnitude
        elif direction == "up":
            delta_y = -magnitude
        elif direction == "right":
            delta_x = magnitude
        elif direction == "left":
            delta_x = -magnitude
        await self.page.mouse.move(x, y)
        await self.page.mouse.wheel(delta_x, delta_y)
        state = await self._state()
        self._check_cancel()
        return state

    async def wait(self, seconds: int) -> ComputerState:
        """Wait for `seconds` seconds."""
        self._check_cancel()
        await asyncio.sleep(seconds)
        state = await self._state()
        self._check_cancel()
        return state

    async def go_back(self) -> ComputerState:
        """Navigate back in browser history."""
        self._check_cancel()
        await self.page.go_back()
        state = await self._state()
        self._check_cancel()
        return state

    async def go_forward(self) -> ComputerState:
        """Navigate forward in browser history."""
        self._check_cancel()
        await self.page.go_forward()
        state = await self._state()
        self._check_cancel()
        return state

    async def search(self) -> ComputerState:
        """Navigate to Google search to start a fresh search."""
        self._check_cancel()
        await self.page.goto("https://www.google.com", wait_until="networkidle", timeout=15_000)
        state = await self._state()
        self._check_cancel()
        return state

    async def key_combination(self, keys: list[str]) -> ComputerState:
        """Press a key combination (e.g., ['Control', 'c'])."""
        self._check_cancel()
        combo = "+".join(keys)
        await self.page.keyboard.press(combo)
        state = await self._state()
        self._check_cancel()
        return state

    async def drag_and_drop(
        self, x: int, y: int, destination_x: int, destination_y: int
    ) -> ComputerState:
        """Drag from (x, y) and drop at (destination_x, destination_y)."""
        self._check_cancel()
        await self.page.mouse.move(x, y)
        await self.page.mouse.down()
        await self.page.mouse.move(destination_x, destination_y)
        await self.page.mouse.up()
        state = await self._state()
        self._check_cancel()
        return state

    # ──────────────────────────── Convenience helpers ─────────────────────────
    # These wrap BaseComputer methods for callers that prefer the story-spec API.

    async def screenshot(self) -> bytes:
        """Return PNG bytes of the current viewport — NOT full_page (perf)."""
        return await self._current_screenshot()

    async def click(self, target) -> ComputerState:
        """
        Click using a bounding-box dict {x, y, width, height} or CSS selector string.

        Bounding box → center click via mouse coordinates (Computer Use model output).
        String → CSS selector click.
        Retries up to 2 times on failure.
        """
        self._check_cancel()
        last_exc = None
        for attempt in range(3):
            try:
                if isinstance(target, dict):
                    cx = target["x"] + target["width"] // 2
                    cy = target["y"] + target["height"] // 2
                    await self.page.mouse.click(cx, cy)
                else:
                    await self.page.click(str(target))
                break
            except Exception as exc:
                last_exc = exc
                if attempt == 2:
                    raise
                await asyncio.sleep(0.3)
                self._check_cancel()
        state = await self._state()
        self._check_cancel()
        return state

    async def type_text(self, selector: str, text: str) -> ComputerState:
        """Click a selector then type text at 30ms/char delay."""
        self._check_cancel()
        await self.page.click(selector)
        self._check_cancel()
        await self.page.keyboard.type(text, delay=30)
        state = await self._state()
        self._check_cancel()
        return state

    async def detect_captcha(self) -> bool:
        """
        Heuristic CAPTCHA detection — scans page HTML and title for known CAPTCHA signatures.

        Checks for: reCAPTCHA, hCaptcha, Cloudflare Turnstile / Challenge, generic 'captcha'.
        Returns True if any match found, False otherwise.
        Non-fatal: returns False on any error so execution is never aborted by detection.
        """
        try:
            html = await self.page.content()
            if _CAPTCHA_RE.search(html):
                return True
            title = await self.page.title()
            if _CAPTCHA_RE.search(title):
                return True
        except Exception:
            return False
        return False

    async def read_page(self, selector: Optional[str] = None) -> str:
        """
        Extract inner text from `selector` (or `body` if None).
        Wraps output in <page_content> to mark it as untrusted data.
        """
        self._check_cancel()
        target = selector if selector else "body"
        text = await self.page.inner_text(target)
        self._check_cancel()
        return f"<page_content>\n{text}\n</page_content>"
