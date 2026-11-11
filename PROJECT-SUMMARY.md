# Power Family Wishlist - Project Summary

## What It Is

A Flask web app for coordinating family gift-giving. Family members create wishlists, browse each other's lists, and claim items they plan to buy. List owners cannot see what has been claimed, keeping gifts a surprise.

## Tech Stack

- **Backend:** Flask 3.0 (Python 3.12), Flask-SQLAlchemy, Flask-Login, Flask-WTF (CSRF protection app-wide), Flask-Limiter (login throttling)
- **Database:** PostgreSQL (production via Railway), SQLite (local dev)
- **Frontend:** Bootstrap 5, Jinja2 templates
- **Email:** SendGrid HTTP API (not Flask-Mail SMTP)
- **Image Scraping:** requests + BeautifulSoup4 (og:image, twitter:image, itemprop)
- **Auth:** Passkeys via webauthn==2.7.1 (optional, password fallback always available)
- **Hosting:** Railway (auto-deploys from GitHub, Procfile runs gunicorn)

## Database Models

Five models in `app/models.py`:

**User** - Authentication and profiles. Fields include email, password_hash, name, is_admin, gift_delivery_email, invite/reset tokens with expiry, archiving fields (is_active, archived_at, archived_by_id, archived_reason), and child promotion fields (promoted_from_child, promoted_at, promoted_by_id). Uses werkzeug password hashing.

