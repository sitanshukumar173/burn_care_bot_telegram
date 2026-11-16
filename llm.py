"""Gemini (free tier) wrapper: burn-only Q&A and burn photo analysis."""

import asyncio
import base64
import json
import logging

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from prompts import IMAGE_SYSTEM_PROMPT, TEXT_SYSTEM_PROMPT
from tbsa import Depth, Region

log = logging.getLogger(__name__)

_REGION_VALUES = {region.value for region in Region}
_SIDELESS_REGIONS = {
    "upper_arm_front",
    "upper_arm_back",
    "forearm_front",
    "forearm_back",
    "hand_palm",
    "hand_back",
    "thigh_front",
    "thigh_back",
    "lower_leg_front",
    "lower_leg_back",
    "foot_top",
    "foot_sole",
}
_MECHANISMS = {
    "thermal_or_contact",
    "chemical_possible",
    "electrical_possible",
    "friction_possible",
    "sun_or_radiation_possible",
    "unknown",
}


def _normalize_vision_payload(payload: dict) -> dict:
    """Normalize common bare-region outputs from providers without inventing a side."""
    side_uncertain = bool(payload.get("side_uncertain", False))
    for finding in payload.get("regions", []):
        raw_region = str(finding.get("region", "")).strip().lower().replace(" ", "_")
        if raw_region in _SIDELESS_REGIONS:
            finding["region"] = f"right_{raw_region}"
            side_uncertain = True
        elif raw_region in _REGION_VALUES:
            finding["region"] = raw_region
        else:
            finding["region"] = raw_region
    payload["side_uncertain"] = side_uncertain
    mechanism = str(payload.get("mechanism", "unknown")).strip().lower()
    payload["mechanism"] = mechanism if mechanism in _MECHANISMS else "unknown"
    return payload


class TextReply(BaseModel):
    in_scope: bool
    answer: str


class RegionFinding(BaseModel):
    region: Region
    fraction: float = Field(
        description="0.0-1.0 of that whole region that is burned")
    depth: Depth


class ImageFindings(BaseModel):
    is_burn: bool
    description: str
    regions: list[RegionFinding]
    circumferential: bool
    red_flags: list[str]
    side_uncertain: bool = False
    mechanism: str = "unknown"


class LLMError(Exception):
    pass


class BurnLLM:
    def __init__(
        self,
        api_key: str,
        models: list[str],
        emergency_numbers: str,
        vision_models: list[str] | None = None,
        vision_provider: str = "gemini",
        groq_api_key: str = "",
        groq_vision_model: str = "qwen/qwen3.8-27b",
    ):
        self._client = genai.Client(api_key=api_key)
        self._models = models  # tried in order; free-tier models are often overloaded
        self._vision_models = vision_models or models
        self._vision_provider = vision_provider
        self._groq_api_key = groq_api_key
        self._groq_vision_model = groq_vision_model
        self._emergency_numbers = emergency_numbers

    async def _generate(
        self,
        contents,
        system_prompt: str,
        schema: type[BaseModel],
        max_tokens: int = 500,
        timeout: float = 10.0,
        models: list[str] | None = None,
    ):
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
            max_output_tokens=max_tokens,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True),
        )
        response = None
        for model in models or self._models:
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model, contents=contents, config=config
                    ),
                    timeout=timeout,
                )
                break
            # overload (503), quota (429), network, safety blocks, timeout
            except Exception as exc:
                err_text = str(exc)[:120] or type(exc).__name__
                log.warning("Gemini model %s failed: %s", model, err_text)
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

    async def answer(
        self,
        question: str,
        history: list[tuple[str, str]],
        language: str,
        recent_context: str = "",
    ) -> TextReply:
        """history: previous (role, text) turns, role is "user" or "model"."""
        contents = [
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
            for role, text in history
        ]
        contents.append(types.Content(role="user", parts=[
                        types.Part.from_text(text=question)]))
        prompt = TEXT_SYSTEM_PROMPT.format(
            emergency_numbers=self._emergency_numbers,
            language=language,
            conversation_context=recent_context or "No additional burn or hospital context is available.",
        )
        return await self._generate(contents, prompt, TextReply, max_tokens=500, timeout=8.0)

    async def analyze_image(self, image: bytes, mime_type: str, caption: str, language: str) -> ImageFindings:
        if self._vision_provider == "groq":
            try:
                return await self._analyze_image_groq(image, mime_type, caption, language)
            except LLMError:
                log.warning("Groq vision output failed validation; falling back to Gemini vision")
        return await self._analyze_image_gemini(image, mime_type, caption, language)

    async def _analyze_image_gemini(
        self, image: bytes, mime_type: str, caption: str, language: str
    ) -> ImageFindings:
        parts = [types.Part.from_bytes(data=image, mime_type=mime_type)]
        parts.append(types.Part.from_text(
            text=f"User caption: {caption}" if caption else "No caption was provided."
        ))
        return await self._generate(
            [types.Content(role="user", parts=parts)],
            IMAGE_SYSTEM_PROMPT.format(language=language),
            ImageFindings,
            max_tokens=600,
            timeout=12.0,
            models=self._vision_models,
        )

    async def _analyze_image_groq(
        self, image: bytes, mime_type: str, caption: str, language: str
    ) -> ImageFindings:
        image_data = base64.b64encode(image).decode("ascii")
        prompt = IMAGE_SYSTEM_PROMPT.format(language=language)
        user_text = f"User caption: {caption}" if caption else "No caption was provided."
        payload = {
            "model": self._groq_vision_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}",
                            },
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_completion_tokens": 600,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._groq_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            payload = _normalize_vision_payload(json.loads(content))
            return ImageFindings.model_validate(payload)
        except Exception as exc:
            log.error("Groq vision analysis failed: %s", str(exc)[:200])
            raise LLMError("vision model failed") from exc
