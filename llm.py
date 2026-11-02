"""Gemini (free tier) wrapper: burn-only Q&A and burn photo analysis."""

import asyncio
import json
import logging
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from prompts import IMAGE_SYSTEM_PROMPT, TEXT_SYSTEM_PROMPT
from tbsa import Depth, Region

log = logging.getLogger(__name__)

QUOTA_COOLDOWN_S = 30 * 60  # free tier: 20 requests/day per model, so skip exhausted ones


class TextReply(BaseModel):
    in_scope: bool
    answer: str


class RegionFinding(BaseModel):
    region: Region
    fraction: float = Field(description="0.0-1.0 of that whole region that is burned")
    depth: Depth


class ImageFindings(BaseModel):
    is_burn: bool
    description: str
    regions: list[RegionFinding]
    circumferential: bool
    red_flags: list[str]


class LLMError(Exception):
    pass


class BurnLLM:
    def __init__(self, api_key: str, models: list[str], emergency_numbers: str):
        self._client = genai.Client(api_key=api_key)
        self._models = models  # tried in order; free-tier models are often overloaded
        self._cooldown_until: dict[str, float] = {}
        self._emergency_numbers = emergency_numbers

    async def _generate(self, contents, system_prompt: str, schema: type[BaseModel]):
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        response = None
        for model in self._models:
            if self._cooldown_until.get(model, 0) > time.monotonic():
                continue
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model, contents=contents, config=config
                    ),
                    timeout=12,
                )
                break
            except Exception as exc:  # overload (503), quota (429), network, safety blocks, timeout
                log.warning("Gemini model %s failed: %s", model, str(exc)[:120])
                message = str(exc)
                if "RESOURCE_EXHAUSTED" in message:
                    self._cooldown_until[model] = time.monotonic() + QUOTA_COOLDOWN_S
                elif "503" in message or "UNAVAILABLE" in message or isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
                    # Avoid retrying an overloaded or timed-out model on every user turn.
                    self._cooldown_until[model] = time.monotonic() + 120
        if response is None:
            log.error("All Gemini models failed or are out of quota")
            raise LLMError("all models failed")

        if isinstance(response.parsed, schema):
            return response.parsed
        try:
            return schema.model_validate(json.loads(response.text or ""))
        except Exception as exc:
            log.error("Unparseable Gemini response: %r", response.text)
            raise LLMError("unparseable response") from exc

    async def answer(self, question: str, history: list[tuple[str, str]], language: str) -> TextReply:
        """history: previous (role, text) turns, role is "user" or "model"."""
        contents = [
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
            for role, text in history
        ]
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
        prompt = TEXT_SYSTEM_PROMPT.format(emergency_numbers=self._emergency_numbers, language=language)
        return await self._generate(contents, prompt, TextReply)

    async def analyze_image(self, image: bytes, mime_type: str, caption: str, language: str) -> ImageFindings:
        parts = [types.Part.from_bytes(data=image, mime_type=mime_type)]
        parts.append(types.Part.from_text(
            text=f"User caption: {caption}" if caption else "No caption was provided."
        ))
        return await self._generate(
            [types.Content(role="user", parts=parts)], IMAGE_SYSTEM_PROMPT.format(language=language), ImageFindings
        )
