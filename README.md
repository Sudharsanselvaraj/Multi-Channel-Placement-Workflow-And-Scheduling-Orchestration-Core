<div align="center">

"""
 ██╗  ██╗ █████╗ ██╗   ██╗███████╗██╗      ██████╗  ██████╗
 ██║  ██║██╔══██╗██║   ██║██╔════╝██║     ██╔═══██╗██╔════╝
 ███████║███████║██║   ██║█████╗  ██║     ██║   ██║██║
 ██╔══██║██╔══██║╚██╗ ██╔╝██╔══╝  ██║     ██║   ██║██║
 ██║  ██║██║  ██║ ╚████╔╝ ███████╗███████╗╚██████╔╝╚██████╗
 ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝ ╚═════╝  ╚═════╝
                     G U A R D I A N
"""

print(BANNER)

**Multi-Channel Placement Workflow & Scheduling Orchestration Core**

*24/7 Autonomous Email Intelligence · Real-Time Shortlist Detection · Zero-Miss Architecture*

---

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.10-FF6B35?style=flat-square)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-2CA5E0?style=flat-square&logo=telegram&logoColor=white)
![Render](https://img.shields.io/badge/Deployed-Render-46E3B7?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Production-brightgreen?style=flat-square)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [System Architecture](#system-architecture)
4. [Full Data Flow](#full-data-flow)
5. [Module Reference](#module-reference)
6. [Notification Pipeline](#notification-pipeline)
7. [Priority & Scoring Engine](#priority--scoring-engine)
8. [Identity Detection Engine](#identity-detection-engine)
9. [Event Extraction Engine](#event-extraction-engine)
10. [Scheduler Architecture](#scheduler-architecture)
11. [API Reference](#api-reference)
12. [Configuration Reference](#configuration-reference)
13. [Deployment Guide — Render + UptimeRobot](#deployment-guide)
14. [Local Development](#local-development)
15. [Telegram Bot Commands](#telegram-bot-commands)
16. [Project Structure](#project-structure)
17. [Tech Stack](#tech-stack)
18. [Security Design](#security-design)
19. [Failure & Recovery Model](#failure--recovery-model)

---

## Overview

**Haveloc Guardian** is a production-grade, fully autonomous placement monitoring system built for students on the Haveloc placement portal. It continuously polls Gmail via IMAP, detects placement-related emails from Haveloc senders, parses Excel/PDF shortlist attachments to detect identity presence, extracts structured event metadata, and delivers multi-channel notifications through a priority-based orchestration pipeline — all without any manual intervention.

The system runs on Render (free tier) with UptimeRobot keepalive, executes a check cycle every 60 seconds, and maintains state across restarts via JSON-backed deduplication and event registries.

**Core guarantee:** If your name or register number appears in any Haveloc email or its attachment, you will receive a CRITICAL alert within 60 seconds — on Telegram, and optionally via Pushover (iPhone push) and Fast2SMS (India SMS fallback).

---

## Problem Statement

Placement communications through the Haveloc portal arrive as emails at unpredictable times. The student's identity may be buried inside an Excel spreadsheet attached to the email, not in the email body itself. Missing these notifications — due to sleep, distraction, or delayed awareness — can directly cost career opportunities.

Manual monitoring is unsustainable. This system eliminates the problem entirely through:

- Continuous 60-second IMAP polling, 24/7/365
- Automated attachment download and full-document identity scan
- Keyword-weighted priority classification (CRITICAL / HIGH / MEDIUM / LOW)
- Immediate multi-channel blast for shortlist events
- Countdown reminders at 60, 30, and 10 minutes before every tracked event
- MD5-based email deduplication to prevent repeated alerts

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HAVELOC GUARDIAN                                │
│                    Render Cloud · Singapore Region                      │
│                                                                         │
│  ┌─────────────────┐        ┌──────────────────────────────────────┐    │
│  │   FastAPI App   │        │          HavelocGuardian             │    │
│  │   (main.py)     │        │           (guardian.py)              │    │
│  │                 │        │                                      │    │
│  │  GET  /health   │        │  ┌────────────────────────────────┐  │    │
│  │  GET  /status   │        │  │      APScheduler (AsyncIO)     │  │    │ 
│  │  POST /check    │◄──────►│  │                                │  │    │
│  │  POST /webhook  │        │  │  email_poll  → every 60s       │  │    │
│  │  GET  /         │        │  │  daily_summary → 20:00 IST     │  │    │
│  └─────────────────┘        │  │  system_status → every 6h      │  │    │
│                             │  │  reminder_N → DateTrigger      │  │    │
│                             │  └────────────────────────────────┘  │    │
│                             └──────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌─────────────┐              ┌─────────────────────┐
  │ UptimeRobot │              │    Gmail IMAP SSL   │
  │ ping /health│              │   imap.gmail.com    │
  │ every 5 min │              │      Port 993       │
  └─────────────┘              └─────────────────────┘
```

```
                        INTERNAL MODULE MAP

  EmailMonitor ──────────────────────────────────────────────────────┐
  │  IMAP SSL connect / retry                                        │
  │  Sender filter (haveloc.com domains)                             │
  │  Body extraction (text/plain → text/html fallback)               │
  │  Attachment download (xlsx, xls, csv, pdf, txt)                  │
  │  MD5 deduplication (processed_ids.json)                          │
  │  Priority scoring (keyword-weighted)                             │
  └──────────────────────────────────────────────────────────────────┘
         │
         ▼ email_data dict
  AttachmentParser ──────────────────────────────────────────────────┐
  │  .xlsx/.xls  → openpyxl (multi-sheet, read_only)                 │
  │  .csv        → csv.reader (streaming)                            │
  │  .pdf        → pdfplumber (text + table extraction)              │
  │  .txt        → line-by-line scan                                 │
  │  identity_score() → (found, confidence, matched_identity)        │
  │  Confidence: 1.0 exact | 0.8 partial | 0.0 none                  │
  └──────────────────────────────────────────────────────────────────┘
         │
         ▼ attachment_results[]
  EventExtractor ────────────────────────────────────────────────────┐
  │  Company extraction (regex + known company fallback list)        │
  │  Event type classification (12 types mapped)                     │
  │  Date parsing (6 patterns + relative: today/tomorrow)            │
  │  Time parsing (12hr / 24hr / relative)                           │
  │  Duration extraction (mins/hrs → normalized to minutes)          │
  │  End time computation (start + duration)                         │
  │  Meeting link extraction (URL filter)                            │
  │  Platform detection (HackerRank, Zoom, Teams, etc.)              │
  │  Instruction extraction (regex on notes/important blocks)        │
  └──────────────────────────────────────────────────────────────────┘
         │
         ▼ event dict
  NotificationOrchestrator ─────────────────────────────────────────┐
  │  Route: SHORTLIST → all channels                                │
  │  Route: EMERGENCY → Telegram ×3                                 │
  │  Route: HIGH/CRITICAL → Telegram + Pushover                     │
  │  Route: MEDIUM/LOW → Telegram only                              │
  │  Calendar event creation (if datetime_obj available)            │
  │  Reminder scheduling (60/30/10 min via APScheduler)             │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼ dispatch
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │  Telegram    │   │   Pushover   │   │  Fast2SMS    │
  │  (primary)   │   │ (iPhone push)│   │ (SMS India)  │
  │  Bot API     │   │  REST API    │   │  REST API    │
  └──────────────┘   └──────────────┘   └──────────────┘
         │
         ▼
  ┌──────────────────────┐
  │   Google Calendar    │
  │   Event + Reminders  │
  │   (OAuth2 v3 API)    │
  └──────────────────────┘
```

---

## Full Data Flow

```
  ┌──────────────────────────────────────────────────────────┐
  │                  60-SECOND POLL CYCLE                    │
  └──────────────────────────────────────────────────────────┘
         │
         ▼
  [1] IMAP FETCH
      └─ Search inbox: FROM "alerts@haveloc.com"
      └─ Search inbox: FROM "srm@haveloc.com"
      └─ Search inbox: FROM "haveloc" (domain catch-all)
      └─ Deduplicate message IDs (set union)
         │
         ▼
  [2] DEDUPLICATION CHECK
      └─ Generate MD5 hash: (Message-ID + Subject)
      └─ Compare against logs/processed_ids.json
      └─ If already seen → SKIP
      └─ If new → CONTINUE
         │
         ▼
  [3] SENDER VALIDATION
      └─ Check from_addr against haveloc_senders_list
      └─ Check from_addr against haveloc_domains_list
      └─ If not Haveloc → SKIP
         │
         ▼
  [4] BODY + ATTACHMENT EXTRACTION
      └─ Walk MIME parts → extract text/plain (fallback: strip HTML)
      └─ Walk MIME parts → download supported attachments
         Supported: .xlsx .xls .csv .pdf .txt
         Save to: logs/temp_attachments/
         │
         ▼
  [5] PRIORITY SCORING
      └─ Score += 3 per HIGH keyword match
      └─ Score += 1 per MEDIUM keyword match
      └─ Score >= 10 → CRITICAL
      └─ Score  5-9  → HIGH
      └─ Score  2-4  → MEDIUM
      └─ Score  0-1  → LOW
      └─ Emergency flag: "today" / "urgent" / "deadline" / "asap"
         │
         ▼
  [6] ATTACHMENT PARSING (per file)
      └─ Excel: openpyxl, all sheets, all rows, all columns
      └─ CSV: csv.reader, streaming
      └─ PDF: pdfplumber, text lines + table cells
      └─ TXT: line-by-line
      └─ identity_score(cell) → (found, confidence, match_label)
         Stop early if confidence == 1.0
         │
         ▼
  [7] EVENT EXTRACTION
      └─ Company: regex + subject heuristics + known list (100+ companies)
      └─ Event type: keyword-to-label mapping (12 types)
      └─ Date: 6 regex patterns + relative date resolution
      └─ Time: 12hr / 24hr regex
      └─ Duration: min/hr patterns → normalize to minutes
      └─ End time: start_dt + duration_mins
      └─ Link: URL regex with skip-filter
      └─ Platform: keyword detection (10 platforms)
      └─ Instructions: regex on note/important blocks
         │
         ▼
  [8] NOTIFICATION ROUTING
      ┌──────────────────────────────────────────────────────┐
      │  identity_found == True  →  SHORTLIST PATH           │
      │    Telegram: full shortlist message (rich markdown)  │
      │    SMS: shortlist alert                              │
      │    Calendar: create event + 4 reminders              │
      │    APScheduler: queue 60/30/10 min countdown jobs    │
      ├──────────────────────────────────────────────────────┤
      │  is_emergency == True  →  EMERGENCY PATH             │
      │    Telegram: emergency message × 3                   │
      ├──────────────────────────────────────────────────────┤
      │  priority in CRITICAL/HIGH  →  GENERAL HIGH PATH     │
      │    Telegram: general alert with keywords             │
      ├──────────────────────────────────────────────────────┤
      │  priority MEDIUM/LOW  →  SILENT PATH                 │
      │    Telegram: minimal notification                    │
      └──────────────────────────────────────────────────────┘
         │
         ▼
  [9] CLEANUP
      └─ Remove temp attachment files
      └─ Save email hash to processed_ids.json
      └─ Update runtime stats
```

---

## Module Reference

### `guardian.py` — Orchestration Core

The `HavelocGuardian` class is the runtime core. It owns the APScheduler instance and wires all subsystems together.

```
HavelocGuardian
│
├── __init__()
│     └─ Instantiates: EmailMonitor, AttachmentParser,
│                       EventExtractor, NotificationOrchestrator
│     └─ stats: {total_processed, shortlists_found, events_tracked,
│                start_time, last_check}
│
├── startup()
│     └─ mkdir logs/temp_attachments
│     └─ email_monitor.connect()
│     └─ scheduler.add_job(run_check, IntervalTrigger(60s))
│     └─ scheduler.add_job(send_daily_summary, CronTrigger(20:00 IST))
│     └─ scheduler.add_job(send_status, CronTrigger(*/6h))
│     └─ scheduler.start()
│     └─ Sends startup Telegram notification
│     └─ Runs first check immediately
│
├── run_check()
│     └─ Calls fetch_new_emails()
│     └─ Per email: parse attachments → extract event → route notification
│     └─ Updates runtime stats
│
├── send_daily_summary()   → delegates to orchestrator
├── send_status()          → assembles stats dict → orchestrator
└── shutdown()             → scheduler.shutdown + imap.disconnect
```

### `app/core/email_monitor.py` — IMAP Engine

```
EmailMonitor
│
├── connect()          IMAP4_SSL + login + select("inbox") [retry ×3]
├── disconnect()       Graceful IMAP logout
├── fetch_new_emails() Full poll cycle → List[email_data dict]
├── is_haveloc_sender() Sender validation against configured lists
├── decode_header_value() RFC2047 header decoding
├── extract_body()     MIME walk → text/plain, HTML strip fallback
└── download_attachments() Filter by extension → save to temp dir

Functions:
├── compute_priority_score(text) → (score, label, matched_keywords)
├── is_emergency(text)           → bool
├── load_processed_ids()         → set
├── save_processed_id(hash)      → persists to JSON
└── generate_email_hash(id, sub) → MD5 hex string
```

### `app/parsers/attachment_parser.py` — Document Intelligence

```
AttachmentParser
│
├── parse(filepath)     → result dict (dispatcher)
├── _parse_excel()      openpyxl read_only, multi-sheet iteration
├── _parse_csv()        csv.reader streaming
├── _parse_pdf()        pdfplumber text lines + table cells
└── _parse_txt()        line-by-line file scan

identity_score(cell_text) → (found: bool, confidence: float, label: str)
  Priority order:
    1. Register number  → confidence 1.0
    2. Email address    → confidence 1.0
    3. Exact name match → confidence 1.0
    4. Partial name     → confidence 0.8
    5. No match         → confidence 0.0
```

### `app/parsers/event_extractor.py` — NLP Metadata Engine

```
EventExtractor
│
└── extract(email_data) → event dict
    ├── _extract_company()      Subject heuristics + COMPANY_PATTERNS
    │                           + 100+ known company fallback list
    ├── _extract_event_type()   EVENT_TYPE_MAP (12 types)
    ├── _extract_date()         6 regex patterns + relative resolution
    ├── _extract_time()         3 regex patterns (12hr/24hr)
    ├── _extract_duration()     3 patterns → normalized to minutes
    ├── _extract_link()         URL regex with skip-filter
    ├── _extract_platform()     10 platform keyword mappings
    ├── _extract_instructions() regex on note/important/guideline blocks
    └── _parse_full_datetime()  dateutil.parser + IST localize
```

### `app/handlers/notification_orchestrator.py` — Routing Core

```
NotificationOrchestrator
│
├── handle_email(email_data, event, attachment_results)
│     └─ Routing decision tree (identity → emergency → HIGH → LOW)
│     └─ Calendar event creation
│     └─ Reminder scheduling
│
├── _send_shortlist_alerts()   Telegram + SMS
├── _send_emergency_alerts()   Telegram ×3
├── _send_general_alerts()     Telegram
├── send_daily_summary()       → reminder_scheduler.get_todays/upcoming
└── send_status(status_dict)   → telegram.send_system_status
```

### `app/handlers/calendar_manager.py` — Google Calendar

```
CalendarManager
│
├── _get_service()    OAuth2 lazy init, token refresh, token.json cache
└── create_event()    Build calendar_event dict → events().insert()
    Reminders: popup 60min, popup 30min, popup 10min, email 60min
    Color: Red (colorId=11)
    Location: meeting_link (if present)
```

### `app/handlers/reminder_scheduler.py` — Countdown Engine

```
ReminderScheduler
│
├── schedule_reminders(event_id, company, event_type,
│                       datetime_obj, time_str, notifiers)
│     └─ For each offset in [60, 30, 10]:
│           reminder_time = datetime_obj - timedelta(minutes=offset)
│           Skip if reminder_time <= now
│           scheduler.add_job(send_reminder, DateTrigger)
│
├── get_todays_events()     → filter tracked_events.json by today's date
└── get_upcoming_events(7)  → filter by now < dt <= now+7days, sorted
```

---

## Notification Pipeline

```
  INCOMING EMAIL (Haveloc sender, new hash)
         │
         ├─── identity_found == True ──────────────────────────────────┐
         │                                                             │
         │    ┌────────────────────────────────────────────────────┐   │
         │    │  🚨 SHORTLIST ALERT (FULL BLAST)                    │  │
         │    │                                                     │  │
         │    │  Telegram ──► Rich markdown message                 │  │
         │    │    Company | Event | Date | Time | Duration         │  │
         │    │    Identity match | Confidence % | Filename         │  │
         │    │    Priority score | Meeting link | Instructions     │  │
         │    │                                                     │  │
         │    │  SMS ──────► 160-char shortlist alert               │  │
         │    │    "SHORTLISTED! {company} - {event} at {time}"     │  │
         │    │                                                     │  │
         │    │  Calendar ─► Event + 4 reminder overrides           │  │
         │    │  Scheduler ► 60/30/10 min countdown jobs            │  │
         │    └─────────────────────────────────────────────────────┘  │
         │                                                             │
         ├─── is_emergency == True ────────────────────────────────────┤
         │    ┌──────────────────────────────────┐                     │
         │    │  🆘 EMERGENCY ALERT              │                     │
         │    │  Telegram ×3 (repeated sends)    │                     │
         │    └──────────────────────────────────┘                     │
         │                                                             │
         ├─── priority in {CRITICAL, HIGH} ───────────────────────────┤
         │    ┌──────────────────────────────────┐                    │
         │    │  ⚠️ GENERAL HIGH ALERT           │                    │
         │    │  Telegram: general alert msg     │                    │
         │    │  Calendar: if datetime available │                    │
         │    │  Reminders: if datetime present  │                    │
         │    └──────────────────────────────────┘                    │
         │                                                            │
         └─── priority in {MEDIUM, LOW} ──────────────────────────────┘
              ┌──────────────────────────────────┐
              │  ℹ️ MINIMAL ALERT                │
              │  Telegram: general_alert only    │
              └──────────────────────────────────┘

  COUNTDOWN REMINDER JOBS (APScheduler DateTrigger)
  ┌──────────────────────────────────────────────────────────────┐
  │  T-60 min → 🟢 Telegram + Pushover                           │
  │  T-30 min → 🟡 Telegram + Pushover + SMS                     │
  │  T-10 min → 🔴 Telegram + Pushover(siren) + SMS              │
  └──────────────────────────────────────────────────────────────┘

  SCHEDULED JOBS (APScheduler CronTrigger)
  ┌──────────────────────────────────────────────────────────────┐
  │  20:00 IST daily → Daily summary (today's events + upcoming) │
  │  Every 6 hours   → System status report                      │
  └──────────────────────────────────────────────────────────────┘
```

---

## Priority & Scoring Engine

The scoring engine runs against the concatenated `subject + body` text of every email.

```
KEYWORD SCORING TABLE

  HIGH PRIORITY KEYWORDS (score += 3 per match)
  ─────────────────────────────────────────────
  shortlist      selected        test
  interview      assessment      deadline
  today          urgent          exam
  evaluation     process scheduled        online test
  aptitude       technical round hr round
  offer          placed          congratulations

  MEDIUM PRIORITY KEYWORDS (score += 1 per match)
  ─────────────────────────────────────────────────
  application submitted   schedule      next step
  round                   instructions  registration
  confirm

  LOW PRIORITY KEYWORDS (score += 0 per match)
  ─────────────────────────────────────────────
  announcement    newsletter    general information
  update          information

SCORE → LABEL MAPPING
  score >= 10  →  CRITICAL   🚨
  score  5-9   →  HIGH       ⚠️
  score  2-4   →  MEDIUM     📢
  score  0-1   →  LOW        ℹ️

EMERGENCY FLAG (independent of score)
  Triggers if ANY of these appear in email text:
  today | urgent | deadline | now | immediately | asap
```

---

## Identity Detection Engine

Every cell, row, and line in every supported attachment is scanned against the configured identity. Detection stops early on a confidence 1.0 match.

```
IDENTITY MATCHING PRIORITY

  1. Register Number (exact substring match)
     Input:   "RA2311003050045"
     Matches: "RA2311003050045", "ra2311003050045"
     Confidence: 1.0

  2. College Email (exact substring match)
     Input:   "ss0856@srmist.edu.in"
     Matches: "ss0856@srmist.edu.in", "SS0856@SRMIST.EDU.IN"
     Confidence: 1.0

  3. Name Variants (configurable, comma-separated)
     Configured: "Sudharsan S,Sudharsan,SUDHARSAN,sudharsan"
     Exact cell match  → Confidence: 1.0
     Substring match   → Confidence: 0.8

  4. No match          → Confidence: 0.0

DOCUMENT SCAN COVERAGE

  Excel (.xlsx/.xls)
  ├── All sheets in workbook
  ├── All rows (ws.iter_rows, read_only=True)
  ├── All columns joined: "col1 | col2 | col3"
  └── Early stop: confidence == 1.0

  PDF (.pdf)
  ├── All pages
  ├── page.extract_text() → split by newline
  ├── page.extract_tables() → all table cells
  └── Early stop: confidence == 1.0 per page

  CSV (.csv)
  ├── Streaming read (memory-safe)
  ├── Row text: "col1 | col2 | col3"
  └── Early stop: confidence == 1.0

  TXT (.txt)
  ├── Line-by-line scan
  └── Early stop: confidence == 1.0
```

---

## Event Extraction Engine

```
EXTRACTION TARGETS

  Company Name
  ├── Subject heuristics (first 5 lines of email)
  │     Pattern: "REMINDER: {Company}"
  │     Pattern: "^{COMPANY} Hackathon|Test|Interview"
  │     Pattern: "{Company} - {Role}"
  ├── Regex patterns (COMPANY_PATTERNS list, 7 patterns)
  ├── Known company fallback (100+ companies hardcoded)
  └── Default: "Placement Alert"

  Event Type (12 mapped types)
  ├── online test      → "Online Test"
  ├── aptitude test    → "Aptitude Test"
  ├── technical test   → "Technical Test"
  ├── interview        → "Interview"
  ├── hr interview     → "HR Interview"
  ├── technical interview → "Technical Interview"
  ├── assessment       → "Assessment"
  ├── gd               → "Group Discussion"
  ├── group discussion → "Group Discussion"
  ├── ppt              → "Pre-Placement Talk"
  ├── pre-placement    → "Pre-Placement Talk"
  └── default          → "Placement Event"

  Date (6 regex patterns)
  ├── DD-MM-YYYY / DD/MM/YYYY   e.g., 07-04-2026
  ├── YYYY-MM-DD                e.g., 2026-04-07
  ├── D Month YYYY              e.g., 7 April 2026
  ├── Month D, YYYY             e.g., April 7, 2026
  ├── "today"   → datetime.now(IST).strftime()
  └── "tomorrow" → (now + 1day).strftime()

  Time (3 patterns)
  ├── HH:MM AM/PM               e.g., 2:00 PM
  ├── HH AM/PM                  e.g., 2 PM
  └── HH:MM (24hr)              e.g., 14:00

  Duration
  ├── {N} MINS / MINUTES        e.g., 90 MINS
  ├── {N} HRS / HOURS           e.g., 1.5 HRS → 90 mins
  └── duration: {N} mins

  Platform Detection
  ├── hackerrank → HackerRank
  ├── hackerearth → HackerEarth
  ├── amcat → AMCAT
  ├── mettl → Mettl
  ├── zoom → Zoom
  ├── meet.google → Google Meet
  ├── teams → Microsoft Teams
  └── webex → Webex
```

---

## Scheduler Architecture

```
APScheduler (AsyncIOScheduler, timezone=Asia/Kolkata)

  Job: email_poll
  ├── Trigger: IntervalTrigger(seconds=60)
  ├── misfire_grace_time: 30s
  └── replace_existing: True

  Job: daily_summary
  ├── Trigger: CronTrigger(hour=20, minute=0)
  └── replace_existing: True

  Job: system_status
  ├── Trigger: CronTrigger(hour="*/6")
  └── replace_existing: True

  Dynamic Jobs: reminder_{event_id}_{N}min
  ├── Trigger: DateTrigger(run_date=event_dt - timedelta(minutes=N))
  ├── misfire_grace_time: 300s
  └── replace_existing: True

State persistence:
  logs/processed_ids.json   →  MD5 hashes of processed emails
  logs/tracked_events.json  →  Event registry for reminders/summary
  logs/token.json           →  Google Calendar OAuth2 token
```

---

## API Reference

### `GET /health`
Health check endpoint. Pinged by UptimeRobot every 5 minutes to keep Render free tier alive.

**Response:**
```json
{
  "status": "ok",
  "service": "haveloc-guardian",
  "timestamp": "2026-04-07T14:32:00+05:30",
  "uptime_stats": {
    "total_processed": 42,
    "shortlists_found": 3,
    "last_check": "02:31 PM, 07 Apr"
  }
}
```

### `GET /status`
Full system status including scheduler job queue.

**Response:**
```json
{
  "status": "running",
  "user": "Sudharsan S",
  "monitoring": "ss0856@srmist.edu.in",
  "poll_interval": 60,
  "stats": { ... },
  "scheduler_jobs": [
    { "id": "email_poll", "next_run": "2026-04-07 14:33:00+05:30" },
    { "id": "daily_summary", "next_run": "2026-04-07 20:00:00+05:30" },
    { "id": "system_status", "next_run": "2026-04-07 18:00:00+05:30" }
  ]
}
```

### `POST /trigger-check`
Manually trigger an immediate email check (runs in background).

**Response:**
```json
{
  "message": "Email check triggered",
  "timestamp": "2026-04-07T14:32:00+05:30"
}
```

### `POST /telegram-webhook`
Telegram Bot webhook receiver. Processes commands from the authorized chat only.

**Security:** Validates `chat_id` against `TELEGRAM_CHAT_ID`. Unknown chat IDs are silently dropped.

### `GET /`
Live status dashboard (HTML). Displays pulse indicator, email stats, and identity config.

---

## Configuration Reference

All configuration is loaded from environment variables (via `.env` locally, Render env vars in production).

```
VARIABLE                  DEFAULT                         DESCRIPTION
─────────────────────────────────────────────────────────────────────────────
USER_NAME                 Sudharsan S                     Display name
USER_NAME_VARIANTS        Sudharsan,SUDHARSAN,...         Comma-sep search variants
REGISTER_NUMBER           RA2311003050045                 Primary identity token
COLLEGE_EMAIL             ss0856@srmist.edu.in            Email identity token

GMAIL_ADDRESS             (required)                      Gmail to monitor
GMAIL_APP_PASSWORD        (required)                      Gmail App Password (not login pw)
IMAP_SERVER               imap.gmail.com                  IMAP host
IMAP_PORT                 993                             IMAP SSL port

TELEGRAM_BOT_TOKEN        (required)                      BotFather token
TELEGRAM_CHAT_ID          (required)                      Your personal chat ID

PUSHOVER_USER_KEY         (optional)                      Pushover user key
PUSHOVER_API_TOKEN        (optional)                      Pushover app token

FAST2SMS_API_KEY          (optional)                      Fast2SMS API key (India)
USER_PHONE                (optional)                      +91XXXXXXXXXX

GOOGLE_CALENDAR_ID        primary                         Calendar to create events in
GOOGLE_CREDENTIALS_JSON   credentials.json                OAuth2 client secrets path

POLL_INTERVAL_SECONDS     60                              Email check frequency (seconds)
EMERGENCY_POLL_INTERVAL   30                              (reserved for future use)
TIMEZONE                  Asia/Kolkata                    All scheduling timezone
DAILY_SUMMARY_TIME        20:00                           HH:MM for daily digest

HAVELOC_SENDERS           alerts@haveloc.com,...          Exact sender whitelist
HAVELOC_SENDER_DOMAINS    haveloc.com,career,...          Domain substring whitelist

LOG_LEVEL                 INFO                            Loguru log level
ENVIRONMENT               production                      Runtime environment tag
```

---

## Deployment Guide

### Prerequisites

- GitHub account with this repo pushed
- Render account (free tier)
- UptimeRobot account (free)
- Gmail App Password enabled on your college account
- Telegram bot token + your chat ID

### Step 1 — Gmail App Password

```
Google Account → Security → 2-Step Verification
→ App Passwords → Select app: Mail → Generate
→ Copy the 16-character password
```

### Step 2 — Telegram Bot Setup

```
1. Open Telegram → search @BotFather
2. Send: /newbot
3. Follow prompts → copy the token
4. Start your bot → send /start
5. Get your chat ID:
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   → Look for "chat": {"id": XXXXXXXXX}
```

### Step 3 — Deploy on Render

```
1. Push repo to GitHub
2. Render Dashboard → New → Web Service → Connect GitHub repo
3. Configure:
     Name:          haveloc-guardian
     Region:        Singapore
     Branch:        main
     Runtime:       Python 3
     Build Command: pip install --no-cache-dir -r requirements.txt
     Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
     Plan:          Free

4. Add Environment Variables (Render Dashboard → Environment):
     GMAIL_ADDRESS         → your college email
     GMAIL_APP_PASSWORD    → 16-char app password
     TELEGRAM_BOT_TOKEN    → BotFather token
     TELEGRAM_CHAT_ID      → your numeric chat ID
     (add optional vars as needed)

5. Click Deploy
```

### Step 4 — UptimeRobot Keepalive

```
1. UptimeRobot Dashboard → Add New Monitor
2. Monitor Type: HTTP(s)
3. Friendly Name: Haveloc Guardian
4. URL: https://your-service.onrender.com/health
5. Monitoring Interval: Every 5 minutes
6. Create Monitor
```

This prevents Render's free tier from spinning down. Your health endpoint returns in <100ms, well within Render's keepalive window.

### Step 5 — Google Calendar (Optional)

```
1. Google Cloud Console → New Project
2. APIs & Services → Enable: Google Calendar API
3. Credentials → Create OAuth 2.0 Client ID
     Application type: Desktop app
4. Download JSON → rename to credentials.json
5. Run locally once:
     python guardian.py
     → Browser opens → authorize
     → logs/token.json is created
6. Upload logs/token.json to Render as Secret File
     (Dashboard → Environment → Secret Files)
```

---

## Local Development

```bash
# Clone
git clone https://github.com/Sudharsanselvaraj/Multi-Channel-Placement-Workflow-And-Scheduling-Orchestration-Core
cd Multi-Channel-Placement-Workflow-And-Scheduling-Orchestration-Core

# Install dependencies
pip install -r requirements.txt

# Configure
cp env.example .env
# Edit .env with your credentials

# Run
uvicorn main:app --reload --port 8000

# Endpoints
open http://localhost:8000          # Live dashboard
open http://localhost:8000/health   # Health check
open http://localhost:8000/status   # Full status JSON
curl -X POST http://localhost:8000/trigger-check  # Force check
```

**Logs location:**
```
logs/guardian_YYYY-MM-DD.log     # Daily rotating log
logs/errors.log                  # Error-only log (30 day retention)
logs/processed_ids.json          # Deduplication store
logs/tracked_events.json         # Event registry
logs/temp_attachments/           # Transient attachment downloads
```

---

## Telegram Bot Commands

| Command | Description |
|---|---|
| `/status` | System health, uptime, email count, shortlists found, last check time |
| `/check` | Force an immediate email check right now |
| `/events` | List upcoming tracked events (next 7 days) |
| `/summary` | Today's placement events + upcoming events digest |
| `/help` | All available commands |

---

## Project Structure

```
Multi-Channel-Placement-Workflow-And-Scheduling-Orchestration-Core/
│
├── main.py                          FastAPI app · /health · /status
│                                    /trigger-check · /telegram-webhook · /
│
├── guardian.py                      HavelocGuardian orchestration core
│                                    APScheduler setup · run_check() loop
│
├── requirements.txt                 Python dependencies (pinned versions)
├── runtime.txt                      python-3.11.9 (Render runtime hint)
├── render.yaml                      Render deployment manifest
├── env.example                      Environment variable template
│
├── config/
│   ├── __init__.py
│   └── settings.py                  Pydantic BaseSettings · all env vars
│                                    with list property helpers
│
├── app/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── email_monitor.py         IMAP4_SSL engine · fetch · deduplicate
│   │                                Body extraction · attachment download
│   │                                Priority scoring · emergency detection
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── attachment_parser.py     Excel/CSV/PDF/TXT document scanner
│   │   │                            identity_score() confidence engine
│   │   └── event_extractor.py       Company/date/time/duration extraction
│   │                                100+ company fallback list · 12 event types
│   │
│   ├── notifiers/
│   │   ├── __init__.py
│   │   ├── telegram_notifier.py     Telegram Bot API · 6 message templates
│   │   │                            shortlist · general · emergency · reminder
│   │   │                            daily_summary · system_status
│   │   ├── pushover_notifier.py     Pushover REST API · iPhone push
│   │   │                            Priority 2 (emergency ack required)
│   │   └── sms_notifier.py          Fast2SMS India REST API · 160-char limit
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── notification_orchestrator.py  Routing logic · fallback chain
│   │   │                                 Calendar trigger · reminder trigger
│   │   ├── calendar_manager.py           Google Calendar OAuth2 v3
│   │   │                                 Event creation · 4-reminder config
│   │   └── reminder_scheduler.py         APScheduler DateTrigger jobs
│   │                                     Countdown: 60/30/10 min
│   │                                     tracked_events.json persistence
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py                Loguru config · stdout + daily file
│                                    + errors.log · auto-rotation · gzip
│
└── logs/                            (gitignored, created at runtime)
    ├── guardian_YYYY-MM-DD.log
    ├── errors.log
    ├── processed_ids.json
    ├── tracked_events.json
    ├── token.json
    └── temp_attachments/
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Runtime | Python 3.11 | Core language |
| Web Framework | FastAPI 0.110 | HTTP API + lifespan management |
| ASGI Server | Uvicorn 0.27 | Production ASGI server |
| Scheduler | APScheduler 3.10 | Async cron + date-triggered jobs |
| Email Protocol | imaplib (stdlib) | IMAP4_SSL email polling |
| Settings | Pydantic-Settings 2.2 | Env var management + validation |
| HTTP Client | httpx (async) | Telegram / Pushover / Fast2SMS |
| Excel Parser | openpyxl | .xlsx / .xls read-only scanning |
| PDF Parser | pdfplumber | Text + table extraction |
| Date Parsing | python-dateutil | Flexible NLP date parsing |
| Timezone | pytz | IST localization |
| Retry Logic | tenacity | Exponential backoff decorators |
| Logging | loguru | Structured rotating logs |
| Calendar | google-api-python-client | Calendar v3 event management |
| Auth | google-auth-oauthlib | OAuth2 credential flow |
| Notifications | Telegram Bot API | Primary alert channel |
| Notifications | Pushover API | iPhone push (priority 2 emergency) |
| Notifications | Fast2SMS | India SMS fallback |
| Deployment | Render (free tier) | Cloud hosting |
| Keepalive | UptimeRobot | Render free-tier anti-sleep |

---

## Security Design

```
SECURITY PRINCIPLES

  ✅ Email-only monitoring
     No Haveloc portal login. No CAPTCHA bypass. No web scraping.
     The system reads only emails forwarded to your Gmail inbox.

  ✅ Gmail App Password isolation
     Uses a scoped App Password, not your Google account password.
     Revocable independently. Does not expose your primary credentials.

  ✅ Telegram webhook auth
     All webhook requests validated against TELEGRAM_CHAT_ID.
     Unknown chat IDs receive no response and generate no action.

  ✅ No credential logging
     Settings are loaded from env vars. No credentials appear in logs.
     Token files are gitignored.

  ✅ Minimal data retention
     processed_ids.json stores only MD5 hashes (not email content).
     Attachment files are deleted immediately after parsing.
     Logs auto-rotate after 7 days (compressed) and 30 days (errors).

  ✅ Read-only Gmail access
     IMAP polling uses the INBOX in read-only fetch mode.
     No emails are marked read, moved, or deleted by this system.
```

---

## Failure & Recovery Model

```
FAILURE SCENARIO          BEHAVIOR
────────────────────────────────────────────────────────────────────
IMAP connection drop      tenacity retry ×3, exponential backoff (2–15s)
                          On abort: disconnect → reconnect → retry

Telegram send failure     tenacity retry ×3, exponential backoff (2–8s)

SMS send failure          tenacity retry ×2, exponential backoff (2–6s)
                          Non-blocking: failure logged, pipeline continues

Calendar API failure      tenacity retry ×3, exponential backoff (2–10s)
                          Non-blocking: event skipped, reminder unaffected

Render service crash      Render auto-restart (web service health check)
                          processed_ids.json and tracked_events.json persist
                          across restarts — no duplicate notifications

UptimeRobot ping missed   Render may sleep up to 15 min on free tier
                          Emails accumulate in inbox during downtime
                          On wake: system fetches ALL unprocessed emails
                          in single cycle (no emails lost)

JSON corruption           load_processed_ids() returns empty set on parse error
                          Worst case: re-notification of recent emails

APScheduler misfire       misfire_grace_time=300s for reminders
                          Jobs missed by <5 min will still fire on wake
```

---

## Logging Output Example

```
2026-04-07 14:31:00 | INFO     | guardian:run_check:47 - 🔍 STARTING EMAIL CHECK
2026-04-07 14:31:01 | INFO     | email_monitor:fetch_new_emails:112 - 📬 Found 2 email(s)
2026-04-07 14:31:01 | INFO     | email_monitor:fetch_new_emails:138 - ✅ PASSED FILTER: Ather Energy Online Test
2026-04-07 14:31:02 | INFO     | attachment_parser:parse:48 - 🎯 IDENTITY FOUND in shortlist.xlsx
                                  Match: Register Number: RA2311003050045 | Confidence: 100%
2026-04-07 14:31:02 | INFO     | event_extractor:extract:61 - 📋 Extracted — Company: Ather Energy
                                  Type: Online Test | Date: 07-04-2026 | Time: 2:00 PM
2026-04-07 14:31:02 | INFO     | notification_orchestrator:handle_email:38 - 🎯 SHORTLIST CONFIRMED
2026-04-07 14:31:02 | INFO     | telegram_notifier:send:89 - ✅ Telegram notification sent
2026-04-07 14:31:03 | INFO     | sms_notifier:send:31 - ✅ SMS sent via Fast2SMS
2026-04-07 14:31:03 | INFO     | calendar_manager:create_event:78 - ✅ Calendar event created
2026-04-07 14:31:03 | INFO     | reminder_scheduler:schedule_reminders:47 - ⏰ Scheduled 60min reminder
2026-04-07 14:31:03 | INFO     | reminder_scheduler:schedule_reminders:47 - ⏰ Scheduled 30min reminder
2026-04-07 14:31:03 | INFO     | reminder_scheduler:schedule_reminders:47 - ⏰ Scheduled 10min reminder
2026-04-07 14:31:03 | INFO     | guardian:run_check:89 - 📬 Check complete. Processed: 2 emails
```

---

## Telegram Message Examples

**Shortlist Alert:**
```
🚨 SHORTLISTED — PLACEMENT ALERT 🚨

🏢 Company: Ather Energy
📋 Event: Online Test
📅 Date: 07-04-2026
⏰ Time: 2:00 PM
⏱ Duration: 90 minutes
🕐 Ends at: 3:30 PM
🖥 Platform: HackerRank

🟢 Identity Match: Register Number: RA2311003050045
📎 Found in: shortlist.xlsx
🎯 Confidence: 100%

📧 Subject: Ather Energy Online Test Notification
🔢 Priority Score: 12 (CRITICAL)

🔗 Link: https://hackerrank.com/...
⏱ Detected at 02:31 PM, 07 Apr 2026

🔔 Reminders scheduled: 60min, 30min, 10min before
```

**10-Minute Reminder:**
```
🔴 REMINDER — 10 MINUTES LEFT

🏢 Ather Energy — Online Test
⏰ Starts at 2:00 PM

⚡ GET READY NOW!
✅ Charge laptop | ✅ Check internet | ✅ Open test link
```

---

<div align="center">

*Haveloc Guardian — Built by Sudharsan S · SRMIST Trichy*
*Agentic AI Engineer · LLM Systems & Backend Infrastructure*

**You sleep. It watches.**

</div>
