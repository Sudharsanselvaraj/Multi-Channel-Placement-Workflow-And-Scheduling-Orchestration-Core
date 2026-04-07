import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from config.settings import settings

FAST2SMS_API = "https://www.fast2sms.com/dev/bulkV2"


class SMSNotifier:

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    async def send(self, message: str) -> bool:
        if not settings.fast2sms_api_key or not settings.user_phone:
            logger.warning("Fast2SMS not configured, skipping.")
            return False

        phone = settings.user_phone.replace("+91", "").replace("+", "").strip()

        # Try new Fast2SMS API format
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://www.fast2sms.com/dev/bulkV2",
                    headers={
                        "authorization": settings.fast2sms_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "message": message[:160],
                        "language": "english",
                        "route": "q",
                        "numbers": phone,
                    },
                    timeout=15,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("return"):
                        logger.info("✅ SMS sent via Fast2SMS")
                        return True
                    else:
                        logger.error(f"SMS error: {response.status_code} — {data}")
                else:
                    logger.error(f"SMS error: {response.status_code} — {response.text}")
            except Exception as e:
                logger.error(f"SMS exception: {e}")
            return False

    async def send_shortlist_alert(self, company: str, event_type: str, time_str: str):
        msg = f"SHORTLISTED! {company} - {event_type} at {time_str}. Check Telegram immediately."
        await self.send(msg)

    async def send_reminder(self, company: str, minutes_left: int, time_str: str):
        msg = f"REMINDER: {company} test in {minutes_left} mins at {time_str}. Get ready now!"
        await self.send(msg)
