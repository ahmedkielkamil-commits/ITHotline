"""Provider/tech-side database write operations and write routes."""

import json
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

import businesRead
import redis as redis_store
import techRead
from auth import get_provider_assigned_ticket, get_provider_viewable_ticket, provider_required

provider_write_bp = Blueprint("provider_write", __name__, url_prefix="/provider")
provider_ticket_write_bp = Blueprint("provider_ticket_write", __name__, url_prefix="/tickets")

JOURNEY_STATUSES = {"en_route", "on_site"}
TERMINAL_STATUSES = {"complete", "confirmed", "cancelled"}
VALID_SKILLS = {"pos", "network", "cameras", "equipment", "other"}

import db


def insert_provider(
    fname: str,
    lname: str,
    email: str,
    phone: str | None,
    password_hash: str,
    skills_json: str,
    vouched_by_name: str | None,
    vouched_by_relationship: str | None,
    wkt: str,
) -> int:
    return db.last_insert_id(
        """
        INSERT INTO ITWorker (
            fname, lname, email, phone, password, status, tier, availability,
            service_radius_m, skills, vouched_by_name, vouched_by_relationship, match_anchor
        )
        VALUES (%s, %s, %s, %s, %s, 'pending', 'shadow', FALSE, 8000, %s, %s, %s, ST_GeomFromText(%s, 4326))
        """,
        (
            fname,
            lname,
            email,
            phone,
            password_hash,
            skills_json,
            vouched_by_name,
            vouched_by_relationship,
            wkt,
        ),
    )


def update_itworker(itid: int, updates: list[str], params: list) -> None:
    if not updates:
        return
    params.append(itid)
    db.execute(
        f"UPDATE ITWorker SET {', '.join(updates)} WHERE itid = %s",
        tuple(params),
    )


def update_provider_location(itid: int, wkt: str) -> None:
    db.execute(
        "UPDATE ITWorker SET match_anchor = ST_GeomFromText(%s, 4326) WHERE itid = %s",
        (wkt, itid),
    )


def update_provider_availability(itid: int, updates: list[str], params: list) -> None:
    params.append(itid)
    db.execute(
        f"UPDATE ITWorker SET {', '.join(updates)} WHERE itid = %s",
        tuple(params),
    )


