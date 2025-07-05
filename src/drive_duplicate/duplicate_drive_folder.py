  
"""
Standalone Google  Drive folder duplicator.
- Uses credentials.json in the repo root
- Stores its own token in the same folder (token_drive.json)
- Reads constants from drive_config.json next to this file
"""

from __future__ import annotations 

import json
from pathlib import Path
from typing import Sequence, List

# Third‑party libraries that power Google OAuth and Drive API access.
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from tqdm import tqdm

# ──────────────────────────────────────────────────────────────
# Paths & constants
# ──────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

CONFIG_PATH = HERE / "drive_config.json"  # JSON config containing source/destination IDs.
TOKEN_PATH = HERE / "token_drive.json"    # Stored OAuth token (refreshed automatically).
CREDENTIALS_PATH = ROOT / "credentials.json"  # OAuth 2.0 client secrets downloaded from GCP.

SCOPES: List[str] = [                     # OAuth scope(s) requested—here: full Drive access.
    "https://www.googleapis.com/auth/drive",
]

# ──────────────────────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────────────────────

def ensure_credentials_file():
    """Exit early if credentials.json is missing, with a helpful message."""
    if not CREDENTIALS_PATH.exists():
        sys.exit(
            f"credentials.json not found at {CREDENTIALS_PATH}.\n"
            "Download your OAuth 2.0 Desktop credentials from Google Cloud "
            "Console and save as credentials.json in the repo root."
        )


def load_credentials(scopes: Sequence[str]) -> Credentials:
    """Return a valid `Credentials` object; refresh or perform OAuth flow if needed."""
    ensure_credentials_file()
    creds: Credentials | None = None

    # Re‑use an existing token if we have one and it’s non‑empty.
    if TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes)

    # If we lack credentials OR they’re invalid/expired, refresh or re‑auth.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            # Launch local web server + browser to complete OAuth “Installed App” flow.
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, scopes)
            creds = flow.run_local_server(port=0)
        # Persist the (possibly new) token for next run.
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def get_drive_service() -> Resource:
    """Factory: build and return a Google Drive API v3 service client."""
    creds = load_credentials(SCOPES)
    return build("drive", "v3", credentials=creds)

# ──────────────────────────────────────────────────────────────
# Drive utility functions
# ──────────────────────────────────────────────────────────────

def create_folder(service: Resource, name: str, parent_id: str | None) -> str:
    """
    Create a folder `name` under `parent_id` (or root if None) and
    return its new Drive file ID.
    """
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]
    return service.files().create(body=meta, fields="id").execute()["id"]


def list_children(service: Resource, folder_id: str, mime: str | None = None):
    q = f"'{folder_id}' in parents and trashed = false"
    if mime:
        q += f" and mimeType = '{mime}'"
    page_token = None
    while True:
        resp = (
            service.files()
            .list(q=q, fields="nextPageToken, files(id, name, mimeType)", pageToken=page_token)
            .execute()
        )
        for item in resp.get("files", []):
            yield item
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def copy_file(service: Resource, file_id: str, name: str, parent_id: str):
    """Copy a single Drive *file* (`file_id`) into `parent_id` with new `name`"""
    body = {"name": name, "parents": [parent_id]}
    service.files().copy(fileId=file_id, body=body).execute()


def copy_folder_recursive(
    service: Resource,
    src_id: str,
    dst_parent_id: str | None,
    new_name: str
) -> str:

    dst_id = create_folder(service, new_name, dst_parent_id)

    # tqdm gives a neat progress bar; leave=False keeps parent bars tidy
    for child in tqdm(list_children(service, src_id), desc=new_name, leave=False):
        if child["mimeType"] == "application/vnd.google-apps.folder":
            # Recurse for sub‑folders
            copy_folder_recursive(service, child["id"], dst_id, child["name"])
        else:
            # Simple file copy for non‑folders
            copy_file(service, child["id"], child["name"], dst_id)
    return dst_id

# ──────────────────────────────────────────────────────────────
# Main entrypoint
# ──────────────────────────────────────────────────────────────

def duplicate_from_config():
    """Read drive_config.json and kick off the duplication process."""
    if not CONFIG_PATH.exists():
        sys.exit(f"Config file not found: {CONFIG_PATH}")

    cfg = json.loads(CONFIG_PATH.read_text())

    folder_names = cfg["FOLDERS_TO_COPY"]  # list of folder names to duplicate
    src_parent = cfg["SOURCE_PARENT_FOLDER_ID"]  # parent folder to search in
    dst_parent = cfg.get("DESTINATION_PARENT_FOLDER_ID")  # parent for new batch folder
    new_batch_name = cfg.get("NEW_BATCH_FOLDER_NAME", "Copied Folders")

    service = get_drive_service()

    try:
        batch_folder_id = create_folder(service, new_batch_name, dst_parent)
        found_folders = find_folders_by_name(service, src_parent, folder_names)

        missing = [name for name in folder_names if name not in found_folders]
        if missing:
            print(f"Warning: These folders were not found: {missing}")

        for name, src_id in found_folders.items():
            print(f"Copying folder: {name}")
            copy_folder_recursive(service, src_id, batch_folder_id, name)

        print(f"Done! Duplicated folders are in: {batch_folder_id}")
    except HttpError as err:
        sys.exit(f"Drive API error: {err}")

def find_folders_by_name(service: Resource, parent_id: str, names: Sequence[str]) -> dict[str, str]:
    """Return a mapping of folder name → ID for matching folders under parent_id."""
    wanted = set(names)
    found = {}
    for item in list_children(service, parent_id, mime="application/vnd.google-apps.folder"):
        if item["name"] in wanted:
            found[item["name"]] = item["id"]
    return found

if __name__ == "__main__":     # True only when script is run directly, not imported
    duplicate_from_config()    # Fire off the whole flow
