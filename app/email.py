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
    
    subject = f"🎁 Join the Power Family Wishlist!"
    
    text_body = f"""Hi {name},

You've been invited to join the Power Family Wishlist!

No more guessing what people want - everyone creates their own wishlist with the things they'd actually like to receive. You can see what everyone wants, claim items so there are no duplicates, and give gifts you know they'll love.

And the best part? You can't see what's been claimed from YOUR list, so the surprise is still there!

Click the link below to set up your account and add your wishlist:
{invite_url}

This link will expire in 48 hours.

Happy gift giving!
"""
    
    html_body = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #0d6efd;">🎁 Welcome to the Power Family Wishlist!</h2>
    
    <p>Hi {name},</p>
    
    <p>You've been invited to join our family wishlist system!</p>
    
    <p><strong>How it works:</strong></p>
    <ul>
        <li>Create your wishlist with items you'd actually like to receive</li>
        <li>Browse what everyone else wants - no more guessing!</li>
        <li>Claim items to let others know you've got it covered</li>
        <li>Give gifts you know they'll love</li>
    </ul>
    
    <p style="background-color: #f0f8ff; padding: 15px; border-left: 4px solid #0d6efd; margin: 20px 0;">
        <strong>🎉 The best part?</strong> You can't see what's been claimed from YOUR list, so the surprise is still there!
    </p>
    
    <p style="margin: 30px 0;">
        <a href="{invite_url}" style="background-color: #0d6efd; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Set Up Your Account</a>
    </p>
    
    <p><small style="color: #666;">This link will expire in 48 hours.</small></p>
    
    <p>Happy gift giving!</p>
</div>
"""
    
    send_email(subject, user.email, text_body, html_body)


def send_password_reset_email(user, token):
    """Send password reset email"""
    reset_url = url_for('main.reset_password', token=token, _external=True)
    
    subject = "Reset Your Power Family Wishlist Password"
    
    text_body = f"""Hi {user.name},

You requested to reset your password for the Power Family Wishlist.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this, please ignore this email.
"""
    
    html_body = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #0d6efd;">🔑 Reset Your Password</h2>
    
    <p>Hi {user.name},</p>
    
    <p>You requested to reset your password for the Power Family Wishlist.</p>
    
    <p style="margin: 30px 0;">
        <a href="{reset_url}" style="background-color: #0d6efd; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
    </p>
    
    <p><small style="color: #666;">This link will expire in 24 hours.</small></p>
    
    <p><small style="color: #666;">If you didn't request this, please ignore this email.</small></p>
</div>
"""
    
    send_email(subject, user.email, text_body, html_body)


def send_item_deleted_notification(item):
    """Notify users when a claimed item is deleted"""
    for claim in item.claims:
        claimer = claim.claimer
        subject = f"Item Removed from {item.list.owner.name}'s Wishlist"
        
        text_body = f"""Hi {claimer.name},

An item you claimed has been removed from {item.list.owner.name}'s wishlist:

"{item.title}"

You may want to choose a different gift from their list.
"""
        
        html_body = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #dc3545;">⚠️ Item Removed</h2>
    
    <p>Hi {claimer.name},</p>
    
    <p>An item you claimed has been removed from <strong>{item.list.owner.name}'s wishlist</strong>:</p>
    
    <p style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #dc3545;">
        <strong>"{item.title}"</strong>
    </p>
    
    <p>You may want to choose a different gift from their list.</p>
</div>
"""
        
        send_email(subject, claimer.email, text_body, html_body)
