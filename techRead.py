"""Provider/tech-side database read operations and GET routes."""

import json

from flask import Blueprint, g, jsonify, request

import businesRead
import db
from auth import provider_required

provider_read_bp = Blueprint("provider_read", __name__, url_prefix="/provider")
provider_ticket_read_bp = Blueprint("provider_ticket_read", __name__, url_prefix="/tickets")

PROVIDER_SELECT = """
    SELECT itid, fname, lname, email, phone, status, tier, availability,
           avail_start_time, avail_end_time, service_radius_m, skills,
           vouched_by_name, vouched_by_relationship,
           ST_Y(match_anchor) AS lat, ST_X(match_anchor) AS lng
    FROM ITWorker
    WHERE itid = %s
"""

PROVIDER_LOGIN_SELECT = """
    SELECT itid, fname, lname, email, phone, password, status, tier, availability,
           avail_start_time, avail_end_time, service_radius_m, skills,
           vouched_by_name, vouched_by_relationship,
           ST_Y(match_anchor) AS lat, ST_X(match_anchor) AS lng
    FROM ITWorker WHERE email = %s
"""


def fetch_provider_by_id(itid: int) -> dict | None:
    return db.fetch_one(PROVIDER_SELECT, (itid,))


def fetch_provider_by_email(email: str, *, include_password: bool = False) -> dict | None:
    if include_password:
        return db.fetch_one(PROVIDER_LOGIN_SELECT, (email,))
    return db.fetch_one(
        """
        SELECT itid, fname, lname, email, phone, status, tier, availability,
               avail_start_time, avail_end_time, service_radius_m, skills,
               vouched_by_name, vouched_by_relationship,
               ST_Y(match_anchor) AS lat, ST_X(match_anchor) AS lng
        FROM ITWorker WHERE email = %s
        """,
        (email,),
    )


def fetch_provider_id_by_email(email: str) -> dict | None:
    return db.fetch_one("SELECT itid FROM ITWorker WHERE email = %s", (email,))


def fetch_provider_id_by_phone(phone: str, exclude_itid: int | None = None) -> dict | None:
    if exclude_itid is not None:
        return db.fetch_one(
            "SELECT itid FROM ITWorker WHERE phone = %s AND itid != %s",
            (phone, exclude_itid),
        )
    return db.fetch_one("SELECT itid FROM ITWorker WHERE phone = %s", (phone,))


def fetch_provider_for_twilio(normalized_phone: str, raw_phone: str) -> dict | None:
    return db.fetch_one(
        """
        SELECT itid, fname, status, availability, phone
        FROM ITWorker
        WHERE phone = %s OR phone = %s
        """,
        (normalized_phone, raw_phone),
    )


def list_open_tickets(itid: int, wkt: str) -> list[dict]:
    """Open tickets within service radius of the provider's current location (wkt)."""
    return db.fetch_all(
        """
        SELECT t.*,
               b.name AS business_name,
               b.address AS business_address,
               ST_Y(b.location) AS business_lat,
               ST_X(b.location) AS business_lng,
               ST_Distance_Sphere(ST_GeomFromText(%s, 4326), b.location) AS distance_m
        FROM ticket t
        JOIN businesses b ON t.businessid = b.businessid
        JOIN ITWorker w ON w.itid = %s
        WHERE t.status = 'open'
          AND t.itid IS NULL
          AND w.status = 'approved'
          AND w.availability = 1
          AND ST_Distance_Sphere(ST_GeomFromText(%s, 4326), b.location) <= w.service_radius_m
        ORDER BY distance_m ASC,
                 CASE WHEN t.severity = 'urgent' THEN 0 ELSE 1 END,
                 t.created_at ASC
        """,
        (wkt, itid, wkt),
    )


