#!/usr/bin/env python3
"""Copy the public HTTPS URL from ngrok (port 5001) into app .env files."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NGROK_API = "http://127.0.0.1:4040/api/tunnels"
API_PORT = 5001

ENV_TARGETS: list[tuple[Path, dict[str, str]]] = [
    (
        ROOT / "businessSide" / ".env",
        {
            "EXPO_PUBLIC_NGROK_API_URL": "",
            "EXPO_PUBLIC_USE_NGROK": "true",
        },
    ),
    (
        ROOT / "techSide" / ".env",
        {
            "EXPO_PUBLIC_NGROK_API_URL": "",
            "EXPO_PUBLIC_USE_NGROK": "true",
        },
    ),
    (
        ROOT / "admin-panel" / ".env",
        {
            "VITE_NGROK_API_URL": "",
        },
    ),
]


def fetch_tunnels() -> list[dict]:
    with urllib.request.urlopen(NGROK_API, timeout=3) as resp:
        payload = json.load(resp)
    return payload.get("tunnels", [])


def tunnel_for_port(tunnels: list[dict], port: int) -> str | None:
    needle = f":{port}"
    for tunnel in tunnels:
        addr = str(tunnel.get("config", {}).get("addr", ""))
        if needle in addr or addr.endswith(str(port)):
            public = tunnel.get("public_url", "")
            if public.startswith("https://"):
                return public.rstrip("/")
    for tunnel in tunnels:
        public = tunnel.get("public_url", "")
        if public.startswith("https://"):
            return public.rstrip("/")
    return None


def upsert_env_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def patch_env(path: Path, values: dict[str, str]) -> None:
    text = path.read_text() if path.exists() else ""
    for key, value in values.items():
        if value == "" and key not in values:
            continue
        text = upsert_env_value(text, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main() -> int:
    try:
        tunnels = fetch_tunnels()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(
            "Could not reach ngrok at http://127.0.0.1:4040.\n"
            "Start a tunnel first:\n"
            f"  ngrok http {API_PORT}",
            file=sys.stderr,
        )
        print(f"({exc})", file=sys.stderr)
        return 1

    url = tunnel_for_port(tunnels, API_PORT)
    if not url:
        print(
            f"No HTTPS ngrok tunnel found for port {API_PORT}.",
            file=sys.stderr,
        )
        return 1

    for path, keys in ENV_TARGETS:
        values = {k: (url if v == "" else v) for k, v in keys.items()}
        patch_env(path, values)
        print(f"Updated {path.relative_to(ROOT)}")

    print(f"\nNgrok API URL: {url}")
    print("\nRemote testers:")
    print("  1. cd businessSide (or techSide) && npm run start:remote")
    print("  2. Share the Expo QR / link from the terminal")
    print("  3. Restart Expo if it was already running (-c clears cache)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
