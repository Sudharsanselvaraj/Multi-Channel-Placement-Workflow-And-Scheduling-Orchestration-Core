import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from config.settings import settings

PUSHOVER_API = "https://api.pushover.net/1/messages.json"


class PushoverNotifier:

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def send(self, title: str, message: str, priority: int = 0, sound: str = "pushover") -> bool:
        if not settings.pushover_user_key or not settings.pushover_api_token:
            logger.warning("Pushover not configured, skipping.")
            return False

        async with httpx.AsyncClient() as client:
            response = await client.post(
                PUSHOVER_API,
                data={
                    "token": settings.pushover_api_token,
                    "user": settings.pushover_user_key,
                    "title": title,
                    "message": message,
                    "priority": priority,  # 2 = emergency (requires ack), 1 = high, 0 = normal
                    "sound": sound,
                    "retry": 60,   # retry every 60s for emergency priority
                    "expire": 3600, # expire after 1 hour for emergency
                },
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("✅ Pushover notification sent")
                return True
            else:
                logger.error(f"Pushover error: {response.status_code} — {response.text}")
                return False

    async def send_shortlist_alert(self, company: str, event_type: str, time_str: str):
        await self.send(
            title=f"🚨 SHORTLISTED — {company}",
            message=f"{event_type} at {time_str}. Check Telegram for details.",
            priority=2,
            sound="siren",
        )

    async def send_reminder(self, company: str, minutes_left: int, time_str: str):
        priority = 2 if minutes_left <= 10 else 1
        sound = "siren" if minutes_left <= 10 else "bugle"
        await self.send(
            title=f"⏰ {minutes_left} min left — {company}",
            message=f"Test/Interview starts at {time_str}. Get ready!",
            priority=priority,
            sound=sound,
        )

    async def send_emergency(self, company: str, time_str: str):
        await self.send(
            title=f"🆘 URGENT — {company}",
            message=f"Urgent placement event at {time_str}. Check NOW.",
            priority=2,
            sound="siren",
        )