def fetch_active_ticket(itid: int) -> dict | None:
    return db.fetch_one(
        """
        SELECT t.*,
               w.fname AS worker_fname,
               w.lname AS worker_lname,
               w.vouched_by_name,
               w.vouched_by_relationship,
               b.name AS business_name,
               b.address AS business_address,
               b.email AS business_email,
               ST_Y(b.location) AS business_lat,
               ST_X(b.location) AS business_lng
        FROM ticket t
        LEFT JOIN ITWorker w ON t.itid = w.itid
        JOIN businesses b ON t.businessid = b.businessid
        WHERE t.itid = %s
          AND t.status IN ('claimed', 'en_route', 'on_site')
        ORDER BY t.claimed_at DESC
        LIMIT 1
        """,
        (itid,),
    )


def list_provider_history(itid: int) -> list[dict]:
    return db.fetch_all(
        """
        SELECT t.*,
               w.fname AS worker_fname,
               w.lname AS worker_lname,
               b.name AS business_name,
               b.address AS business_address
        FROM ticket t
        LEFT JOIN ITWorker w ON t.itid = w.itid
        JOIN businesses b ON t.businessid = b.businessid
        WHERE t.itid = %s
          AND t.status IN ('complete', 'confirmed')
        ORDER BY COALESCE(t.completion_time, t.created_at) DESC
        """,
        (itid,),
    )


def get_provider_assigned_ticket(ticket_id: int, itid: int) -> dict | None:
    return db.fetch_one(
        """
        SELECT t.*,
               w.fname AS worker_fname,
               w.lname AS worker_lname,
               w.vouched_by_name,
               w.vouched_by_relationship,
               b.name AS business_name,
               b.address AS business_address,
               b.email AS business_email,
               ST_Y(b.location) AS business_lat,
               ST_X(b.location) AS business_lng
        FROM ticket t
        LEFT JOIN ITWorker w ON t.itid = w.itid
        JOIN businesses b ON t.businessid = b.businessid
        WHERE t.ticketid = %s AND t.itid = %s
        """,
        (ticket_id, itid),
    )


