import imaplib
import email
import email.message
from email.header import decode_header
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv
from Service import EmailService

load_dotenv()

email_svc = EmailService()

# ─────────────────────────────────────────────
#  CONFIG
#  Add as many accounts as you need here —
#  just follow the same pattern in your .env
# ─────────────────────────────────────────────

ACCOUNTS = [
    {
        "label":    "school",
        "host":     "imap.gmail.com",
        "port":     993,
        "user":     os.getenv("EMAIL1"),
        "password": os.getenv("EMAIL1PW"),
    },
    #{
    #    "label":    "personal",
    #    "host":     "outlook.office365.com",
    #    "port":     993,
    #    "user":     os.getenv("EMAIL2"),
    #    "password": os.getenv("EMAIL2PW"),
    #},
]

# How many of the most recent emails to fetch per account per run
FETCH_LIMIT = 20


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _decode_str(value: str) -> str:
    """
    Email headers are sometimes encoded (e.g. =?utf-8?b?...?=).
    This decodes them back to a plain string.
    """
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded).strip()


def _extract_body_preview(msg: email.message.Message, limit: int = 200) -> str:
    """
    Pulls the first `limit` characters of plain text from the email body.
    Skips HTML parts — we only want readable text.
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))

            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body    = part.get_payload(decode=True).decode(charset, errors="replace")
                    return body.strip()[:limit]
                except Exception:
                    continue
    else:
        if msg.get_content_type() == "text/plain":
            try:
                charset = msg.get_content_charset() or "utf-8"
                body    = msg.get_payload(decode=True).decode(charset, errors="replace")
                return body.strip()[:limit]
            except Exception:
                pass
    return ""


def _parse_sender(raw_from: str) -> tuple[str, str]:
    """
    Splits a raw From header like 'Jake Smith <jake@stripe.com>'
    into (name, address).
    """
    raw_from = _decode_str(raw_from)
    if "<" in raw_from and ">" in raw_from:
        name    = raw_from[:raw_from.index("<")].strip().strip('"')
        address = raw_from[raw_from.index("<") + 1 : raw_from.index(">")].strip()
    else:
        name    = ""
        address = raw_from.strip()
    return name, address.lower()


def _parse_date(date_str: str) -> datetime:
    """
    Tries several common email date formats.
    Falls back to now() if nothing parses.
    """
    if not date_str:
        return datetime.now()

    # Strip timezone name in parentheses e.g. "(EST)"
    date_str = date_str.split("(")[0].strip()

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return datetime.now()


def _needs_action(subject: str, body_preview: str) -> tuple[bool, str]:
    """
    Very simple heuristic to flag emails that likely need a response.
    Phase 4: replace this with an actual LLM call for smarter detection.
    """
    combined = (subject + " " + body_preview).lower()

    reply_signals = [
        "can you", "could you", "please", "let me know",
        "thoughts?", "available", "following up", "wanted to reach out",
        "would love to", "are you free", "catch up", "quick call",
    ]
    followup_signals = [
        "re:", "following up", "checking in", "just wanted to",
        "circling back", "any update",
    ]
    meeting_signals = [
        "meeting", "call", "zoom", "teams", "coffee chat",
        "schedule", "calendar invite", "availability",
    ]

    if any(s in combined for s in meeting_signals):
        return True, "schedule_meeting"
    if any(s in combined for s in followup_signals):
        return True, "follow_up"
    if any(s in combined for s in reply_signals):
        return True, "reply_needed"

    return False, "none"


# ─────────────────────────────────────────────
#  CORE: CONNECT + FETCH
# ─────────────────────────────────────────────

def _connect(account: dict) -> Optional[imaplib.IMAP4_SSL]:
    """Opens an IMAP SSL connection and logs in."""
    try:
        conn = imaplib.IMAP4_SSL(account["host"], account["port"])
        conn.login(account["user"], account["password"])
        return conn
    except imaplib.IMAP4.error as e:
        print(f"[email_parser] Login failed for {account['label']}: {e}")
        return None


def _fetch_recent(conn: imaplib.IMAP4_SSL, limit: int) -> list[email.message.Message]:
    """Selects the inbox and returns the most recent `limit` messages."""
    conn.select("INBOX")

    # Search for ALL mail — we filter by what's already in the DB later
    # TODO (Phase 4): swap to UNSEEN if you only want unread
    status, data = conn.search(None, "ALL")
    if status != "OK":
        return []

    mail_ids    = data[0].split()
    recent_ids  = mail_ids[-limit:]   # grab the tail — most recent
    messages    = []

    for mail_id in reversed(recent_ids):   # newest first
        status, msg_data = conn.fetch(mail_id, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        messages.append(msg)

    return messages


# ─────────────────────────────────────────────
#  CORE: PARSE + SAVE
# ─────────────────────────────────────────────

def _process_message(msg: email.message.Message, account_label: str) -> Optional[dict]:
    """
    Converts a raw email.message.Message into our Email model shape
    and saves it via EmailService. Returns the saved dict or None.
    """
    subject      = _decode_str(msg.get("Subject", "(no subject)"))
    sender_name, sender_address = _parse_sender(msg.get("From", ""))
    received_at  = _parse_date(msg.get("Date", ""))
    body_preview = _extract_body_preview(msg)
    requires_action, action_type = _needs_action(subject, body_preview)

    email_record = {
        "account":            account_label,
        "sender_name":        sender_name,
        "sender_address":     sender_address,
        "sender_contact_id":  None,            # EmailService will try to resolve this
        "subject":            subject,
        "body_preview":       body_preview,
        "received_at":        received_at.isoformat(),
        "is_read":            False,
        "requires_action":    requires_action,
        "action_type":        action_type,
        "linked_contact_id":  None,
        "linked_task_id":     None,
    }

    try:
        new_id = email_svc.create(email_record)
        email_record["id"] = new_id
        print(f"[email_parser] Saved email #{new_id}: '{subject}' from {sender_address}")
        return email_record
    except Exception as e:
        print(f"[email_parser] Failed to save email '{subject}': {e}")
        return None


# ─────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────

def run_email_sync() -> dict:
    """
    Main function — call this from scheduler.py or directly from a route.
    Loops over all configured accounts, fetches recent mail, saves new ones.
    Returns a summary of what was processed.
    """
    summary = {"accounts_checked": 0, "emails_saved": 0, "action_required": 0}

    for account in ACCOUNTS:
        if not account["user"] or not account["password"]:
            print(f"[email_parser] Skipping {account['label']} — credentials not set in .env")
            continue

        print(f"[email_parser] Connecting to {account['label']} ({account['user']})...")
        conn = _connect(account)
        if not conn:
            continue

        messages = _fetch_recent(conn, FETCH_LIMIT)
        conn.logout()

        summary["accounts_checked"] += 1

        for msg in messages:
            result = _process_message(msg, account["label"])
            if result:
                summary["emails_saved"]    += 1
                if result.get("requires_action"):
                    summary["action_required"] += 1

    print(f"[email_parser] Done. {summary}")
    return summary

