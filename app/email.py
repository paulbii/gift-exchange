from flask import url_for, current_app
import os
import requests


def send_email(subject, recipients, text_body, html_body=None):
    """Send an email using SendGrid HTTP API"""
    # Get SendGrid API key from environment
    api_key = os.environ.get('SENDGRID_API_KEY') or os.environ.get('MAIL_PASSWORD')
    sender = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@giftexchange.com')
    
    if not api_key:
        current_app.logger.error('No SendGrid API key configured')
        return False
    
    # Ensure recipients is a list
    if not isinstance(recipients, list):
        recipients = [recipients]
    
    # Build SendGrid API request
    data = {
        "personalizations": [
            {
                "to": [{"email": email} for email in recipients]
            }
        ],
        "from": {"email": sender},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_body}
        ]
    }
    
    # Add HTML content if provided
    if html_body:
        data["content"].append({"type": "text/html", "value": html_body})
    
    # Send via SendGrid HTTP API
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            current_app.logger.info(f'Email sent successfully to {recipients}')
            return True
        else:
            current_app.logger.error(f'SendGrid error {response.status_code}: {response.text}')
            return False
            
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')
        return False


def send_invite_email(user, token, name):
    """Send invitation email to new user"""
    invite_url = url_for('main.register', token=token, _external=True)
    
    subject = f"You're invited to {current_app.config['APP_NAME']}!"
    
    text_body = f"""Hi {name},

You've been invited to join our family gift exchange!

Click the link below to set up your account:
{invite_url}

This link will expire in 48 hours.

Happy gift giving!
"""
    
    html_body = f"""
<p>Hi {name},</p>

<p>You've been invited to join our family gift exchange!</p>

<p><a href="{invite_url}">Click here to set up your account</a></p>

<p><small>This link will expire in 48 hours.</small></p>

<p>Happy gift giving!</p>
"""
    
    send_email(subject, user.email, text_body, html_body)


def send_password_reset_email(user, token):
    """Send password reset email"""
    reset_url = url_for('main.reset_password', token=token, _external=True)
    
    subject = "Reset Your Password"
    
    text_body = f"""Hi {user.name},

You requested to reset your password for {current_app.config['APP_NAME']}.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this, please ignore this email.
"""
    
    html_body = f"""
<p>Hi {user.name},</p>

<p>You requested to reset your password for {current_app.config['APP_NAME']}.</p>

<p><a href="{reset_url}">Click here to reset your password</a></p>

<p><small>This link will expire in 24 hours.</small></p>

<p>If you didn't request this, please ignore this email.</p>
"""
    
    send_email(subject, user.email, text_body, html_body)


def send_item_deleted_notification(item):
    """Notify users when a claimed item is deleted"""
    for claim in item.claims:
        claimer = claim.claimer
        subject = f"Item Removed from {item.list.owner.name}'s List"
        
        text_body = f"""Hi {claimer.name},

An item you claimed has been removed from {item.list.owner.name}'s wishlist:

"{item.title}"

You may want to choose a different gift.
"""
        
        html_body = f"""
<p>Hi {claimer.name},</p>

<p>An item you claimed has been removed from {item.list.owner.name}'s wishlist:</p>

<p><strong>"{item.title}"</strong></p>

<p>You may want to choose a different gift.</p>
"""
        
        send_email(subject, claimer.email, text_body, html_body)
