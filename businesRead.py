"""Business-side database read operations and GET routes."""

import json
from datetime import datetime

from flask import Blueprint, g, jsonify, request

import db
import minio
from auth import (
    business_or_provider_required,
    business_required,
    get_provider_viewable_ticket,
)

business_read_bp = Blueprint("business_read", __name__, url_prefix="/business")
ticket_read_bp = Blueprint("ticket_read", __name__, url_prefix="/tickets")
providers_count_bp = Blueprint("providers_count", __name__, url_prefix="/providers")
message_read_bp = Blueprint("message_read", __name__)

IN_PROGRESS_STATUSES = {"open", "claimed", "en_route", "on_site"}

CATEGORY_LABELS = {
    "pos": "POS",
    "network": "Network",
    "cameras": "Cameras",
    "equipment": "Equipment",
    "other": "Other",
}

BUSINESS_SELECT = """
    SELECT businessid, name, email, address, type, status,
           ST_Y(location) AS lat, ST_X(location) AS lng
    FROM businesses
    WHERE businessid = %s
"""

BUSINESS_LOGIN_SELECT = """
    SELECT businessid, name, email, address, type, status, password,
           ST_Y(location) AS lat, ST_X(location) AS lng
    FROM businesses WHERE email = %s
"""


def fetch_business_by_id(business_id: int) -> dict | None:
    return db.fetch_one(BUSINESS_SELECT, (business_id,))


def fetch_business_by_email(email: str, *, include_password: bool = False) -> dict | None:
    if include_password:
        return db.fetch_one(BUSINESS_LOGIN_SELECT, (email,))
    return db.fetch_one(
        """
        SELECT businessid, name, email, address, type, status,
               ST_Y(location) AS lat, ST_X(location) AS lng
        FROM businesses WHERE email = %s
        """,
        (email,),
    )


def fetch_business_id_by_email(email: str) -> dict | None:
    return db.fetch_one("SELECT businessid FROM businesses WHERE email = %s", (email,))


def list_tickets_for_business(business_id: int) -> list[dict]:
    return db.fetch_all(
        """
        SELECT t.*,
               w.fname AS worker_fname,
               w.lname AS worker_lname
        FROM ticket t
        LEFT JOIN ITWorker w ON t.itid = w.itid
        WHERE t.businessid = %s
        ORDER BY t.created_at DESC
        """,
        (business_id,),
    )


def fetch_owned_ticket_row(ticket_id: int, business_id: int) -> dict | None:
    return db.fetch_one(
        """
        SELECT t.*,
               w.fname AS worker_fname,
               w.lname AS worker_lname,
               w.vouched_by_name,
               w.vouched_by_relationship,
               b.name AS business_name,
               b.address AS business_address,
               ST_Y(b.location) AS business_lat,
               ST_X(b.location) AS business_lng
        FROM ticket t
        LEFT JOIN ITWorker w ON t.itid = w.itid
        JOIN businesses b ON t.businessid = b.businessid
        WHERE t.ticketid = %s AND t.businessid = %s
        """,
        (ticket_id, business_id),
    )


def fetch_ticket_photos(ticket_id: int) -> list[dict]:
    return db.fetch_all(
        "SELECT * FROM photos WHERE ticketid = %s ORDER BY upload_time ASC",
        (ticket_id,),
    )


def fetch_messages_for_ticket(ticket_id: int) -> list[dict]:
    return db.fetch_all(
        """
        SELECT messageid, ticketid, sendertype, content, send_time, read_time
        FROM messages
        WHERE ticketid = %s
        ORDER BY send_time ASC
        """,
        (ticket_id,),
    )


