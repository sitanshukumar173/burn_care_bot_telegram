import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_token: str
    gemini_api_key: str
    gemini_models: list[str]
    gemini_vision_models: list[str]
    vision_provider: str
    groq_api_key: str
    groq_vision_model: str
    emergency_numbers: str
    osm_user_agent: str
    analytics_database: str
    google_sheets_id: str
    google_service_account_file: str


def load_config() -> Config:
    vision_provider = os.getenv("VISION_PROVIDER", "gemini").strip().lower()
    required = ["TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY"]
    if vision_provider == "groq":
        required.append("GROQ_API_KEY")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)} (see .env.example)")
    return Config(
        telegram_token=os.environ["TELEGRAM_BOT_TOKEN"],
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        gemini_models=[m.strip() for m in os.getenv(
            "GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3.5-flash,gemini-3.6-flash,gemini-3.8-flash,gemini-3.7-flash,gemini-3-flash-preview,gemini-flash-latest"
        ).split(",") if m.strip()],
        gemini_vision_models=[m.strip() for m in os.getenv(
            "GEMINI_VISION_MODELS", os.getenv(
                "GEMINI_MODELS",
                "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest",
            )
        ).split(",") if m.strip()],
        vision_provider=vision_provider,
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_vision_model=os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
        emergency_numbers=os.getenv("EMERGENCY_NUMBERS", "112 (emergency) / 108 (ambulance)"),
        osm_user_agent=os.getenv("OSM_USER_AGENT", "BurnCareTelegramBot/1.0"),
        analytics_database=os.getenv("ANALYTICS_DATABASE", "analytics.db"),
        google_sheets_id=os.getenv("GOOGLE_SHEETS_ID", ""),
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
    )
