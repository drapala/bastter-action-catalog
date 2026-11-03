"""Opens Chrome on the Bastter login page and stores the session cookies in the macOS keychain.

Run: .venv/bin/python tools/login.py
Log in in the window (email and password, or Google). The script waits until /bs2/ opens without
a redirect, saves the bastter.com cookies to the keychain (service bastter-session), prints when the session
cookie expires, and closes Chrome. Chrome keeps a temporary profile while the window is open. The cookies never
go to a file in this repository. The keychain call receives them as an argument, which other processes of the
same macOS user can see while it runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

KEYCHAIN_SERVICE = "bastter-session"
TIMEOUT_S = int(os.environ.get("BASTTER_LOGIN_TIMEOUT", "600"))


def store(jar: dict[str, str]) -> None:
    subprocess.run(
        [
            "security",
            "delete-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            "bastter",
        ],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            "bastter",
            "-w",
            json.dumps(jar),
        ],
        check=True,
    )


def main() -> int:
    with sync_playwright() as p:
        chrome = p.chromium.launch(channel="chrome", headless=False)
        context = chrome.new_context()
        page = context.new_page()
        page.goto("https://bastter.com/login?ReturnUrl=%2Fbs2%2F")
        deadline = time.time() + TIMEOUT_S
        while time.time() < deadline:
            response = page.request.get("https://bastter.com/bs2/", max_redirects=0)
            if response.status == 200:
                cookies = context.cookies("https://bastter.com")
                store({c["name"]: c["value"] for c in cookies})
                print(
                    f"stored {len(cookies)} cookies in the keychain (service {KEYCHAIN_SERVICE})"
                )
                expiry = next(
                    (
                        c["expires"]
                        for c in cookies
                        if c["name"] == "SessionV3" and c["expires"] > 0
                    ),
                    None,
                )
                if expiry:
                    print(
                        "the session cookie expires on",
                        time.strftime("%Y-%m-%d", time.localtime(expiry)),
                    )
                chrome.close()
                return 0
            time.sleep(3)
        chrome.close()
    print("timed out waiting for the login", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
