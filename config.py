import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_token: str
    gemini_api_key: str
    gemini_models: list[str]
    emergency_numbers: str
    osm_user_agent: str


def load_config() -> Config:
    missing = [k for k in ("TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY") if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)} (see .env.example)")
    return Config(
        telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        gemini_models=[m.strip() for m in os.getenv(
            "GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3.5-flash,gemini-3.6-flash,gemini-3.8-flash,gemini-3.7-flash,gemini-3-flash-preview,gemini-flash-latest"
        ).split(",") if m.strip()],
        emergency_numbers=os.getenv("EMERGENCY_NUMBERS", "112 (emergency) / 108 (ambulance)"),
        osm_user_agent=os.getenv("OSM_USER_AGENT", "BurnCareTelegramBot/1.0"),
    )
