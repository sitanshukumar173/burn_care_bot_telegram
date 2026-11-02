"""CSJMU BurnCare Saathi Telegram bot: burn-only Q&A, photo-based %TBSA estimate, nearby hospitals.

Talks in English, Hindi or Hinglish; the user picks on /start (or later with /language).
"""

import html
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
from hospitals import HospitalFinder, parse_hospital_request
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
from llm import BurnLLM, LLMError
from tbsa import CHILD_GROUPS, AgeGroup, BurnCase, RegionBurn, assess, parkland_ml

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("burnbot")

HISTORY_TURNS = 6
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TELEGRAM_LIMIT = 4000
BUTTON_ACTIONS = button_actions()
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LOGO_PATH = Path(__file__).parent / "logo.jpg"


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _numbers(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.bot_data["config"].emergency_numbers


def _get_case(context: ContextTypes.DEFAULT_TYPE) -> BurnCase:
    return context.user_data.setdefault("case", BurnCase())


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
    await update.effective_message.reply_text(t(_lang(context), "reset_done"))


# ---------- photo assessment ----------

def _format_report(case: BurnCase, lang: str, numbers: str, description: str, red_flags: list[str]) -> str:
    result = assess(case)
    lines = [t(lang, "report_title", age=age_label(case.age, lang))]
    if description:
        lines.append(f"<i>{html.escape(description)}</i>")
    lines.append("")
    lines.append(t(lang, "burned_areas"))
    for burn, pct in result.rows:
        lines.append(t(
            lang, "region_line",
            region=html.escape(region_name(burn.region, lang)),
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

    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)
    image = bytes(await tg_file.download_as_bytearray())
    llm: BurnLLM = context.bot_data["llm"]
    try:
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

    case = _get_case(context)
    for f in findings.regions:
        case.add(RegionBurn(f.region, f.fraction, f.depth))
    case.circumferential = case.circumferential or findings.circumferential
    context.user_data["last_findings"] = (findings.description, findings.red_flags)
    log.info("Photo assessed: %d regions", len(findings.regions))

    if case.age is None:
        await message.reply_text(
            t(lang, "age_question"), parse_mode=ParseMode.HTML, reply_markup=_age_keyboard(lang)
        )
        return
    await _send_long(
        update,
        _format_report(case, lang, _numbers(context), findings.description, findings.red_flags),
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
    await _send_long(
        update,
        _format_report(case, lang, _numbers(context), description, red_flags),
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
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    finder: HospitalFinder = context.bot_data["finder"]
    numbers = _numbers(context)
    try:
        places = await finder.nearby(lat, lon)
        log.info("Hospital lookup found %d places", len(places))
    except Exception:
        log.exception("Hospital lookup failed")
        await update.effective_message.reply_text(t(lang, "map_down", numbers=numbers))
        return

    if not places:
        await update.effective_message.reply_text(t(lang, "no_hospitals", where=where, numbers=numbers))
        return

    lines = [
        t(lang, "hospitals_title", where=html.escape(where)),
        t(lang, "emergency_line", numbers=html.escape(numbers)),
        "",
    ]
    for p in places:
        tag = t(lang, "tag_burn") if p.burn_unit else t(lang, "tag_major") if p.major else ""
        lines.append(f"<b>{html.escape(p.name)}</b>")
        lines.append(f"{tag}{t(lang, 'kind_' + p.kind)} · {p.distance_km:.1f} km")
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
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    try:
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

    await context.bot.send_chat_action(update.message.chat_id, ChatAction.TYPING)
    llm: BurnLLM = context.bot_data["llm"]
    history: list = context.user_data.setdefault("history", [])
    try:
        reply = await llm.answer(text, history, LLM_LANGUAGE[lang])
    except LLMError:
        await update.message.reply_text(t(lang, "llm_down", numbers=_numbers(context)))
        return

    if not reply.in_scope or not reply.answer.strip():
        await update.message.reply_text(t(lang, "out_of_scope"))
        return

    history.extend([("user", text), ("model", reply.answer)])
    del history[:-HISTORY_TURNS]
    await _send_long(update, reply.answer)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        lang = (context.user_data or {}).get("lang", DEFAULT_LANG)
        try:
            await update.effective_message.reply_text(t(lang, "generic_error", numbers=_numbers(context)))
        except Exception:
            pass  # usually the network is down, so this reply would fail too


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
        .build()
    )
    app.bot_data["config"] = config
    app.bot_data["llm"] = BurnLLM(config.gemini_api_key, config.gemini_models, config.emergency_numbers)
    app.bot_data["finder"] = HospitalFinder(config.osm_user_agent)

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

    log.info("CSJMU BurnCare Saathi bot started with models %s", ", ".join(config.gemini_models))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
