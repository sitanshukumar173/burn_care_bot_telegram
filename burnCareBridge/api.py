"""BurnCare bridge API.

Thin HTTP wrapper around the deployed CSJMU BurnCare Saathi Telegram bot code.
It imports the bot's own modules (llm.py, tbsa.py, hospitals.py, i18n.py) at
runtime, so every answer, photo report, TBSA calculation and hospital lookup is
exactly what the Telegram bot produces — nothing is reimplemented.

Run on the EC2 host where the bot is already deployed. Set BOT_REPO to the
path of the bot clone on that machine. Secrets stay on the server: the bot's
.env is loaded here and keys are never returned in any response.
"""

import html
import io
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

def _bot_repo_path() -> Path:
    configured = os.environ.get("BOT_REPO")
    if configured:
        return Path(configured).expanduser().resolve()

    candidates = (
        Path(__file__).parent / "burn_care_bot_telegram",
        Path(__file__).parent.parent / "burn-care-bot",
        Path(__file__).parent.parent,
    )
    for candidate in candidates:
        if (candidate / "config.py").is_file() and (candidate / "llm.py").is_file():
            return candidate.resolve()
    return candidates[0].resolve()


BOT_REPO = _bot_repo_path()
load_dotenv(BOT_REPO / ".env")  # TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, GEMINI_MODELS, ...

import sys
sys.path.insert(0, str(BOT_REPO))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import load_config
from i18n import (
    AGE_LABELS,
    CHOOSE_LANGUAGE,
    DEFAULT_LANG,
    LANGS,
    LLM_LANGUAGE,
    age_label,
    depth_label,
    region_name,
    t,
)
from tbsa import (
    CHILD_GROUPS,
    DEPTH_ORDER,
    AgeGroup,
    BurnCase,
    Depth,
    Region,
    RegionBurn,
    assess,
    parkland_ml,
)
from hospitals import HospitalFinder
from llm import BurnLLM, LLMError
import re

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("burnbridge")

