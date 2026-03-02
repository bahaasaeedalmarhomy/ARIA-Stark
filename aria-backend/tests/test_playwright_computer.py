"""
Unit tests for Story 3.2: Playwright Browser Actions — PlaywrightComputer methods.

AC coverage map:
  AC 1 (navigate/networkidle)           : test_navigate_goto_args, test_navigate_check_cancel_called_twice
  AC 2 (click/bbox/selector/retry)      : test_click_bbox_center, test_click_css_selector,
                                          test_click_retry_succeeds_on_third, test_click_exhausted_retries
  AC 3 (type/delay=30)                  : test_type_text_delay, test_type_text_at_delay
  AC 4 (scroll)                         : test_scroll_document_down, test_scroll_document_up
  AC 5 (read_page)                      : test_read_page_body, test_read_page_selector
  AC 6 (BargeInException / cancel flag) : See test_executor_agent.py::test_check_cancel_raises_barge_in_exception_when_flag_set
                                          (DO NOT duplicate — referenced in docstring only)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tools.playwright_computer import PlaywrightComputer, BargeInException


# ─────────────────────── Helpers ─────────────────────────────────────────────

def _make_pc(session_id: str = "test-session") -> PlaywrightComputer:
    """Return a PlaywrightComputer with a mock page and no-op _check_cancel."""
    pc = PlaywrightComputer(session_id=session_id)
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"
    mock_page.screenshot = AsyncMock(return_value=b"\x89PNG")
    mock_page.inner_text = AsyncMock(return_value="page text")
    pc.page = mock_page
    pc._check_cancel = MagicMock()  # no-op by default
    return pc


# ──────────────────────────────────────────────────────────────────────────────
# AC 1 — navigate (FR8, FR15)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_navigate_goto_args():
    """navigate must call page.goto with wait_until='networkidle' and timeout=15_000 (AC: 1)."""
    pc = _make_pc()
    await pc.navigate("https://example.com")

    pc.page.goto.assert_called_once_with(
        "https://example.com",
        wait_until="networkidle",
        timeout=15_000,
    )


@pytest.mark.asyncio
async def test_navigate_check_cancel_called_twice():
    """
    navigate must call _check_cancel both BEFORE and AFTER page.goto (cancel flag guard, AC: 1).

    Note: BargeInException raised from _check_cancel is covered by
    test_executor_agent.py::test_check_cancel_raises_barge_in_exception_when_flag_set (AC: 6).
    """
    pc = _make_pc()
    check_count = 0

    def _counting_check():
        nonlocal check_count
        check_count += 1

    pc._check_cancel = _counting_check
    await pc.navigate("https://example.com")

    assert check_count == 2, (
        f"Expected _check_cancel called 2× (before + after goto), got {check_count}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# AC 2 — click (FR9, FR14)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_click_bbox_center():
    """click with bbox dict {x:10, y:20, w:50, h:30} must call mouse.click at center (35, 35) (AC: 2)."""
    pc = _make_pc()
    bbox = {"x": 10, "y": 20, "width": 50, "height": 30}
    await pc.click(bbox)

    # cx = 10 + 50//2 = 35; cy = 20 + 30//2 = 35
    pc.page.mouse.click.assert_called_once_with(35, 35)


@pytest.mark.asyncio
async def test_click_css_selector():
    """click with CSS selector string must call page.click with that selector (AC: 2)."""
    pc = _make_pc()
    await pc.click("#submit-btn")

    pc.page.click.assert_called_once_with("#submit-btn")


@pytest.mark.asyncio
async def test_click_retry_succeeds_on_third():
    """
    click must retry up to 2 times on failure and succeed on the 3rd attempt
    without raising an exception (AC: 2, retry logic for AC: 6).
    """
    pc = _make_pc()

    call_count = 0

    async def _flaky_click(x, y):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("element not found")

    pc.page.mouse.click = _flaky_click

    # Should NOT raise — third attempt succeeds
    await pc.click({"x": 0, "y": 0, "width": 10, "height": 10})

    assert call_count == 3, f"Expected 3 click attempts, got {call_count}"


@pytest.mark.asyncio
async def test_click_exhausted_retries():
    """click must propagate exception after all 3 attempts fail (AC: 2, failure path for AC: 6)."""
    pc = _make_pc()
    pc.page.mouse.click = AsyncMock(side_effect=RuntimeError("permanently broken"))

    with pytest.raises(RuntimeError, match="permanently broken"):
        await pc.click({"x": 0, "y": 0, "width": 10, "height": 10})

    assert pc.page.mouse.click.call_count == 3, (
        f"Expected exactly 3 click attempts, got {pc.page.mouse.click.call_count}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# AC 3 — type (FR10)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_type_text_delay():
    """type_text must call keyboard.type with delay=30 (AC: 3)."""
    pc = _make_pc()
    await pc.type_text("#email", "hello@example.com")

    pc.page.click.assert_called_once_with("#email")
    pc.page.keyboard.type.assert_called_once_with("hello@example.com", delay=30)


@pytest.mark.asyncio
async def test_type_text_at_delay():
    """type_text_at must call keyboard.type with delay=30 (AC: 3)."""
    pc = _make_pc()
    await pc.type_text_at(100, 200, "test text", press_enter=False, clear_before_typing=False)

    pc.page.mouse.click.assert_called_once_with(100, 200)
    pc.page.keyboard.type.assert_called_once_with("test text", delay=30)


# ──────────────────────────────────────────────────────────────────────────────
# AC 4 — scroll (FR11)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scroll_document_down():
    """scroll_document('down') must call mouse.wheel with delta_y=500 (AC: 4)."""
    pc = _make_pc()
    await pc.scroll_document("down")

    pc.page.mouse.wheel.assert_called_once_with(0, 500)


@pytest.mark.asyncio
async def test_scroll_document_up():
    """scroll_document('up') must call mouse.wheel with delta_y=-500 (AC: 4)."""
    pc = _make_pc()
    await pc.scroll_document("up")

    pc.page.mouse.wheel.assert_called_once_with(0, -500)


# ──────────────────────────────────────────────────────────────────────────────
# AC 5 — read_page (FR13)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_page_body():
    """read_page(None) must call page.inner_text('body') and wrap in <page_content> (AC: 5)."""
    pc = _make_pc()
    pc.page.inner_text = AsyncMock(return_value="some content")

    result = await pc.read_page(None)

    pc.page.inner_text.assert_called_once_with("body")
    assert "<page_content>" in result
    assert "some content" in result
    assert "</page_content>" in result


@pytest.mark.asyncio
async def test_read_page_selector():
    """read_page('#main') must call page.inner_text('#main') (AC: 5)."""
    pc = _make_pc()
    pc.page.inner_text = AsyncMock(return_value="main content")

    result = await pc.read_page("#main")

    pc.page.inner_text.assert_called_once_with("#main")
    assert "main content" in result


# ──────────────────────────────────────────────────────────────────────────────
# Story 3.4 — detect_captcha (AC: 3)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_captcha_true_when_recaptcha_in_page():
    """detect_captcha returns True when page HTML contains reCAPTCHA signature (AC: 3)."""
    pc = _make_pc()
    pc.page.content = AsyncMock(return_value="<div class='g-recaptcha'></div>")
    pc.page.title = AsyncMock(return_value="Checkout")

    result = await pc.detect_captcha()

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_true_when_hcaptcha_in_page():
    """detect_captcha returns True when page HTML contains hCaptcha signature (AC: 3)."""
    pc = _make_pc()
    pc.page.content = AsyncMock(return_value="<div class='h-captcha' data-sitekey='key'></div>")
    pc.page.title = AsyncMock(return_value="Login")

    result = await pc.detect_captcha()

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_true_when_captcha_in_title():
    """detect_captcha returns True when page title contains 'captcha' (AC: 3)."""
    pc = _make_pc()
    pc.page.content = AsyncMock(return_value="<html><body>Normal page</body></html>")
    pc.page.title = AsyncMock(return_value="Just a CAPTCHA challenge")

    result = await pc.detect_captcha()

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_false_when_normal_page():
    """detect_captcha returns False when page has no CAPTCHA signatures (AC: 3)."""
    pc = _make_pc()
    pc.page.content = AsyncMock(return_value="<html><body><h1>Welcome</h1></body></html>")
    pc.page.title = AsyncMock(return_value="Welcome — Shop")

    result = await pc.detect_captcha()

    assert result is False


@pytest.mark.asyncio
async def test_detect_captcha_returns_false_on_exception():
    """detect_captcha returns False (non-fatal) when page.content() raises (AC: 3)."""
    pc = _make_pc()
    pc.page.content = AsyncMock(side_effect=RuntimeError("page crash"))

    result = await pc.detect_captcha()

    assert result is False
