  
"""
Standalone Google  Drive folder duplicator.
- Uses credentials.json in the repo root
- Stores its own token in the same folder (token_drive.json)
- Reads constants from drive_config.json next to this file
"""

from __future__ import annotations 

import sys
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

def locate_source_parent(service: Resource, root_id: str, folder_name: str) -> str:
    """Return the ID of `folder_name` under `root_id`, or exit on error."""
    lookup = find_folders_by_name(service, root_id, [folder_name])
    if folder_name not in lookup:
        sys.exit(f'Source folder "{folder_name}" not found under root ID {root_id}')
    return lookup[folder_name]


def get_or_create_destination_folder(service: Resource, root_id: str, dest_name: str) -> str:
    """Find or create the destination folder under `root_id` and return its ID."""
    lookup = find_folders_by_name(service, root_id, [dest_name])
    if dest_name in lookup:
        dest_id = lookup[dest_name]
        print(f'Using existing destination folder "{dest_name}" ({dest_id})')
    else:
        dest_id = create_folder(service, dest_name, root_id)
        print(f'Created destination folder "{dest_name}" ({dest_id})')
    return dest_id


def get_or_create_batch_folder(service: Resource, parent_id: str, batch_name: str) -> str:
    """Find or create the batch folder under `parent_id` and return its ID."""
    lookup = find_folders_by_name(service, parent_id, [batch_name])
    if batch_name in lookup:
        batch_id = lookup[batch_name]
        print(f'Using existing batch folder "{batch_name}" ({batch_id})')
    else:
        batch_id = create_folder(service, batch_name, parent_id)
        print(f'Created batch folder "{batch_name}" ({batch_id})')
    return batch_id

def copy_selected_folders(service: Resource, src_parent_id: str, batch_folder_id: str, folder_names: Sequence[str]) -> None:
    """Copy each folder in `folder_names` (if found) into `batch_folder_id`."""
    found = find_folders_by_name(service, src_parent_id, folder_names)
    missing = [n for n in folder_names if n not in found]
    if missing:
        print(f"Warning: These folders were not found: {missing}")

    for name, src_id in found.items():
        print(f"Copying folder: {name}")
        copy_folder_recursive(service, src_id, batch_folder_id, name)


def find_folders_by_name(service: Resource, parent_id: str, names: Sequence[str]) -> dict[str, str]:
    """Return a mapping of folder name → ID for matching folders under parent_id."""
    wanted = set(names)
    found = {}
    for item in list_children(service, parent_id, mime_type_filter="application/vnd.google-apps.folder"):
        if item["name"] in wanted:
            found[item["name"]] = item["id"]
    return found


def list_children(service: Resource, folder_id: str, mime_type_filter: str | None = None ):
    """Yield metadata dictionaries for each item directly under *folder_id*."""

    query = f"'{folder_id}' in parents and trashed = false"
    if mime_type_filter:
        query += f" and mimeType = '{mime_type_filter}'"
    page_token: str | None = None

    while True:
        response = (
            service.files()
            .list(q=query, fields="nextPageToken, files(id, name, mimeType)", pageToken=page_token)
            .execute()
        )
        for item in response.get("files", []):
            yield item
        page_token = response.get("nextPageToken")
        if not page_token:
            break


def copy_file(service: Resource, file_id: str, name: str, parent_id: str):
    """Copy a single Drive *file* (`file_id`) into `parent_id` with new `name`"""
    body = {"name": name, "parents": [parent_id]}
    service.files().copy(fileId=file_id, body=body).execute()


def copy_folder_recursive( service: Resource, src_id: str, dst_parent_id: str | None, new_name: str,) -> str:
    """
    Copy a Drive folder tree. If a folder with `new_name` already exists under
    dst_parent_id, merge into it by adding only the *missing* children.
    """

    # Reuse‑or‑create the destination folder
    existing_match = None
    for item in list_children(
        service,
        dst_parent_id,
        mime_type_filter="application/vnd.google-apps.folder",
    ):
        if item["name"] == new_name:
            existing_match = item["id"]
            break

    dst_id = existing_match or create_folder(service, new_name, dst_parent_id)

    # Build a quick lookup of names already present in dst_id  (files + folders)
    existing_names = {
        child["name"] for child in list_children(service, dst_id)
    }

    # Copy / recurse only for items that are missing
    for child in tqdm(list_children(service, src_id), desc=new_name, leave=False):
        if child["name"] in existing_names:
            continue  # already present → skip
        if child["mimeType"] == "application/vnd.google-apps.folder":
            copy_folder_recursive(service, child["id"], dst_id, child["name"])
        else:
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

    folder_names = cfg["FOLDERS_TO_COPY"]                    # List of folder names to duplicate
    root_id = cfg["ROOT_FOLDER_ID"]                          # ID of the root to search in
    source_folder_name = cfg["SOURCE_FOLDER_NAME"]           # Folder inside root that holds sources
    dest_root_name = cfg["DESTINATION_FOLDER_NAME"]          # Name of parent folder under root

    new_batch_name = cfg.get("NEW_BATCH_FOLDER_NAME", "Copied Folders")

    service = get_drive_service()

    try:
        # Resolve source
        src_parent = locate_source_parent(service, root_id, source_folder_name)

        # Resolve destination root, 
        dest_parent = get_or_create_destination_folder(service, root_id, dest_root_name)

        # Resolve batch folder
        batch_folder_id = get_or_create_batch_folder(service, dest_parent, new_batch_name)

        # Copy selected folders
        copy_selected_folders(service, src_parent, batch_folder_id, folder_names)

        print(f"Done! Duplicated folders are in: {batch_folder_id}")
    except HttpError as err:
        sys.exit(f"Drive API error: {err}")

if __name__ == "__main__":     # True only when script is run directly, not imported
    duplicate_from_config()    # Fire off the whole flow
