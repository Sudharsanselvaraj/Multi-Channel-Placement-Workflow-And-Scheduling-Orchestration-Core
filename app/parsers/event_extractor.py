import re
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as dateutil_parser
import pytz

from app.utils.logger import logger
from config.settings import settings


IST = pytz.timezone(settings.timezone)

# ── Regex Patterns ────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",           # 07-04-2026
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",             # 2026-04-07
    r"(\d{1,2}\s+\w+\s+\d{4})",                   # 7 April 2026
    r"(\w+\s+\d{1,2},?\s+\d{4})",                 # April 7, 2026
    r"(today|tomorrow)",                            # relative dates
]

TIME_PATTERNS = [
    r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))",         # 2:00 PM
    r"(\d{1,2}\s*(?:AM|PM|am|pm))",               # 2 PM
    r"(\d{1,2}:\d{2})",                            # 14:00
]

DURATION_PATTERNS = [
    r"(\d+)\s*(?:MINS?|MINUTES?|HRS?|HOURS?)",
    r"duration\s*[:\-]?\s*(\d+)\s*(?:mins?|hours?|hrs?)",
    r"(\d+)\s*(?:mins?|hours?|hrs?)\s*(?:long|duration)?",
]

COMPANY_PATTERNS = [
    r"(?:company|firm|organization|employer)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.]+)",
    r"(?:drive|recruitment|hiring)\s+(?:by|from|at|of)\s+([A-Z][A-Za-z\s&\.]+)",
    r"^([A-Z][A-Za-z\s&\.]{2,30})\s+(?:Online Test|Interview|Assessment|Drive)",
    r"(?:at|by|from)\s+([A-Z][A-Za-z\s&\.]{2,40})\s+(?:Intern|Job|Position|Role|Test|Interview)",  # Job at Company
    r"(?:at|by|from)\s+([A-Z][A-Za-z\s&\.]{2,40})\s*$",  # Company at end of line
    r"^([A-Z][A-Za-z\s&\.]{2,40})\s*[-|]\s*(?:Intern|Job|Recruitment|Hiring)",  # Company - Job
    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:Technologies|Services|India|Private|Ltd|Inc|Corporation)",  # Full company names
]

LINK_PATTERNS = [
    r"https?://[^\s<>\"]+",
    r"www\.[^\s<>\"]+",
]

EVENT_TYPE_MAP = {
    "online test": "Online Test",
    "aptitude test": "Aptitude Test",
    "technical test": "Technical Test",
    "written test": "Written Test",
    "interview": "Interview",
    "hr interview": "HR Interview",
    "technical interview": "Technical Interview",
    "assessment": "Assessment",
    "gd": "Group Discussion",
    "group discussion": "Group Discussion",
    "ppt": "Pre-Placement Talk",
    "pre-placement": "Pre-Placement Talk",
}


