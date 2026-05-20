"""Checks whether a given app version is live on its store.

Exits 0 when the version is live for users, exits 2 when it is not yet live,
and exits 1 on configuration or transport errors. Prints a single-line JSON
status to stdout so the calling workflow can log/inspect it.

iOS: queries the App Store Connect API and treats `READY_FOR_SALE` as live.
Android: queries the Google Play Developer API and treats a `production`
track release with `status == "completed"` as live.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BUNDLE_ID = "app.aptnote.mobile"


def _emit(status: dict[str, Any]) -> None:
    print(json.dumps(status, ensure_ascii=False))


def _fail(reason: str) -> "int":
    _emit({"live": False, "state": "error", "reason": reason})
    return 1


def _http_get(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# iOS — App Store Connect
# ---------------------------------------------------------------------------

def _asc_jwt(key_id: str, issuer_id: str, private_key_pem: bytes) -> str:
    try:
        import jwt  # PyJWT
    except ImportError:
        raise SystemExit(_fail("PyJWT not installed; pip install 'pyjwt[crypto]'"))
    now = int(time.time())
    return jwt.encode(
        {"iss": issuer_id, "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
        private_key_pem,
        algorithm="ES256",
        headers={"kid": key_id, "typ": "JWT"},
    )


def check_ios(version_name: str) -> int:
    key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID", "").strip()
    issuer_id = os.environ.get("APP_STORE_CONNECT_ISSUER_ID", "").strip()
    key_b64 = os.environ.get("APP_STORE_CONNECT_KEY_BASE64", "").strip()
    if not (key_id and issuer_id and key_b64):
        return _fail("missing APP_STORE_CONNECT_{KEY_ID,ISSUER_ID,KEY_BASE64}")
    try:
        private_key_pem = base64.b64decode(key_b64)
    except Exception as exc:
        return _fail(f"APP_STORE_CONNECT_KEY_BASE64 decode failed: {exc}")

    token = _asc_jwt(key_id, issuer_id, private_key_pem)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    apps_url = (
        "https://api.appstoreconnect.apple.com/v1/apps"
        f"?filter[bundleId]={urllib.parse.quote(BUNDLE_ID)}"
        "&fields[apps]=bundleId"
        "&limit=1"
    )
    try:
        apps_resp = _http_get(apps_url, headers)
    except urllib.error.HTTPError as exc:
        return _fail(f"app lookup HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as exc:
        return _fail(f"app lookup network error: {exc}")

    data = apps_resp.get("data") or []
    if not data:
        return _fail(f"no App Store Connect app with bundleId {BUNDLE_ID}")
    app_resource_id = data[0]["id"]

    versions_url = (
        f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_resource_id)}/appStoreVersions"
        f"?filter[versionString]={urllib.parse.quote(version_name)}"
        "&fields[appStoreVersions]=versionString,appStoreState,platform"
        "&limit=20"
    )
    try:
        versions_resp = _http_get(versions_url, headers)
    except urllib.error.HTTPError as exc:
        return _fail(f"versions HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as exc:
        return _fail(f"versions network error: {exc}")

    entries = versions_resp.get("data") or []
    states = []
    for entry in entries:
        attrs = entry.get("attributes") or {}
        if attrs.get("platform") not in (None, "IOS"):
            continue
        state = attrs.get("appStoreState", "UNKNOWN")
        states.append(state)
        # READY_FOR_SALE is the only state where existing App Store users
        # can actually receive the update. PENDING_DEVELOPER_RELEASE means
        # Apple approved it but the developer hasn't pushed the button yet.
        if state == "READY_FOR_SALE":
            _emit({"live": True, "state": state, "version": version_name})
            return 0
    _emit({
        "live": False,
        "state": ",".join(states) if states else "NOT_FOUND",
        "version": version_name,
        "reason": "version not yet READY_FOR_SALE",
    })
    return 2


# ---------------------------------------------------------------------------
# Android — Google Play Developer API
# ---------------------------------------------------------------------------

def check_android(version_name: str) -> int:
    raw = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return _fail("missing GOOGLE_PLAY_SERVICE_ACCOUNT_JSON secret")
    try:
        sa = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"GOOGLE_PLAY_SERVICE_ACCOUNT_JSON parse error: {exc}")

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        return _fail("google-api-python-client / google-auth not installed")

    creds = service_account.Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    service = build("androidpublisher", "v3", credentials=creds, cache_discovery=False)

    try:
        edit = service.edits().insert(packageName=BUNDLE_ID, body={}).execute()
        edit_id = edit["id"]
        try:
            track = service.edits().tracks().get(
                packageName=BUNDLE_ID, editId=edit_id, track="production",
            ).execute()
        finally:
            try:
                service.edits().delete(packageName=BUNDLE_ID, editId=edit_id).execute()
            except HttpError:
                # Edits expire on their own; cleanup failure is non-fatal.
                pass
    except HttpError as exc:
        return _fail(f"Play API HTTP {exc.status_code}: {exc.error_details or exc}")

    releases = track.get("releases") or []
    matches = [r for r in releases if r.get("name") == version_name]
    if not matches:
        # Fall back: a release whose versionCodes list maps to this name
        # via Play (rare — usually `name` is set). Surface the raw track.
        _emit({
            "live": False,
            "state": "NOT_FOUND",
            "version": version_name,
            "reason": "version not present on production track",
            "track_releases": [
                {"name": r.get("name"), "status": r.get("status"), "userFraction": r.get("userFraction")}
                for r in releases
            ],
        })
        return 2

    for release in matches:
        status = release.get("status")
        user_fraction = release.get("userFraction")
        # "completed" = 100% rollout. "inProgress" with userFraction < 1
        # means staged rollout — we deliberately wait for full availability
        # so we never advertise a version some users still cannot get.
        if status == "completed":
            _emit({"live": True, "state": status, "version": version_name})
            return 0
        _emit({
            "live": False,
            "state": status or "UNKNOWN",
            "version": version_name,
            "userFraction": user_fraction,
            "reason": "production release not yet completed (full rollout)",
        })
        return 2

    return _fail("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=["ios", "android"])
    parser.add_argument("--version", required=True, help="versionName, e.g. 1.0.5")
    args = parser.parse_args()
    if args.platform == "ios":
        return check_ios(args.version)
    return check_android(args.version)


if __name__ == "__main__":
    sys.exit(main())
