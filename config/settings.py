from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os


class Settings(BaseSettings):
    # User Identity
    user_name: str = "Sudharsan S"
    user_name_variants: str = "Sudharsan,SUDHARSAN,sudharsan,Sudharsan S"
    register_number: str = "RA2211028010001"
    college_email: str = "sudharsan@srmist.edu.in"

    # Gmail IMAP
    gmail_address: str = ""
    gmail_app_password: str = ""
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Google Calendar
    google_calendar_id: str = "primary"
    google_credentials_json: str = "credentials.json"
    google_service_account_json: str = ""

    # Pushover
    pushover_user_key: str = ""
    pushover_api_token: str = ""

    # Fast2SMS
    fast2sms_api_key: str = ""
    user_phone: str = ""

    # Monitoring
    poll_interval_seconds: int = 60
    emergency_poll_interval: int = 30
    timezone: str = "Asia/Kolkata"

    # Senders
    haveloc_senders: str = "alerts@haveloc.com,srm@haveloc.com"
    haveloc_sender_domains: str = "haveloc.com,career,placement,recruitment"

    # System
    environment: str = "production"
    log_level: str = "INFO"
    daily_summary_time: str = "20:00"

    @property
    def name_variants_list(self) -> List[str]:
        return [v.strip() for v in self.user_name_variants.split(",")]

    @property
    def haveloc_senders_list(self) -> List[str]:
        return [s.strip() for s in self.haveloc_senders.split(",")]

    @property
    def haveloc_domains_list(self) -> List[str]:
        return [d.strip() for d in self.haveloc_sender_domains.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
