import functools
import json
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, g, jsonify, request

JWT_SECRET = None
JWT_EXPIRE_HOURS = 168

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT / password helpers
# ---------------------------------------------------------------------------


def init_auth(secret: str, expire_hours: int = 168) -> None:
    global JWT_SECRET, JWT_EXPIRE_HOURS
    JWT_SECRET = secret
    JWT_EXPIRE_HOURS = expire_hours


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(business_id: int) -> str:
    payload = {
        "sub": str(business_id),
        "role": "business",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_provider_token(itid: int) -> str:
    payload = {
        "sub": str(itid),
        "role": "provider",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_admin_token(admin_id: int) -> str:
    payload = {
        "sub": str(admin_id),
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_bearer_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "Authentication required"}), 401)
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)
    return payload, None


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------


def business_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        payload, err = _decode_bearer_token()
        if err:
            return err
        if payload.get("role") != "business":
            return jsonify({"error": "Invalid token role"}), 401

        import businesRead

        business = businesRead.fetch_business_by_id(int(payload["sub"]))
        if not business:
            return jsonify({"error": "Business not found"}), 401
        g.business = business
        g.auth_role = "business"
        return view(*args, **kwargs)

    return wrapped


def provider_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        payload, err = _decode_bearer_token()
        if err:
            return err
        if payload.get("role") != "provider":
            return jsonify({"error": "Invalid token role"}), 401

        import techRead

        provider = techRead.fetch_provider_by_id(int(payload["sub"]))
        if not provider:
            return jsonify({"error": "Provider not found"}), 401
        g.provider = provider
        g.auth_role = "provider"
        return view(*args, **kwargs)

    return wrapped


def business_or_provider_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        payload, err = _decode_bearer_token()
        if err:
            return err
        role = payload.get("role")
        if role == "business":
            import businesRead

            business = businesRead.fetch_business_by_id(int(payload["sub"]))
            if not business:
                return jsonify({"error": "Business not found"}), 401
            g.business = business
            g.auth_role = "business"
            return view(*args, **kwargs)
        if role == "provider":
            import techRead

            provider = techRead.fetch_provider_by_id(int(payload["sub"]))
            if not provider:
                return jsonify({"error": "Provider not found"}), 401
            g.provider = provider
            g.auth_role = "provider"
            return view(*args, **kwargs)
        return jsonify({"error": "Invalid token role"}), 401

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        payload, err = _decode_bearer_token()
        if err:
            return err
        if payload.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        import adminRead

        admin = adminRead.fetch_admin_by_id(int(payload["sub"]))
        if not admin:
            return jsonify({"error": "Admin not found"}), 401
        g.admin = admin
        g.auth_role = "admin"
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Ticket access helpers (delegate to read modules)
# ---------------------------------------------------------------------------


def get_owned_ticket(ticket_id: int):
    import businesRead

    return businesRead.fetch_owned_ticket_row(ticket_id, g.business["businessid"])


def get_provider_assigned_ticket(ticket_id: int):
    import techRead

    return techRead.get_provider_assigned_ticket(ticket_id, g.provider["itid"])


def get_provider_viewable_ticket(ticket_id: int):
    import techRead

    return techRead.get_provider_viewable_ticket(ticket_id, g.provider["itid"])


# ---------------------------------------------------------------------------
# Business auth routes — /auth/business/*
# ---------------------------------------------------------------------------

auth_bp = Blueprint("auth", __name__, url_prefix="/auth/business")

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


@auth_bp.post("/register")
def business_register():
    import businesRead
    import businessWrite

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    address = (data.get("address") or "").strip()
    biz_type = data.get("type") or ""
    lat = data.get("lat")
    lng = data.get("lng")

    if not all([name, email, password, address, biz_type]):
        return jsonify({"error": "name, email, password, address, and type are required"}), 400
    if biz_type not in VALID_BUSINESS_TYPES:
        return jsonify({"error": "Invalid business type"}), 400

    lat_f = None
    lng_f = None
    if lat is not None and lng is not None:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            return jsonify({"error": "lat and lng must be numbers"}), 400
    else:
        # Placeholder until admin geocodes the saved address (location column is NOT NULL).
        lat_f, lng_f = 33.753, -84.39

    if businesRead.fetch_business_id_by_email(email):
        return jsonify({"error": "Email already registered"}), 400

    wkt = f"POINT({lng_f} {lat_f})"
    business_id = businessWrite.insert_business(
        name, hash_password(password), address, email, biz_type, wkt
    )
    business = businesRead.fetch_business_by_id(business_id)
    token = create_token(business_id)
    return jsonify({"token": token, "business": businesRead.business_json(business)}), 201


