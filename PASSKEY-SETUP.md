# Passkey / WebAuthn Support

## Overview

Users can now optionally register passkeys (fingerprint, face, or screen lock) as an alternative to password login. Password login still works. Passkeys are managed from the Profile page.

## What Changed

### New files
- `app/webauthn.py` - Blueprint with five endpoints for passkey registration, login, and deletion.

### Modified files
- `requirements.txt` - Added `webauthn==2.7.1`
- `config.py` - Added three new config values: `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `WEBAUTHN_ORIGIN`
- `app/__init__.py` - Registered the `webauthn_bp` blueprint
- `app/models.py` - Added `WebAuthnCredential` model
- `app/templates/login.html` - Added "Sign in with Passkey" button below the password form
- `app/templates/profile.html` - Added passkey management card (add/remove passkeys)
- `app/templates/register.html` - Added tip about passkey setup
- `app/templates/dashboard.html` - Added dismissable passkey setup banner for users without passkeys
- `.env.example` - Added WebAuthn env vars

## Database Migration (Production)

Since this project uses manual SQL migrations, run the following against your production PostgreSQL database:

```sql
CREATE TABLE webauthn_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id BYTEA NOT NULL UNIQUE,
    public_key BYTEA NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    device_name VARCHAR(100) DEFAULT 'My Passkey',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_webauthn_credentials_user_id ON webauthn_credentials(user_id);
CREATE INDEX ix_webauthn_credentials_credential_id ON webauthn_credentials(credential_id);

-- Add passkey prompt dismissed flag to users table
ALTER TABLE users ADD COLUMN passkey_prompt_dismissed BOOLEAN DEFAULT FALSE NOT NULL;
```

For local development with SQLite, the tables/columns are created automatically by `db.create_all()`.

## Environment Variables (Production)

Add these to your Railway (or hosting) environment:

```
WEBAUTHN_RP_ID=your-domain.com
WEBAUTHN_RP_NAME=Power Family Wishlist
WEBAUTHN_ORIGIN=https://your-domain.com
```

Important notes on these values:

- `WEBAUTHN_RP_ID` must be the domain without scheme or port (e.g., `giftexchange.up.railway.app`)
- `WEBAUTHN_ORIGIN` must include `https://` and match the URL users see in their browser
- These values are bound to registered passkeys. If you change your domain, existing passkeys will stop working.

## How It Works

### Registration (Profile page)
1. User clicks "Add Passkey"
2. Browser generates a new key pair and prompts for biometric verification
3. Public key and credential ID are stored in `webauthn_credentials`
4. User names the passkey (e.g., "iPhone", "MacBook")

### Login
1. User clicks "Sign in with Passkey" on the login page
2. Browser prompts for passkey selection and biometric verification
3. Server verifies the signature against the stored public key
4. User is logged in and redirected to dashboard

### Deletion (Profile page)
1. User clicks "Remove" next to a passkey
2. Credential is deleted from the database
3. User can still log in with password or other passkeys

## Browser Support

Passkeys are supported in all modern browsers: Chrome 67+, Safari 14+, Firefox 60+, Edge 79+. The passkey button is hidden automatically in unsupported browsers.
