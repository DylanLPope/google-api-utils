# How to Run `duplicate_drive_folder.py`
Follow these steps to run the Drive Folder Duplicator script with its own authentication:
---

### 1. Prepare your environment
Open a terminal and navigate to the root of the repo.
---

### 2. Create and activate a Python virtual environment
    python -m venv venv
Activate the environment:

   - **Windows PowerShell:**
         Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
         .\venv\Scripts\Activate.ps1
   
   - **Windows CMD:**
         venv\Scripts\activate.bat
   
   - **macOS/Linux:**
         source venv/bin/activate
---

### 3. Install dependencies
Install manually:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib tqdm
---

### 4. Add your Google API credentials
- Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
- Create an **OAuth 2.0 Client ID** (Desktop app).
- Download the JSON file and save it as `credentials.json` in the **repo root**.

> **Important:** Do not commit this file to version control.
---

### 5. Configure folder IDs
Edit `src/drive_duplicate/drive_config.json` with:

{
    "ROOT_FOLDER_ID": "rootFolderID",
    "SOURCE_FOLDER_NAME": "Name of Source Folder to copy content from",
    "FOLDERS_TO_COPY": [
        "Folder name for target class",
        "Folder name for target class",
        "Folder name for target class"
    ],
    "DESTINATION_FOLDER_NAME": "Session-Year",
    "NEW_BATCH_FOLDER_NAME": "Target Teacher"
}
---

### 6. Run the script
From the repo root, execute:
    python src/drive_duplicate/duplicate_drive_folder.py
---

### 7. Authenticate
- A browser window opens for Google authentication on first run.
- `token_drive.json` is created next to the script to store your OAuth token.
- The folder duplicates recursively, and the new folder ID is printed.
---

### System Metadata and Folder Behavior
The duplicator automatically adds a _system folder to each copied folder containing a hidden .meta.json file. This file:
- Tracks the origin of the copied folder.
- Enables merging new content in future runs.
- Ensures missing files and subfolders are added without affecting existing edits.
- Allows folders to be renamed freely without breaking future updates.

Important: Do not delete or modify the _system folder or .meta.json file. Doing so may prevent updates from functioning correctly.
---

### Troubleshooting
- If `token_drive.json` gets corrupted, delete it and rerun the script.

- For PowerShell activation issues, run:
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
before activating your virtual environment.
---