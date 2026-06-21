"""Record a live Claude agent playing Minecraft with Playwright."""
import asyncio, subprocess, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="C:/Users/lokas/mc-speedrun-rl/recordings/live",
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto("http://localhost:3007")
        await page.wait_for_timeout(3000)
        print("Recording started - viewer open", flush=True)
        print("Waiting for agent to finish (or Ctrl+C to stop)...", flush=True)

        # Just keep recording until interrupted
        try:
            while True:
                await page.wait_for_timeout(5000)
        except KeyboardInterrupt:
            pass

        await context.close()
        await browser.close()
        print("\nVideo saved to recordings/live/", flush=True)

asyncio.run(main())
