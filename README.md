# CSJMU BurnCare Saathi Telegram Bot (CSJMU × MEDIOTECH)

A Telegram chatbot that only answers questions about human burn injuries. It uses Google Gemini's free API tier.

- 📸 **Photo → burn %**: send a photo of a burn. Gemini identifies the burned body regions, what fraction of each is burned and how deep. The bot then calculates **%TBSA with the Lund & Browder chart** (the age-adjusted Rule of Nines used in burn units) in plain Python, and grades it as *home care / see a doctor / emergency* using ABA and NHS criteria. Several photos of different areas add up to one case.
- 🩹 **First aid** and 🛡 **prevention**: fixed, reviewed texts (`prompts.py`). They don't change between LLM replies.
- 📍 **Nearby hospitals**: share your Telegram location, or type `/hospitals <city>`. Uses OpenStreetMap (free, no key). Shows the nearest hospitals and flags large government/teaching hospitals and burn units.
- 💬 **Burn-only Q&A**: Gemini answers with structured output that includes an `in_scope` flag. Anything not about burns gets a fixed refusal.
- 💧 `/parkland <kg>`: Parkland fluid formula, as a reference for clinicians.

## Setup

1. **Telegram token**: in Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot` and copy the token.
2. **Gemini key (free)**: https://aistudio.google.com/apikey
3. Install and configure:
   ```bash
   cd burn-care-bot
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # then paste both keys into .env
   ```
4. Run: `python bot.py`, then open your bot in Telegram and send `/start`.

Tests: `pytest`

## Files

| File | Purpose |
|---|---|
| `bot.py` | Telegram handlers and the main entry point |
| `llm.py` | Gemini calls: burn-only Q&A, photo analysis (structured JSON) |
| `tbsa.py` | Lund & Browder table, %TBSA, severity triage, Parkland formula |
| `hospitals.py` | OpenStreetMap hospital search and geocoding |
| `prompts.py` | System prompts and the fixed first-aid, prevention and formula texts |

## Limitations (read before showing this to anyone)

- **A photo estimate is rough.** One photo shows only part of the body, and burn depth is hard to judge even in person. The output is a guide, not a diagnosis.
- **Privacy:** photos go to Google's Gemini API. On the free tier, Google may use the data to improve its products, so don't use it for real patient data without a paid tier or a local model.
- **Free-tier limits:** Gemini free quotas are per minute and per day. If they run out, the bot replies with a "try again" message plus first-aid guidance.
- **Hospital data** comes from OpenStreetMap and is incomplete in places. Few hospitals are tagged as burn units.
- Emergency numbers default to India (112 / 108). Change `EMERGENCY_NUMBERS` in `.env` for other countries.
- Conversation state lives in memory and is lost on restart.
