import json
import os
from datetime import datetime, timedelta
from typing import Optional

import pytz
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from config.settings import settings

IST = pytz.timezone(settings.timezone)


class CalendarManager:

    def __init__(self):
        self._service = None

    def _get_service(self):
        """Lazy init Google Calendar service."""
        if self._service:
            return self._service

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            SCOPES = ["https://www.googleapis.com/auth/calendar"]
            creds = None
            token_path = "logs/token.json"

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        settings.google_credentials_json, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(token_path, "w") as token:
                    token.write(creds.to_json())

            self._service = build("calendar", "v3", credentials=creds)
            logger.info("✅ Google Calendar connected")
            return self._service

        except Exception as e:
            logger.error(f"Google Calendar init failed: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_event(self, event_data: dict, email_data: dict) -> Optional[str]:
        """Create a Google Calendar event and return event URL."""
        service = self._get_service()
        if not service:
            logger.warning("Calendar service unavailable, skipping event creation.")
            return None

        datetime_obj: Optional[datetime] = event_data.get("datetime_obj")
        if not datetime_obj:
            logger.warning("No datetime object, cannot create calendar event.")
            return None

        duration = event_data.get("duration_mins", 90)
        end_dt = datetime_obj + timedelta(minutes=duration)

        company = event_data.get("company", "Unknown Company")
        event_type = event_data.get("event_type", "Placement Event")

        description_parts = [
            f"🏢 Company: {company}",
            f"📋 Type: {event_type}",
            f"📧 Email Subject: {email_data['subject']}",
            f"🔢 Priority: {email_data['priority']}",
        ]

        if event_data.get("platform"):
            description_parts.append(f"🖥 Platform: {event_data['platform']}")
        if event_data.get("meeting_link"):
            description_parts.append(f"🔗 Link: {event_data['meeting_link']}")
        if event_data.get("instructions"):
            description_parts.append(f"📝 Instructions: {event_data['instructions'][:200]}")

        description_parts.append("\n🛡 Created by Haveloc Guardian")

        calendar_event = {
            "summary": f"🎯 {company} — {event_type}",
            "description": "\n".join(description_parts),
            "start": {
                "dateTime": datetime_obj.isoformat(),
                "timeZone": settings.timezone,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": settings.timezone,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                    {"method": "email", "minutes": 60},
                ],
            },
            "colorId": "11",  # Red for urgency
        }

        if event_data.get("meeting_link"):
            calendar_event["location"] = event_data["meeting_link"]

        try:
            created = service.events().insert(
                calendarId=settings.google_calendar_id,
                body=calendar_event,
            ).execute()

            event_url = created.get("htmlLink", "")
            logger.info(f"✅ Calendar event created: {company} — {event_type} | {event_url}")
            return event_url

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            raise
