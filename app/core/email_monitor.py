import imaplib
import email
import email.header
import hashlib
import json
import os
import re
from datetime import datetime
from email.message import Message
from pathlib import Path
from typing import List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from config.settings import settings


PROCESSED_IDS_FILE = Path("logs/processed_ids.json")

# ── Keyword scoring ───────────────────────────────────────────────────────────

HIGH_PRIORITY_KEYWORDS = [
    "shortlist", "selected", "test", "interview", "assessment",
    "deadline", "today", "urgent", "exam", "evaluation",
    "process scheduled", "online test", "aptitude", "technical round",
    "hr round", "offer", "placed", "congratulations",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "application submitted", "schedule", "next step",
    "round", "instructions", "registration", "confirm",
]

LOW_PRIORITY_KEYWORDS = [
    "announcement", "newsletter", "general information",
    "update", "information",
]

EMERGENCY_TRIGGERS = ["today", "urgent", "deadline", "now", "immediately", "asap"]


def compute_priority_score(text: str) -> Tuple[int, str, List[str]]:
    """
    Returns (score, priority_label, matched_keywords)
    score >= 10 → CRITICAL
    score 5-9   → HIGH
    score 2-4   → MEDIUM
    score 0-1   → LOW
    """
    text_lower = text.lower()
    matched = []
    score = 0

    for kw in HIGH_PRIORITY_KEYWORDS:
        if kw in text_lower:
            score += 3
            matched.append(kw)

    for kw in MEDIUM_PRIORITY_KEYWORDS:
        if kw in text_lower:
            score += 1
            matched.append(kw)

    for kw in LOW_PRIORITY_KEYWORDS:
        if kw in text_lower:
            score += 0
            matched.append(kw)

    if score >= 10:
        label = "CRITICAL"
    elif score >= 5:
        label = "HIGH"
    elif score >= 2:
        label = "MEDIUM"
    else:
        label = "LOW"

    return score, label, matched


def is_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in EMERGENCY_TRIGGERS)


# ── Deduplication ─────────────────────────────────────────────────────────────

def load_processed_ids() -> set:
    if PROCESSED_IDS_FILE.exists():
        try:
            with open(PROCESSED_IDS_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_processed_id(email_id: str):
    ids = load_processed_ids()
    ids.add(email_id)
    PROCESSED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_IDS_FILE, "w") as f:
        json.dump(list(ids), f)


def generate_email_hash(msg_id: str, subject: str) -> str:
    return hashlib.md5(f"{msg_id}:{subject}".encode()).hexdigest()


# ── IMAP Connection ───────────────────────────────────────────────────────────

class EmailMonitor:
    def __init__(self):
        self.mail: Optional[imaplib.IMAP4_SSL] = None
        self.processed_ids = load_processed_ids()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def connect(self):
        logger.info("Connecting to Gmail IMAP...")
        self.mail = imaplib.IMAP4_SSL(settings.imap_server, settings.imap_port)
        self.mail.login(settings.gmail_address, settings.gmail_app_password)
        self.mail.select("inbox")
        logger.info("✅ Connected to Gmail IMAP")

    def disconnect(self):
        try:
            if self.mail:
                self.mail.logout()
        except Exception:
            pass
        self.mail = None

    def is_haveloc_sender(self, from_addr: str) -> bool:
        from_lower = from_addr.lower()
        if any(sender in from_lower for sender in settings.haveloc_senders_list):
            return True
        if any(domain in from_lower for domain in settings.haveloc_domains_list):
            return True
        return False

    def decode_header_value(self, value: str) -> str:
        decoded_parts = email.header.decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result)

    def extract_body(self, msg: Message) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass
                elif part.get_content_type() == "text/html" and not body:
                    try:
                        raw = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        # Strip HTML tags
                        body += re.sub(r"<[^>]+>", " ", raw)
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
            except Exception:
                pass
        return body.strip()

    def download_attachments(self, msg: Message, temp_dir: str = "logs/temp_attachments") -> List[str]:
        saved_paths = []
        os.makedirs(temp_dir, exist_ok=True)

        SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".txt"}

        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename()
                if not filename:
                    continue

                filename = self.decode_header_value(filename)
                ext = Path(filename).suffix.lower()

                if ext not in SUPPORTED_EXTENSIONS:
                    logger.debug(f"Skipping unsupported attachment: {filename}")
                    continue

                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))

                saved_paths.append(filepath)
                logger.info(f"📎 Downloaded attachment: {filename}")

        return saved_paths

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
    def fetch_new_emails(self) -> List[dict]:
        """Poll inbox for new Haveloc emails. Returns parsed email dicts."""
        results = []

        try:
            # Reconnect if needed
            if not self.mail:
                self.connect()

            self.mail.select("inbox")

            # Build search query for Haveloc senders
            search_criteria = []
            for sender in settings.haveloc_senders_list:
                # Search ALL emails from sender (not just UNSEEN)
                _, data = self.mail.search(None, f'(FROM "{sender}")')
                if data[0]:
                    search_criteria.extend(data[0].split())

            # Also search by domain keywords
            _, data = self.mail.search(None, '(FROM "haveloc")')
            if data[0]:
                search_criteria.extend(data[0].split())

            # Deduplicate message IDs
            unique_ids = list(set(search_criteria))

            # Deduplicate message IDs
            unique_ids = list(set(search_criteria))

            if not unique_ids:
                logger.debug("No new Haveloc emails found.")
                return []

            logger.info(f"📬 Found {len(unique_ids)} new email(s) to process")

            for num in unique_ids:
                _, msg_data = self.mail.fetch(num, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = self.decode_header_value(msg.get("Subject", "No Subject"))
                from_addr = msg.get("From", "")
                date_str = msg.get("Date", "")
                msg_id = msg.get("Message-ID", str(num))

                email_hash = generate_email_hash(msg_id, subject)

                if email_hash in self.processed_ids:
                    logger.debug(f"Skipping already processed email: {subject}")
                    continue

                is_haveloc = self.is_haveloc_sender(from_addr)
                if not is_haveloc:
                    logger.debug(f"Skipping non-Haveloc sender: {from_addr}")
                    continue

                logger.info(f"✅ PASSED FILTER: {subject[:40]} from {from_addr[:30]}")

                body = self.extract_body(msg)
                attachments = self.download_attachments(msg)

                full_text = f"{subject} {body}"
                score, priority, keywords = compute_priority_score(full_text)
                emergency = is_emergency(full_text)

                email_data = {
                    "id": email_hash,
                    "msg_id": msg_id,
                    "subject": subject,
                    "from": from_addr,
                    "date": date_str,
                    "body": body,
                    "attachments": attachments,
                    "priority_score": score,
                    "priority": priority,
                    "matched_keywords": keywords,
                    "is_emergency": emergency,
                    "processed_at": datetime.now().isoformat(),
                }

                results.append(email_data)
                save_processed_id(email_hash)
                self.processed_ids.add(email_hash)

                logger.info(
                    f"✉️  [{priority}] {subject} | Score: {score} | Emergency: {emergency}"
                )

        except imaplib.IMAP4.abort:
            logger.warning("IMAP connection aborted, reconnecting...")
            self.disconnect()
            self.connect()
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            self.disconnect()
            raise

        return results
