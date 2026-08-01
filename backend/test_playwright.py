import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://instagram.com")
        print("Browser opened")
        await asyncio.sleep(10)
        await browser.close()

asyncio.run(test())
