"""Uploads an AAB to a Google Play test track via the Play Developer API.

Mirrors what `xcrun altool --upload-app` does for iOS/TestFlight: takes a
signed artifact, an authenticated session, and pushes it to a test track so
testers can install it immediately.

Restricted to test tracks (internal/alpha/beta) on purpose — production
rollouts should remain a deliberate human action in Play Console rather
than a CI side effect.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

BUNDLE_ID = "app.aptnote.mobile"
ALLOWED_TRACKS = ("internal", "alpha", "beta")


def _emit(status: dict[str, Any]) -> None:
    print(json.dumps(status, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aab", required=True, help="Path to the signed AAB file")
    parser.add_argument("--track", required=True, choices=ALLOWED_TRACKS)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-code", required=True, type=int,
                        help="Expected versionCode in the AAB. Used as a cross-check against what Play sees after upload.")
    parser.add_argument("--release-notes", default="",
                        help="Optional ko-KR release notes string. Empty = no notes.")
    args = parser.parse_args()

    if not os.path.isfile(args.aab):
        _emit({"ok": False, "reason": f"AAB not found: {args.aab}"})
        return 1

    raw = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        _emit({"ok": False, "reason": "missing GOOGLE_PLAY_SERVICE_ACCOUNT_JSON secret"})
        return 1
    try:
        sa = json.loads(raw)
    except json.JSONDecodeError as exc:
        _emit({"ok": False, "reason": f"service account JSON parse error: {exc}"})
        return 1

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        _emit({"ok": False, "reason": "google-api-python-client / google-auth not installed"})
        return 1

    creds = service_account.Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    service = build("androidpublisher", "v3", credentials=creds, cache_discovery=False)

    try:
        edit = service.edits().insert(packageName=BUNDLE_ID, body={}).execute()
        edit_id = edit["id"]
    except HttpError as exc:
        _emit({"ok": False, "reason": f"edits.insert HTTP {exc.status_code}: {exc.error_details or exc}"})
        return 1

    try:
        media = MediaFileUpload(
            args.aab,
            mimetype="application/octet-stream",
            resumable=True,
            chunksize=10 * 1024 * 1024,
        )
        bundle = service.edits().bundles().upload(
            packageName=BUNDLE_ID, editId=edit_id, media_body=media,
        ).execute()
        # Play returns the versionCode it parsed from the AAB — verify it
        # matches what the workflow thinks it built. Mismatch usually means
        # the wrong artifact was passed to the upload step.
        reported_code = int(bundle.get("versionCode", -1))
        if reported_code != args.version_code:
            raise SystemExit(_fail_and_delete(
                service, edit_id,
                f"versionCode mismatch: AAB reports {reported_code}, workflow said {args.version_code}",
            ))

        release: dict[str, Any] = {
            "name": args.version_name,
            "versionCodes": [str(reported_code)],
            "status": "completed",  # test tracks deliver to testers immediately
        }
        if args.release_notes.strip():
            release["releaseNotes"] = [{"language": "ko-KR", "text": args.release_notes.strip()}]

        service.edits().tracks().update(
            packageName=BUNDLE_ID,
            editId=edit_id,
            track=args.track,
            body={"releases": [release]},
        ).execute()

        commit_resp = service.edits().commit(packageName=BUNDLE_ID, editId=edit_id).execute()
    except HttpError as exc:
        _fail_and_delete(service, edit_id,
                         f"Play API HTTP {exc.status_code}: {exc.error_details or exc}")
        return 1
    except Exception as exc:
        _fail_and_delete(service, edit_id, f"unexpected error: {exc}")
        return 1

    _emit({
        "ok": True,
        "track": args.track,
        "versionName": args.version_name,
        "versionCode": reported_code,
        "editId": commit_resp.get("id"),
    })
    return 0


def _fail_and_delete(service: Any, edit_id: str, reason: str) -> int:
    try:
        service.edits().delete(packageName=BUNDLE_ID, editId=edit_id).execute()
    except Exception:
        # Uncommitted edits expire on their own; cleanup failure is harmless.
        pass
    _emit({"ok": False, "reason": reason})
    return 1


if __name__ == "__main__":
    sys.exit(main())