def get_provider_viewable_ticket(ticket_id: int, itid: int, wkt: str | None = None) -> dict | None:
    assigned = get_provider_assigned_ticket(ticket_id, itid)
    if assigned:
        return assigned

    if wkt:
        return db.fetch_one(
            """
            SELECT t.*,
                   NULL AS worker_fname,
                   NULL AS worker_lname,
                   NULL AS vouched_by_name,
                   NULL AS vouched_by_relationship,
                   b.name AS business_name,
                   b.address AS business_address,
                   b.email AS business_email,
                   ST_Y(b.location) AS business_lat,
                   ST_X(b.location) AS business_lng
            FROM ticket t
            JOIN businesses b ON t.businessid = b.businessid
            JOIN ITWorker w ON w.itid = %s
            WHERE t.ticketid = %s
              AND t.status = 'open'
              AND t.itid IS NULL
              AND w.status = 'approved'
              AND w.availability = 1
              AND ST_Distance_Sphere(ST_GeomFromText(%s, 4326), b.location) <= w.service_radius_m
            """,
            (itid, ticket_id, wkt),
        )

    return db.fetch_one(
        """
        SELECT t.*,
               NULL AS worker_fname,
               NULL AS worker_lname,
               NULL AS vouched_by_name,
               NULL AS vouched_by_relationship,
               b.name AS business_name,
               b.address AS business_address,
               b.email AS business_email,
               ST_Y(b.location) AS business_lat,
               ST_X(b.location) AS business_lng
        FROM ticket t
        JOIN businesses b ON t.businessid = b.businessid
        JOIN ITWorker w ON w.itid = %s
        WHERE t.ticketid = %s
          AND t.status = 'open'
          AND t.itid IS NULL
          AND w.status = 'approved'
          AND w.availability = 1
          AND ST_Distance_Sphere(w.match_anchor, b.location) <= w.service_radius_m
        """,
        (itid, ticket_id),
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


def fetch_ticket_for_dispatch(ticket_id: int) -> dict | None:
    return db.fetch_one(
        """
        SELECT t.ticketid, t.type, t.severity, t.status, t.problemReport,
               b.name AS business_name, b.address AS business_address,
               ST_Y(b.location) AS biz_lat, ST_X(b.location) AS biz_lng
        FROM ticket t
        JOIN businesses b ON t.businessid = b.businessid
        WHERE t.ticketid = %s
        """,
        (ticket_id,),
    )


def list_providers_for_dispatch(wkt: str, radius_multiplier: float) -> list[dict]:
    return db.fetch_all(
        """
        SELECT w.itid, w.fname, w.phone, w.skills, w.service_radius_m,
               ST_Distance_Sphere(w.match_anchor, ST_GeomFromText(%s, 4326)) AS distance_m
        FROM ITWorker w
        WHERE w.status = 'approved'
          AND w.availability = 1
          AND w.phone IS NOT NULL
          AND TRIM(w.phone) != ''
          AND ST_Distance_Sphere(w.match_anchor, ST_GeomFromText(%s, 4326))
              <= (w.service_radius_m * %s)
        """,
        (wkt, wkt, radius_multiplier),
    )


def _format_time_field(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


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


def provider_json(row: dict) -> dict:
    return {
        "itid": row["itid"],
        "firstName": row["fname"],
        "lastName": row["lname"],
        "email": row["email"],
        "phone": row.get("phone"),
        "status": row["status"],
        "tier": row["tier"],
        "availability": bool(row.get("availability")),
        "avail_start_time": _format_time_field(row.get("avail_start_time")),
        "avail_end_time": _format_time_field(row.get("avail_end_time")),
        "service_radius_m": row.get("service_radius_m"),
        "skills": _parse_skills(row.get("skills")),
        "vouchedBy": row.get("vouched_by_name"),
        "vouchedRelationship": row.get("vouched_by_relationship"),
        "approved": row["status"] == "approved",
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lng": float(row["lng"]) if row.get("lng") is not None else None,
    }


def open_ticket_json(row: dict) -> dict:
    distance_m = float(row["distance_m"]) if row.get("distance_m") is not None else None
    summary = businesRead.ticket_summary(row)
    summary.update(
        {
            "businessName": row.get("business_name"),
            "businessArea": row.get("business_address"),
            "businessAddress": row.get("business_address"),
            "businessLat": float(row["business_lat"]) if row.get("business_lat") is not None else None,
            "businessLng": float(row["business_lng"]) if row.get("business_lng") is not None else None,
            "distance_m": distance_m,
            "distance_mi": round(distance_m / 1609.34, 2) if distance_m is not None else None,
        }
    )
    return summary


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


@provider_read_bp.get("/me")
@provider_required
def me():
    return jsonify(provider_json(g.provider)), 200


@provider_ticket_read_bp.get("/open")
@provider_required
def list_open():
    if g.provider["status"] != "approved":
        return jsonify({"error": "Provider must be approved to view open tickets"}), 403
    if not g.provider["availability"]:
        return jsonify({"error": "Turn on availability to view open tickets"}), 403

    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    if lat is None or lng is None:
        lat = float(g.provider["lat"]) if g.provider.get("lat") is not None else None
        lng = float(g.provider["lng"]) if g.provider.get("lng") is not None else None
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    wkt = f"POINT({lng} {lat})"
    import techWrite

    techWrite.update_provider_location(g.provider["itid"], wkt)
    rows = list_open_tickets(g.provider["itid"], wkt)
    filtered = [row for row in rows if _provider_skills_match(row["type"], g.provider.get("skills"))]
    return jsonify({"tickets": [open_ticket_json(r) for r in filtered]}), 200


@provider_ticket_read_bp.get("/active")
@provider_required
def get_active():
    row = fetch_active_ticket(g.provider["itid"])
    if not row:
        return jsonify({"ticket": None}), 200
    photos = fetch_ticket_photos(row["ticketid"])
    return jsonify({"ticket": businesRead.provider_ticket_detail(row, photos)}), 200


@provider_ticket_read_bp.get("/history")
@provider_required
def list_history():
    rows = list_provider_history(g.provider["itid"])
    return jsonify({"tickets": [businesRead.ticket_summary(r) for r in rows]}), 200