class EventExtractor:

    def extract(self, email_data: dict) -> dict:
        """Extract all event details from email subject + body."""
        text = f"{email_data['subject']}\n{email_data['body']}"
        text_upper = text.upper()

        event = {
            "company": self._extract_company(text),
            "event_type": self._extract_event_type(text),
            "date": self._extract_date(text),
            "time": self._extract_time(text),
            "duration_mins": self._extract_duration(text),
            "end_time": None,
            "meeting_link": self._extract_link(text),
            "platform": self._extract_platform(text),
            "instructions": self._extract_instructions(text),
            "raw_date_str": "",
            "datetime_obj": None,
        }

        # Compute end time
        if event["time"] and event["duration_mins"]:
            try:
                start_dt = self._parse_full_datetime(event["date"], event["time"])
                if start_dt:
                    event["datetime_obj"] = start_dt
                    end_dt = start_dt + timedelta(minutes=event["duration_mins"])
                    event["end_time"] = end_dt.strftime("%I:%M %p")
            except Exception as e:
                logger.debug(f"Could not compute end time: {e}")

        logger.info(
            f"📋 Extracted — Company: {event['company']} | "
            f"Type: {event['event_type']} | "
            f"Date: {event['date']} | Time: {event['time']}"
        )

        return event

    def _extract_company(self, text: str) -> str:
        # First: look for company names in subject line (usually at start or after keywords)
        subject_lines = text.split("\n")[:5]
        
        # Common patterns in Haveloc emails
        company_patterns = [
            # "REMINDER: COMPANY NAME" or "COMPANY NAME - something"
            r"(?:REMINDER|NEW|INVITE|URGENT|REGISTRATION|INFO)\s*[:\-]?\s*([A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?)",
            # "COMPANY EVENT" - like "INFOSYS HACKWITHINFY"
            r"^([A-Z][A-Za-z]{3,20})\s+(?:Hackathon|HackWithInfy|Buildathon|Test|Quiz|Exam|Webinar|Session|Talk|Challenge|Innovation|InnoVent|Sparkle|Srijan|Eureka|Techathon|Quest|Quiz)",
            # "Company - Job" pattern
            r"^([A-Z][A-Za-z\s&\.]{2,35})\s*[-|]\s*",
            # "Job at Company" 
            r"(?:Intern|Job|Position|Role|Engineer|Developer)\s+(?:at|at\s+)([A-Z][A-Za-z\s&\.]{2,40})",
            # Full company names with common suffixes
            r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?:Technologies|Services|India|Private|Ltd|LLC|Inc|Corporation|Group|Enterprises|Solutions|Hub)",
        ]
        
        for line in subject_lines:
            for pattern in company_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    company = match.group(1).strip()
                    if 2 < len(company) < 50:
                        return company

        # Try regex patterns on full text
        for pattern in COMPANY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                company = match.group(1).strip()
                if 2 < len(company) < 50:
                    return company

        # Last resort: check for known company names
        known_companies = ['INFOSYS', 'TCS', 'WIPRO', 'ACCENTURE', 'CAPGEMINI', 'DELOITTE', 'EY', 'KPMG', 'IBM', 'ORACLE', 'MICROSOFT', 'GOOGLE', 'AMAZON', 'META', 'FLIPKART', 'PAYTM', 'ZOMATO', 'SWIGGY', 'BYJUS', 'UNISYS', 'L&T', 'TATA', 'GP', 'HCL', 'PHILIPS', 'BAYER', 'SCHNEIDER', 'VOLVO', 'MAHINDRA', 'MARUTI', 'HYUNDAI', 'SONY', 'SAMSUNG', 'LG', 'CANON', 'DELL', 'HP', 'LENOVO', 'ASUS', 'ACER', 'INTEL', 'AMD', 'NVIDIA', 'CISCO', 'VMWARE', 'SAP', 'SALESFORCE', 'SERVICENOW', 'ATLASSIAN', 'UBER', 'OLA', 'GROFFERS', 'CRED', 'RAZORPAY', 'AWS', 'AZURE', 'ATHER', 'LEAP', 'JP MORGAN', 'CITI', 'BARCLAYS', 'GARTNER', 'ZS', 'PLAYSIMPLE', 'JACOB', 'RELTIO', 'AMDOCS', 'VISA', 'BOSCH', 'SIEMENS', 'ABB', 'GE', 'DNV', 'KB', 'BNY', 'MELLON', 'FIDELITY', 'VIRTUSA', 'COMCAST', 'COGNIZANT', 'GENPACT', 'JUSPAY', 'GROWW', 'ZERODHA', 'FISERV', 'ADP', 'VMWARE', 'AUTODESK', 'ADOBE', 'CADENCE', 'MENTOR', 'GRAPHICS', 'ANTERO', 'VAL', 'HEX', 'AWL', 'ANAND', 'CRO', 'MAVEN', 'NINJAR', 'CAREER', 'FORCE', 'NEXT', 'GEN', 'NOVO', 'NXT', 'RIVIAN', 'ISRO', 'DRDO', 'NTPC', 'IOCL', 'BPCL', 'HAL']
        text_upper = text.upper()
        for comp in known_companies:
            if comp in text_upper:
                return comp.title()

        return "Placement Alert"

    def _extract_event_type(self, text: str) -> str:
        text_lower = text.lower()
        for key, label in EVENT_TYPE_MAP.items():
            if key in text_lower:
                return label
        return "Placement Event"

    def _extract_date(self, text: str) -> Optional[str]:
        text_lower = text.lower()

        if "today" in text_lower:
            return datetime.now(IST).strftime("%d-%m-%Y")
        if "tomorrow" in text_lower:
            return (datetime.now(IST) + timedelta(days=1)).strftime("%d-%m-%Y")

        for pattern in DATE_PATTERNS[:-1]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1)
                try:
                    parsed = dateutil_parser.parse(raw, dayfirst=True)
                    return parsed.strftime("%d-%m-%Y")
                except Exception:
                    return raw

        return None

    def _extract_time(self, text: str) -> Optional[str]:
        for pattern in TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        for pattern in DURATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                # If it's in hours, convert to mins
                if re.search(r"hr|hour", match.group(0), re.IGNORECASE):
                    return value * 60
                return value
        return None

    def _extract_link(self, text: str) -> Optional[str]:
        for pattern in LINK_PATTERNS:
            match = re.search(pattern, text)
            if match:
                link = match.group(0)
                # Filter out unrelated links (images, unsubscribe, etc.)
                skip_keywords = ["unsubscribe", "logo", "image", "pixel", "track"]
                if not any(kw in link.lower() for kw in skip_keywords):
                    return link
        return None

    def _extract_platform(self, text: str) -> Optional[str]:
        platforms = {
            "hackerrank": "HackerRank",
            "hackerearth": "HackerEarth",
            "codingninjas": "Coding Ninjas",
            "amcat": "AMCAT",
            "cocubes": "CoCubes",
            "mettl": "Mettl",
            "testgorilla": "TestGorilla",
            "zoom": "Zoom",
            "meet.google": "Google Meet",
            "teams": "Microsoft Teams",
            "webex": "Webex",
        }
        text_lower = text.lower()
        for key, label in platforms.items():
            if key in text_lower:
                return label
        return None

    def _extract_instructions(self, text: str) -> Optional[str]:
        """Extract instruction section if present."""
        patterns = [
            r"(?:instructions?|guidelines?|notes?)\s*[:\-]\s*(.{20,300})",
            r"(?:please note|kindly note|important)\s*[:\-]?\s*(.{20,300})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:300]
        return None

    def _parse_full_datetime(self, date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
        if not date_str or not time_str:
            return None
        try:
            combined = f"{date_str} {time_str}"
            dt = dateutil_parser.parse(combined, dayfirst=True)
            return IST.localize(dt)
        except Exception:
            return None
