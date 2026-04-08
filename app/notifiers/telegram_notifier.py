import asyncio
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from config.settings import settings


TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def _priority_emoji(priority: str) -> str:
    return {
        "CRITICAL": "🚨",
        "HIGH": "⚠️",
        "MEDIUM": "📢",
        "LOW": "ℹ️",
    }.get(priority, "📬")


def _truncate(text: str, length: int = 80) -> str:
    if len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + "..."


def _build_shortlist_message(email_data: dict, event: dict, attachment_result: dict) -> str:
    emoji = _priority_emoji(email_data["priority"])
    confidence_bar = "🟢" if attachment_result["confidence"] >= 0.9 else "🟡"

    company = event.get('company', 'Unknown')
    event_type = event.get('event_type', 'Placement Event')
    date = event.get('date') or "TBD"
    time = event.get('time') or "TBD"
    subject = _truncate(email_data['subject'], 60)

    lines = [
        f"{emoji} <b>SHORTLISTED — PLACEMENT ALERT</b> {emoji}",
        "",
        f"<b>🏢 Company:</b> {company}",
        f"<b>📋 Event:</b> {event_type}",
    ]
    
    if date != "TBD":
        lines.append(f"<b>📅 Date:</b> {date}")
    if time != "TBD":
        lines.append(f"<b>⏰ Time:</b> {time}")
    
    duration = event.get('duration_mins')
    if duration:
        lines.append(f"<b>⏱ Duration:</b> {duration} minutes")
    
    platform = event.get('platform')
    if platform:
        lines.append(f"<b>🖥 Platform:</b> {platform}")
    
    lines.extend([
        "",
        f"{confidence_bar} <b>Identity Match:</b> {attachment_result['matched_identity']}",
        f"<b>📎 Found in:</b> {attachment_result['filename']}",
        f"<b>🎯 Confidence:</b> {attachment_result['confidence']:.0%}",
        "",
        f"<b>📧 Subject:</b> {subject}",
        f"<b>🔢 Priority:</b> {email_data['priority_score']} ({email_data['priority']})",
    ])

    if event.get("meeting_link"):
        lines.append(f"<b>🔗 Link:</b> {event['meeting_link']}")

    lines.append(f"\n<i>Detected at {datetime.now().strftime('%I:%M %p, %d %b %Y')}</i>")
    lines.append("<i>Reminders: 60min, 30min, 10min before</i>")

    return "\n".join(lines)


def _build_general_alert_message(email_data: dict, event: dict) -> str:
    emoji = _priority_emoji(email_data["priority"])
    priority = email_data["priority"]
    keywords = ', '.join(email_data.get('matched_keywords', [])[:5])
    
    company = event.get('company', 'Unknown')
    event_type = event.get('event_type', 'Placement Event')
    date = event.get('date') or "TBD"
    time = event.get('time') or "TBD"
    subject = _truncate(email_data['subject'])
    
    lines = [
        f"{emoji} <b>{priority} PLACEMENT ALERT</b>",
        "",
        f"<b>🏢 Company:</b> {company}",
        f"<b>📋 Event:</b> {event_type}",
    ]
    
    if date != "TBD":
        lines.append(f"<b>📅 Date:</b> {date}")
    if time != "TBD":
        lines.append(f"<b>⏰ Time:</b> {time}")
    
    lines.append(f"<b>📧 Subject:</b> {subject}")
    lines.append(f"<b>🔑 Keywords:</b> {keywords}")
    lines.append(f"\n<i>Detected at {datetime.now().strftime('%I:%M %p, %d %b %Y')}</i>")

    return "\n".join(lines)


def _build_reminder_message(company: str, event_type: str, minutes_left: int, time_str: str) -> str:
    urgency = "🔴" if minutes_left <= 10 else "🟡" if minutes_left <= 30 else "🟢"
    action = "<b>⚡ GET READY NOW!</b>" if minutes_left <= 10 else "<b>📝 Prepare your system and be ready.</b>"
    prep = "✅ Charge laptop | ✅ Check internet | ✅ Open test link" if minutes_left <= 30 else ""
    
    lines = [
        f"{urgency} <b>REMINDER — {minutes_left} MINUTES LEFT</b>",
        "",
        f"<b>🏢 Company:</b> {company}",
        f"<b>📋 Event:</b> {event_type}",
        "",
        f"<b>⏰ Starts at:</b> {time_str}",
        "",
        action,
    ]
    
    if prep:
        lines.append(prep)
    
    return "\n".join(lines)


