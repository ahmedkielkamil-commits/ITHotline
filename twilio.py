"""Twilio SMS dispatch and inbound claim handling."""

import importlib
import json
import logging
import os
import re
import sys
from pathlib import Path

from flask import Blueprint, request

import redis as redis_store
import techRead
import techWrite

logger = logging.getLogger(__name__)


def _load_twilio_lib():
    this_module = sys.modules[__name__]
    project_dir = Path(__file__).resolve().parent
    sys.modules.pop("twilio", None)
    original_path = sys.path.copy()
    sys.path = [entry for entry in sys.path if Path(entry).resolve() != project_dir]
    try:
        return importlib.import_module("twilio")
    finally:
        sys.path = original_path
        sys.modules["twilio"] = this_module


def _twilio_client():
    sdk = _load_twilio_lib()
    return sdk.rest.Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
TWILIO_ENABLED = os.environ.get("TWILIO_ENABLED", "false").lower() in {"1", "true", "yes"}
ESCALATION_RADIUS_MULTIPLIER = 1.5

CATEGORY_LABELS = {
    "pos": "POS",
    "network": "Network",
    "cameras": "Cameras",
    "equipment": "Equipment",
    "other": "Other",
}

twilio_bp = Blueprint("twilio", __name__, url_prefix="/twilio")


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if phone and phone.startswith("+"):
        return phone
    return f"+{digits}" if digits else ""


def _business_area(address: str) -> str:
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        return ", ".join(parts[-2:])
    return address or "your area"


def _format_distance(meters: float) -> str:
    miles = meters / 1609.34
    if miles < 0.1:
        return "nearby"
    return f"{miles:.1f} mi"


def _send_sms(to_phone: str, body: str) -> None:
    normalized = _normalize_phone(to_phone)
    if not normalized:
        logger.warning("Skipping SMS — invalid phone %r", to_phone)
        return

    if not TWILIO_ENABLED or not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        logger.info("[SMS dry-run] to=%s body=%s", normalized, body)
        return

    try:
        client = _twilio_client()
        client.messages.create(to=normalized, from_=TWILIO_FROM_NUMBER, body=body)
        logger.info("SMS sent to %s", normalized)
    except Exception:
        logger.exception("Twilio send failed for %s", normalized)


def notify_providers_for_ticket(ticket_id: int, radius_multiplier: float = 1.0) -> int:
    """
    SMS eligible providers for an open ticket. Returns count of providers notified.
    Never raises — failures are logged so ticket creation continues.
    """
    try:
        ticket = techRead.fetch_ticket_for_dispatch(ticket_id)
        if not ticket or ticket["status"] != "open":
            return 0

        wkt = f"POINT({ticket['biz_lng']} {ticket['biz_lat']})"
        providers = techRead.list_providers_for_dispatch(wkt, radius_multiplier)

        notified = 0
        category = CATEGORY_LABELS.get(ticket["type"], ticket["type"])
        urgency = "URGENT" if ticket["severity"] == "urgent" else "Standard"
        area = _business_area(ticket["business_address"])

        for provider in providers:
            skills_raw = provider.get("skills")
            if skills_raw:
                if isinstance(skills_raw, str):
                    skills = json.loads(skills_raw)
                else:
                    skills = skills_raw
                if ticket["type"] not in skills:
                    continue

            distance_label = _format_distance(float(provider["distance_m"]))
            body = (
                f"IT Hotline — {urgency} {category} job near {area} "
                f"({distance_label}). Reply YES to claim ticket #{ticket_id}."
            )
            _send_sms(provider["phone"], body)
            redis_store.store_pending_offer(provider["phone"], ticket_id)
            notified += 1

        logger.info("Ticket %s: notified %s provider(s)", ticket_id, notified)
        return notified
    except Exception:
        logger.exception("Provider dispatch failed for ticket %s", ticket_id)
        return 0


def _twiml(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'


@twilio_bp.post("/inbound")
def inbound_sms():
    from_number = request.values.get("From", "")
    body = (request.values.get("Body") or "").strip()
    normalized = _normalize_phone(from_number)

    if not normalized:
        return _twiml("Unable to identify your phone number."), 200, {"Content-Type": "text/xml"}

    if not re.match(r"^yes\b", body, re.IGNORECASE):
        return _twiml("Reply YES to claim your most recent job offer."), 200, {"Content-Type": "text/xml"}

    provider = techRead.fetch_provider_for_twilio(normalized, from_number)
    if not provider:
        return _twiml("Phone not registered with IT Hotline."), 200, {"Content-Type": "text/xml"}
    if provider["status"] != "approved":
        return _twiml("Your provider account is not approved yet."), 200, {"Content-Type": "text/xml"}
    if not provider["availability"]:
        return _twiml("Turn on availability in the app to claim jobs."), 200, {"Content-Type": "text/xml"}

    ticket_id = redis_store.pending_ticket_for_phone(normalized) or redis_store.pending_ticket_for_phone(from_number)
    if not ticket_id:
        return _twiml("No open job offer found for this number."), 200, {"Content-Type": "text/xml"}

    won = techWrite.atomic_claim_ticket(ticket_id, provider["itid"])
    if not won:
        redis_store.clear_pending_offer(normalized, ticket_id)
        return _twiml(f"Ticket #{ticket_id} was already claimed."), 200, {"Content-Type": "text/xml"}

    redis_store.clear_pending_offer(normalized, ticket_id)
    logger.info("Ticket %s claimed via SMS by provider %s", ticket_id, provider["itid"])
    return _twiml(f"You claimed ticket #{ticket_id}. Open the app for details."), 200, {"Content-Type": "text/xml"}