EMERGENCY_RE = re.compile(
    r"large|face|chemical|electric|breath|unconscious|infant|baby|severe|inhalation|smoke"
    r"|बड़ा|चेहरा|रसायन|बिजली|साँस|बेहोश|गंभीर",
    re.IGNORECASE,
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="BurnCare Bridge", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_config = None
_llm = None
_finder = None


def get_config():
    global _config
    if _config is None:
        try:
            _config = load_config()
        except SystemExit as exc:
            raise HTTPException(status_code=503, detail=f"Server not configured: {exc}")
    return _config


def get_llm() -> BurnLLM:
    global _llm
    if _llm is None:
        cfg = get_config()
        _llm = BurnLLM(cfg.gemini_api_key, cfg.gemini_models, cfg.emergency_numbers)
    return _llm


def get_finder() -> HospitalFinder:
    global _finder
    if _finder is None:
        _finder = HospitalFinder(get_config().osm_user_agent)
    return _finder


def lang_or_default(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def _safe_t(lang: str, key: str, numbers: str) -> str:
    """t() with {numbers} filled in; fall back to raw text, then empty string."""
    for kwargs in ({"numbers": numbers}, {}):
        try:
            return t(lang, key, **kwargs)
        except Exception:
            continue
    log.warning("i18n key %s unavailable", key)
    return ""


def optimize_image(raw_bytes: bytes, max_dim: int = 1200, quality: int = 85):
    """Same optimization the Telegram bot applies before calling Gemini."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception as exc:  # keep bot's fallback behaviour
        log.warning("Image optimization fallback: %s", exc)
        return raw_bytes, "image/jpeg"


@app.get("/api/health")
def health():
    return {"ok": True, "service": "burncare-bridge"}


@app.get("/api/strings")
def strings(lang: str | None = None):
    lang = lang_or_default(lang)
    numbers = get_config().emergency_numbers
    keys = (
        "welcome", "help", "first_aid", "prevention", "formula", "photo_tips",
        "llm_down", "out_of_scope", "photo_failed", "image_too_large", "not_burn",
        "age_question", "age_set", "send_photo_first", "reset_done",
        "ask_place", "place_not_found", "your_location",
        "hospitals_title", "emergency_line", "kind_hospital", "kind_clinic",
        "tag_burn", "tag_major", "directions", "hospitals_footer",
        "map_down", "no_hospitals", "disclaimer", "generic_error",
    )
    out = {}
    for key in keys:
        out[key] = _safe_t(lang, key, numbers)
    out["emergency_numbers"] = numbers
    out["age_options"] = [{"value": g.value, "label": age_label(g, lang)} for g in AgeGroup]
    out["choose_language"] = CHOOSE_LANGUAGE
    return out


# ---------------- chat ----------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[tuple[str, str]] = Field(default_factory=list)
    lang: str | None = None


@app.post("/api/chat")
async def chat(body: ChatRequest):
    cfg = get_config()
    lang = lang_or_default(body.lang)
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")

    history = [(role, msg) for role, msg in body.history if role in ("user", "model")][-12:]
    try:
        reply = await get_llm().answer(text, history, LLM_LANGUAGE[lang])
    except LLMError:
        return {
            "in_scope": True,
            "answer": t(lang, "llm_down", numbers=cfg.emergency_numbers),
            "emergency": bool(EMERGENCY_RE.search(text)),
        }
    except Exception as exc:
        log.exception("Chat error: %s", exc)
        return {
            "in_scope": True,
            "answer": t(lang, "llm_down", numbers=cfg.emergency_numbers),
            "emergency": bool(EMERGENCY_RE.search(text)),
        }

    if not reply.in_scope or not reply.answer.strip():
        return {"in_scope": False, "answer": t(lang, "out_of_scope"), "emergency": False}

    return {
        "in_scope": True,
        "answer": reply.answer,
        "emergency": bool(EMERGENCY_RE.search(text)),
    }


# ---------------- photo analysis ----------------

@app.post("/api/photo")
async def photo(
    file: UploadFile = File(...),
    caption: str = Form(""),
    lang: str = Form("en"),
):
    lang = lang_or_default(lang)
    raw = await file.read()
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB limit")
    image, mime_type = optimize_image(raw)
    try:
        findings = await get_llm().analyze_image(image, mime_type, caption.strip(), LLM_LANGUAGE[lang])
    except LLMError:
        raise HTTPException(status_code=503, detail="llm_down")
    except Exception as exc:
        log.exception("Photo error: %s", exc)
        raise HTTPException(status_code=503, detail="llm_down")

    return {
        "is_burn": findings.is_burn,
        "description": findings.description,
        "red_flags": findings.red_flags,
        "circumferential": findings.circumferential,
        "regions": [
            {"region": f.region.value, "fraction": f.fraction, "depth": f.depth.value}
            for f in findings.regions
        ],
    }


# ---------------- TBSA assessment ----------------

class BurnIn(BaseModel):
    region: str
    fraction: float = Field(ge=0.0, le=1.0)
    depth: str


class AssessRequest(BaseModel):
    burns: list[BurnIn] = Field(min_length=1, max_length=34)
    age: str
    circumferential: bool = False
    lang: str | None = None
    description: str = ""
    red_flags: list[str] = Field(default_factory=list)


def _format_report_text(case: BurnCase, lang: str, numbers: str, description: str, red_flags: list[str]) -> dict:
    """Port of the Telegram bot's _format_report to structured JSON + plain text."""
    result = assess(case)
    lines = [t(lang, "report_title", age=age_label(case.age, lang))]
    if description:
        lines.append(f"<i>{html.escape(description)}</i>")
    lines.append("")
    lines.append(t(lang, "burned_areas"))
    rows = []
    for burn, pct in result.rows:
        region_label = region_name(burn.region, lang)
        depth_text = depth_label(burn.depth, lang)
        lines.append(
            t(lang, "region_line", region=region_label, fraction=f"{burn.fraction:.0%}",
              depth=depth_text, pct=f"{pct:.1f}")
        )
        rows.append({
            "region": burn.region.value,
            "region_label": region_label,
            "fraction": burn.fraction,
            "depth": burn.depth.value,
            "depth_label": depth_text,
            "pct": round(pct, 1),
        })
    lines.append("")
    tbsa_line = t(lang, "tbsa_line", tbsa=f"{result.tbsa:.1f}")
    lines.append(tbsa_line)
    if result.superficial_only:
        lines.append(t(lang, "superficial_line", pct=f"{result.superficial_only:.1f}"))
    lines.append(t(lang, "palm_check"))
    lines.append("")
    lines.append(t(lang, f"level_{result.level}", numbers=numbers))
    lines.extend("• " + t(lang, "reason_" + key, **params) for key, params in result.reasons)
    if red_flags:
        lines.append("")
        lines.append(t(lang, "noticed"))
        lines.extend("• " + html.escape(f) for f in red_flags)
    lines.append("")
    lines.append(t(lang, "elec_chem"))
    lines.append("")
    lines.append(t(lang, "next_steps"))
    lines.append("")
    lines.append(t(lang, "disclaimer", numbers=numbers))
    return {
        "tbsa": result.tbsa,
        "superficial_only": result.superficial_only,
        "level": result.level,
        "rows": rows,
        "reasons": [t(lang, "reason_" + key, **params) for key, params in result.reasons],
        "report_text": "\n".join(lines),
    }


@app.post("/api/assess")
async def assess_endpoint(body: AssessRequest):
    lang = lang_or_default(body.lang)
    numbers = get_config().emergency_numbers
    try:
        age = AgeGroup(body.age)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid age group: {body.age}")

    case = BurnCase()
    case.age = age
    case.circumferential = body.circumferential
    for item in body.burns:
        try:
            region = Region(item.region)
            depth = Depth(item.depth)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid region or depth: {item.region} / {item.depth}")
        case.add(RegionBurn(region, item.fraction, depth))
    if not case.burns:
        raise HTTPException(status_code=400, detail="No valid burns supplied")

    return _format_report_text(case, lang, numbers, body.description, body.red_flags)


# ---------------- Parkland formula ----------------

class ParklandRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    tbsa: float = Field(ge=0, le=100)
    age_group: str


@app.post("/api/parkland")
async def parkland(body: ParklandRequest):
    try:
        age = AgeGroup(body.age_group)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid age group: {body.age_group}")

    total, first_8h, next_16h = parkland_ml(body.weight_kg, body.tbsa)
    threshold = 10 if age in CHILD_GROUPS else 20
    lines = [
        "💧 Parkland formula (reference for medical professionals only)",
        f"4 mL × {body.weight_kg:g} kg × {body.tbsa:.1f}% TBSA = {total:,.0f} mL Ringer's lactate in 24 h",
        f"• First 8 h from time of burn: {first_8h:,.0f} mL",
        f"• Next 16 h: {next_16h:,.0f} mL",
    ]
    if body.tbsa < threshold:
        lines.append(f"\nℹ️ TBSA is below {threshold}%. Formal IV resuscitation is usually not required.")
    if age in CHILD_GROUPS:
        lines.append("ℹ️ Children also need maintenance fluids on top of this.")
    lines.append("\n⚠️ The TBSA here is a photo-based estimate. Fluids must be decided and adjusted "
                 "by a clinician based on urine output.")
    return {"text": "\n".join(lines)}


# ---------------- hospitals ----------------

class HospitalsRequest(BaseModel):
    lat: float | None = None
    lon: float | None = None
    place: str | None = None


@app.post("/api/hospitals")
async def hospitals(body: HospitalsRequest):
    lang = DEFAULT_LANG
    numbers = get_config().emergency_numbers
    finder = get_finder()

    lat, lon, where = body.lat, body.lon, None
    if lat is not None and lon is not None:
        where = t(lang, "your_location")
    elif body.place:
        try:
            found = await finder.geocode(body.place.strip())
        except Exception as exc:
            log.warning("Geocode failed: %s", exc)
            found = None
        if not found:
            return {"ok": False, "error": "place_not_found",
                    "message": t(lang, "place_not_found", place=body.place)}
        lat, lon, name = found
        where = name.split(",")[0]
    else:
        raise HTTPException(status_code=400, detail="Provide lat/lon or place")

    try:
        places = await finder.nearby(lat, lon)
    except Exception as exc:
        log.exception("Hospital lookup failed: %s", exc)
        return {"ok": False, "error": "map_down",
                "message": _safe_t(lang, "map_down", numbers)}

    return {
        "ok": True,
        "where": where,
        "title": t(lang, "hospitals_title", where=where),
        "emergency_line": _safe_t(lang, "emergency_line", numbers),
        "footer": _safe_t(lang, "hospitals_footer"),
        "no_hospitals": t(lang, "no_hospitals", where=where, numbers=numbers),
        "places": [
            {
                "name": p.name,
                "kind": p.kind,
                "distance_km": round(p.distance_km, 1),
                "phone": p.phone,
                "burn_unit": p.burn_unit,
                "major": p.major,
                "directions_url": p.directions_url,
            }
            for p in places
        ],
        "tag_burn": t(lang, "tag_burn"),
        "tag_major": t(lang, "tag_major"),
        "kind_hospital": t(lang, "kind_hospital"),
        "kind_clinic": t(lang, "kind_clinic"),
        "directions": t(lang, "directions"),
        "emergency_numbers": numbers,
    }
