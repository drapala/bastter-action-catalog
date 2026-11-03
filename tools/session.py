"""HTTP client for bastter.com that uses the browser session stored in the macOS keychain.

The session cookies come from a logged-in browser (service `bastter-session`, account `bastter`).
They are never written to this repository.
"""

from __future__ import annotations

import json
import subprocess

import httpx

BASE_URL = "https://bastter.com"
KEYCHAIN_SERVICE = "bastter-session"


def load_cookies() -> dict[str, str]:
    out = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            "bastter",
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"No Bastter session in the keychain (service {KEYCHAIN_SERVICE}). Log in again."
        )
    return json.loads(out.stdout)


def client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        cookies=load_cookies(),
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        follow_redirects=False,
        timeout=60,
    )


def logged_in(http: httpx.Client) -> bool:
    """A logged-out request to /bs2/ redirects to the sales page."""
    return http.get("/bs2/").status_code == 200
