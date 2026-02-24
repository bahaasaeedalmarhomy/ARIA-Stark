import os
from dotenv import load_dotenv

load_dotenv()

# Playwright launch args required for containerized environments:
# --no-sandbox: required because Docker containers run as root
# --disable-dev-shm-usage: Cloud Run /dev/shm is limited (64MB); prevents crashes
PLAYWRIGHT_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


async def launch_chromium():
    """
    Launch a Chromium browser instance with Cloud Run-compatible settings.
    Stub: full ComputerUseToolset integration will be added in Story 3.1.
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
