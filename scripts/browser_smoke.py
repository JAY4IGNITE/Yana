import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
            ],
        )
        page = await browser.new_page(viewport={"width": 380, "height": 540})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto("http://127.0.0.1:5173")
        await page.get_by_role("combobox", name="Assistant mode").select_option("agent")
        await page.get_by_role("textbox").fill("Show system info")
        await page.get_by_role("button", name="Send Message").click()
        await page.get_by_text("Completed", exact=True).wait_for(timeout=45000)
        await page.get_by_text("View result for step 1", exact=True).click()
        assert await page.locator("details pre").inner_text()
        composer = await page.get_by_role("textbox").bounding_box()
        assert composer and composer["y"] + composer["height"] <= 540, composer
        await page.screenshot(path=str(output / "assistant-task.png"), full_page=True)
        print(json.dumps({"taskCompleted": True, "pageErrors": errors}))
        await page.get_by_role("button", name="Settings", exact=True).click()
        await page.get_by_role("button", name="Restart", exact=True).click()
        await page.get_by_role("status").filter(has_text="For browser preview").wait_for()
        await page.screenshot(path=str(output / "assistant-general-settings.png"), full_page=True)
        await page.get_by_text("Voice & Audio", exact=True).click()
        await page.screenshot(
            path=str(output / "assistant-settings.png"), full_page=True
        )
        print(
            "Settings visible:",
            await page.get_by_label("Microphone Input").is_visible(),
        )
        await page.get_by_role("button", name="Close Settings").click()
        await page.get_by_text("Dismiss", exact=True).click()
        uploaded = []

        async def transcribe(route):
            wav = route.request.post_data_buffer
            assert wav and wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
            assert int.from_bytes(wav[24:28], "little") == 16000
            assert len(wav) > 44
            uploaded.append(len(wav))
            await route.fulfill(json={"transcript": "Show system info"})

        await page.route("**/api/voice/transcribe", transcribe)
        await page.get_by_role("button", name="Toggle Microphone").click()
        await page.get_by_title("Stop listening", exact=True).wait_for()
        # Give the fake microphone enough samples for a real MediaRecorder clip.
        await page.wait_for_timeout(600)
        await page.get_by_role("button", name="Toggle Microphone").click()
        await page.get_by_text("Completed", exact=True).wait_for(timeout=45000)
        assert uploaded
        assert not errors, errors
        print(
            json.dumps(
                {
                    "voiceCaptureWavBytes": uploaded,
                    "voiceTaskCompleted": True,
                    "transcription": "stubbed; no microphone audio sent externally",
                }
            )
        )
        await browser.close()


asyncio.run(main())
