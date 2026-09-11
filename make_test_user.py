#!/usr/bin/env python3
"""Create approved test business + provider with a known password."""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import db
from auth import hash_password

PASSWORD = "password123"
BUSINESS_EMAIL = "test.business@ithotline.local"
PROVIDER_EMAIL = "test.provider@ithotline.local"
DEFAULT_WKT = "POINT(-84.4135506 33.7515371)"
BUSINESS_ADDRESS = "111 James P Brawley Dr SW, Atlanta, GA 30314"


def upsert_business() -> int:
    row = db.fetch_one("SELECT businessid FROM businesses WHERE email = %s", (BUSINESS_EMAIL,))
    hashed = hash_password(PASSWORD)
    if row:
        db.execute(
            """
            UPDATE businesses
            SET name = %s, password = %s, address = %s, type = 'market',
                status = 'approved', location = ST_GeomFromText(%s, 4326)
            WHERE businessid = %s
            """,
            (
                "Test Corner Market",
                hashed,
                BUSINESS_ADDRESS,
                DEFAULT_WKT,
                row["businessid"],
            ),
        )
        return int(row["businessid"])

    return db.last_insert_id(
        """
        INSERT INTO businesses (name, password, address, email, type, status, location)
        VALUES (%s, %s, %s, %s, 'market', 'approved', ST_GeomFromText(%s, 4326))
        """,
        (
            "Test Corner Market",
            hashed,
            BUSINESS_ADDRESS,
            BUSINESS_EMAIL,
            DEFAULT_WKT,
        ),
    )


def upsert_provider() -> int:
    row = db.fetch_one("SELECT itid FROM ITWorker WHERE email = %s", (PROVIDER_EMAIL,))
    hashed = hash_password(PASSWORD)
    skills = json.dumps(["pos", "network", "equipment"])
    if row:
        db.execute(
            """
            UPDATE ITWorker
            SET fname = %s, lname = %s, password = %s, phone = %s,
                status = 'approved', availability = TRUE, skills = %s,
                vouched_by_name = %s, vouched_by_relationship = %s,
                match_anchor = ST_GeomFromText(%s, 4326)
            WHERE itid = %s
            """,
            (
                "Test",
                "Tech",
                hashed,
                "+14045559999",
                skills,
                "Rev. James Holloway",
                "Community referral",
                DEFAULT_WKT,
                row["itid"],
            ),
        )
        return int(row["itid"])

    return db.last_insert_id(
        """
        INSERT INTO ITWorker (
            fname, lname, email, phone, password, status, tier, availability,
            service_radius_m, skills, vouched_by_name, vouched_by_relationship, match_anchor
        )
        VALUES (%s, %s, %s, %s, %s, 'approved', 'practitioner', TRUE, 10000, %s, %s, %s,
                ST_GeomFromText(%s, 4326))
        """,
        (
            "Test",
            "Tech",
            PROVIDER_EMAIL,
            "+14045559999",
            hashed,
            skills,
            "Rev. James Holloway",
            "Community referral",
            DEFAULT_WKT,
        ),
    )


def main() -> int:
    try:
        business_id = upsert_business()
        provider_id = upsert_provider()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Test users ready (password for both: password123)")
    print(f"  Business  id={business_id}  email={BUSINESS_EMAIL}  status=approved")
    print(f"  Provider  id={provider_id}  email={PROVIDER_EMAIL}  status=approved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
