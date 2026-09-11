import importlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
WORDS_KEY = os.environ.get("REDIS_WORDS_KEY", "ithotline:words")
ESCALATION_SET_KEY = os.environ.get("REDIS_ESCALATION_SET", "ithotline:escalations")
ESCALATION_DELAY_MINUTES = int(os.environ.get("TICKET_ESCALATION_MINUTES", "10"))
RQ_QUEUE_NAME = os.environ.get("RQ_QUEUE_NAME", "ithotline")

SMS_PENDING_PREFIX = "ithotline:sms_pending:"
SMS_TICKET_PHONES_PREFIX = "ithotline:sms_ticket:"
SMS_PENDING_TTL = int(os.environ.get("SMS_PENDING_TTL_SECONDS", "3600"))
SHADOW_LOG_PREFIX = "ithotline:shadow:"
SHADOW_LOG_TTL = int(os.environ.get("SHADOW_LOG_TTL_SECONDS", "86400"))
ESCALATION_RADIUS_MULTIPLIER = 1.5

logger = logging.getLogger(__name__)


def _load_redis_lib():
    this_module = sys.modules[__name__]
    project_dir = Path(__file__).resolve().parent
    sys.modules.pop("redis", None)
    original_path = sys.path.copy()
    sys.path = [entry for entry in sys.path if Path(entry).resolve() != project_dir]
    try:
        return importlib.import_module("redis")
    finally:
        sys.path = original_path
        sys.modules["redis"] = this_module


_redis_lib = _load_redis_lib()
client = _redis_lib.from_url(REDIS_URL, decode_responses=True)


def list_words():
    return client.hgetall(WORDS_KEY)


def add_word(word):
    text = word.strip()
    if not text:
        raise ValueError("Enter a word to store.")

    entry_id = str(uuid.uuid4())
    client.hset(WORDS_KEY, entry_id, text)
    return entry_id, text


def delete_word(entry_id):
    if not entry_id:
        raise ValueError("Missing entry id.")
    return client.hdel(WORDS_KEY, entry_id) > 0


def clear_words():
    return client.delete(WORDS_KEY) > 0


def get_rq_connection():
    """Binary-safe Redis connection for RQ (separate from decode_responses client)."""
    return _redis_lib.from_url(REDIS_URL)


def get_rq_queue():
    from rq import Queue

    return Queue(RQ_QUEUE_NAME, connection=get_rq_connection())


def flag_ticket_escalation(ticket_id: int, reason: str = "No provider claimed within SLA") -> None:
    ticket_key = str(ticket_id)
    payload = {
        "ticketid": ticket_id,
        "reason": reason,
        "flagged_at": datetime.now(timezone.utc).isoformat(),
    }
    client.sadd(ESCALATION_SET_KEY, ticket_key)
    client.set(f"ithotline:escalation:{ticket_key}", json.dumps(payload))


def list_escalations() -> list[dict]:
    ids = client.smembers(ESCALATION_SET_KEY)
    results = []
    for ticket_key in sorted(ids, key=int):
        raw = client.get(f"ithotline:escalation:{ticket_key}")
        if raw:
            results.append(json.loads(raw))
    return results


def check_ticket_escalation(ticket_id: int) -> None:
    """RQ job: flag ticket for admin review if still unclaimed; widen SMS dispatch."""
    row = db.fetch_one(
        "SELECT ticketid, status, businessid FROM ticket WHERE ticketid = %s",
        (ticket_id,),
    )
    if not row:
        logger.warning("Escalation check: ticket %s not found", ticket_id)
        return
    if row["status"] != "open":
        logger.info("Escalation check: ticket %s status=%s, no action", ticket_id, row["status"])
        return

    flag_ticket_escalation(
        ticket_id,
        reason=f"Still open after {ESCALATION_DELAY_MINUTES} minutes",
    )
    logger.warning("Ticket %s flagged for admin escalation", ticket_id)

    from twilio import notify_providers_for_ticket

    notified = notify_providers_for_ticket(ticket_id, radius_multiplier=ESCALATION_RADIUS_MULTIPLIER)
    logger.info(
        "Ticket %s escalation re-notify sent to %s provider(s) at %.1fx radius",
        ticket_id,
        notified,
        ESCALATION_RADIUS_MULTIPLIER,
    )


def schedule_ticket_escalation(ticket_id: int) -> None:
    queue = get_rq_queue()
    queue.enqueue_in(
        timedelta(minutes=ESCALATION_DELAY_MINUTES),
        check_ticket_escalation,
        ticket_id,
    )


def _normalize_phone(phone: str) -> str:
    import re

    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if phone and phone.startswith("+"):
        return phone
    return f"+{digits}" if digits else ""


def store_pending_offer(phone: str, ticket_id: int) -> None:
    normalized = _normalize_phone(phone)
    if not normalized:
        return
    client.set(f"{SMS_PENDING_PREFIX}{normalized}", str(ticket_id), ex=SMS_PENDING_TTL)
    client.sadd(f"{SMS_TICKET_PHONES_PREFIX}{ticket_id}", normalized)


def pending_ticket_for_phone(phone: str) -> int | None:
    normalized = _normalize_phone(phone)
    if not normalized:
        return None
    raw = client.get(f"{SMS_PENDING_PREFIX}{normalized}")
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def clear_pending_offer(phone: str, ticket_id: int) -> None:
    normalized = _normalize_phone(phone)
    if normalized:
        key = f"{SMS_PENDING_PREFIX}{normalized}"
        if client.get(key) == str(ticket_id):
            client.delete(key)
    if normalized:
        client.srem(f"{SMS_TICKET_PHONES_PREFIX}{ticket_id}", normalized)


def store_shadow_completion(ticket_id: int, payload: dict) -> None:
    client.set(f"{SHADOW_LOG_PREFIX}{ticket_id}", json.dumps(payload), ex=SHADOW_LOG_TTL)
