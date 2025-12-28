from flask import url_for, current_app
from flask_mail import Message
from app import mail


def send_email(subject, recipients, text_body, html_body=None):
    """Send an email"""
    msg = Message(
        subject=subject,
        recipients=recipients if isinstance(recipients, list) else [recipients],
        body=text_body,
        html=html_body
    )
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')


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
