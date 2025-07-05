# Google API Utils

This repository contains modular, standalone automation scripts that interact with various [Google APIs](https://developers.google.com/products). These utilities are designed to support internal workflows and improve productivity by simplifying common tasks such as folder duplication, file management, sharing, and more.

Each automation lives in its own subdirectory under `src/`, with clearly scoped logic, separate configuration, and its own README.

---

## Authentication

All tools in this repo use **a single `credentials.json`** (OAuth 2.0 Desktop app) stored in the **repo root**. Tokens are generated per tool and stored locally in their respective folders (e.g. `token_drive.json` in `drive_duplicate/`) to prevent cross-tool interference.

> Credentials are **not committed** to source control. See `credentials-steps.md` for setup guidance.

---

## Tools

### `drive_duplicate`

> Searches a target folder and creates duplicates of identified sub-folders.
> Designed to create duplicate versions of folders without altering the main read-only folder

- Uses the Drive v3 API.
- Preserves folder structure and names.
- Automatically handles authentication and token storage.
- Full details and usage instructions: [`src/drive_duplicate/README.md`](src/drive_duplicate/README.md)

E.g Use Case:
- Creating instructor specific curriculum folders from main curriculum
- Allows intructors to have their own versions of slides, assignments, etc. to be edited without affecting other intructors content
- Intructors teaching 2 time-slots of the same class can have seperate slides decks, allowing examples and interactive components in the slides to be class specific

---