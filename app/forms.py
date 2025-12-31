from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, DecimalField, IntegerField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, NumberRange, URL
from app.models import User


class LoginForm(FlaskForm):
    """User login form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class RegistrationForm(FlaskForm):
    """New user registration (for invited users)"""
    name = StringField('Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Complete Setup')


class InviteUserForm(FlaskForm):
    """Admin form to invite new family members"""
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Invitation')
    
    def validate_email(self, field):
        """Check if email already exists"""
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('This email is already registered.')


class PasswordResetRequestForm(FlaskForm):
    """Request password reset"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')


class PasswordResetForm(FlaskForm):
    """Reset password with token"""
    password = PasswordField('New Password', validators=[DataRequired()])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


class ProfileForm(FlaskForm):
    """Edit user profile"""
    name = StringField('Name', validators=[DataRequired()])
    gift_delivery_email = StringField('Gift Delivery Email', validators=[Optional(), Email()])
    submit = SubmitField('Save Changes')


class ChangeEmailForm(FlaskForm):
    """Change account email"""
    new_email = StringField('New Email', validators=[DataRequired(), Email()])
    password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Change Email')
    
    def validate_new_email(self, field):
        """Check if email already exists"""
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('This email is already in use.')


class ChangePasswordForm(FlaskForm):
    """Change password"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    new_password2 = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')


class ItemForm(FlaskForm):
    """Add or edit wishlist item"""
    title = StringField('Item Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    url = StringField('Link/URL', validators=[Optional(), URL()])
    image_url = StringField('Image URL', validators=[Optional(), URL()])
    price = DecimalField('Price', validators=[Optional()], places=2)
    allow_multiple = BooleanField('Allow multiple people to buy this')
    max_claims = IntegerField('How many?', validators=[Optional(), NumberRange(min=1)], default=1)
    submit = SubmitField('Save Item')


class AddChildForm(FlaskForm):
    """Add a child profile (parent-managed)"""
    name = StringField('Child\'s Name', validators=[DataRequired()])
    submit = SubmitField('Add Child')


class PromoteChildForm(FlaskForm):
    """Promote child profile to full account"""
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    send_invitation = BooleanField('Send invitation email now', default=True)
    submit = SubmitField('Promote to Full Account')


class ArchiveUserForm(FlaskForm):
    """Archive a user account"""
    reason = TextAreaField('Reason for archiving (optional)')
    confirm = BooleanField('I understand this will hide the user from the dashboard', validators=[DataRequired()])
    submit = SubmitField('Archive User')


class DeleteUserForm(FlaskForm):
    """Permanently delete a user (scary!)"""
    admin_password = PasswordField('Your Admin Password', validators=[DataRequired()])
    confirm_email = StringField('Type user\'s email to confirm', validators=[DataRequired()])
    submit = SubmitField('Permanently Delete User')

