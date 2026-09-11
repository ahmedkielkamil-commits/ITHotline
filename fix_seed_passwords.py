#!/usr/bin/env python3
"""Set password123 on all seed businesses and IT workers (fixes old @pw placeholder hashes)."""

import sys

from dotenv import load_dotenv

load_dotenv()

import db
from auth import hash_password

PASSWORD = "password123"


def main() -> int:
    hashed = hash_password(PASSWORD)
    try:
        biz = db.execute("UPDATE businesses SET password = %s", (hashed,))
        workers = db.execute("UPDATE ITWorker SET password = %s", (hashed,))
        admins = db.execute("UPDATE admins SET password = %s", (hashed,))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Check DB credentials in .env and that MySQL is running.", file=sys.stderr)
        return 1

    print(f"Updated passwords to '{PASSWORD}' for all accounts:")
    print(f"  businesses: {biz} row(s)")
    print(f"  ITWorker:   {workers} row(s)")
    print(f"  admins:     {admins} row(s)")
    print("\nYou can now log in with any seed email + password123")
    print("  e.g. lakewood.market@example.com / password123")
    return 0


if __name__ == "__main__":
    sys.exit(main())
