# User Management System Deployment Guide

## Overview:
Complete admin user management system with:
- ✅ Archive/restore users
- ✅ Archive/restore child profiles
- ✅ Promote child profiles to full accounts
- ✅ Permanent deletion (with safeguards)
- ✅ Comprehensive admin interface

---

## What's New:

### For Admins:
1. **User Management Dashboard** (/admin/users)
   - View all active and archived users
   - See who manages which children
   - Track promotions and archiving history

2. **Archive Users**
   - Prevents login
   - Hides from dashboard
   - Preserves all data
   - Fully reversible

3. **Promote Children**
   - Convert child profile → full account
   - Preserves entire wishlist history
   - Sends invitation email
   - Seamless transition

4. **Safety Features**
   - Can't archive last admin
   - Can't archive parent with active children
   - Permanent deletion requires password confirmation

---

## Files Changed (5):

1. ✅ **app/models.py** - Added archiving and promotion fields
2. ✅ **app/forms.py** - Added PromoteChildForm, ArchiveUserForm, DeleteUserForm
3. ✅ **app/routes.py** - Added 7 new admin routes
4. ✅ **app/templates/base.html** - Added "Users" link to admin navbar
5. ✅ **NEW: app/templates/admin/** - 3 new admin templates

---

## Database Migration Required:

### Step 1: Connect to Railway Database

```bash
railway connect Postgres
```

### Step 2: Run Migration SQL

```sql
-- Add archiving fields to users table
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN archived_at TIMESTAMP;
ALTER TABLE users ADD COLUMN archived_by_id INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN archived_reason TEXT;

-- Add child promotion fields
ALTER TABLE users ADD COLUMN promoted_from_child BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE users ADD COLUMN promoted_at TIMESTAMP;
ALTER TABLE users ADD COLUMN promoted_by_id INTEGER REFERENCES users(id);

-- Create index for faster queries
CREATE INDEX idx_users_is_active ON users(is_active);
```

### Step 3: Verify

```sql
\d users
```

You should see the new columns listed.

### Step 4: Exit

```
\q
```

---

## Deployment Steps:

### Step 1: Run Database Migration (above)
**Do this FIRST before deploying code!**

### Step 2: Replace Files Locally

```bash
cd gift-exchange

# Create admin templates directory
mkdir -p app/templates/admin

# Replace these files:
# - app/models.py
# - app/forms.py
# - app/routes.py
# - app/templates/base.html
# - app/templates/admin/user_management.html (NEW)
# - app/templates/admin/archive_user.html (NEW)
# - app/templates/admin/promote_child.html (NEW)
```

### Step 3: Push to GitHub

```bash
git add app/models.py app/forms.py app/routes.py app/templates/base.html app/templates/admin/
git commit -m "Add comprehensive user management system with archive and promote features"
git push
```

### Step 4: Wait for Railway (~2 minutes)
Railway auto-deploys

---

## Testing After Deployment:

### Test 1: Access User Management
1. Log in as admin (paul@love2tap.com)
2. Click **"Users"** in navbar
3. Should see User Management dashboard
4. Should see all active users listed

### Test 2: Archive a Test User (if you have one)
1. On User Management page
2. Find a test user
3. Click **"Archive"**
4. Read the warnings
5. Check the confirmation box
6. Add optional reason
7. Click **"Archive User"**
8. User should move to "Archived Users" section
9. Try logging in as that user → Should see "account has been archived" message

### Test 3: Restore Archived User
1. Find user in "Archived Users" section
2. Click **"Restore"**
3. User should move back to "Active Users"
4. User should be able to log in again

### Test 4: Promote Child Profile
1. Find a user who manages children
2. Under their name, find managed child
3. Click **"Promote"**
4. Enter child's email address
5. Keep "Send invitation email now" checked
6. Click **"Promote to Full Account"**
7. Child should disappear from "Children You Manage"
8. Child should appear as independent user in Active Users
9. Child should receive invitation email
10. Child can set password and log in independently

### Test 5: Archive Child Profile
1. Find a user who manages children
2. Under their name, find managed child
3. Click **"Archive"**
4. Child should disappear from dashboard
5. Still visible in User Management under parent

### Test 6: Prevent Parent Archiving
1. Try to archive a user who manages active children
2. Should see error: "Cannot Archive!"
3. Should list which children need handling first

### Test 7: Dashboard Filters
1. Archive a user
2. Log out
3. Log in as different family member
4. Go to dashboard
5. Archived user should NOT appear
6. Only active users visible

---

## How It Works:

### Database Schema:

**User Table (new fields):**
```sql
is_active BOOLEAN (default TRUE)
archived_at TIMESTAMP (NULL when active)
archived_by_id INTEGER (who archived them)
archived_reason TEXT (why archived)

promoted_from_child BOOLEAN (was this a child?)
promoted_at TIMESTAMP (when promoted)
promoted_by_id INTEGER (who promoted them)
```

### Archive Flow:

```
Active User
  ↓ Click "Archive"
  ↓ Confirm action
is_active = False
archived_at = NOW
archived_by_id = admin ID
  ↓ Results:
  - Can't log in
  - Not on dashboard
  - Data preserved
  - Reversible
```

### Promote Flow:

```
Child Profile
  - No email
  - Managed by parent
  - Can't log in
  ↓ Click "Promote"
  ↓ Enter email
  ↓ Send invitation
  
Full Account
  - Has email
  - Independent
  - Can log in
  - Same wishlist (preserved!)
  - Same user ID (integrity!)
```

---

## Admin Interface Overview:

### User Management Dashboard Shows:

**Active Users:**
- Name, email, created date
- Admin badge
- Promoted badge (if was child)
- Children they manage
- Actions: View, Archive

**For Each Child:**
- Promote button
- Archive button

**Archived Users:**
- Name, email (if not child)
- Archived date and by whom
- Reason for archiving
- Actions: Restore, Delete

---

## Safety Features:

### ✅ Archive Protections:
1. **Can't archive last admin** - Prevents lockout
2. **Can't archive if manages children** - Must handle children first
3. **Confirmation required** - Must check box

### ✅ Promotion Protections:
1. **Email uniqueness** - Can't use existing email
2. **Preserves history** - All data stays intact
3. **Same user ID** - Database relationships preserved

### ✅ Delete Protections:
1. **Only archived users** - Can't delete active users directly
2. **Admin password required** - Confirms it's really admin
3. **Email confirmation** - Must type exact email/name
4. **Scary warnings** - Very clear about consequences

---

## Use Cases:

### Scenario 1: Kid Graduates
```
Emma (age 8) → Child profile managed by Mom
[Time passes]
Emma (age 13) → Ready for own account

Admin clicks "Promote"
Enters emma@example.com
Emma gets invitation email
Sets password
Logs in
Has all her old wishlist items!
Mom can still shop for her
```

### Scenario 2: Test Cleanup
```
Created "Test User" for testing
Worked fine, don't need anymore

Admin clicks "Archive"
Test User hidden from dashboard
Database still has data (safe)
Can restore if needed
```

### Scenario 3: Duplicate Prevention
```
Both parents created profiles for same child
Results in 2 child profiles

Keep one, archive the other
Merge wishlists manually if needed
Dashboard now clean
```

### Scenario 4: User Requests Deletion
```
Family member: "Please delete my account"

Admin archives user first
User disappears from dashboard
User can't log in
Wait a few days (cooling off period)
If still wants deletion:
  Admin goes to archived section
  Enters admin password
  Types email confirmation
  Permanently deletes
```

---

## Important Notes:

**Archiving is Soft Delete:**
- ✅ Data preserved in database
- ✅ Can be undone
- ✅ Safe for testing/mistakes
- ✅ Industry standard approach

**Promotion is Permanent:**
- ⚠️ Can't "demote" back to child
- ⚠️ Child becomes independent
- ✅ But history preserved
- ✅ Parent can still view their list

**Permanent Deletion is Scary:**
- ❌ Cannot be undone
- ❌ All data lost forever
- ❌ Claims on others' lists removed
- ⚠️ Use very sparingly

---

## Edge Cases Handled:

✅ **Last admin protection** - Can't archive yourself if you're the only admin  
✅ **Parent with children** - Must handle children before archiving parent  
✅ **Login prevention** - Archived users get clear message  
✅ **Dashboard filtering** - Only active users visible  
✅ **Email uniqueness** - Can't promote to existing email  
✅ **Password confirmation** - Delete requires admin password  

---

## Future Enhancements (Optional):

### Could Add:
- Bulk archive (select multiple users)
- Transfer child management (move to different parent)
- Archive history log (who archived when)
- Auto-archive after X months inactive
- Export user data before deletion
- Merge duplicate users

### For Now:
The current implementation is comprehensive and safe for family use!

---

**This is a production-ready user management system!** 🎉

Your family now has:
- Clean user administration
- Safe archiving with undo
- Child profile graduation path
- Protection against accidents
- Professional-grade tools
