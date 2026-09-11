"""Admin feature — read-only database operations (no Flask imports)."""

import json
from typing import Any

import db

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

VALID_USER_STATUSES = {"pending", "approved", "suspended"}
VALID_USER_ROLES = {"business", "provider"}


def normalize_limit(limit: int | None) -> int:
    if limit is None or limit < 1:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def normalize_offset(offset: int | None) -> int:
    if offset is None or offset < 0:
        return 0
    return offset


def paginate(items: list[Any], total: int, limit: int, offset: int) -> dict:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def fetch_admin_by_id(admin_id: int) -> dict | None:
    return db.fetch_one(
        """
        SELECT adminid, fname, lname, email
        FROM admins
        WHERE adminid = %s
        """,
        (admin_id,),
    )


def fetch_admin_by_email(email: str, *, include_password: bool = False) -> dict | None:
    cols = "adminid, fname, lname, email" + (", password" if include_password else "")
    return db.fetch_one(f"SELECT {cols} FROM admins WHERE email = %s", (email,))


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


def _business_summary(row: dict) -> dict:
    return {
        "id": f"business-{row['businessid']}",
        "type": "business",
        "name": row["name"],
        "email": row["email"],
        "status": row["status"],
        "phone": None,
        "region": row.get("address"),
        "subtype": row.get("type"),
    }


def _provider_summary(row: dict) -> dict:
    return {
        "id": f"provider-{row['itid']}",
        "type": "provider",
        "name": f"{row['fname']} {row['lname']}".strip(),
        "email": row["email"],
        "status": row["status"],
        "phone": row.get("phone"),
        "region": None,
        "subtype": row.get("tier"),
    }


def _business_detail(row: dict) -> dict:
    lat = row.get("lat")
    lng = row.get("lng")
    return {
        "id": f"business-{row['businessid']}",
        "type": "business",
        "businessid": row["businessid"],
        "name": row["name"],
        "email": row["email"],
        "address": row["address"],
        "category": row["type"],
        "status": row["status"],
        "lat": float(lat) if lat is not None else None,
        "lng": float(lng) if lng is not None else None,
    }


def _provider_detail(row: dict) -> dict:
    lat = row.get("lat")
    lng = row.get("lng")
    return {
        "id": f"provider-{row['itid']}",
        "type": "provider",
        "itid": row["itid"],
        "firstName": row["fname"],
        "lastName": row["lname"],
        "name": f"{row['fname']} {row['lname']}".strip(),
        "email": row["email"],
        "phone": row.get("phone"),
        "status": row["status"],
        "tier": row["tier"],
        "availability": bool(row.get("availability")),
        "service_radius_m": row.get("service_radius_m"),
        "skills": _parse_skills(row.get("skills")),
        "vouchedBy": row.get("vouched_by_name"),
        "vouchedRelationship": row.get("vouched_by_relationship"),
        "lat": float(lat) if lat is not None else None,
        "lng": float(lng) if lng is not None else None,
    }


def _pending_business_item(row: dict) -> dict:
    detail = _business_detail(row)
    detail["owner"] = row["name"]
    detail["contact"] = row["email"]
    detail["daysWaiting"] = None
    return detail


def _pending_provider_item(row: dict) -> dict:
    detail = _provider_detail(row)
    detail["daysWaiting"] = None
    return detail


def parse_user_ref(user_ref: str) -> tuple[str, int] | None:
    if not user_ref or "-" not in user_ref:
        return None
    user_type, raw_id = user_ref.split("-", 1)
    if user_type not in VALID_USER_ROLES:
        return None
    try:
        return user_type, int(raw_id)
    except ValueError:
        return None


