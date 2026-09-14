"""Multimodal Vision Engine for analyzing images, diagrams, and desktop screenshots."""

import base64
import io

from openai import AsyncOpenAI
from PIL import Image

from app.config import settings
from app.errors import AIError
from app.logger import logger


class MultimodalVisionEngine:
    """Processes images and desktop screenshots using multimodal vision LLMs."""

    def __init__(self) -> None:
        key = settings.ai_heavy_api_key.get_secret_value() or settings.ai_api_key.get_secret_value()
        base_url = settings.ai_heavy_base_url or settings.ai_base_url
        self.model = settings.ai_heavy_model or "meta/llama-3.2-11b-vision-instruct"

        self.client = AsyncOpenAI(
            api_key=key or "dummy-key",
            base_url=base_url,
            timeout=float(settings.tool_timeout_seconds),
        )

    def encode_image_bytes(self, image_bytes: bytes, max_dimension: int = 1280) -> str:
        """Compress and encode image bytes into a base64 JPEG string."""
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            img = raw_img.convert("RGB")
            # Resize if large to preserve bandwidth
            if max(img.width, img.height) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str = "Describe what is in this image in detail.",
    ) -> str:
        """Send image and prompt to vision model for analysis."""
        try:
            b64_img = self.encode_image_bytes(image_bytes)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                            },
                        ],
                    }
                ],
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return content or "No description generated."
        except Exception as e:
            logger.error("Multimodal vision analysis failed: %s", e)
            raise AIError(f"Vision analysis failed: {e}") from e

    async def analyze_screen(
        self,
        prompt: str = "Analyze the active screen and describe the open application or interface.",
    ) -> str:
        """Capture the current Windows desktop screen and describe it."""
        try:
            from PIL import ImageGrab

            screenshot = ImageGrab.grab()
            buf = io.BytesIO()
            screenshot.save(buf, format="JPEG", quality=85)
            return await self.analyze_image(buf.getvalue(), prompt)
        except Exception as e:
            logger.error("Screen capture or vision analysis failed: %s", e)
            raise AIError(f"Desktop screen analysis failed: {e}") from e


vision_engine = MultimodalVisionEngine()
