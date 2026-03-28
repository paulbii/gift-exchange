# Power Family Wishlist - Project Summary

## What It Is

A Flask web app for coordinating family gift-giving. Family members create wishlists, browse each other's lists, and claim items they plan to buy. List owners cannot see what has been claimed, keeping gifts a surprise.

## Tech Stack

- **Backend:** Flask 3.0 (Python), Flask-SQLAlchemy, Flask-Login, Flask-WTF
- **Database:** PostgreSQL (production via Railway), SQLite (local dev)
- **Frontend:** Bootstrap 5, Jinja2 templates
- **Email:** SendGrid HTTP API (not Flask-Mail SMTP)
- **Image Scraping:** requests + BeautifulSoup4 (og:image, twitter:image, itemprop)
- **Hosting:** Railway (auto-deploys from GitHub, Procfile runs gunicorn)

## Database Models

Four models in `app/models.py`:

**User** - Authentication and profiles. Fields include email, password_hash, name, is_admin, gift_delivery_email, invite/reset tokens with expiry, archiving fields (is_active, archived_at, archived_by_id, archived_reason), and child promotion fields (promoted_from_child, promoted_at, promoted_by_id). Uses werkzeug password hashing.

**List** - Wishlists. Has owner_id (the user who owns it) and managed_by_id (parent who manages a child's list). Items ordered by position.

**Item** - Wishlist items. Fields: title, description, url, image_url, price (Decimal), notes, max_claims (1 = single, 999 = unlimited), position (priority ordering), received_at (null = active, set = archived/received), created_by_id.

**Claim** - Tracks who claimed which item. Unique constraint on (item_id, claimed_by_id). One user can only claim an item once.

## Key Relationships

- User has one owned_list and can manage multiple child lists
- User has many claims
- List has many items (ordered by position)
- Item has many claims
- Child profiles: a User whose owned_list has a non-null managed_by_id

## Route Structure (app/routes.py)

### Public Routes
- `/` - Landing page (redirects to dashboard if logged in)
- `/login` - Login (blocks archived users)
- `/logout` - Logout
- `/register/<token>` - Complete registration from invite link (48hr expiry)
- `/forgot-password` - Request password reset
- `/reset-password/<token>` - Reset password (24hr expiry)
- `/help` - Public help page

### Dashboard & Lists (login required)
- `/dashboard` - Shows all active family members and their lists
- `/my-list` - View/manage your own list (active + received tabs)
- `/manage-child-list/<list_id>` - Manage a child's list
- `/list/<list_id>` - View someone else's list (with claim buttons)
- `/help-guide` - In-app help guide

### Item Management (login required)
- `/item/add/<list_id>` - Add item (auto-fetches product image from URL)
- `/item/edit/<item_id>` - Edit item (re-fetches image if URL changed)
- `/item/delete/<item_id>` - Delete item (notifies claimers via email)
- `/item/mark-received/<item_id>` - Mark as received (soft archive)
- `/item/restore/<item_id>` - Restore received item (creates a copy)
- `/item/move/<item_id>/<direction>` - Reorder (up/down position swap)
- `/fetch-product-image` - JSON API endpoint for image fetching

### Claim Management (login required)
- `/claim/<item_id>` - Claim an item (POST)
- `/unclaim/<item_id>` - Unclaim an item (POST)

### Admin Routes (admin only)
- `/admin/invite` - Invite new family member (creates user + sends email)
- `/admin/users` - User management dashboard
- `/admin/users/<id>/archive` - Archive a user (soft delete, reversible)
- `/admin/users/<id>/restore` - Restore archived user
- `/admin/users/<id>/delete` - Permanent delete (requires admin password + email confirmation)
- `/admin/child/<id>/archive` - Archive child profile
- `/admin/child/<id>/restore` - Restore child profile
- `/admin/child/<id>/promote` - Promote child to full account (assigns email, sends invite)

### Profile (login required)
- `/profile` - Edit name and gift delivery email
- `/change-password` - Change password

## Templates

17 templates in `app/templates/`:

- `base.html` - Layout with navbar (admin sees "Users" and "Invite" links)
- `index.html` - Landing page
- `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`
- `dashboard.html` - Family member grid with list links
- `my_list.html` - Own list with active/received tabs, child list sidebar
- `view_list.html` - Other person's list with claim/unclaim buttons
- `item_form.html` - Add/edit item form with image preview
- `invite_user.html` - Admin invite form (shows invite URL after success)
- `profile.html`, `change_password.html`
- `add_child.html` - Add child profile form
- `help.html`, `help_guide.html`

3 admin templates in `app/templates/admin/`:

- `user_management.html` - Active and archived user lists
- `archive_user.html` - Archive confirmation with warnings
- `promote_child.html` - Promote child form (enter email)

## Email System (app/email.py)

Uses SendGrid HTTP API directly (not Flask-Mail SMTP). Three email types:

1. **Invite email** - Sent when admin invites a new member. Contains setup link.
2. **Password reset email** - Sent on forgot-password request.
3. **Item deleted notification** - Sent to all claimers when an item is deleted.

API key comes from SENDGRID_API_KEY or MAIL_PASSWORD env var. Sender from MAIL_DEFAULT_SENDER.

## Forms (app/forms.py)

12 WTForms classes: LoginForm, RegistrationForm, InviteUserForm (validates email uniqueness), PasswordResetRequestForm, PasswordResetForm, ProfileForm, ChangeEmailForm, ChangePasswordForm, ItemForm (with allow_multiple toggle and image_url), AddChildForm, PromoteChildForm, ArchiveUserForm, DeleteUserForm.

## Image Auto-Fetch Feature

When adding/editing items with a product URL, the backend fetches the page and extracts images from og:image, twitter:image, or itemprop="image" meta tags. Follows redirects (handles Amazon sponsored links). 15-second timeout. Silent failure. Manual image URL override available. Images display at 200x200px with rounded corners and onerror hiding.

## User Management System

- **Archive:** Sets is_active=False. User cannot log in, hidden from dashboard, data preserved, reversible.
- **Restore:** Sets is_active=True. User can log in again.
- **Promote child:** Converts child profile to full account. Assigns real email, removes parent management, sends invite. Preserves all wishlist data and user ID. Not reversible.
- **Delete:** Permanent. Requires admin password + email/name confirmation. CASCADE deletes related data.

Safety guards: cannot archive last admin, cannot archive parent with active children, delete requires archived status first.

## Configuration (config.py)

Base Config loads from .env file. DevelopmentConfig uses SQLite (dev.db). ProductionConfig uses DATABASE_URL from environment (fixes postgres:// to postgresql:// for Railway). App factory pattern in `app/__init__.py`.

## Deployment

Railway auto-deploys from GitHub. Procfile: `web: gunicorn run:app`. Database migrations are manual SQL ALTER TABLE statements (no Flask-Migrate). Two migration sets documented: user management fields and image_url column.

## File Structure

```
gift-exchange/
  app/
    __init__.py        # App factory, extension init, blueprint registration
    models.py          # User, List, Item, Claim models
    routes.py          # All route handlers (~1020 lines)
    forms.py           # 12 WTForms classes
    email.py           # SendGrid email functions
    templates/         # 17 Jinja2 templates + 3 admin templates
  config.py            # Dev/Prod config classes
  run.py               # Entry point, shell context
  create_admin.py      # CLI script for first admin setup
  requirements.txt     # 12 Python packages
  Procfile             # gunicorn run:app
  .env.example         # Environment variable template
  redesigned-templates.zip  # Packaged template redesign (not yet applied)
```

## Environment Variables

Required for production: FLASK_ENV, SECRET_KEY, DATABASE_URL (auto-set by Railway), MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD (SendGrid API key), MAIL_DEFAULT_SENDER. Optional: SENDGRID_API_KEY, APP_NAME.

## Notes

- The `redesigned-templates.zip` file exists in the repo root but has not been applied to the templates directory.
- No Flask-Migrate. Schema changes require manual SQL.
- `datetime.utcnow()` used throughout (no timezone awareness).
- The app name in code/emails is "Power Family Wishlist" (configurable via APP_NAME env var).
