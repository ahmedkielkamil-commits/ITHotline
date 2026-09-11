import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS

import adminRead
import adminWrite
from adminWrite import AdminWriteError
from auth import admin_auth_bp, admin_required, auth_bp, auth_session_bp, init_auth, provider_auth_bp
from businesRead import business_read_bp, message_read_bp, providers_count_bp, ticket_read_bp
from businessWrite import business_write_bp, message_write_bp, photo_write_bp, ticket_write_bp
from techRead import provider_read_bp, provider_ticket_read_bp
from techWrite import provider_ticket_write_bp, provider_write_bp
from twilio import twilio_bp


def _admin_error_response(exc: AdminWriteError):
    status = 404 if exc.code == "not_found" else 400
    return jsonify({"error": str(exc)}), status


def register_admin_routes(app: Flask) -> None:
    @app.get("/admin/users")
    @admin_required
    def admin_list_users():
        try:
            result = adminRead.list_users(
                status=request.args.get("status"),
                role=request.args.get("role"),
                search=request.args.get("search") or request.args.get("q"),
                limit=request.args.get("limit", type=int),
                offset=request.args.get("offset", type=int),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result), 200

    @app.get("/admin/users/<user_ref>")
    @admin_required
    def admin_get_user(user_ref: str):
        user = adminRead.get_user_detail(user_ref)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user), 200

    @app.patch("/admin/users/<user_ref>/status")
    @admin_required
    def admin_update_user_status(user_ref: str):
        data = request.get_json(silent=True) or {}
        status = (data.get("status") or "").strip().lower()
        if not status:
            return jsonify({"error": "status is required"}), 400
        try:
            user = adminWrite.set_user_status(user_ref, status)
        except AdminWriteError as exc:
            return _admin_error_response(exc)
        return jsonify(user), 200

    @app.get("/admin/businesses/pending")
    @admin_required
    def admin_list_pending_businesses():
        result = adminRead.list_pending_businesses(
            limit=request.args.get("limit", type=int),
            offset=request.args.get("offset", type=int),
        )
        return jsonify(result), 200

    @app.get("/admin/businesses/<int:business_id>")
    @admin_required
    def admin_get_business(business_id: int):
        business = adminRead.get_business_detail(business_id)
        if not business:
            return jsonify({"error": "Business not found"}), 404
        return jsonify(business), 200

    @app.post("/admin/businesses/<int:business_id>/approve")
    @admin_required
    def admin_approve_business(business_id: int):
        try:
            business = adminWrite.approve_business(business_id)
        except AdminWriteError as exc:
            return _admin_error_response(exc)
        return jsonify(business), 200

    @app.post("/admin/businesses/<int:business_id>/reject")
    @admin_required
    def admin_reject_business(business_id: int):
        data = request.get_json(silent=True) or {}
        reason = (data.get("reason") or data.get("rejectReason") or "").strip() or None
        try:
            business = adminWrite.reject_business(business_id, reason)
        except AdminWriteError as exc:
            return _admin_error_response(exc)
        return jsonify(business), 200

    @app.get("/admin/providers/pending")
    @admin_required
    def admin_list_pending_providers():
        result = adminRead.list_pending_providers(
            limit=request.args.get("limit", type=int),
            offset=request.args.get("offset", type=int),
        )
        return jsonify(result), 200

    @app.get("/admin/providers/<int:provider_id>")
    @admin_required
    def admin_get_provider(provider_id: int):
        provider = adminRead.get_provider_detail(provider_id)
        if not provider:
            return jsonify({"error": "Provider not found"}), 404
        return jsonify(provider), 200

    @app.post("/admin/providers/<int:provider_id>/approve")
    @admin_required
    def admin_approve_provider(provider_id: int):
        try:
            provider = adminWrite.approve_provider(provider_id)
        except AdminWriteError as exc:
            return _admin_error_response(exc)
        return jsonify(provider), 200

    @app.post("/admin/providers/<int:provider_id>/reject")
    @admin_required
    def admin_reject_provider(provider_id: int):
        data = request.get_json(silent=True) or {}
        reason = (data.get("reason") or data.get("rejectReason") or "").strip() or None
        try:
            provider = adminWrite.reject_provider(provider_id, reason)
        except AdminWriteError as exc:
            return _admin_error_response(exc)
        return jsonify(provider), 200


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

    init_auth(
        secret=os.environ.get("JWT_SECRET", "jwt-dev-change-me"),
        expire_hours=int(os.environ.get("JWT_EXPIRE_HOURS", "168")),
    )

    CORS(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(auth_bp)
    app.register_blueprint(auth_session_bp)
    app.register_blueprint(provider_auth_bp)
    app.register_blueprint(admin_auth_bp)
    app.register_blueprint(business_read_bp)
    app.register_blueprint(business_write_bp)
    app.register_blueprint(providers_count_bp)
    app.register_blueprint(ticket_read_bp)
    app.register_blueprint(ticket_write_bp)
    app.register_blueprint(message_read_bp)
    app.register_blueprint(message_write_bp)
    app.register_blueprint(photo_write_bp)
    app.register_blueprint(provider_read_bp)
    app.register_blueprint(provider_write_bp)
    app.register_blueprint(provider_ticket_read_bp)
    app.register_blueprint(provider_ticket_write_bp)
    app.register_blueprint(twilio_bp)

    register_admin_routes(app)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)
