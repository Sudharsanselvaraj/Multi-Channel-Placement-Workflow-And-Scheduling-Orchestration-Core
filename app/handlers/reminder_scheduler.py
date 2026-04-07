import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from app.utils.logger import logger
from config.settings import settings

IST = pytz.timezone(settings.timezone)
EVENTS_FILE = Path("logs/tracked_events.json")


def load_tracked_events() -> List[dict]:
    if EVENTS_FILE.exists():
        try:
            with open(EVENTS_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_tracked_event(event_record: dict):
    events = load_tracked_events()
    # Avoid duplicates by event ID
    existing_ids = {e["id"] for e in events}
    if event_record["id"] not in existing_ids:
        events.append(event_record)
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=2, default=str)


class ReminderScheduler:

    def __init__(self, scheduler: AsyncIOScheduler):
        self.scheduler = scheduler

    def schedule_reminders(
        self,
        event_id: str,
        company: str,
        event_type: str,
        datetime_obj: datetime,
        time_str: str,
        notifiers: dict,
    ):
        """Schedule 60, 30, and 10 minute reminders for an event."""
        now = datetime.now(IST)
        reminder_offsets = [60, 30, 10]

        for minutes_before in reminder_offsets:
            reminder_time = datetime_obj - timedelta(minutes=minutes_before)

            if reminder_time <= now:
                logger.debug(f"Skipping {minutes_before}min reminder — already past")
                continue

            job_id = f"reminder_{event_id}_{minutes_before}min"

            async def send_reminder(
                _company=company,
                _event_type=event_type,
                _minutes=minutes_before,
                _time=time_str,
                _notifiers=notifiers,
            ):
                logger.info(f"⏰ Sending {_minutes}min reminder for {_company}")

                telegram = _notifiers.get("telegram")
                pushover = _notifiers.get("pushover")
                sms = _notifiers.get("sms")

                tasks = []
                if telegram:
                    tasks.append(telegram.send_reminder(_company, _event_type, _minutes, _time))
                if pushover:
                    tasks.append(pushover.send_reminder(_company, _minutes, _time))
                if sms and _minutes <= 30:
                    tasks.append(sms.send_reminder(_company, _minutes, _time))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.error(f"Reminder notification error: {r}")

            self.scheduler.add_job(
                send_reminder,
                trigger=DateTrigger(run_date=reminder_time, timezone=IST),
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info(
                f"⏰ Scheduled {minutes_before}min reminder for {company} at "
                f"{reminder_time.strftime('%I:%M %p, %d %b')}"
            )

        # Save to tracked events
        save_tracked_event({
            "id": event_id,
            "company": company,
            "event_type": event_type,
            "datetime": datetime_obj.isoformat(),
            "time_str": time_str,
            "reminders_scheduled": reminder_offsets,
        })

    def get_todays_events(self) -> List[dict]:
        events = load_tracked_events()
        today = datetime.now(IST).date()
        todays = []
        for ev in events:
            try:
                ev_date = datetime.fromisoformat(ev["datetime"]).date()
                if ev_date == today:
                    todays.append(ev)
            except Exception:
                pass
        return todays

    def get_upcoming_events(self, days: int = 7) -> List[dict]:
        events = load_tracked_events()
        now = datetime.now(IST)
        cutoff = now + timedelta(days=days)
        upcoming = []
        for ev in events:
            try:
                ev_dt = datetime.fromisoformat(ev["datetime"])
                if now < ev_dt <= cutoff:
                    upcoming.append(ev)
            except Exception:
                pass
        return sorted(upcoming, key=lambda e: e["datetime"])
