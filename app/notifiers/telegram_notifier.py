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


def _build_shortlist_message(email_data: dict, event: dict, attachment_result: dict) -> str:
    emoji = _priority_emoji(email_data["priority"])
    confidence_bar = "🟢" if attachment_result["confidence"] >= 0.9 else "🟡"

    msg = f"""
{emoji} *SHORTLISTED — PLACEMENT ALERT* {emoji}

🏢 *Company:* {event.get('company', 'Unknown')}
📋 *Event:* {event.get('event_type', 'Placement Event')}
📅 *Date:* {event.get('date', 'TBD')}
⏰ *Time:* {event.get('time', 'TBD')}
⏱ *Duration:* {f"{event.get('duration_mins')} minutes" if event.get('duration_mins') else 'TBD'}
🕐 *Ends at:* {event.get('end_time', 'TBD')}
🖥 *Platform:* {event.get('platform', 'TBD')}

{confidence_bar} *Identity Match:* {attachment_result['matched_identity']}
📎 *Found in:* {attachment_result['filename']}
🎯 *Confidence:* {attachment_result['confidence']:.0%}

📧 *Subject:* {email_data['subject']}
🔢 *Priority Score:* {email_data['priority_score']} ({email_data['priority']})
""".strip()

    if event.get("meeting_link"):
        msg += f"\n\n🔗 *Link:* {event['meeting_link']}"

    if event.get("instructions"):
        instructions_short = event["instructions"][:150]
        msg += f"\n\n📝 *Instructions:* {instructions_short}..."

    msg += f"\n\n⏱ _Detected at {datetime.now().strftime('%I:%M %p, %d %b %Y')}_"
    msg += "\n\n🔔 *Reminders scheduled: 60min, 30min, 10min before*"

    return msg


def _build_general_alert_message(email_data: dict, event: dict) -> str:
    emoji = _priority_emoji(email_data["priority"])
    priority = email_data["priority"]
    keywords = ', '.join(email_data.get('matched_keywords', [])[:5])
    
    company = event.get('company', 'Unknown')
    event_type = event.get('event_type', 'Placement Event')
    date = event.get('date', 'TBD')
    time = event.get('time', 'TBD')
    subject = email_data['subject']
    body = email_data.get('body', '')
    
    msg = f"""
{emoji} *{priority} PLACEMENT ALERT*

🏢 *Company:* {company}
📋 *Event:* {event_type}
📅 *Date:* {date}
⏰ *Time:* {time}

📧 *Subject:* {subject[:80]}{'...' if len(subject) > 80 else ''}

🔑 *Matched:* {keywords}
"""
    
    if body:
        body_preview = body[:100].replace('\n', ' ').strip()
        msg += f"\n📝 {body_preview}..."

    msg += f"\n\n_Detected at {datetime.now().strftime('%I:%M %p, %d %b %Y')}_"

    return msg


def _build_reminder_message(company: str, event_type: str, minutes_left: int, time_str: str) -> str:
    urgency = "🔴" if minutes_left <= 10 else "🟡" if minutes_left <= 30 else "🟢"
    return f"""
{urgency} *REMINDER — {minutes_left} MINUTES LEFT*

🏢 *{company}* — {event_type}
⏰ Starts at *{time_str}*

{"⚡ GET READY NOW!" if minutes_left <= 10 else "📝 Prepare your environment."}
{"✅ Charge laptop | ✅ Check internet | ✅ Open test link" if minutes_left <= 30 else ""}
""".strip()


def _build_emergency_message(email_data: dict, event: dict) -> str:
    company = event.get('company', 'Unknown')
    event_type = event.get('event_type', 'Placement Event')
    date = event.get('date', 'TBD')
    time = event.get('time', 'TBD')
    body = email_data.get('body', '')
    
    # Extract key info from body for more context
    keywords = ', '.join(email_data.get('matched_keywords', [])[:5])
    
    msg = f"""
🚨 *URGENT PLACEMENT ALERT* 🚨

🏢 *Company:* {company}
📋 *Event:* {event_type}
📅 *Date:* {date}
⏰ *Time:* {time}

📧 *Subject:* {email_data['subject']}

🔑 *Keywords:* {keywords}
"""
    
    if body:
        # Add first 100 chars of body for context
        body_preview = body[:150].replace('\n', ' ').strip()
        msg += f"\n📝 *Preview:* {body_preview}..."
    
    msg += "\n\n⚡ ACT IMMEDIATELY — This is urgent!"
    
    return msg.strip()


def _build_daily_summary_message(events_today: list, upcoming: list) -> str:
    msg = f"""
📊 *DAILY PLACEMENT SUMMARY*
_{datetime.now().strftime('%A, %d %B %Y')}_

"""
    if events_today:
        msg += f"📅 *Today's Events ({len(events_today)}):*\n"
        for ev in events_today:
            msg += f"  • {ev.get('company')} — {ev.get('event_type')} at {ev.get('time')}\n"
    else:
        msg += "✅ No placement events today.\n"

    if upcoming:
        msg += f"\n⏭ *Upcoming ({len(upcoming)}):*\n"
        for ev in upcoming[:5]:
            msg += f"  • {ev.get('company')} — {ev.get('date')}\n"

    msg += "\n_Haveloc Guardian is running 24/7_ 🛡"
    return msg.strip()


class TelegramNotifier:

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def send(self, message: str, parse_mode: str = "Markdown") -> bool:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            logger.warning("Telegram not configured, skipping.")
            return False

        # Escape special Markdown characters to avoid parse errors
        import re
        def escape_markdown(text):
            # Escape special characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
            return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)
        
        # Clean and escape message
        message = escape_markdown(str(message))

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False,
                },
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
        # Send only once to avoid errors
        await self.send(msg)

    async def send_reminder(self, company: str, event_type: str, minutes_left: int, time_str: str):
        msg = _build_reminder_message(company, event_type, minutes_left, time_str)
        await self.send(msg)

    async def send_daily_summary(self, events_today: list, upcoming: list):
        msg = _build_daily_summary_message(events_today, upcoming)
        await self.send(msg)

    async def send_system_status(self, status: dict):
        msg = f"""
🛡 *GUARDIAN SYSTEM STATUS*

🟢 Status: *Running*
📬 Emails Processed: {status.get('total_processed', 0)}
🎯 Shortlists Found: {status.get('shortlists_found', 0)}
📅 Events Tracked: {status.get('events_tracked', 0)}
⏱ Uptime: {status.get('uptime', 'N/A')}
🕐 Last Check: {status.get('last_check', 'N/A')}
""".strip()
        await self.send(msg)
