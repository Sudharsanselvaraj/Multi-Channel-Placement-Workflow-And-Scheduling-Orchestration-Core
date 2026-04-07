import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Fix imports
sys.path.insert(0, str(Path(__file__).parent))

from app.core.email_monitor import EmailMonitor
from app.parsers.attachment_parser import AttachmentParser
from app.parsers.event_extractor import EventExtractor
from app.handlers.notification_orchestrator import NotificationOrchestrator
from app.utils.logger import logger
from config.settings import settings

IST = pytz.timezone(settings.timezone)


class HavelocGuardian:

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=IST)
        self.email_monitor = EmailMonitor()
        self.attachment_parser = AttachmentParser()
        self.event_extractor = EventExtractor()
        self.orchestrator = NotificationOrchestrator(scheduler=self.scheduler)

        self.stats = {
            "total_processed": 0,
            "shortlists_found": 0,
            "events_tracked": 0,
            "start_time": datetime.now(IST),
            "last_check": None,
        }

    async def run_check(self):
        """Single polling cycle."""
        self.stats["last_check"] = datetime.now(IST).strftime("%I:%M %p, %d %b")
        
        remaining = 382 - len(self.email_monitor.processed_ids)
        logger.info(f"🔍 STARTING EMAIL CHECK - {remaining} remaining emails")
        
        try:
            emails = self.email_monitor.fetch_new_emails()
            print(f"🔍 DEBUG: fetch_new_emails returned {len(emails)} emails", file=sys.stderr)
            logger.info(f"📬 fetch_new_emails returned {len(emails)} emails")

            for email_data in emails:
                self.stats["total_processed"] += 1
                subject = email_data.get('subject', 'No Subject')[:40]
                priority = email_data['priority']
                emergency = email_data.get('is_emergency', False)
                attachments = email_data.get('attachments', [])
                
                logger.info(f"📧 [{priority}] {subject}")
                logger.info(f"   → emergency={emergency}, attachments={len(attachments)}")

                # Parse attachments
                attachment_results = []
                for filepath in attachments:
                    result = self.attachment_parser.parse(filepath)
                    attachment_results.append(result)
                    if result["identity_found"]:
                        self.stats["shortlists_found"] += 1

                # Extract event details
                event = self.event_extractor.extract(email_data)
                if event.get("datetime_obj"):
                    self.stats["events_tracked"] += 1

                # Check if we should notify
                identity_in_attachments = any(r.get("identity_found") for r in attachment_results)
                should_notify = priority in ("CRITICAL", "HIGH") or emergency or identity_in_attachments
                
                logger.info(f"   → identity_found={identity_in_attachments}, should_notify={should_notify}")
                
                if should_notify:
                    logger.info(f"🔔 >>> CALLING ORCHESTRATOR for {priority} email: {subject}")
                    await self.orchestrator.handle_email(email_data, event, attachment_results)
                    logger.info(f"✅ >>> ORCHESTRATOR DONE for {subject}")
                else:
                    logger.info(f"⏭️ Skipping notification - low priority")

                # Cleanup
                for filepath in attachments:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
                        
            logger.info(f"📬 Check complete. Processed: {len(emails)} emails")

        except Exception as e:
            logger.error(f"Error in check cycle: {e}")

    def _get_uptime(self) -> str:
        delta = datetime.now(IST) - self.stats["start_time"]
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"

    async def send_daily_summary(self):
        logger.info("📊 Sending daily summary...")
        await self.orchestrator.send_daily_summary()

    async def send_status(self):
        status = {**self.stats, "uptime": self._get_uptime()}
        await self.orchestrator.send_status(status)

    async def startup(self):
        logger.info("🛡 Haveloc Guardian starting up...")

        # Ensure directories exist
        Path("logs/temp_attachments").mkdir(parents=True, exist_ok=True)

        # Connect to email
        self.email_monitor.connect()

        # Schedule email polling
        self.scheduler.add_job(
            self.run_check,
            trigger=IntervalTrigger(seconds=settings.poll_interval_seconds),
            id="email_poll",
            replace_existing=True,
            misfire_grace_time=30,
        )

        # Daily summary
        summary_hour, summary_min = settings.daily_summary_time.split(":")
        self.scheduler.add_job(
            self.send_daily_summary,
            trigger=CronTrigger(hour=int(summary_hour), minute=int(summary_min), timezone=IST),
            id="daily_summary",
            replace_existing=True,
        )

        # System status every 6 hours
        self.scheduler.add_job(
            self.send_status,
            trigger=CronTrigger(hour="*/6", timezone=IST),
            id="system_status",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"✅ Guardian active | Poll: {settings.poll_interval_seconds}s | "
            f"Timezone: {settings.timezone}"
        )

        # Send startup notification
        await self.orchestrator.telegram.send(
            "🛡 *Haveloc Guardian Started*\n\n"
            f"Monitoring: `{settings.gmail_address}`\n"
            f"Poll interval: {settings.poll_interval_seconds}s\n"
            f"Identity: {settings.user_name} | {settings.register_number}\n\n"
            "_24/7 monitoring active. You won't miss a shortlist._ ✅"
        )

        # Run first check immediately
        await self.run_check()

    async def shutdown(self):
        logger.info("🛑 Guardian shutting down...")
        self.scheduler.shutdown(wait=False)
        self.email_monitor.disconnect()


guardian = HavelocGuardian()


async def main():
    await guardian.startup()

    try:
        # Keep alive
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        await guardian.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
