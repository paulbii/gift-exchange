# Family Gift Exchange App

A web application for coordinating family gift-giving. Create wishlists, claim gifts to purchase, and keep surprises secret!

## Features

- 🎁 **Create wishlists** with items, links, prices, and notes
- 👀 **Privacy-first**: List owners never see what's been claimed
- ✅ **Prevent duplicates** by claiming items
- 👨‍👩‍👧‍👦 **Parent-managed** child profiles
- 📧 **Email delivery addresses** for digital gifts
- 📱 **Mobile-responsive** design with Bootstrap 5
- 🔢 **Priority ordering** - reorder your list by importance
- 🎯 **Multi-claim support** for items like gift cards

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL (or SQLite for local dev)
- **Frontend**: Bootstrap 5, Jinja2 templates
- **Email**: Flask-Mail (SendGrid recommended for production)
- **Hosting**: Railway (recommended) or any Python hosting

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.9 or higher
- pip (Python package installer)
- Git

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd gift-exchange
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your settings
# For local development, you can use these minimal settings:
```

Example `.env` for local development:
```
FLASK_ENV=development
SECRET_KEY=your-random-secret-key-here
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

**Note on Gmail**: 
- You need to use an "App Password" not your regular Gmail password
- Enable 2FA on your Google account
- Generate app password at: https://myaccount.google.com/apppasswords

### 5. Initialize Database

```bash
# The database will be created automatically when you first run the app
# It will create a file called dev.db in your project folder
```

### 6. Run the App

```bash
python run.py
```

Visit `http://localhost:5000` in your browser!

### 7. Create First Admin User

Since this is your first time running the app, you'll need to create an admin user manually:

```bash
# Open Python shell
python
```

```python
from app import create_app, db
from app.models import User, List

app = create_app('development')
with app.app_context():
    # Create admin user
    admin = User(
        email='your-email@example.com',
        name='Your Name',
        is_admin=True
    )
    admin.set_password('your-password')
    
    db.session.add(admin)
    db.session.commit()
    
    # Create admin's list
    admin_list = List(
        owner_id=admin.id,
        name=f"{admin.name}'s List"
    )
    db.session.add(admin_list)
    db.session.commit()
    
    print("Admin user created!")
    exit()
```

Now you can log in as admin and invite your family!

---

## Deployment to Railway

Railway is the recommended hosting platform - it's simple and has a generous free tier.

### Prerequisites

- GitHub account
- Railway account (sign up at https://railway.app)

### Step 1: Push Code to GitHub

```bash
# Initialize git if you haven't
git init
git add .
git commit -m "Initial commit"

# Create a new repository on GitHub, then:
git remote add origin <your-github-repo-url>
git push -u origin main
```

### Step 2: Deploy to Railway

1. **Go to Railway**: https://railway.app
2. **Click "New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Authorize Railway** to access your GitHub
5. **Select your gift-exchange repository**

### Step 3: Add PostgreSQL Database

1. In your Railway project, click **"New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Railway will automatically create a database and set the `DATABASE_URL` variable

### Step 4: Configure Environment Variables

In Railway project settings → Variables, add:

```
FLASK_ENV=production
SECRET_KEY=<generate a random secret key>
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=<your-sendgrid-api-key>
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
APP_NAME=Family Gift Exchange
```

**To generate a SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 5: Deploy

Railway will automatically deploy your app! You'll get a URL like `your-app.railway.app`

### Step 6: Create Admin User on Production

Use Railway's "Deploy Logs" console or connect via Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run shell
railway run python
```

Then create admin user same as local development section above.

---

## Email Setup (SendGrid)

For production, use SendGrid for reliable email delivery:

1. **Sign up** at https://sendgrid.com (free tier: 100 emails/day)
2. **Verify your sender email** in SendGrid settings
3. **Create an API key** in Settings → API Keys
4. **Set environment variables**:
   ```
   MAIL_SERVER=smtp.sendgrid.net
   MAIL_PORT=587
   MAIL_USERNAME=apikey
   MAIL_PASSWORD=<your-api-key>
   ```

---

## Usage Guide

### For Administrators

1. **Log in** as admin
2. **Invite family members**: Click "Invite" → Enter name & email
3. They'll receive an email with setup link
4. **Manage settings** in your profile

### For Regular Users

1. **Receive invitation email** from admin
2. **Click link** and set your password
3. **Add items to your list**: 
   - Click "My List"
   - Click "Add Item"
   - Fill in details (title required, rest optional)
   - Set priority with up/down arrows
4. **Claim gifts from others**:
   - Click on family member's name
   - Browse their list
   - Click "Claim" on items you'll buy
5. **View only available items**: Toggle filter on others' lists

### For Parents

1. **Add child profile**: Click "Add Child Profile"
2. **Manage child's list**: Same as your own list
3. **Graduate child** when ready (admin only): Convert to full user account

---

## Project Structure

```
gift-exchange/
├── app/
│   ├── __init__.py          # Flask app initialization
│   ├── models.py            # Database models
│   ├── routes.py            # URL routes and logic
│   ├── forms.py             # WTForms definitions
│   ├── email.py             # Email utilities
│   ├── templates/           # HTML templates
│   └── static/              # CSS, JS, images
├── config.py                # Configuration settings
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
├── Procfile                 # Railway deployment config
├── .env.example            # Environment variables template
└── README.md               # This file
```

---

## Common Tasks

### Reset Database (Development Only!)

```bash
# Delete the database file
rm dev.db

# Restart the app - it will create a new empty database
python run.py
```

### Access Database Console

```bash
# Open Flask shell
flask shell

# Query users
>>> User.query.all()

# Query lists
>>> List.query.all()

# etc.
```

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

---

## Troubleshooting

### "No module named 'app'"

Make sure you're in the project root directory and your virtual environment is activated.

### Email not sending

- Check your MAIL_USERNAME and MAIL_PASSWORD are correct
- For Gmail, make sure you're using an App Password (not regular password)
- Check spam folder

### "Internal Server Error" on Railway

- Check Railway logs: Project → Deployments → View Logs
- Common issues:
  - Missing environment variables
  - Database connection issues
  - SECRET_KEY not set

### Database connection fails on Railway

Railway's DATABASE_URL is automatically set. If you see errors:
- Make sure PostgreSQL service is running
- Check that DATABASE_URL variable exists in Railway settings

### Can't claim items

- Make sure you're not trying to claim from your own list
- Check if item is already at max claims
- Verify you're logged in

---

## Security Notes

- **Never commit .env file** to git (it's in .gitignore)
- **Use strong SECRET_KEY** in production
- **Use HTTPS** in production (Railway provides this automatically)
- **Keep dependencies updated** for security patches

---

## Development Tips

### Debugging

Set `DEBUG = True` in development (already set in DevelopmentConfig)

### Database Migrations

For database schema changes, you can use Flask-Migrate (not included in starter):

```bash
pip install Flask-Migrate
```

Or manually drop and recreate tables (development only).

### Adding Features

1. Update models in `app/models.py`
2. Create forms in `app/forms.py`
3. Add routes in `app/routes.py`
4. Create templates in `app/templates/`

---

## Future Enhancements

See the PRD for potential features:
- Multiple lists per user
- Multiple family groups
- Item images
- Budget tracking
- Shopping list export
- Calendar integration

---

## Support

For issues or questions:
1. Check this README
2. Review the PRD document
3. Check Railway logs (for deployment issues)
4. Search Flask documentation: https://flask.palletsprojects.com/

---

## License

This is a personal/family project. Use and modify as you wish!
