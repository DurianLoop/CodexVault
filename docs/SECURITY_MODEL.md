# Security Model

Codex Vault is local-first. It does not automatically upload `.codex` content.

## Local Data

Runtime data is stored under `%LOCALAPPDATA%\CodexVault` by default:

- backups
- exports
- import history
- achievement state
- local account simulation data
- backend SQLite data

Set `CODEXVAULT_DATA_DIR` to isolate test data.

## Export Exclusions

Exports exclude sensitive and volatile files by default:

- `.env`
- `auth.json`
- `cap_sid`
- `installation_id`
- token/API key/password/private-key-like names or content
- sessions and archived sessions
- cache folders
- SQLite runtime files
- logs
- generated backups and exports

## Import Protections

Imports require a manifest, reject absolute paths, reject `..` traversal, and create a backup before writing from the desktop workflow.

The preview identifies add, replace, skip, rename-capable actions, unknown top-level folders, and markdown diffs for changed `.md` files.

## Backend Boundaries

Backend sync APIs require bearer tokens for private operations. Packs have owners. A user can list and directly download only their own packs. Another user needs a valid share code that has not expired or exceeded its download limit.

Download audit records are written for every successful backend download.

## Current Limits

- The backend is a private-beta architecture preview, not a hosted production service.
- Password hashing uses PBKDF2-HMAC-SHA256 with per-user salts.
- Share codes are private beta tokens, not public marketplace links.
- The Windows executable is unsigned in this beta.
