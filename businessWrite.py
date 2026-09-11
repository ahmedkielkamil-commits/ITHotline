"""Business-side database write operations and write routes."""

import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

import businesRead
import minio
import redis as redis_store
from auth import (
    business_or_provider_required,
    business_required,
    get_owned_ticket,
    get_provider_assigned_ticket,
)
from twilio import notify_providers_for_ticket

business_write_bp = Blueprint("business_write", __name__, url_prefix="/business")
ticket_write_bp = Blueprint("ticket_write", __name__, url_prefix="/tickets")
message_write_bp = Blueprint("message_write", __name__)
photo_write_bp = Blueprint("photo_write", __name__, url_prefix="/photos")

VALID_TYPES = {"pos", "network", "cameras", "equipment", "other"}
VALID_SEVERITY = {"urgent", "standard"}
CANCELLABLE = {"open", "claimed", "en_route", "on_site"}
VALID_BUSINESS_TYPES = {
    "market",
    "restaurant",
    "gas_station",
    "barbershop",
    "church",
    "daycare",
    "auto",
    "other",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

import db


def insert_business(
    name: str,
    password_hash: str,
    address: str,
    email: str,
    biz_type: str,
    wkt: str,
) -> int:
    return db.last_insert_id(
        """
        INSERT INTO businesses (name, password, address, email, type, status, location)
        VALUES (%s, %s, %s, %s, %s, 'pending', ST_GeomFromText(%s, 4326))
        """,
        (name, password_hash, address, email, biz_type, wkt),
    )


def update_business(business_id: int, updates: list[str], params: list) -> None:
    if not updates:
        return
    params.append(business_id)
    db.execute(
        f"UPDATE businesses SET {', '.join(updates)} WHERE businessid = %s",
        tuple(params),
    )


def update_business_location(business_id: int, wkt: str) -> None:
    db.execute(
        "UPDATE businesses SET location = ST_GeomFromText(%s, 4326) WHERE businessid = %s",
        (wkt, business_id),
    )


def insert_ticket(business_id: int, ticket_type: str, severity: str, problem_report: str) -> int:
    return db.last_insert_id(
        """
        INSERT INTO ticket (businessid, itid, type, severity, status, problemReport)
        VALUES (%s, NULL, %s, %s, 'open', %s)
        """,
        (business_id, ticket_type, severity, problem_report),
    )


def attach_problem_photo_keys(ticket_id: int, photo_keys: list[str]) -> None:
    for key in photo_keys:
        if not key or not isinstance(key, str):
            continue
        db.execute(
            """
            INSERT INTO photos (ticketid, upload_type, miniokey)
            VALUES (%s, 'problem', %s)
            """,
            (ticket_id, key.strip()),
        )


def cancel_ticket(ticket_id: int, business_id: int, reason: str) -> None:
    db.execute(
        """
        UPDATE ticket
        SET status = 'cancelled', cancelReason = %s
        WHERE ticketid = %s AND businessid = %s
        """,
        (reason, ticket_id, business_id),
    )


def confirm_ticket(ticket_id: int, business_id: int, rating: int) -> None:
    db.execute(
        """
        UPDATE ticket
        SET business_rating = %s,
            business_confirmed = %s,
            status = 'confirmed'
        WHERE ticketid = %s AND businessid = %s
        """,
        (rating, datetime.now(timezone.utc).replace(tzinfo=None), ticket_id, business_id),
    )


def insert_message(ticket_id: int, sender: str, content: str) -> int:
    return db.last_insert_id(
        """
        INSERT INTO messages (ticketid, sendertype, content)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, sender, content),
    )


def insert_photo(ticket_id: int, upload_type: str, miniokey: str) -> int:
    return db.last_insert_id(
        """
        INSERT INTO photos (ticketid, upload_type, miniokey)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, upload_type, miniokey),
    )


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@ticket_write_bp.post("")
@business_required
def create_ticket():
    data = request.get_json(silent=True) or {}
    ticket_type = data.get("type")
    severity = data.get("severity")
    problem_report = (data.get("problemReport") or "").strip()
    photo_keys = data.get("photoKeys") or []

    if ticket_type not in VALID_TYPES:
        return jsonify({"error": "Invalid ticket type"}), 400
    if severity not in VALID_SEVERITY:
        return jsonify({"error": "Invalid severity"}), 400
    if not problem_report:
        return jsonify({"error": "problemReport is required"}), 400

    ticket_id = insert_ticket(g.business["businessid"], ticket_type, severity, problem_report)
    if photo_keys:
        attach_problem_photo_keys(ticket_id, photo_keys)

    try:
        redis_store.schedule_ticket_escalation(ticket_id)
    except Exception:
        pass

    try:
        notify_providers_for_ticket(ticket_id)
    except Exception:
        pass

    ticket = get_owned_ticket(ticket_id)
    photos = businesRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.ticket_detail(ticket, photos)), 201


