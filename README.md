# 🛡 Haveloc Guardian

> 24/7 Placement Email Monitoring & Alert Automation System  
> Built for **Sudharsan S** · SRMIST Trichy · Agentic AI Engineer

---

## What it does

Monitors your college Gmail 24/7 for Haveloc placement emails, parses Excel/PDF shortlists, and fires alerts through Telegram → Pushover (iPhone) → SMS before you miss a single opportunity.

```
Email arrives → Detect sender → Parse body + attachments
→ Find your name/reg number → Extract company/date/time
→ Blast alerts → Create calendar event → Schedule 3 reminders
```

---

## Features

| Feature | Detail |
|---|---|
| 📬 Email polling | Every 60s via IMAP |
| 📎 Attachment parsing | Excel (.xlsx/.xls), PDF, CSV, TXT |
| 🎯 Identity detection | Name variants + Register number + Email |
| 📊 Priority scoring | Keyword-weighted (CRITICAL / HIGH / MEDIUM / LOW) |
| 🚨 Multi-channel alerts | Telegram → Pushover → SMS (fallback chain) |
| 📅 Google Calendar | Auto-creates events with 60/30/10 min reminders |
| ⏰ Countdown reminders | 60 min, 30 min, 10 min before event |
| 📊 Daily summary | 8 PM IST digest |
| 🤖 Telegram commands | /status /check /events /summary /help |
| 🔁 Deduplication | Never notifies same email twice |
| 🛡 Crash recovery | Auto-retry with exponential backoff |
| 🌐 Dashboard | Live status page at / |

---

## Quick Setup

### 1. Clone & Install

```bash
git clone https://github.com/Sudharsanselvaraj/haveloc-guardian
cd haveloc-guardian
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Gmail App Password

1. Go to Google Account → Security → 2-Step Verification → App Passwords
2. Create app password for "Mail"
3. Paste into `GMAIL_APP_PASSWORD` in `.env`

### 4. Telegram Bot

1. Message `@BotFather` on Telegram
2. `/newbot` → get token → set `TELEGRAM_BOT_TOKEN`
3. Message your bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copy `chat.id` → set `TELEGRAM_CHAT_ID`

### 5. Pushover (iPhone Push)

1. Install Pushover app (₹100 one-time)
2. Get User Key from app
3. Create application at pushover.net → get API token
4. Set `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN`

### 6. Google Calendar (Optional)

1. Go to Google Cloud Console
2. Enable Google Calendar API
3. Create OAuth2 credentials → download as `credentials.json`
4. Place in project root
5. Run locally once to authorize: `python guardian.py`
6. Upload generated `logs/token.json` to Render as secret file

### 7. Fast2SMS (SMS Fallback, Optional)

1. Register at fast2sms.com
2. Get API key → set `FAST2SMS_API_KEY`
3. Set `USER_PHONE` (e.g., +919XXXXXXXXX)

---

## Deploy on Render

### Option A: render.yaml (recommended)

1. Push to GitHub
2. Connect repo to Render
3. Render auto-detects `render.yaml`
4. Add secret env vars in Render dashboard:
   - `GMAIL_APP_PASSWORD`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `PUSHOVER_USER_KEY` / `PUSHOVER_API_TOKEN`
5. Deploy

### Option B: Manual

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`

### Keep Render Free Tier Awake

1. Go to [UptimeRobot](https://uptimerobot.com)
2. New monitor → HTTP(s)
3. URL: `https://your-render-url.onrender.com/health`
4. Interval: 5 minutes
5. Done — Render won't sleep

---

## Telegram Bot Commands

| Command | Action |
|---|---|
| `/status` | System health, stats, uptime |
| `/check` | Force an email check right now |
| `/events` | List upcoming tracked events |
| `/summary` | Today's placement summary |
| `/help` | All commands |

---

## Priority Levels

| Level | Score | Action |
|---|---|---|
| CRITICAL | 10+ | All channels + emergency mode |
| HIGH | 5-9 | Telegram + Pushover |
| MEDIUM | 2-4 | Telegram only |
| LOW | 0-1 | Telegram silent notification |

---

## Identity Detection

Searches every row/column across all sheets for:

- `Sudharsan` (any case)
- `Sudharsan S`
- `RA2211028010001`
- `sudharsan@srmist.edu.in`

Returns confidence score: `1.0` (exact) → `0.8` (partial) → `0.6` (fuzzy)

---

## Project Structure

```
haveloc-guardian/
├── main.py                          # FastAPI app + dashboard
├── guardian.py                      # Main loop + APScheduler
├── requirements.txt
├── render.yaml
├── .env.example
├── config/
│   └── settings.py
├── app/
│   ├── core/
│   │   └── email_monitor.py         # IMAP polling + deduplication
│   ├── parsers/
│   │   ├── attachment_parser.py     # Excel/PDF/CSV/TXT parser
│   │   └── event_extractor.py      # Company/date/time extraction
│   ├── notifiers/
│   │   ├── telegram_notifier.py    # Telegram rich messages
│   │   ├── pushover_notifier.py    # iPhone push notifications
│   │   └── sms_notifier.py         # Fast2SMS fallback
│   ├── handlers/
│   │   ├── calendar_manager.py     # Google Calendar integration
│   │   ├── reminder_scheduler.py   # Countdown reminders
│   │   └── notification_orchestrator.py  # Routes all alerts
│   └── utils/
│       └── logger.py               # Loguru logger
└── logs/
    ├── processed_ids.json           # Deduplication store
    ├── tracked_events.json          # Event registry
    └── guardian_YYYY-MM-DD.log
```

---

## Notification Flow

```
New Haveloc Email
       │
       ▼
  Priority Score
       │
  ┌────┴────────────────┐
  │                     │
Identity Found?     Emergency?
  │ YES                 │ YES
  ▼                     ▼
ALL CHANNELS      Telegram ×3
+ Calendar        + Pushover
+ Reminders       + Pushover Emergency
  │
  ▼
Telegram → Pushover → SMS (if both fail)
```

---

## Local Development

```bash
cp .env.example .env
# Fill in credentials
python -m uvicorn main:app --reload --port 8000
```

Dashboard: http://localhost:8000  
Health: http://localhost:8000/health  
Status: http://localhost:8000/status

---

*Haveloc Guardian — You sleep, it watches.* 🛡