**List** - Wishlists. Has owner_id (the user who owns it) and managed_by_id (parent who manages a child's list). Items ordered by position.

**Item** - Wishlist items. Fields: title, description, url, image_url, price (Decimal), notes, max_claims (1 = single, 999 = unlimited), position (priority ordering), received_at (null = active, set = archived/received), created_by_id.

**Claim** - Tracks who claimed which item. Unique constraint on (item_id, claimed_by_id). One user can only claim an item once.

**WebAuthnCredential** - Passkey credentials for passwordless login. Fields: credential_id (LargeBinary, unique), public_key (LargeBinary), sign_count, device_name, created_at. Belongs to User via user_id FK with cascade delete.

## Key Relationships

- User has one owned_list and can manage multiple child lists
- User has many claims
- User has many webauthn_credentials (passkeys)
- List has many items (ordered by position)
- Item has many claims
- Child profiles: a User whose owned_list has a non-null managed_by_id

## Route Structure (app/routes.py)

### Public Routes
- `/` - Landing page (redirects to dashboard if logged in)
- `/login` - Login (blocks archived users; 10 attempts per minute per visitor)
- `/logout` - Logout (POST)
- `/register/<token>` - Complete registration from invite link (48hr expiry)
- `/forgot-password` - Request password reset (5 per minute per visitor)
- `/reset-password/<token>` - Reset password (24hr expiry)
- `/help` - Public help page

### Dashboard & Lists (login required)
- `/dashboard` - Shows all active family members and their lists
- `/my-list` - View/manage your own list (active + received tabs)
- `/manage-child-list/<list_id>` - Manage a child's list
- `/list/<list_id>` - Shopping view of a list (with claim buttons). Only the list's owner is blocked; a parent who manages a child's list can shop it and claim from it
- `/help-guide` - In-app help guide

### Item Management (login required)
- `/item/add/<list_id>` - Add item (auto-fetches product image from URL)
- `/item/edit/<item_id>` - Edit item (re-fetches image if URL changed)
- `/item/delete/<item_id>` - Delete item (notifies claimers via email)
- `/item/mark-received/<item_id>` - Mark as received (soft archive)
- `/item/restore/<item_id>` - Restore received item (creates a copy)
- `/item/move/<item_id>/<direction>` - Reorder (POST; `up`/`down` swap among active items, `top` moves to first)

### Claim Management (login required)
- `/claim/<item_id>` - Claim an item (POST)
- `/unclaim/<item_id>` - Unclaim an item (POST)
- `/my-claims` - Everything you have claimed, grouped by person

### Admin Routes (admin only)
- `/admin/invite` - Invite new family member (creates user + sends email)
- `/admin/users` - User management dashboard (shows pending/expired invites with their links)
- `/admin/users/<id>/resend-invite` - Issue a fresh invitation link and email (POST)
- `/admin/users/<id>/archive` - Archive a user (soft delete, reversible)
- `/admin/users/<id>/restore` - Restore archived user
- `/admin/users/<id>/delete` - Permanent delete (requires admin password + email confirmation)
- `/admin/child/<id>/archive` - Archive child profile
- `/admin/child/<id>/restore` - Restore child profile
- `/admin/child/<id>/promote` - Promote child to full account (assigns email, sends invite)

### Profile (login required)
- `/profile` - Edit name and gift delivery email
- `/change-password` - Change password

### Passkey / WebAuthn Routes (app/webauthn.py)
- `/webauthn/register/options` (POST, login required) - Get registration challenge
- `/webauthn/register/verify` (POST, login required) - Verify and store new passkey
- `/webauthn/login/options` (POST, public) - Get authentication challenge
- `/webauthn/login/verify` (POST, public) - Verify passkey and log in
- `/webauthn/delete/<id>` (POST, login required) - Remove a passkey
- `/webauthn/dismiss-prompt` (POST, login required) - Dismiss dashboard passkey banner

## Templates

19 templates in `app/templates/`:

- `base.html` - Layout with navbar (admin sees "Users" and "Invite" links)
- `index.html` - Landing page
- `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`
- `dashboard.html` - Family member grid with list links
- `my_list.html` - Own list with active/received tabs, child list sidebar
- `view_list.html` - Other person's list with claim/unclaim buttons (compact rows on phones)
- `item_form.html` - Add/edit item form with image preview
- `invite_user.html` - Admin invite form (shows invite URL after success)
- `profile.html`, `change_password.html`
- `add_child.html` - Add child profile form
- `help.html`, `help_guide.html`
- `my_claims.html` - Your claimed gifts
- `error.html` - Branded 404 / 500 / expired-page / too-many-attempts page

3 admin templates in `app/templates/admin/`:

- `user_management.html` - Active and archived user lists
- `archive_user.html` - Archive confirmation with warnings
- `promote_child.html` - Promote child form (enter email)

## Email System (app/email.py)

Uses SendGrid HTTP API directly. Send functions return True/False so routes can tell the admin when an email did not go out. Three email types:

1. **Invite email** - Sent when admin invites a new member. Contains setup link.
2. **Password reset email** - Sent on forgot-password request.
3. **Item deleted notification** - Sent to all claimers when an item is deleted.

API key comes from SENDGRID_API_KEY or MAIL_PASSWORD env var. Sender from MAIL_DEFAULT_SENDER.

## Forms (app/forms.py)

11 WTForms classes: LoginForm, RegistrationForm, InviteUserForm (validates email uniqueness), PasswordResetRequestForm, PasswordResetForm, ProfileForm, ChangePasswordForm, ItemForm (with allow_multiple toggle and image_url), AddChildForm, PromoteChildForm, ArchiveUserForm, DeleteUserForm.

## Image Auto-Fetch Feature

When adding/editing items with a product URL, the backend fetches the page and extracts images from og:image, twitter:image, or itemprop="image" meta tags. Follows redirects (handles Amazon sponsored links), refusing private/internal addresses at every hop. 8-second timeout per hop. Silent failure. Manual image URL override available. Images display at 200x200px with rounded corners and onerror hiding.

## User Management System

- **Archive:** Sets is_active=False. User cannot log in, hidden from dashboard, data preserved, reversible.
- **Restore:** Sets is_active=True. User can log in again.
- **Promote child:** Converts child profile to full account. Assigns real email, removes parent management, sends invite. Preserves all wishlist data and user ID. Not reversible.
- **Delete:** Permanent. Requires admin password + email/name confirmation. CASCADE deletes related data.

Safety guards: cannot archive last admin, cannot archive parent with active children, delete requires archived status first.

## Configuration (config.py)

Base Config loads from .env file. DevelopmentConfig uses SQLite (dev.db). ProductionConfig uses DATABASE_URL from environment (rewritten to `postgresql+psycopg2://`), requires SECRET_KEY, and sets Secure cookies. Rate limiting is off in development. App factory pattern in `app/__init__.py`, which also registers the error pages and retries the startup database call a few times.

## Deployment

Railway auto-deploys from GitHub. Procfile: `web: gunicorn run:app`. `runtime.txt` pins Python 3.12 (minor version only; Railway's builder rejects old exact patch pins). `requirements.txt` is generated from `requirements.in` with every package pinned: `uv pip compile requirements.in -o requirements.txt --python-version 3.12`. Database migrations are manual SQL ALTER TABLE statements (no Flask-Migrate). Two migration sets documented: user management fields and image_url column.

## File Structure

```
gift-exchange/
  app/
    __init__.py        # App factory, extension init, blueprint registration
    models.py          # User, List, Item, Claim models
    routes.py          # All route handlers (~1020 lines)
    webauthn.py        # Passkey registration, login, management (6 endpoints)
    forms.py           # 11 WTForms classes
    email.py           # SendGrid email functions
    templates/         # 19 Jinja2 templates + 3 admin templates
  config.py            # Dev/Prod config classes
  run.py               # Entry point, shell context
  create_admin.py      # CLI script for first admin setup
  requirements.in      # Direct dependencies (edit this one)
  requirements.txt     # Generated, fully pinned
  runtime.txt          # Python version for Railway
  tests/               # pytest suite (./venv/bin/python -m pytest tests/)
  fix_placeholder_passwords.py  # One-off prod cleanup (run 2026-11-11, found nothing)
  Procfile             # gunicorn run:app
  .env.example         # Environment variable template
```

## Environment Variables

Required for production: FLASK_ENV, SECRET_KEY (the app will not start without it), DATABASE_URL (auto-set by Railway), SENDGRID_API_KEY or MAIL_PASSWORD (the SendGrid API key), MAIL_DEFAULT_SENDER, WEBAUTHN_RP_ID (bare domain), WEBAUTHN_RP_NAME, WEBAUTHN_ORIGIN (full https URL). Optional: APP_NAME. The other MAIL_* variables are leftovers from Flask-Mail and are no longer read.

## Notes

- No Flask-Migrate. Schema changes require manual SQL.
- Timestamps are naive UTC, via the `utcnow()` helper in `app/models.py`.
- The app name in code/emails is "Power Family Wishlist" (configurable via APP_NAME env var).
- Passkeys are optional. Password login always works as a fallback. Users manage passkeys from their Profile page. A dismissable dashboard banner prompts existing users to set up passkeys.