@ticket_write_bp.post("/<int:ticket_id>/cancel")
@business_required
def cancel_ticket_route(ticket_id: int):
    ticket = get_owned_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] == "confirmed":
        return jsonify({"error": "Confirmed tickets cannot be cancelled"}), 400
    if ticket["status"] == "cancelled":
        return jsonify({"error": "Ticket is already cancelled"}), 400
    if ticket["status"] == "complete":
        return jsonify({"error": "Completed tickets cannot be cancelled"}), 400
    if ticket["status"] not in CANCELLABLE:
        return jsonify({"error": "Ticket cannot be cancelled in its current state"}), 400

    data = request.get_json(silent=True) or {}
    reason = (data.get("cancelReason") or "Cancelled by business").strip()
    cancel_ticket(ticket_id, g.business["businessid"], reason)
    ticket = get_owned_ticket(ticket_id)
    photos = businesRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.ticket_detail(ticket, photos)), 200


@ticket_write_bp.post("/<int:ticket_id>/confirm")
@business_required
def confirm_ticket_route(ticket_id: int):
    ticket = get_owned_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] != "complete":
        return jsonify({"error": "Ticket must be complete before confirmation"}), 400

    data = request.get_json(silent=True) or {}
    rating = data.get("business_rating")
    if rating not in (0, 1):
        return jsonify({"error": "business_rating must be 0 or 1"}), 400

    confirm_ticket(ticket_id, g.business["businessid"], rating)
    ticket = get_owned_ticket(ticket_id)
    photos = businesRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.ticket_detail(ticket, photos)), 200


@business_write_bp.put("/me")
@business_required
def update_me():
    data = request.get_json(silent=True) or {}
    business_id = g.business["businessid"]
    updates = []
    params: list = []

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty"}), 400
        updates.append("name = %s")
        params.append(name)

    if "address" in data:
        address = (data.get("address") or "").strip()
        if not address:
            return jsonify({"error": "address cannot be empty"}), 400
        updates.append("address = %s")
        params.append(address)

    if "type" in data:
        biz_type = data.get("type")
        if biz_type not in VALID_BUSINESS_TYPES:
            return jsonify({"error": "Invalid business type"}), 400
        updates.append("type = %s")
        params.append(biz_type)

    if updates:
        update_business(business_id, updates, params)

    if "lat" in data and "lng" in data and data["lat"] is not None and data["lng"] is not None:
        try:
            lat_f = float(data["lat"])
            lng_f = float(data["lng"])
        except (TypeError, ValueError):
            return jsonify({"error": "lat and lng must be numbers"}), 400
        wkt = f"POINT({lng_f} {lat_f})"
        update_business_location(business_id, wkt)

    business = businesRead.fetch_business_by_id(business_id)
    return jsonify(businesRead.business_json(business)), 200


@message_write_bp.post("/tickets/<int:ticket_id>/messages")
@business_or_provider_required
def create_message(ticket_id: int):
    import techRead
    import techWrite

    if g.auth_role == "business":
        ticket = get_owned_ticket(ticket_id)
        sender = "business"
    else:
        ticket = get_provider_assigned_ticket(ticket_id)
        sender = "provider"
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    if sender == "business":
        message_id = insert_message(ticket_id, sender, content)
        row = businesRead.fetch_message_by_id(message_id)
    else:
        message_id = techWrite.insert_message(ticket_id, sender, content)
        row = techRead.fetch_message_by_id(message_id)
    return jsonify(businesRead.message_json(row)), 201


@photo_write_bp.post("")
@business_or_provider_required
def upload_photo():
    import techRead
    import techWrite

    ticket_id = request.form.get("ticket_id", type=int)
    upload_type = (request.form.get("upload_type") or "problem").strip()
    file = request.files.get("file")

    if not ticket_id:
        return jsonify({"error": "ticket_id is required"}), 400
    if upload_type not in {"problem", "completion"}:
        return jsonify({"error": "upload_type must be problem or completion"}), 400
    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    if g.auth_role == "business":
        if upload_type != "problem":
            return jsonify({"error": "Business uploads must use upload_type=problem"}), 400
        ticket = get_owned_ticket(ticket_id)
    else:
        if upload_type != "completion":
            return jsonify({"error": "Provider uploads must use upload_type=completion"}), 400
        ticket = get_provider_assigned_ticket(ticket_id)
        if ticket and ticket["status"] in {"open", "cancelled", "confirmed"}:
            ticket = None
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    ext = os.path.splitext(secure_filename(file.filename))[1].lower() or ".jpg"
    object_key = f"tickets/{ticket_id}/{upload_type}_{uuid.uuid4().hex}{ext}"
    data = file.read()
    content_type = file.mimetype or "application/octet-stream"
    minio.upload_bytes(object_key, data, content_type)

    if g.auth_role == "business":
        photo_id = insert_photo(ticket_id, upload_type, object_key)
        row = businesRead.fetch_photo_by_id(photo_id)
    else:
        photo_id = techWrite.insert_photo(ticket_id, upload_type, object_key)
        row = techRead.fetch_photo_by_id(photo_id)
    payload = businesRead.photo_json(row)
    return jsonify({"miniokey": object_key, "url": payload["url"], "photo": payload}), 201
