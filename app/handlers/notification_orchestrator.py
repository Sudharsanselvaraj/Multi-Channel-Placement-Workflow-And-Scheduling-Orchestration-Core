import asyncio
import uuid
from datetime import datetime
from typing import Optional

from app.notifiers.telegram_notifier import TelegramNotifier
from app.notifiers.sms_notifier import SMSNotifier
from app.handlers.calendar_manager import CalendarManager
from app.handlers.reminder_scheduler import ReminderScheduler
from app.utils.logger import logger
from config.settings import settings


class NotificationOrchestrator:
    """
    Orchestrates the notification pipeline:
    1. Telegram (primary) - all CRITICAL, HIGH, SHORTLIST
    2. SMS via Fast2SMS (only for CRITICAL + SHORTLIST)
    3. Google Calendar (always)
    4. Reminder scheduling
    """

    def __init__(self, scheduler=None):
        self.telegram = TelegramNotifier()
        self.sms = SMSNotifier()
        self.calendar = CalendarManager()
        self.reminder_scheduler = ReminderScheduler(scheduler) if scheduler else None

        self.notifiers = {
            "telegram": self.telegram,
            "sms": self.sms,
        }

    async def handle_email(self, email_data: dict, event: dict, attachment_results: list):
        """Main entry — routes based on priority and identity match."""
        from app.utils.logger import logger
        import sys
        
        subject = email_data.get('subject', 'No Subject')[:30]
        priority = email_data.get('priority', 'UNKNOWN')
        emergency = email_data.get('is_emergency', False)
        
        print(f"🔥 ORCHESTRATOR CALLED: priority={priority}, emergency={emergency}, subject={subject}", file=sys.stderr)
        logger.info(f"🔥 ORCHESTRATOR: {priority} email - {subject}")
        
        identity_found = any(r["identity_found"] for r in attachment_results)
        
        identity_found = any(r["identity_found"] for r in attachment_results)
        best_attachment = max(
            attachment_results,
            key=lambda r: r["confidence"],
            default={"identity_found": False, "confidence": 0, "matched_identity": "", "filename": "N/A"},
        ) if attachment_results else {"identity_found": False, "confidence": 0, "matched_identity": "", "filename": "N/A"}

        event_id = str(uuid.uuid4())[:8]

        # ── SHORTLIST DETECTED ────────────────────────────────────────────────
        if identity_found:
            logger.info("🎯 SHORTLIST CONFIRMED — triggering all channels")
            await self._send_shortlist_alerts(email_data, event, best_attachment)

        # ── EMERGENCY (today/urgent keywords) ────────────────────────────────
        elif email_data.get("is_emergency"):
            logger.info("🆘 EMERGENCY email detected")
            await self._send_emergency_alerts(email_data, event)

        # ── HIGH / CRITICAL priority ──────────────────────────────────────────
        elif email_data["priority"] in ("CRITICAL", "HIGH"):
            logger.info(f"⚠️ {email_data['priority']} email — sending {email_data['priority']} alert")
            await self._send_general_alerts(email_data, event)

        # ── MEDIUM / LOW ──────────────────────────────────────────────────────
        else:
            logger.info(f"ℹ️ {email_data['priority']} email — minimal alert")
            await self.telegram.send_general_alert(email_data, event)

        # ── CALENDAR (always, if we have a datetime) ──────────────────────────
        calendar_url = None
        if event.get("datetime_obj"):
            calendar_url = self.calendar.create_event(event, email_data)

            if calendar_url:
                await self.telegram.send(
                    f"📅 *Calendar event created!*\n[Open in Google Calendar]({calendar_url})"
                )

        # ── REMINDERS (if shortlisted or high priority with datetime) ─────────
        if self.reminder_scheduler and event.get("datetime_obj") and (identity_found or email_data["priority"] in ("CRITICAL", "HIGH")):
            self.reminder_scheduler.schedule_reminders(
                event_id=event_id,
                company=event.get("company", "Unknown"),
                event_type=event.get("event_type", "Placement Event"),
                datetime_obj=event["datetime_obj"],
                time_str=event.get("time", "TBD"),
                notifiers=self.notifiers,
            )

    async def _send_shortlist_alerts(self, email_data: dict, event: dict, attachment_result: dict):
        """Full blast — Telegram + SMS for shortlist."""
        await self.telegram.send_shortlist_alert(email_data, event, attachment_result)
        await self.sms.send_shortlist_alert(
            event.get("company", "Unknown"),
            event.get("event_type", ""),
            event.get("time", "TBD"),
        )

    async def _send_emergency_alerts(self, email_data: dict, event: dict):
        tasks = [
            self.telegram.send_emergency_alert(email_data, event),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_general_alerts(self, email_data: dict, event: dict):
        await self.telegram.send_general_alert(email_data, event)

    async def send_daily_summary(self):
        if not self.reminder_scheduler:
            return
        todays = self.reminder_scheduler.get_todays_events()
        upcoming = self.reminder_scheduler.get_upcoming_events()
        await self.telegram.send_daily_summary(todays, upcoming)

    async def send_status(self, status: dict):
        await self.telegram.send_system_status(status)