def _build_emergency_message(email_data: dict, event: dict) -> str:
    company = event.get('company', 'Unknown')
    event_type = event.get('event_type', 'Placement Event')
    date = event.get('date') or "TBD"
    time = event.get('time') or "TBD"
    subject = email_data['subject']
    keywords = ', '.join(email_data.get('matched_keywords', [])[:5])
    
    lines = [
        "🚨 <b>URGENT PLACEMENT ALERT</b> 🚨",
        "",
        f"<b>🏢 Company:</b> {company}",
        f"<b>📋 Event:</b> {event_type}",
    ]
    
    if date != "TBD":
        lines.append(f"<b>📅 Date:</b> {date}")
    if time != "TBD":
        lines.append(f"<b>⏰ Time:</b> {time}")
    
    lines.extend([
        f"<b>📧 Subject:</b> {subject}",
        f"<b>🔑 Keywords:</b> {keywords}",
        "",
        "<b>⚡ ACTION REQUIRED:</b> Please check your email and attend immediately.",
    ])
    
    return "\n".join(lines)


def _build_daily_summary_message(events_today: list, upcoming: list) -> str:
    lines = [
        "📊 <b>DAILY PLACEMENT SUMMARY</b>",
        f"_{datetime.now().strftime('%A, %d %B %Y')}_",
        "",
    ]
    
    if events_today:
        lines.append(f"<b>📅 Today's Events ({len(events_today)}):</b>")
        for ev in events_today:
            time = ev.get('time', 'TBD')
            lines.append(f"  • {ev.get('company')} — {ev.get('event_type')} at {time}")
    else:
        lines.append("✅ No placement events today.")
    
    if upcoming:
        lines.append(f"\n<b>⏭ Upcoming ({len(upcoming)}):</b>")
        for ev in upcoming[:5]:
            date = ev.get('date', 'TBD')
            lines.append(f"  • {ev.get('company')} — {date}")
    
    lines.append("\n<i>Haveloc Guardian is running 24/7</i> 🛡")
    return "\n".join(lines)


class TelegramNotifier:

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def send(self, message: str, parse_mode: str = "HTML") -> bool:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            logger.warning("Telegram not configured, skipping.")
            return False

        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json=payload,
                timeout=15,
            )
            if response.status_code == 200:
                logger.info("✅ Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram error: {response.status_code} — {response.text}")
                return False

    async def send_shortlist_alert(self, email_data: dict, event: dict, attachment_result: dict):
        msg = _build_shortlist_message(email_data, event, attachment_result)
        await self.send(msg)

    async def send_general_alert(self, email_data: dict, event: dict):
        msg = _build_general_alert_message(email_data, event)
        await self.send(msg)

    async def send_emergency_alert(self, email_data: dict, event: dict):
        msg = _build_emergency_message(email_data, event)
        await self.send(msg)

    async def send_reminder(self, company: str, event_type: str, minutes_left: int, time_str: str):
        msg = _build_reminder_message(company, event_type, minutes_left, time_str)
        await self.send(msg)

    async def send_daily_summary(self, events_today: list, upcoming: list):
        msg = _build_daily_summary_message(events_today, upcoming)
        await self.send(msg)

    async def send_system_status(self, status: dict):
        msg = f"""
🛡 <b>GUARDIAN SYSTEM STATUS</b>

🟢 <b>Status:</b> Running
📬 <b>Emails Processed:</b> {status.get('total_processed', 0)}
🎯 <b>Shortlists Found:</b> {status.get('shortlists_found', 0)}
📅 <b>Events Tracked:</b> {status.get('events_tracked', 0)}
⏱ <b>Uptime:</b> {status.get('uptime', 'N/A')}
🕐 <b>Last Check:</b> {status.get('last_check', 'N/A')}
""".strip()
        await self.send(msg)