def list_users(
    *,
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    limit = normalize_limit(limit)
    offset = normalize_offset(offset)
    if status and status not in VALID_USER_STATUSES:
        raise ValueError(f"Invalid status filter: {status}")
    if role and role not in VALID_USER_ROLES:
        raise ValueError(f"Invalid role filter: {role}")

    search_term = f"%{search.strip()}%" if search and search.strip() else None
    union_parts: list[str] = []
    params: list[Any] = []

    if role in (None, "business"):
        business_sql = """
            SELECT 'business' AS user_type, businessid AS raw_id, name, email, status,
                   type AS subtype, address AS region_hint, NULL AS phone
            FROM businesses
            WHERE 1=1
        """
        if status:
            business_sql += " AND status = %s"
            params.append(status)
        if search_term:
            business_sql += " AND (name LIKE %s OR email LIKE %s)"
            params.extend([search_term, search_term])
        union_parts.append(business_sql)

    if role in (None, "provider"):
        provider_sql = """
            SELECT 'provider' AS user_type, itid AS raw_id,
                   CONCAT(fname, ' ', lname) AS name, email, status,
                   tier AS subtype, NULL AS region_hint, phone
            FROM ITWorker
            WHERE 1=1
        """
        if status:
            provider_sql += " AND status = %s"
            params.append(status)
        if search_term:
            provider_sql += " AND (CONCAT(fname, ' ', lname) LIKE %s OR email LIKE %s OR phone LIKE %s)"
            params.extend([search_term, search_term, search_term])
        union_parts.append(provider_sql)

    if not union_parts:
        return paginate([], 0, limit, offset)

    union_sql = " UNION ALL ".join(union_parts)
    count_row = db.fetch_one(f"SELECT COUNT(*) AS cnt FROM ({union_sql}) AS combined", tuple(params))
    total = int(count_row["cnt"]) if count_row else 0

    rows = db.fetch_all(
        f"""
        SELECT user_type, raw_id, name, email, status, subtype, region_hint, phone
        FROM ({union_sql}) AS combined
        ORDER BY name ASC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )

    items = []
    for row in rows:
        if row["user_type"] == "business":
            items.append(
                _business_summary(
                    {
                        "businessid": row["raw_id"],
                        "name": row["name"],
                        "email": row["email"],
                        "status": row["status"],
                        "type": row["subtype"],
                        "address": row["region_hint"],
                    }
                )
            )
        else:
            parts = row["name"].rsplit(" ", 1)
            fname = parts[0]
            lname = parts[1] if len(parts) > 1 else ""
            items.append(
                _provider_summary(
                    {
                        "itid": row["raw_id"],
                        "fname": fname,
                        "lname": lname,
                        "email": row["email"],
                        "status": row["status"],
                        "phone": row["phone"],
                        "tier": row["subtype"],
                    }
                )
            )

    return paginate(items, total, limit, offset)


def get_user_detail(user_ref: str) -> dict | None:
    parsed = parse_user_ref(user_ref)
    if not parsed:
        return None
    user_type, raw_id = parsed
    if user_type == "business":
        return get_business_detail(raw_id)
    return get_provider_detail(raw_id)


def list_pending_businesses(*, limit: int | None = None, offset: int | None = None) -> dict:
    limit = normalize_limit(limit)
    offset = normalize_offset(offset)

    count_row = db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM businesses WHERE status = 'pending'",
    )
    total = int(count_row["cnt"]) if count_row else 0

    rows = db.fetch_all(
        """
        SELECT businessid, name, email, address, type, status,
               ST_Y(location) AS lat, ST_X(location) AS lng
        FROM businesses
        WHERE status = 'pending'
        ORDER BY name ASC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
    return paginate([_pending_business_item(row) for row in rows], total, limit, offset)


def get_business_detail(business_id: int) -> dict | None:
    row = db.fetch_one(
        """
        SELECT businessid, name, email, address, type, status,
               ST_Y(location) AS lat, ST_X(location) AS lng
        FROM businesses
        WHERE businessid = %s
        """,
        (business_id,),
    )
    if not row:
        return None
    return _business_detail(row)


def list_pending_providers(*, limit: int | None = None, offset: int | None = None) -> dict:
    limit = normalize_limit(limit)
    offset = normalize_offset(offset)

    count_row = db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM ITWorker WHERE status = 'pending'",
    )
    total = int(count_row["cnt"]) if count_row else 0

    rows = db.fetch_all(
        """
        SELECT itid, fname, lname, email, phone, status, tier, availability,
               service_radius_m, skills, vouched_by_name, vouched_by_relationship,
               ST_Y(match_anchor) AS lat, ST_X(match_anchor) AS lng
        FROM ITWorker
        WHERE status = 'pending'
        ORDER BY fname ASC, lname ASC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
    return paginate([_pending_provider_item(row) for row in rows], total, limit, offset)


def get_provider_detail(provider_id: int) -> dict | None:
    row = db.fetch_one(
        """
        SELECT itid, fname, lname, email, phone, status, tier, availability,
               service_radius_m, skills, vouched_by_name, vouched_by_relationship,
               ST_Y(match_anchor) AS lat, ST_X(match_anchor) AS lng
        FROM ITWorker
        WHERE itid = %s
        """,
        (provider_id,),
    )
    if not row:
        return None
    return _provider_detail(row)


def admin_public_json(row: dict) -> dict:
    return {
        "adminid": row["adminid"],
        "firstName": row["fname"],
        "lastName": row["lname"],
        "email": row["email"],
    }
