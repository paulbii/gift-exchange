# Power Family Wishlist

A small web app for coordinating family gift-giving. Everyone keeps a wishlist,
browses each other's lists, and claims the items they plan to buy. Claims are
hidden from the list's owner, so gifts stay a surprise.

For how the app is put together (models, routes, templates, email, passkeys),
see [PROJECT-SUMMARY.md](PROJECT-SUMMARY.md). Related docs:
[USER-MANAGEMENT.md](USER-MANAGEMENT.md), [PASSKEY-SETUP.md](PASSKEY-SETUP.md),
[IMAGE-FETCH-DEPLOYMENT.md](IMAGE-FETCH-DEPLOYMENT.md).

## What it does

- Wishlists with links, prices, auto-fetched product images, and priority order
- Claiming, including multi-claim items such as gift cards
- "My Claims": everything you've committed to buy, in one place
- Parent-managed child profiles that can be promoted to full accounts
- Invite-only sign-up, with password or passkey login
- Admin tools: invite and re-invite, create a password reset link to hand over
  directly, archive, restore, delete

## Stack

Flask 3 on Python 3.12, PostgreSQL in production (SQLite locally), Bootstrap 5
templates, Resend (or SendGrid) for email, hosted on Railway.

## Run it locally

```
python3 -m venv venv
./venv/bin/pip install -r requirements.txt pytest
cp .env.example .env          # set FLASK_ENV=development
./venv/bin/python create_admin.py
FLASK_ENV=development ./venv/bin/flask --app run run
```

Then open http://localhost:5000 and log in as the admin you just created.
Without `DATABASE_URL`, development uses a local `dev.db` SQLite file. Without an
email API key, emails are skipped and the app shows the invitation link to copy.

## Tests

```
./venv/bin/python -m pytest tests/
```

## Deploy

Pushing to `main` deploys to Railway. The service needs these variables:

| Variable | Notes |
| --- | --- |
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | Required. The app will not start without it. |
| `DATABASE_URL` | Set by Railway's Postgres plugin |
| `RESEND_API_KEY` | Email is sent through Resend when this is set. Without it the app falls back to SendGrid (`SENDGRID_API_KEY`, or the older `MAIL_PASSWORD`) |
| `MAIL_DEFAULT_SENDER` | An address on a domain verified with the email provider, e.g. `Wishlist <wishlist@yourdomain.com>` |
| `WEBAUTHN_RP_ID` | Bare domain, no scheme or port |
| `WEBAUTHN_RP_NAME` | Name shown in passkey prompts |
| `WEBAUTHN_ORIGIN` | Full `https://` URL of the site |

Things to know:

- There are no migrations. Tables are created on startup; a change to an
  existing table is a manual `ALTER TABLE` on the production database.
- Dependencies are fully pinned. Edit `requirements.in`, then regenerate:
  `uv pip compile requirements.in -o requirements.txt --python-version 3.12`
- The production database has no public address. To run a script against it,
  run it on the server: `railway ssh python some_script.py`