def atomic_claim_ticket(ticket_id: int, itid: int) -> bool:
    """Claim only if still open and unassigned. Returns True if this caller won."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = db.execute(
        """
        UPDATE ticket
        SET itid = %s, status = 'claimed', claimed_at = %s
        WHERE ticketid = %s AND status = 'open' AND itid IS NULL
        """,
        (itid, now, ticket_id),
    )
    return rows == 1


def update_ticket_status(
    ticket_id: int,
    itid: int,
    new_status: str,
    *,
    set_arrival: bool = False,
) -> None:
    if set_arrival:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.execute(
            """
            UPDATE ticket
            SET status = %s, arrival_time = COALESCE(arrival_time, %s)
            WHERE ticketid = %s AND itid = %s
            """,
            (new_status, now, ticket_id, itid),
        )
        return

    db.execute(
        "UPDATE ticket SET status = %s WHERE ticketid = %s AND itid = %s",
        (new_status, ticket_id, itid),
    )


def complete_ticket(
    ticket_id: int,
    itid: int,
    completion_report: str,
    amount: float,
    provider_rating: int,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(
        """
        UPDATE ticket
        SET status = 'complete',
            completion_time = %s,
            completionReport = %s,
            amount_charged = %s,
            provider_rating = %s
        WHERE ticketid = %s AND itid = %s
        """,
        (now, completion_report, amount, provider_rating, ticket_id, itid),
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


def _provider_skills_match(ticket_type: str, skills_raw) -> bool:
    skills = skills_raw
    if isinstance(skills_raw, str):
        try:
            skills = json.loads(skills_raw)
        except json.JSONDecodeError:
            skills = []
    if not skills:
        return True
    return ticket_type in skills


@provider_write_bp.put("/me")
@provider_required
def update_me():
    data = request.get_json(silent=True) or {}
    itid = g.provider["itid"]
    updates = []
    params: list = []

    for field, column in [
        ("fname", "fname"),
        ("firstName", "fname"),
        ("lname", "lname"),
        ("lastName", "lname"),
        ("phone", "phone"),
        ("vouched_by_name", "vouched_by_name"),
        ("vouchedBy", "vouched_by_name"),
        ("vouched_by_relationship", "vouched_by_relationship"),
        ("vouchedRelationship", "vouched_by_relationship"),
    ]:
        if field in data:
            value = (data.get(field) or "").strip()
            if column == "phone" and value:
                existing = techRead.fetch_provider_id_by_phone(value, exclude_itid=itid)
                if existing:
                    return jsonify({"error": "Phone already in use"}), 400
            if column in {"fname", "lname"} and not value:
                return jsonify({"error": f"{column} cannot be empty"}), 400
            if f"{column} = %s" not in updates:
                updates.append(f"{column} = %s")
                params.append(value or None)

    if "service_radius_m" in data:
        try:
            radius = int(data["service_radius_m"])
        except (TypeError, ValueError):
            return jsonify({"error": "service_radius_m must be an integer"}), 400
        if radius < 500 or radius > 50000:
            return jsonify({"error": "service_radius_m must be between 500 and 50000"}), 400
        updates.append("service_radius_m = %s")
        params.append(radius)

    if "skills" in data:
        raw_skills = data.get("skills")
        if not isinstance(raw_skills, list):
            return jsonify({"error": "skills must be an array"}), 400
        skills = []
        for item in raw_skills:
            if item not in VALID_SKILLS:
                return jsonify({"error": f"Invalid skill: {item}"}), 400
            skills.append(item)
        updates.append("skills = %s")
        params.append(json.dumps(skills))

    if updates:
        update_itworker(itid, updates, params)

    if "lat" in data and "lng" in data and data["lat"] is not None and data["lng"] is not None:
        try:
            lat_f = float(data["lat"])
            lng_f = float(data["lng"])
        except (TypeError, ValueError):
            return jsonify({"error": "lat and lng must be numbers"}), 400
        wkt = f"POINT({lng_f} {lat_f})"
        update_provider_location(itid, wkt)

    provider = techRead.fetch_provider_by_id(itid)
    return jsonify(techRead.provider_json(provider)), 200


@provider_write_bp.put("/availability")
@provider_required
def set_availability():
    data = request.get_json(silent=True) or {}
    if "availability" not in data:
        return jsonify({"error": "availability is required"}), 400

    availability = data.get("availability")
    if not isinstance(availability, bool):
        return jsonify({"error": "availability must be true or false"}), 400

    itid = g.provider["itid"]
    updates = ["availability = %s"]
    params: list = [availability]

    for field in ("avail_start_time", "avail_end_time"):
        if field in data:
            value = data.get(field)
            if value is None or value == "":
                updates.append(f"{field} = NULL")
            else:
                text = str(value).strip()
                if len(text) == 5:
                    text = f"{text}:00"
                updates.append(f"{field} = %s")
                params.append(text)

    update_provider_availability(itid, updates, params)
    if availability:
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is not None and lng is not None:
            wkt = f"POINT({float(lng)} {float(lat)})"
            update_provider_location(itid, wkt)
    provider = techRead.fetch_provider_by_id(itid)
    return jsonify(techRead.provider_json(provider)), 200


@provider_ticket_write_bp.post("/<int:ticket_id>/claim")
@provider_required
def claim_ticket(ticket_id: int):
    if g.provider["status"] != "approved":
        return jsonify({"error": "Provider must be approved to claim tickets"}), 403
    if not g.provider["availability"]:
        return jsonify({"error": "Turn on availability to claim tickets"}), 403

    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lng = data.get("lng")
    preview = None
    if lat is not None and lng is not None:
        wkt = f"POINT({float(lng)} {float(lat)})"
        update_provider_location(g.provider["itid"], wkt)
        preview = techRead.get_provider_viewable_ticket(ticket_id, g.provider["itid"], wkt)
    if not preview:
        preview = get_provider_viewable_ticket(ticket_id)
    if not preview or preview["status"] != "open" or preview.get("itid"):
        return jsonify({"error": "Ticket is not available to claim"}), 404
    if not _provider_skills_match(preview["type"], g.provider.get("skills")):
        return jsonify({"error": "Ticket type does not match your skills"}), 403

    won = atomic_claim_ticket(ticket_id, g.provider["itid"])
    if not won:
        return jsonify({"error": "already claimed"}), 409

    if g.provider.get("phone"):
        redis_store.clear_pending_offer(g.provider["phone"], ticket_id)

    ticket = get_provider_assigned_ticket(ticket_id)
    photos = techRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.provider_ticket_detail(ticket, photos)), 200


@provider_ticket_write_bp.post("/<int:ticket_id>/status")
@provider_required
def update_status(ticket_id: int):
    ticket = get_provider_assigned_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] in TERMINAL_STATUSES:
        return jsonify({"error": "Ticket is closed"}), 400

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in JOURNEY_STATUSES:
        return jsonify({"error": "status must be en_route or on_site"}), 400

    current = ticket["status"]
    if new_status == "en_route":
        if current not in {"claimed", "en_route"}:
            return jsonify({"error": "Cannot mark en_route from current state"}), 400
    elif new_status == "on_site":
        if current not in {"claimed", "en_route", "on_site"}:
            return jsonify({"error": "Cannot mark on_site from current state"}), 400

    update_ticket_status(
        ticket_id,
        g.provider["itid"],
        new_status,
        set_arrival=(new_status == "on_site"),
    )
    ticket = get_provider_assigned_ticket(ticket_id)
    photos = techRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.provider_ticket_detail(ticket, photos)), 200


@provider_ticket_write_bp.post("/<int:ticket_id>/complete")
@provider_required
def complete_ticket_route(ticket_id: int):
    ticket = get_provider_assigned_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    if ticket["status"] in TERMINAL_STATUSES:
        return jsonify({"error": "Ticket is already closed"}), 400
    if ticket["status"] not in {"en_route", "on_site"}:
        return jsonify({"error": "Ticket must be en_route or on_site before completion"}), 400

    data = request.get_json(silent=True) or {}
    completion_report = (data.get("completionReport") or "").strip()
    parts_text = (data.get("parts") or data.get("parts_text") or "").strip()
    apprentice_assisted = data.get("apprentice_assisted", data.get("apprenticeAssisted"))
    apprentice_name = (data.get("apprentice_name") or data.get("apprenticeName") or "").strip()
    amount = data.get("amount_charged")
    provider_rating = data.get("provider_rating")

    if not completion_report:
        return jsonify({"error": "completionReport is required"}), 400
    if amount is None:
        return jsonify({"error": "amount_charged is required"}), 400
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "amount_charged must be a number"}), 400
    if amount_f < 0:
        return jsonify({"error": "amount_charged cannot be negative"}), 400
    if provider_rating not in (0, 1):
        return jsonify({"error": "provider_rating must be 0 or 1"}), 400

    if parts_text:
        completion_report = f"{completion_report}\n\nParts: {parts_text}"

    complete_ticket(ticket_id, g.provider["itid"], completion_report, amount_f, provider_rating)

    if apprentice_assisted or apprentice_name:
        redis_store.store_shadow_completion(
            ticket_id,
            {
                "ticketid": ticket_id,
                "itid": g.provider["itid"],
                "apprentice_assisted": bool(apprentice_assisted),
                "apprentice_name": apprentice_name or None,
                "logged_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    ticket = get_provider_assigned_ticket(ticket_id)
    photos = techRead.fetch_ticket_photos(ticket_id)
    return jsonify(businesRead.provider_ticket_detail(ticket, photos)), 200