@auth_bp.post("/login")
def business_login():
    import businesRead

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if password.startswith(("$2a$", "$2b$", "$2y$")):
        return jsonify(
            {"error": "Enter your plain password, not the bcrypt hash stored in the database"}
        ), 400

    business = businesRead.fetch_business_by_email(email, include_password=True)
    if not business or not verify_password(password, business["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    business.pop("password", None)
    token = create_token(business["businessid"])
    return jsonify({"token": token, "business": businesRead.business_json(business)}), 200


# ---------------------------------------------------------------------------
# Provider auth routes — /auth/provider/*
# ---------------------------------------------------------------------------

provider_auth_bp = Blueprint("provider_auth", __name__, url_prefix="/auth/provider")

VALID_SKILLS = {"pos", "network", "cameras", "equipment", "other"}


def _normalize_skills(raw) -> list[str] | None:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return None
    skills = []
    for item in raw:
        if not isinstance(item, str) or item not in VALID_SKILLS:
            return None
        skills.append(item)
    return skills


@provider_auth_bp.post("/register")
def provider_register():
    import techRead
    import techWrite

    data = request.get_json(silent=True) or {}
    fname = (data.get("fname") or data.get("firstName") or "").strip()
    lname = (data.get("lname") or data.get("lastName") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    phone = (data.get("phone") or "").strip() or None
    lat = data.get("lat")
    lng = data.get("lng")
    skills = _normalize_skills(data.get("skills"))
    vouched_by_name = (data.get("vouched_by_name") or data.get("vouchedBy") or "").strip() or None
    vouched_by_relationship = (
        (data.get("vouched_by_relationship") or data.get("vouchedRelationship") or "").strip() or None
    )

    if not all([fname, lname, email, password]):
        return jsonify({"error": "fname, lname, email, and password are required"}), 400
    if skills is None:
        return jsonify({"error": "skills must be an array of valid categories"}), 400
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be numbers"}), 400

    if techRead.fetch_provider_id_by_email(email):
        return jsonify({"error": "Email already registered"}), 400
    if phone and techRead.fetch_provider_id_by_phone(phone):
        return jsonify({"error": "Phone already registered"}), 400

    wkt = f"POINT({lng_f} {lat_f})"
    itid = techWrite.insert_provider(
        fname,
        lname,
        email,
        phone,
        hash_password(password),
        json.dumps(skills),
        vouched_by_name,
        vouched_by_relationship,
        wkt,
    )

    provider = techRead.fetch_provider_by_id(itid)
    token = create_provider_token(itid)
    return jsonify({"token": token, "provider": techRead.provider_json(provider)}), 201


@provider_auth_bp.post("/login")
def provider_login():
    import techRead

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    provider = techRead.fetch_provider_by_email(email, include_password=True)
    if not provider or not verify_password(password, provider["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    provider.pop("password", None)
    token = create_provider_token(provider["itid"])
    return jsonify({"token": token, "provider": techRead.provider_json(provider)}), 200


# ---------------------------------------------------------------------------
# Session route — /auth/me
# ---------------------------------------------------------------------------

auth_session_bp = Blueprint("auth_session", __name__, url_prefix="/auth")


@auth_session_bp.get("/me")
@business_or_provider_required
def auth_me():
    if g.auth_role == "business":
        import businesRead

        return jsonify({"role": "business", "user": businesRead.business_json(g.business)}), 200
    import techRead

    return jsonify({"role": "provider", "user": techRead.provider_json(g.provider)}), 200


# ---------------------------------------------------------------------------
# Admin auth routes — /auth/admin/*
# ---------------------------------------------------------------------------

admin_auth_bp = Blueprint("admin_auth", __name__, url_prefix="/auth/admin")


@admin_auth_bp.post("/login")
def admin_login():
    import adminRead

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    admin = adminRead.fetch_admin_by_email(email, include_password=True)
    if not admin or not verify_password(password, admin["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    admin.pop("password", None)
    token = create_admin_token(admin["adminid"])
    return jsonify({"token": token, "admin": adminRead.admin_public_json(admin)}), 200