def fetch_message_by_id(message_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM messages WHERE messageid = %s", (message_id,))


def fetch_photo_by_id(photo_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM photos WHERE photoid = %s", (photo_id,))


def count_available_providers(lat: float, lng: float) -> int:
    wkt = f"POINT({lng} {lat})"
    row = db.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM ITWorker
        WHERE availability = 1
          AND status = 'approved'
          AND ST_Distance_Sphere(match_anchor, ST_GeomFromText(%s, 4326)) <= service_radius_m
        """,
        (wkt,),
    )
    return int(row["cnt"]) if row else 0


def _parse_skills(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _format_time_field(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def business_json(row: dict) -> dict:
    return {
        "businessid": row["businessid"],
        "businessName": row["name"],
        "email": row["email"],
        "address": row["address"],
        "type": row["type"],
        "status": row["status"],
        "verified": row["status"] == "approved",
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lng": float(row["lng"]) if row.get("lng") is not None else None,
    }


def ticket_title(problem_report: str) -> str:
    text = problem_report.strip()
    if len(text) <= 48:
        return text
    return text[:45].rstrip() + "..."


def format_short_date(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.date() == datetime.now().date():
        return "Today"
    return dt.strftime("%b %d")


def format_long_date(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%b %d, %Y")


def format_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%I:%M %p").lstrip("0")


def provider_name(row: dict) -> str | None:
    if not row.get("itid"):
        return None
    if row.get("worker_fname"):
        return f"{row['worker_fname']} {row['worker_lname']}"
    return None


def _business_location_fields(row: dict) -> dict:
    lat = row.get("business_lat")
    lng = row.get("business_lng")
    return {
        "businessAddress": row.get("business_address") or row.get("address"),
        "businessLat": float(lat) if lat is not None else None,
        "businessLng": float(lng) if lng is not None else None,
    }


def ticket_summary(row: dict) -> dict:
    amount = float(row["amount_charged"]) if row.get("amount_charged") is not None else None
    return {
        "id": row["ticketid"],
        "category": row["type"],
        "severity": row["severity"],
        "status": row["status"],
        "title": ticket_title(row["problemReport"]),
        "description": row["problemReport"],
        "date": format_short_date(row.get("created_at")),
        "dateLong": format_long_date(row.get("created_at")),
        "amount": amount,
        "provider": provider_name(row),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def provider_detail(row: dict) -> dict | None:
    if not row.get("itid"):
        return None
    fname = row.get("worker_fname") or ""
    lname = row.get("worker_lname") or ""
    initials = f"{fname[:1]}{lname[:1]}".upper() if fname and lname else "??"
    return {
        "name": f"{fname} {lname}".strip(),
        "initials": initials,
        "rating": 4.9,
        "jobs": 0,
        "eta": "12 min",
        "phone": None,
        "vouchedBy": row.get("vouched_by_name"),
        "vouchedRelationship": row.get("vouched_by_relationship"),
    }


def build_timeline(row: dict) -> list[dict]:
    status = row["status"]
    steps = [
        ("Request sent", row.get("created_at")),
        ("Tech assigned", row.get("claimed_at")),
        ("En route", row.get("claimed_at") if status in {"en_route", "on_site", "complete", "confirmed"} else None),
        ("On site", row.get("arrival_time")),
        ("Complete", row.get("completion_time")),
    ]
    status_order = ["open", "claimed", "en_route", "on_site", "complete", "confirmed"]
    current_idx = status_order.index(status) if status in status_order else 0

    timeline = []
    for idx, (label, ts) in enumerate(steps):
        done = idx < current_idx
        if status == "open" and idx == 0:
            done = True
        if status == "claimed" and idx <= 1:
            done = True
        active = (
            (status == "en_route" and idx == 2)
            or (status == "on_site" and idx == 3)
            or (status == "complete" and idx == 4)
        )
        timeline.append(
            {
                "label": label,
                "time": format_time(ts),
                "done": done or active,
                "active": active,
            }
        )
    return timeline


def photo_json(row: dict) -> dict:
    return {
        "id": row["photoid"],
        "ticketid": row["ticketid"],
        "upload_type": row["upload_type"],
        "miniokey": row["miniokey"],
        "url": minio.presigned_url(row["miniokey"]),
        "upload_time": row["upload_time"].isoformat() if row.get("upload_time") else None,
    }


def ticket_detail(row: dict, photos: list[dict]) -> dict:
    detail = ticket_summary(row)
    detail.update(
        {
            "completionReport": row.get("completionReport"),
            "amount_charged": float(row["amount_charged"]) if row.get("amount_charged") is not None else None,
            "business_confirmed": row["business_confirmed"].isoformat() if row.get("business_confirmed") else None,
            "business_rating": row.get("business_rating"),
            "provider_rating": row.get("provider_rating"),
            "claimed_at": row["claimed_at"].isoformat() if row.get("claimed_at") else None,
            "arrival_time": row["arrival_time"].isoformat() if row.get("arrival_time") else None,
            "completion_time": row["completion_time"].isoformat() if row.get("completion_time") else None,
            "cancelReason": row.get("cancelReason"),
            "timeline": build_timeline(row),
            "photos": [photo_json(p) for p in photos],
            "provider": provider_detail(row),
            **_business_location_fields(row),
        }
    )
    return detail


def provider_ticket_detail(row: dict, photos: list[dict]) -> dict:
    detail = ticket_detail(row, photos)
    detail.update(
        {
            "businessName": row.get("business_name"),
            "businessAddress": row.get("business_address"),
            "businessEmail": row.get("business_email"),
            **_business_location_fields(row),
        }
    )
    return detail


def message_json(row: dict) -> dict:
    return {
        "id": row["messageid"],
        "ticketid": row["ticketid"],
        "sendertype": row["sendertype"],
        "content": row["content"],
        "send_time": row["send_time"].isoformat() if row.get("send_time") else None,
        "read_time": row["read_time"].isoformat() if row.get("read_time") else None,
    }


@business_read_bp.get("/me")
@business_required
def me():
    return jsonify(business_json(g.business)), 200


@business_read_bp.get("/providers/available/count")
@business_required
def business_available_provider_count():
    """Count nearby techs using the business address on file — not the caller's device GPS."""
    lat = g.business.get("lat")
    lng = g.business.get("lng")
    if lat is None or lng is None:
        return jsonify({"error": "Business location is not set. Contact support to update your address."}), 400

    count = count_available_providers(float(lat), float(lng))
    if count == 1:
        message = "1 technician available near your business"
    elif count:
        message = f"{count} technicians available near your business"
    else:
        message = "No technicians available near your business right now"
    return jsonify({"count": count, "message": message}), 200


@ticket_read_bp.get("/mine")
@business_required
def list_mine():
    rows = list_tickets_for_business(g.business["businessid"])
    summaries = [ticket_summary(r) for r in rows]
    active = next((s for s in summaries if s["status"] in IN_PROGRESS_STATUSES), None)
    close_out = next((s for s in summaries if s["status"] == "complete"), None)
    skip_ids = {s["id"] for s in (active, close_out) if s}
    recent = [s for s in summaries if s["id"] not in skip_ids][:5]
    past = [s for s in summaries if s["status"] == "confirmed"]

    return jsonify(
        {
            "tickets": summaries,
            "activeTicket": active,
            "closeOutTicket": close_out,
            "recentTickets": recent,
            "pastTickets": past,
        }
    ), 200


@ticket_read_bp.get("/<int:ticket_id>")
@business_or_provider_required
def get_ticket(ticket_id: int):
    photos = fetch_ticket_photos(ticket_id)
    if g.auth_role == "business":
        ticket = fetch_owned_ticket_row(ticket_id, g.business["businessid"])
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404
        return jsonify(ticket_detail(ticket, photos)), 200

    import techRead

    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is not None and lng is not None:
        wkt = f"POINT({lng} {lat})"
        ticket = techRead.get_provider_viewable_ticket(ticket_id, g.provider["itid"], wkt)
    else:
        ticket = get_provider_viewable_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    return jsonify(provider_ticket_detail(ticket, photos)), 200


@message_read_bp.get("/tickets/<int:ticket_id>/messages")
@business_or_provider_required
def list_messages(ticket_id: int):
    from auth import get_provider_assigned_ticket

    if g.auth_role == "business":
        ticket = fetch_owned_ticket_row(ticket_id, g.business["businessid"])
    else:
        ticket = get_provider_assigned_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    rows = fetch_messages_for_ticket(ticket_id)
    return jsonify({"messages": [message_json(r) for r in rows]}), 200


@providers_count_bp.get("/available/count")
def available_count():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng query parameters are required"}), 400

    count = count_available_providers(lat, lng)
    if count == 1:
        message = "1 technician available near you"
    elif count:
        message = f"{count} technicians available near you"
    else:
        message = "No technicians available nearby right now"
    return jsonify({"count": count, "message": message}), 200
