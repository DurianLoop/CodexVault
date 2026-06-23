# Backend API Reference

Default local base URL:

```text
http://127.0.0.1:8765
```

Authenticated endpoints use:

```text
Authorization: Bearer <token>
```

## Health

`GET /api/health`

Returns `{ "ok": true }` with server time.

## Register

`POST /api/register`

```json
{"username":"alice","password":"correct horse"}
```

Returns username and user id.

## Login

`POST /api/login`

```json
{"username":"alice","password":"correct horse"}
```

Returns a bearer token.

## Bind Device

`POST /api/devices`

```json
{"name":"Laptop"}
```

Requires auth. Returns device id, platform, first seen, and last seen.

## Upload Pack

`POST /api/packs`

```json
{
  "name": "Demo Pack",
  "contentBase64": "...",
  "shareTtlHours": 24,
  "maxDownloads": 5
}
```

Requires auth. Returns pack id, private share code, expiration, manifest hash, and pack size.

## List Own Packs

`GET /api/packs`

Requires auth. Returns only packs owned by the authenticated user.

## Share-Code Metadata

`GET /api/share-codes/{code}`

Returns public metadata for a valid code.

## Download

`GET /api/packs/{identifier}/download`

`identifier` can be a pack id or share code.

- Pack id downloads require the authenticated user to own the pack.
- Share code downloads require a valid, unexpired code with remaining downloads.
- Successful downloads create audit records.
