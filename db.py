import os
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

def _connect():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "ithotline"),
        password=os.environ.get("DB_PASSWORD", "ithotline"),
        database=os.environ.get("DB_NAME", "ithotline"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def get_cursor():
    conn = _connect()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def execute(sql: str, params: tuple | dict | None = None) -> int:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def last_insert_id(sql: str, params: tuple | dict | None = None) -> int:
    with get_cursor() as cur:
        cur.execute(sql, params)
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        row = cur.fetchone()
        return int(row["id"])
