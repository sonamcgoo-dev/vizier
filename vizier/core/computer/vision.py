"""
Computer-use: vision analysis.

Sends a screenshot to the local LLM along with a text query so the model
can 'see' the screen and reason about what's happening.  Falls back to
OCR when the model is not vision-capable.
"""
from __future__ import annotations

import logging

from vizier.core.computer.screen import ScreenCapture

log = logging.getLogger("vizier.computer.vision")


class VisionAnalyzer:
    """Analyse screenshots using the local LLM (or OCR fallback)."""

    def __init__(
        self,
        screen: ScreenCapture,
        llm_provider=None,
    ):
        self.screen = screen
        self.llm_provider = llm_provider

    @property
    def has_vision(self) -> bool:
        """Whether the attached LLM supports image inputs."""
        if self.llm_provider and hasattr(self.llm_provider, "supports_vision"):
            return self.llm_provider.supports_vision()
        return False

    async def describe_screen(
        self,
        query: str = "Describe what you see on the screen in detail.",
        region: tuple[int, int, int, int] | None = None,
        scale: float = 0.5,
    ) -> str:
        """Take a screenshot, send it to the LLM with *query*, and return the description."""
        img_path = self.screen.screenshot(region=region, scale=scale)

        if self.llm_provider is None:
            return (
                f"Screenshot saved to {img_path}. "
                "No vision-capable LLM is connected. "
                "OCR text:\n" + self._ocr_fallback(img_path, region)
            )

        try:
            msg = await self.llm_provider.analyze_image(img_path, query)
            if msg:
                return msg
        except Exception as e:
            log.warning(f"Vision analysis failed: {e}")

        return self._ocr_fallback(img_path, region)

    def _ocr_fallback(self, img_path: str, region=None) -> str:
        """Use OCR to extract text from the screenshot as a fallback."""
        try:
            text = self.screen.ocr_region(image_path=img_path)
            if text:
                return text
            return "[No text detected by OCR]"
        except Exception as e:
            return f"[OCR failed: {e}]"
