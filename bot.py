"""CSJMU BurnCare Saathi Telegram bot: burn-only Q&A, photo-based %TBSA estimate, nearby hospitals.

Talks in English, Hindi or Hinglish; the user picks on /start (or later with /language).
"""

import asyncio
from contextlib import asynccontextmanager
import html
import io
import logging
from pathlib import Path
import re

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PersistenceInput,
    PicklePersistence,
    filters,
)

from config import load_config
from analytics import Analytics
from hospitals import HospitalFinder, Place, parse_hospital_request
from i18n import (
    CHOOSE_LANGUAGE,
    DEFAULT_LANG,
    LANG_BUTTONS,
    LANGS,
    LLM_LANGUAGE,
    age_label,
    button_actions,
    depth_label,
    region_name,
    t,
)
from llm import BurnLLM, ImageFindings, LLMError
from tbsa import CHILD_GROUPS, AgeGroup, BurnCase, Region, RegionBurn, assess, parkland_ml

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("burnbot")

CONTEXT_EXCHANGES = 3
MAX_HISTORY_MESSAGES = CONTEXT_EXCHANGES * 2
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TELEGRAM_LIMIT = 4000
BUTTON_ACTIONS = button_actions()
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
HOSPITAL_FOLLOW_UP = re.compile(
    r"\b(which|what|who|best|better|recommend|recommended|nearest|closest|"
    r"burn\s*(?:unit|center|centre)|government|major|kaunsa|kaun\s+sa|"
    r"sabse\s+(?:accha|achha|best)|suggest)\b"
    r"|कौन सा|कौनसा|सबसे अच्छा|बेहतर|नज़दीकी|नजदीकी|सरकारी",
    re.IGNORECASE,
)
LIMB_WORDS = re.compile(r"\b(hand|arm|forearm|हाथ|बांह|बाँह)\b", re.IGNORECASE)
LOGO_PATH = Path(__file__).parent / "logo.jpg"


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _numbers(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.bot_data["config"].emergency_numbers


def _get_case(context: ContextTypes.DEFAULT_TYPE) -> BurnCase:
    return context.user_data.setdefault("case", BurnCase())


def _trim_history(history: list[tuple[str, str]]) -> None:
    """Keep only the most recent three user/model exchanges in local state."""
    del history[:-MAX_HISTORY_MESSAGES]


def _serialize_hospitals(places: list[Place]) -> list[dict]:
    return [
        {
            "name": place.name,
            "distance_km": place.distance_km,
            "burn_unit": place.burn_unit,
            "major": place.major,
        }
        for place in places
    ]


def _hospital_tags(place: Place, lang: str) -> str:
    tags = []
    if place.burn_unit:
        tags.append(t(lang, "tag_burn"))
    if place.major:
        tags.append(t(lang, "tag_major"))
    return "".join(tags)


def _hospital_follow_up(text: str, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Answer simple questions about the most recently displayed hospital list."""
    hospitals = context.user_data.get("last_hospitals")
    if not hospitals or not HOSPITAL_FOLLOW_UP.search(text):
        return None

    asks_nearest = re.search(r"\b(nearest|closest)\b|नज़दीकी|नजदीकी", text, re.IGNORECASE)
    asks_burn = re.search(r"\bburn\s*(?:unit|center|centre)\b|burn|जलन|बर्न", text, re.IGNORECASE)
    asks_major = re.search(r"\b(government|major)\b|सरकारी", text, re.IGNORECASE)

    if asks_nearest:
        selected = min(hospitals, key=lambda hospital: hospital["distance_km"])
        reason = "the nearest listed hospital"
    else:
        matching = hospitals
        if asks_burn:
            matching = [hospital for hospital in hospitals if hospital["burn_unit"]]
        elif asks_major:
            matching = [hospital for hospital in hospitals if hospital["major"]]
        if not matching:
            matching = hospitals
        selected = sorted(
            matching,
            key=lambda hospital: (
                not hospital["burn_unit"],
                not hospital["major"],
                hospital["distance_km"],
            ),
        )[0]
        if selected["burn_unit"]:
            reason = "a burn/plastic-surgery unit"
        elif selected["major"]:
            reason = "a major or government hospital"
        else:
            reason = "a nearby hospital"

    return t(
        _lang(context),
        "hospital_recommendation",
        name=html.escape(selected["name"]),
        distance=f'{selected["distance_km"]:.1f}',
        reason=reason,
        numbers=html.escape(_numbers(context)),
    )


def _burn_context(
    case: BurnCase,
    description: str,
    red_flags: list[str],
    side_uncertain: bool = False,
) -> str:
    lines = ["Latest burn photo/report context:"]
    if description:
        lines.append(f"Photo description: {description}")
    if case.burns:
        areas = ", ".join(
            f"{region_name(burn.region, 'en')}: {burn.fraction:.0%} of region, depth {burn.depth.value}"
            for burn in case.burns.values()
        )
        lines.append(f"Visible/estimated areas: {areas}")
    if case.age is None:
        lines.append("Patient age group: not provided; TBSA and severity level are not calculated yet.")
    else:
        result = assess(case)
        lines.append(f"Patient age group: {case.age.value}")
        lines.append(f"Calculated photo estimate: {result.tbsa:.1f}% TBSA, triage level {result.level}.")
    if side_uncertain:
        lines.append("Left/right side was not reliable from the image.")
    if red_flags:
        lines.append(f"Photo red flags: {', '.join(red_flags)}")
    return "\n".join(lines)


def _record_findings(
    context: ContextTypes.DEFAULT_TYPE,
    findings: ImageFindings,
    confirmed_side: str | None = None,
) -> BurnCase:
    case = _get_case(context)
    for finding in findings.regions:
        region = finding.region
        if confirmed_side and region.value.startswith(("left_", "right_")):
            source_side = "right" if confirmed_side == "left" else "left"
            region = Region(
                region.value.replace(
                    f"{source_side}_",
                    f"{confirmed_side}_",
                    1,
                )
            )
        case.add(RegionBurn(region, finding.fraction, finding.depth))
    case.circumferential = case.circumferential or findings.circumferential
    context.user_data["last_findings"] = (findings.description, findings.red_flags)
    context.user_data["last_side_uncertain"] = findings.side_uncertain
    context.user_data["last_burn_context"] = _burn_context(
        case, findings.description, findings.red_flags, findings.side_uncertain
    )
    return case


def _apply_side_correction(text: str, case: BurnCase) -> str | None:
    """Move photographed arm/hand findings when the user corrects the side."""
    side_match = re.search(r"\b(left|right)\b", text, re.IGNORECASE)
    if not side_match or not LIMB_WORDS.search(text):
        return None
    new_side = side_match.group(1).lower()
    old_side = "right" if new_side == "left" else "left"
    moved = []
    for region, burn in list(case.burns.items()):
        value = region.value
        if not value.startswith(old_side + "_"):
            continue
        if not any(part in value for part in ("hand", "forearm", "upper_arm")):
            continue
        replacement = Region(value.replace(old_side + "_", new_side + "_", 1))
        del case.burns[region]
        case.burns[replacement] = RegionBurn(replacement, burn.fraction, burn.depth)
        moved.append(replacement)
    if not moved:
        return None
    return new_side


def _llm_context(context: ContextTypes.DEFAULT_TYPE) -> str:
    sections = []
    burn_context = context.user_data.get("last_burn_context")
    if burn_context:
        sections.append(burn_context)
    hospitals = context.user_data.get("last_hospitals")
    if hospitals:
        hospital_lines = ["Latest hospital list:"]
        for hospital in hospitals:
            labels = []
            if hospital["burn_unit"]:
                labels.append("burn/plastic-surgery unit")
            if hospital["major"]:
                labels.append("major/government")
            label = f" ({', '.join(labels)})" if labels else ""
            hospital_lines.append(
                f"- {hospital['name']}: {hospital['distance_km']:.1f} km{label}"
            )
        sections.append("\n".join(hospital_lines))
    return "\n\n".join(sections)


def _main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "btn_hospitals"))],
            [KeyboardButton(t(lang, "btn_first_aid")), KeyboardButton(t(lang, "btn_prevention"))],
            [KeyboardButton(t(lang, "btn_formula")), KeyboardButton(t(lang, "btn_photo"))],
            [KeyboardButton(t(lang, "btn_language"))],
        ],
        resize_keyboard=True,
    )


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(LANG_BUTTONS[code], callback_data=f"lang:{code}")] for code in LANGS]
    )


async def _send_long(update: Update, text: str, **kwargs) -> None:
    while text:
        chunk, text = text[:TELEGRAM_LIMIT], text[TELEGRAM_LIMIT:]
        await update.effective_message.reply_text(chunk, **kwargs)


# ---------- language ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(CHOOSE_LANGUAGE, reply_markup=_language_keyboard())


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(CHOOSE_LANGUAGE, reply_markup=_language_keyboard())


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    if lang not in LANGS:
        return
    context.user_data["lang"] = lang
    context.user_data.pop("history", None)  # earlier turns may be in another language
    context.user_data.pop("last_hospitals", None)
    context.user_data.pop("last_burn_context", None)
    context.user_data.pop("last_side_uncertain", None)
    log.info("Language set to %s", lang)
    await query.edit_message_text(t(lang, "language_set"))
    await _send_welcome(update, context)


async def _send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(context)
    text = t(lang, "welcome")
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=_main_keyboard(lang)
    )


# ---------- static commands ----------

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(context)
    await update.effective_message.reply_text(
        t(lang, "help"), parse_mode=ParseMode.HTML, reply_markup=_main_keyboard(lang)
    )


async def first_aid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = t(_lang(context), "first_aid", numbers=html.escape(_numbers(context)))
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def prevention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(t(_lang(context), "prevention"), parse_mode=ParseMode.HTML)


async def formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(t(_lang(context), "formula"), parse_mode=ParseMode.HTML)


async def photo_tips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(t(_lang(context), "photo_tips"), parse_mode=ParseMode.HTML)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("case", None)
    context.user_data.pop("history", None)
    context.user_data.pop("last_hospitals", None)
    context.user_data.pop("last_burn_context", None)
    await update.effective_message.reply_text(t(_lang(context), "reset_done"))


# ---------- photo assessment ----------

def _format_report(
    case: BurnCase,
    lang: str,
    numbers: str,
    description: str,
    red_flags: list[str],
    side_uncertain: bool = False,
) -> str:
    result = assess(case)
    lines = [t(lang, "report_title", age=age_label(case.age, lang))]
    if description:
        lines.append(f"<i>{html.escape(description)}</i>")
    if side_uncertain:
        lines.append(t(lang, "side_uncertain"))
    lines.append("")
    lines.append(t(lang, "burned_areas"))
    for burn, pct in result.rows:
        region = region_name(burn.region, lang)
        if side_uncertain and burn.region.value.startswith(("left_", "right_")):
            side_text = {
                "en": ("left", "right", "side unclear"),
                "hi": ("बाएँ", "दाएँ", "तरफ़ स्पष्ट नहीं"),
                "hinglish": ("left", "right", "side clear nahi"),
            }[lang]
            region = region.replace(side_text[0], side_text[2]).replace(
                side_text[1], side_text[2]
            )
        lines.append(t(
            lang, "region_line",
            region=html.escape(region),
            fraction=f"{burn.fraction:.0%}",
            depth=depth_label(burn.depth, lang),
            pct=f"{pct:.1f}",
        ))
    lines.append("")
    lines.append(t(lang, "tbsa_line", tbsa=f"{result.tbsa:.1f}"))
    if result.superficial_only:
        lines.append(t(lang, "superficial_line", pct=f"{result.superficial_only:.1f}"))
    lines.append(t(lang, "palm_check"))
    lines.append("")
    lines.append(t(lang, f"level_{result.level}", numbers=html.escape(numbers)))
    lines.extend(f"• {html.escape(t(lang, 'reason_' + key, **params))}" for key, params in result.reasons)
    if red_flags:
        lines.append("")
        lines.append(t(lang, "noticed"))
        lines.extend(f"• {html.escape(f)}" for f in red_flags)
    lines.append("")
    lines.append(t(lang, "elec_chem"))
    lines.append("")
    lines.append(t(lang, "next_steps"))
    lines.append("")
    lines.append(html.escape(t(lang, "disclaimer", numbers=numbers)))
    return "\n".join(lines)


def _age_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(age_label(g, lang), callback_data=f"age:{g.value}") for g in AgeGroup]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def optimize_image(raw_bytes: bytes, max_dim: int = 1200, quality: int = 85) -> tuple[bytes, str]:
    """Compress and downscale image in memory to speed up Gemini upload and inference."""
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
    except Exception as exc:
        log.warning("Image optimization fallback: %s", exc)
        return raw_bytes, "image/jpeg"


@asynccontextmanager
async def keep_typing(bot, chat_id: int, action: ChatAction = ChatAction.TYPING, interval: float = 3.5):
    """Keep sending chat action so Telegram shows the user that work is continuously in progress."""
    stop_event = asyncio.Event()

    async def _loop():
        try:
            while not stop_event.is_set():
                try:
                    await bot.send_chat_action(chat_id, action)
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                except (asyncio.TimeoutError, TimeoutError):
                    pass
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    lang = _lang(context)
    if message.photo:
        tg_file = await message.photo[-1].get_file()
        mime_type = "image/jpeg"
    else:
        doc = message.document
        if doc.file_size and doc.file_size > MAX_IMAGE_BYTES:
            await message.reply_text(t(lang, "image_too_large"))
            return
        tg_file = await doc.get_file()
        mime_type = doc.mime_type or "image/jpeg"

    raw_bytes = bytes(await tg_file.download_as_bytearray())
    image, mime_type = optimize_image(raw_bytes)
    llm: BurnLLM = context.bot_data["llm"]
    try:
        async with keep_typing(context.bot, message.chat_id):
            findings = await llm.analyze_image(image, mime_type, message.caption or "", LLM_LANGUAGE[lang])
    except LLMError:
        await message.reply_text(t(lang, "photo_failed"))
        return
    except Exception as exc:
        log.exception("Image assessment error: %s", exc)
        await message.reply_text(t(lang, "photo_failed"))
        return

    if not findings.is_burn or not findings.regions:
        await message.reply_text(t(lang, "not_burn"))
        return

    case = _record_findings(context, findings)
    log.info("Photo assessed: %d regions", len(findings.regions))

    if case.age is None:
        await message.reply_text(
            t(lang, "age_question"), parse_mode=ParseMode.HTML, reply_markup=_age_keyboard(lang)
        )
        return
    await _send_long(
        update,
        _format_report(
            case,
            lang,
            _numbers(context),
            findings.description,
            findings.red_flags,
            findings.side_uncertain,
        ),
        parse_mode=ParseMode.HTML,
    )


async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = _lang(context)
    case = _get_case(context)
    if not case.burns:
        await query.edit_message_text(t(lang, "send_photo_first"))
        return
    case.age = AgeGroup(query.data.split(":", 1)[1])
    await query.edit_message_text(t(lang, "age_set", age=age_label(case.age, lang)))
    description, red_flags = context.user_data.get("last_findings", ("", []))
    context.user_data["last_burn_context"] = _burn_context(
        case,
        description,
        red_flags,
        context.user_data.get("last_side_uncertain", False),
    )
    await _send_long(
        update,
        _format_report(
            case,
            lang,
            _numbers(context),
            description,
            red_flags,
            context.user_data.get("last_side_uncertain", False),
        ),
        parse_mode=ParseMode.HTML,
    )


async def parkland(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clinician reference, kept in English (the medical terms are the same in all three languages)."""
    case = context.user_data.get("case")
    if not case or not case.burns or case.age is None:
        await update.message.reply_text("Send a burn photo first so I can estimate %TBSA, then use /parkland <weight kg>.")
        return
    try:
        weight = float(context.args[0])
    except (IndexError, ValueError):
        weight = 0
    if not 1 <= weight <= 300:
        await update.message.reply_text("Usage: /parkland <weight in kg>, e.g. /parkland 60")
        return

    tbsa = assess(case).tbsa
    total, first_8h, next_16h = parkland_ml(weight, tbsa)
    threshold = 10 if case.age in CHILD_GROUPS else 20
    lines = [
        "💧 <b>Parkland formula</b> (reference for medical professionals only)",
        f"4 mL × {weight:g} kg × {tbsa:.1f}% TBSA = <b>{total:,.0f} mL</b> Ringer's lactate in 24 h",
        f"• First 8 h from time of burn: {first_8h:,.0f} mL",
        f"• Next 16 h: {next_16h:,.0f} mL",
    ]
    if tbsa < threshold:
        lines.append(f"\nℹ️ TBSA is below {threshold}%. Formal IV resuscitation is usually not required.")
    if case.age in CHILD_GROUPS:
        lines.append("ℹ️ Children also need maintenance fluids on top of this.")
    lines.append("\n⚠️ The TBSA here is a photo-based estimate. Fluids must be decided and adjusted "
                 "by a clinician based on urine output.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ---------- hospitals ----------

async def _reply_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           lat: float, lon: float, where: str) -> None:
    lang = _lang(context)
    finder: HospitalFinder = context.bot_data["finder"]
    numbers = _numbers(context)
    try:
        async with keep_typing(context.bot, update.effective_chat.id, ChatAction.FIND_LOCATION):
            places = await finder.nearby(lat, lon)
        log.info("Hospital lookup found %d places", len(places))
    except Exception:
        log.exception("Hospital lookup failed")
        await update.effective_message.reply_text(t(lang, "map_down", numbers=numbers))
        return

    if not places:
        await update.effective_message.reply_text(t(lang, "no_hospitals", where=where, numbers=numbers))
        return

    context.user_data["last_hospitals"] = _serialize_hospitals(places)
    lines = [
        t(lang, "hospitals_title", where=html.escape(where)),
        t(lang, "emergency_line", numbers=html.escape(numbers)),
        "",
    ]
    for p in places:
        lines.append(f"<b>{html.escape(p.name)}</b>")
        lines.append(
            f"{_hospital_tags(p, lang)}{t(lang, 'kind_' + p.kind)} · {p.distance_km:.1f} km"
        )
        if p.phone:
            lines.append(f"📞 {html.escape(p.phone)}")
        lines.append(f'<a href="{p.directions_url}">{t(lang, "directions")}</a>')
        lines.append("")
    lines.append(html.escape(t(lang, "hospitals_footer")))
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=_main_keyboard(lang)
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loc = update.message.location
    context.user_data.pop("awaiting_place", None)
    log.info("Hospital lookup by shared location")
    await _reply_hospitals(update, context, loc.latitude, loc.longitude, t(_lang(context), "your_location"))


async def _ask_for_place(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang(context)
    context.user_data["awaiting_place"] = True
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "btn_share_location"), request_location=True)],
            [KeyboardButton(t(lang, "btn_first_aid")), KeyboardButton(t(lang, "btn_prevention"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.effective_message.reply_text(
        t(lang, "ask_place", numbers=_numbers(context)),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def _hospitals_for_place(update: Update, context: ContextTypes.DEFAULT_TYPE, place: str) -> None:
    context.user_data.pop("awaiting_place", None)
    finder: HospitalFinder = context.bot_data["finder"]
    try:
        async with keep_typing(context.bot, update.effective_chat.id, ChatAction.FIND_LOCATION):
            found = await finder.geocode(place)
    except Exception:
        log.exception("Geocoding failed")
        found = None
    if not found:
        context.user_data["awaiting_place"] = True
        await update.effective_message.reply_text(t(_lang(context), "place_not_found", place=place))
        return
    lat, lon, name = found
    log.info("Hospital lookup by place name")
    await _reply_hospitals(update, context, lat, lon, name.split(",")[0])


async def hospitals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    place = " ".join(context.args or []).strip()
    if place:
        await _hospitals_for_place(update, context, place)
    else:
        await _ask_for_place(update, context)


# ---------- free-text burn Q&A ----------

BUTTON_HANDLERS = {
    "btn_first_aid": first_aid,
    "btn_prevention": prevention,
    "btn_formula": formula,
    "btn_photo": photo_tips,
    "btn_hospitals": hospitals_cmd,
    "btn_language": language_cmd,
}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if "lang" not in context.user_data:
        # Users who never picked a language: guess from the script they write in.
        context.user_data["lang"] = "hi" if DEVANAGARI.search(text) else DEFAULT_LANG
    lang = _lang(context)

    action = BUTTON_ACTIONS.get(text)
    if action:
        context.args = []
        await BUTTON_HANDLERS[action](update, context)
        return

    # "hospital near me", "Bihta mein hospital", "नजदीकी अस्पताल": no LLM needed.
    wants_hospital, place = parse_hospital_request(text)
    if wants_hospital:
        if place:
            await _hospitals_for_place(update, context, place)
        else:
            await _ask_for_place(update, context)
        return

    # Reply to "Where are you?": a short message is taken as a place name.
    if context.user_data.pop("awaiting_place", False) and len(text.split()) <= 6 and "?" not in text:
        await _hospitals_for_place(update, context, text)
        return

    case = context.user_data.get("case")
    if case and case.burns and case.age is not None:
        corrected_side = _apply_side_correction(text, case)
        if corrected_side:
            description, red_flags = context.user_data.get("last_findings", ("", []))
            context.user_data["last_burn_context"] = _burn_context(
                case, description, red_flags
            )
            await update.effective_message.reply_text(
                t(lang, "side_correction", side=corrected_side.capitalize())
            )
            await _send_long(
                update,
                _format_report(case, lang, _numbers(context), description, red_flags),
                parse_mode=ParseMode.HTML,
            )
            return

    hospital_answer = _hospital_follow_up(text, context)
    if hospital_answer:
        await update.effective_message.reply_text(hospital_answer, parse_mode=ParseMode.HTML)
        return

    llm: BurnLLM = context.bot_data["llm"]
    history: list[tuple[str, str]] = context.user_data.setdefault("history", [])
    # Persistence can contain state written by an older version. Trim before
    # sending it to the model as well as after appending the new exchange.
    _trim_history(history)
    try:
        async with keep_typing(context.bot, update.message.chat_id):
            reply = await llm.answer(
                text,
                history,
                LLM_LANGUAGE[lang],
                recent_context=_llm_context(context),
            )
    except LLMError:
        await update.message.reply_text(t(lang, "llm_down", numbers=_numbers(context)))
        return

    if not reply.in_scope or not reply.answer.strip():
        await update.message.reply_text(t(lang, "out_of_scope"))
        return

    history.extend([("user", text), ("model", reply.answer)])
    _trim_history(history)
    await _send_long(update, reply.answer)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        lang = (context.user_data or {}).get("lang", DEFAULT_LANG)
        try:
            await update.effective_message.reply_text(t(lang, "generic_error", numbers=_numbers(context)))
        except Exception:
            pass  # usually the network is down, so this reply would fail too


async def record_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    analytics: Analytics = context.bot_data.get("analytics")
    if analytics:
        analytics.record_update(update)


BOT_COMMANDS = {
    None: [
        ("start", "Start / choose language"),
        ("firstaid", "Burn first aid steps"),
        ("prevention", "How to prevent burns"),
        ("formula", "How burn % is calculated"),
        ("photo", "Tips for sending a burn photo"),
        ("hospitals", "Hospitals near a city or area"),
        ("parkland", "Parkland fluid formula (clinicians)"),
        ("reset", "Start a new burn case"),
        ("language", "Change language / भाषा बदलें"),
        ("help", "Show all commands"),
    ],
    "hi": [
        ("start", "शुरू करें / भाषा चुनें"),
        ("firstaid", "जलने पर प्राथमिक उपचार"),
        ("prevention", "जलने से बचाव"),
        ("formula", "जलने का % कैसे निकालते हैं"),
        ("photo", "फ़ोटो भेजने के टिप्स"),
        ("hospitals", "पास के अस्पताल"),
        ("parkland", "Parkland फ़ॉर्मूला (डॉक्टरों के लिए)"),
        ("reset", "नया केस शुरू करें"),
        ("language", "भाषा बदलें / Change language"),
        ("help", "सभी कमांड"),
    ],
}


async def post_init(app: Application) -> None:
    try:
        await app.bot.set_my_name("CSJMU BurnCare Saathi")
        await app.bot.set_my_description(
            "Welcome to CSJMU BurnCare Saathi, developed by CSJMU & MEDIOTECH.\n\n"
            "• Instant burn first-aid guidance\n"
            "• Lund & Browder %TBSA burn estimation from photos\n"
            "• Nearby hospital and burn center finder\n"
            "• Available in English, Hindi, and Hinglish"
        )
        await app.bot.set_my_short_description("CSJMU BurnCare Saathi: Burn Care First-Aid & Support by CSJMU x MEDIOTECH")
    except Exception as e:
        log.warning("Could not set bot profile metadata: %s", e)

    for language_code, commands in BOT_COMMANDS.items():
        await app.bot.set_my_commands(
            [BotCommand(c, d) for c, d in commands], language_code=language_code
        )


async def post_shutdown(app: Application) -> None:
    analytics: Analytics | None = app.bot_data.get("analytics")
    if analytics:
        await analytics.wait_for_sync()


def main() -> None:
    config = load_config()
    # Remember each user's language and current burn case across restarts.
    persistence = PicklePersistence(
        "bot_state.pickle",
        store_data=PersistenceInput(bot_data=False, chat_data=False, user_data=True, callback_data=False),
    )
    request = HTTPXRequest(
        connection_pool_size=16,
        read_timeout=20.0,
        write_timeout=20.0,
        connect_timeout=15.0,
        pool_timeout=10.0,
    )
    app = (
        Application.builder()
        .token(config.telegram_token)
        .request(request)
        .concurrent_updates(True)
        .persistence(persistence)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["config"] = config
    app.bot_data["llm"] = BurnLLM(
        config.gemini_api_key,
        config.gemini_models,
        config.emergency_numbers,
        config.gemini_vision_models,
        config.vision_provider,
        config.groq_api_key,
        config.groq_vision_model,
    )
    app.bot_data["finder"] = HospitalFinder(config.osm_user_agent)
    app.bot_data["analytics"] = Analytics(
        config.analytics_database,
        config.google_sheets_id,
        config.google_service_account_file,
    )

    app.add_handler(MessageHandler(filters.ALL, record_analytics), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("firstaid", first_aid))
    app.add_handler(CommandHandler("prevention", prevention))
    app.add_handler(CommandHandler("formula", formula))
    app.add_handler(CommandHandler("photo", photo_tips))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("parkland", parkland))
    app.add_handler(CommandHandler("hospitals", hospitals_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(CallbackQueryHandler(handle_language, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(handle_age, pattern=r"^age:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(on_error)

    log.info(
        "CSJMU BurnCare Saathi bot started with text models %s and vision models %s",
        ", ".join(config.gemini_models),
        f"{config.vision_provider}:{', '.join(config.gemini_vision_models)}"
        if config.vision_provider == "gemini"
        else f"{config.vision_provider}:{config.groq_vision_model}",
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=0.0)


if __name__ == "__main__":
    main()
