"""Admin feature — write/mutation database operations (no Flask imports)."""

import adminRead
import db

VALID_ACCOUNT_STATUSES = {"pending", "approved", "suspended"}


class AdminWriteError(Exception):
    def __init__(self, message: str, *, code: str = "write_error"):
        super().__init__(message)
        self.code = code


def set_business_status(business_id: int, status: str) -> dict:
    if status not in VALID_ACCOUNT_STATUSES:
        raise AdminWriteError(f"Invalid status: {status}", code="invalid_status")

    existing = adminRead.get_business_detail(business_id)
    if not existing:
        raise AdminWriteError("Business not found", code="not_found")

    try:
        rows = db.execute(
            "UPDATE businesses SET status = %s WHERE businessid = %s",
            (status, business_id),
        )
        if rows != 1:
            raise AdminWriteError("Business not found", code="not_found")
    except AdminWriteError:
        raise
    except Exception as exc:
        raise AdminWriteError("Failed to update business status") from exc

    updated = adminRead.get_business_detail(business_id)
    if not updated:
        raise AdminWriteError("Business not found after update", code="not_found")
    return updated


def set_provider_status(provider_id: int, status: str) -> dict:
    if status not in VALID_ACCOUNT_STATUSES:
        raise AdminWriteError(f"Invalid status: {status}", code="invalid_status")

    existing = adminRead.get_provider_detail(provider_id)
    if not existing:
        raise AdminWriteError("Provider not found", code="not_found")

    try:
        rows = db.execute(
            "UPDATE ITWorker SET status = %s WHERE itid = %s",
            (status, provider_id),
        )
        if rows != 1:
            raise AdminWriteError("Provider not found", code="not_found")
    except AdminWriteError:
        raise
    except Exception as exc:
        raise AdminWriteError("Failed to update provider status") from exc

    updated = adminRead.get_provider_detail(provider_id)
    if not updated:
        raise AdminWriteError("Provider not found after update", code="not_found")
    return updated


def approve_business(business_id: int) -> dict:
    existing = adminRead.get_business_detail(business_id)
    if not existing:
        raise AdminWriteError("Business not found", code="not_found")
    if existing["status"] != "pending":
        raise AdminWriteError("Only pending businesses can be approved", code="invalid_state")
    return set_business_status(business_id, "approved")


def reject_business(business_id: int, reason: str | None = None) -> dict:
    existing = adminRead.get_business_detail(business_id)
    if not existing:
        raise AdminWriteError("Business not found", code="not_found")
    if existing["status"] != "pending":
        raise AdminWriteError("Only pending businesses can be rejected", code="invalid_state")

    updated = set_business_status(business_id, "suspended")
    if reason:
        updated["rejectReason"] = reason.strip()
    return updated


def approve_provider(provider_id: int) -> dict:
    existing = adminRead.get_provider_detail(provider_id)
    if not existing:
        raise AdminWriteError("Provider not found", code="not_found")
    if existing["status"] != "pending":
        raise AdminWriteError("Only pending providers can be approved", code="invalid_state")
    return set_provider_status(provider_id, "approved")


def reject_provider(provider_id: int, reason: str | None = None) -> dict:
    existing = adminRead.get_provider_detail(provider_id)
    if not existing:
        raise AdminWriteError("Provider not found", code="not_found")
    if existing["status"] != "pending":
        raise AdminWriteError("Only pending providers can be rejected", code="invalid_state")

    updated = set_provider_status(provider_id, "suspended")
    if reason:
        updated["rejectReason"] = reason.strip()
    return updated


def set_user_status(user_ref: str, status: str) -> dict:
    if status not in {"approved", "suspended"}:
        raise AdminWriteError("status must be approved or suspended", code="invalid_status")

    parsed = adminRead.parse_user_ref(user_ref)
    if not parsed:
        raise AdminWriteError("Invalid user id", code="invalid_id")

    user_type, raw_id = parsed
    if user_type == "business":
        return set_business_status(raw_id, status)
    return set_provider_status(raw_id, status)
