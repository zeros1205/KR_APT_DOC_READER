"""Reports the version currently live on a mobile app store.

Prints a single-line JSON status to stdout. Exit codes:
  0 — a live version exists, returned in the payload
  2 — no live version available right now (still in review / staged rollout)
  1 — configuration or transport failure

iOS: App Store Connect, treats `appStoreState == READY_FOR_SALE` as live.
Android: Google Play Developer API, treats a `production` track release
with `status == "completed"` as live (staged `inProgress` rollouts do not
count — not all users can install yet). If production has no completed
release yet, falls back to the open testing (`beta`) track so an app that
is still in public beta reports the beta version as its latest.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BUNDLE_ID = "app.aptnote.mobile"


def _emit(status: dict[str, Any]) -> None:
    print(json.dumps(status, ensure_ascii=False))


def _fail(reason: str) -> int:
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


def current_live_ios() -> int:
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

    # Ask ASC for iOS versions, then pick the live one in code.
    #
    # NOTE: Apple deprecated the `appStoreState` attribute/filter on
    # appStoreVersions (replaced by `appVersionState`). Sending
    # `filter[appStoreState]` now returns HTTP 400 PARAMETER_ERROR.ILLEGAL,
    # which is exactly what broke this step. So we no longer filter by state
    # server-side; we request both the new and legacy state attributes and
    # decide liveness locally (whichever field the API returns).
    versions_url = (
        f"https://api.appstoreconnect.apple.com/v1/apps/{urllib.parse.quote(app_resource_id)}/appStoreVersions"
        "?filter[platform]=IOS"
        "&fields[appStoreVersions]=versionString,appVersionState,appStoreState,platform,createdDate"
        "&limit=20"
    )
    try:
        versions_resp = _http_get(versions_url, headers)
    except urllib.error.HTTPError as exc:
        return _fail(f"versions HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as exc:
        return _fail(f"versions network error: {exc}")

    # Live ("on sale") states. New API field appVersionState uses
    # READY_FOR_DISTRIBUTION; the legacy appStoreState used READY_FOR_SALE.
    # Accept either so the check is robust across the API transition.
    live_states = {"READY_FOR_DISTRIBUTION", "READY_FOR_SALE"}

    def _ver_key(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0,)

    entries = versions_resp.get("data") or []
    live: list[tuple[tuple[int, ...], str, str]] = []
    for entry in entries:
        attrs = entry.get("attributes") or {}
        version = attrs.get("versionString")
        state = attrs.get("appVersionState") or attrs.get("appStoreState") or ""
        if version and state in live_states:
            live.append((_ver_key(version), version, state))

    if live:
        live.sort(reverse=True)  # newest versionString first
        _, version, state = live[0]
        _emit({"live": True, "state": state, "version": version})
        return 0
    _emit({
        "live": False,
        "state": "NO_LIVE_VERSION",
        "reason": "no live iOS appStoreVersion (READY_FOR_DISTRIBUTION/READY_FOR_SALE)",
    })
    return 2


# ---------------------------------------------------------------------------
# Android — Google Play Developer API
# ---------------------------------------------------------------------------

def _version_name_from_release(name: str | None) -> str:
    """Extract a bare semver versionName from a Play release name.

    Play release names default to "<versionCode> (<versionName>)", e.g.
    "19 (1.0.2)". The app (mobile-app/src/version.ts) only understands a
    bare semver string like "1.0.2" and treats anything else as malformed
    (no update shown), so we must publish just the versionName. We prefer a
    dotted version inside parentheses, then any dotted version in the name,
    and finally fall back to the raw name so a value is never silently lost.
    """
    if not name:
        return ""
    semver = r"\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?"
    paren = re.search(r"\(([^)]*)\)", name)
    if paren:
        inner = re.search(semver, paren.group(1))
        if inner:
            return inner.group(0)
    whole = re.search(semver, name)
    if whole:
        return whole.group(0)
    return name.strip()


def current_live_android() -> int:
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

    # production 을 최우선으로 보되, 아직 정식 출시 전(공개테스트 단계)이라
    # production 에 완료된 릴리스가 없으면 open testing(beta) 트랙으로 폴백한다.
    # 앱이 공개테스트 베타로만 배포된 상태에서도 "최신 버전" 이 동기화되도록.
    # production 에 완료 릴리스가 생기면 그쪽이 항상 우선한다.
    track_priority = ("production", "beta")
    checked: list[dict[str, Any]] = []
    try:
        edit = service.edits().insert(packageName=BUNDLE_ID, body={}).execute()
        edit_id = edit["id"]
        try:
            for track_name in track_priority:
                track = service.edits().tracks().get(
                    packageName=BUNDLE_ID, editId=edit_id, track=track_name,
                ).execute()
                releases = track.get("releases") or []
                # Pick the most recent fully-rolled-out release. Play orders
                # releases newest first, but we filter explicitly so a
                # halted/draft entry at the top never wins.
                for release in releases:
                    if release.get("status") == "completed":
                        version = _version_name_from_release(release.get("name"))
                        if version:
                            _emit({"live": True, "state": "completed",
                                   "version": version, "track": track_name})
                            return 0
                checked.append({
                    "track": track_name,
                    "releases": [
                        {"name": r.get("name"), "status": r.get("status"),
                         "userFraction": r.get("userFraction")}
                        for r in releases
                    ],
                })
        finally:
            try:
                service.edits().delete(packageName=BUNDLE_ID, editId=edit_id).execute()
            except HttpError:
                pass
    except HttpError as exc:
        return _fail(f"Play API HTTP {exc.status_code}: {exc.error_details or exc}")

    _emit({
        "live": False,
        "state": "NO_LIVE_VERSION",
        "reason": "no completed release on production or beta (open testing) track",
        "checked_tracks": checked,
    })
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=["ios", "android"])
    args = parser.parse_args()
    if args.platform == "ios":
        return current_live_ios()
    return current_live_android()


if __name__ == "__main__":
    sys.exit(main())
