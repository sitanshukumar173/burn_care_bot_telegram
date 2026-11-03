# BurnCare Bridge (HTTP API)

Thin FastAPI wrapper that exposes the **exact** deployed CSJMU BurnCare Saathi
Telegram bot over HTTP, so the `burnCare.html` web prototype's "BurnCare AI"
tab can talk to it. The Telegram bot itself is untouched and keeps running.

It imports `llm.py`, `tbsa.py`, `hospitals.py`, `i18n.py`, `config.py` from the
bot repo on the server — all answers, photo analysis, TBSA math and hospital
lookups are the bot's own code.

## What it exposes

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/strings?lang=en\|hi\|hinglish` | All fixed texts (first aid, prevention, formula, disclaimers…) |
| `POST /api/chat` | Burn-only Q&A (`{message, history, lang}` → `{answer, in_scope, emergency}`) |
| `POST /api/photo` | Burn photo analysis (multipart: `file`, `caption`, `lang`) — same Gemini vision call as the bot |
| `POST /api/assess` | Lund & Browder report (`{burns, age, circumferential, lang, description, red_flags}`) |
| `POST /api/hospitals` | Nearby hospitals (`{lat,lon}` or `{place}`) — same OpenStreetMap lookup as the bot |
| `POST /api/parkland` | Parkland fluid calculation (`{weight_kg, tbsa, age_group}`) |

The page keeps the burn case itself (same rules as the bot's `BurnCase`), so
the bridge stays stateless. Secrets stay on the server; no key is ever
returned in a response.

## Layout

```
burnCareBridge/
  api.py            # the whole bridge (one file)
  requirements.txt  # bot deps + fastapi/uvicorn
  .env.example
```

The bridge can also live inside the bot repository:

```
burn-care-bot/
  burn-care-bot/     # config.py, llm.py, tbsa.py, hospitals.py, i18n.py
  burnCareBridge/    # this HTTP API
```

In that layout the bridge automatically discovers the sibling bot package.
`BOT_REPO` may still be set explicitly when the bot modules are stored
elsewhere.

## Deploy on the EC2 host (where the bot already lives)

SSH into the instance, then:

```bash
# 1. Go next to the bot clone (path below is an example — adjust to reality)
cd ~
git clone https://github.com/sitanshukumar173/burn_care_bot_telegram.git burn_care_bot_telegram
# (if it's already cloned here, skip — but make sure it has the latest code)

# 2. If the bridge is inside that repository, pull it with the bot code:
cd ~/burn_care_bot_telegram/burnCareBridge

# 3. Use the same venv the bot uses, or make one
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. The bundled layout is auto-detected. Set this only for another layout:
# export BOT_REPO=~/burn_care_bot_telegram/burn-care-bot

# 5. Test
python -m uvicorn api:app --host 127.0.0.1 --port 8123 &
curl http://127.0.0.1:8123/api/health
```

### Serve it over HTTPS (the page on Netlify/Vercel is HTTPS-only)

Pick whichever applies on your EC2 box:

- **You already have a domain + reverse proxy (nginx/Caddy)**: proxy
  `https://your-domain/burncare-api/` → `http://127.0.0.1:8123/` and set
  `location /burncare-api/ { proxy_pass http://127.0.0.1:8123/; }` — the page's
  `API` constant is then `https://your-domain/burncare-api` (trailing slash not
  required; the app uses absolute paths `/api/...`, so use a **subdomain**
  instead of a path prefix: `proxy_pass` a dedicated `api.your-domain` etc.).
- **No domain, want free HTTPS**: use `nip.io` (no signup):
  1. Open EC2 security group inbound for ports 80 and 443
  2. `sudo apt install -y nginx certbot python3-certbot-nginx`
  3. nginx server block with `server_name <dashed-ip>.nip.io;` (e.g. `1-2-3-4.nip.io`) → `proxy_pass http://127.0.0.1:8123;`
  4. `sudo certbot --nginx -d <dashed-ip>.nip.io`
  5. `API = 'https://<dashed-ip>.nip.io'` in the page
- **Cloudflare Tunnel (free, no open ports)**: `cloudflared tunnel --url http://127.0.0.1:8123`
  gives an instant `https://<random>.trycloudflare.com` (changes on restart —
  named tunnel with a domain recommended for a stable URL).

### Keep it running

```bash
sudo tee /etc/systemd/system/burncare-bridge.service >/dev/null <<'EOF'
[Unit]
Description=BurnCare bridge API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/burn-care-bot/burnCareBridge
Environment=BOT_REPO=/home/ubuntu/burn-care-bot
Environment=ALLOWED_ORIGINS=https://your-site.netlify.app
ExecStart=/home/ubuntu/burn-care-bot/burnCareBridge/.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8123
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now burncare-bridge
```

`ALLOWED_ORIGINS` locks CORS to your hosted page origin (comma-separated for
several). Leaving it `*` also works for a quick demo but lets other sites use
your quota.

## Notes / limits

- The bridge and the Telegram bot **share the same Gemini key** and the same
  free-tier quota. Heavy demo traffic can starve the bot (and vice versa).
  The bot already has a multi-model fallback chain; expect occasional
  "try again" replies on the free tier.
- The page sends `history` with every message (last 12 entries = 6 turns,
  exactly like the bot keeps in memory); the bridge is stateless.
- Photo flow in the page mirrors the bot: analyze → ask age → Lund & Browder
  report; multiple photos of different areas add up to one case.
- No authentication: fine for a prototype demo on an obscure URL; add a simple
  header token later if it gets shared widely.
- Do **not** use real patient photos — free-tier Gemini data terms apply.
