from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import secrets


class User(UserMixin, db.Model):
    """User model for authentication and profile"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    gift_delivery_email = db.Column(db.String(120))  # Optional, defaults to email
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Tokens for various auth flows
    invite_token = db.Column(db.String(100), unique=True)
    invite_token_expires = db.Column(db.DateTime)
    password_reset_token = db.Column(db.String(100), unique=True)
    password_reset_expires = db.Column(db.DateTime)
    email_verification_token = db.Column(db.String(100), unique=True)
    email_verification_expires = db.Column(db.DateTime)
    
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Archiving fields
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    archived_at = db.Column(db.DateTime)
    archived_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    archived_reason = db.Column(db.Text)
    
    # Child promotion fields
    promoted_from_child = db.Column(db.Boolean, default=False, nullable=False)
    promoted_at = db.Column(db.DateTime)
    promoted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    owned_list = db.relationship('List', foreign_keys='List.owner_id', backref='owner', uselist=False, cascade='all, delete-orphan')
    managed_lists = db.relationship('List', foreign_keys='List.managed_by_id', backref='manager')
    claims = db.relationship('Claim', backref='claimer', cascade='all, delete-orphan')
    invited_users = db.relationship('User', foreign_keys=[invited_by_id], backref=db.backref('invited_by', remote_side=[id]))
    archived_by = db.relationship('User', foreign_keys=[archived_by_id], remote_side=[id], backref='archived_users')
    promoted_by = db.relationship('User', foreign_keys=[promoted_by_id], remote_side=[id], backref='promoted_users')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_invite_token(self):
        """Generate secure invite token"""
        self.invite_token = secrets.token_urlsafe(32)
        self.invite_token_expires = datetime.utcnow() + timedelta(hours=48)
        return self.invite_token
    
    def generate_password_reset_token(self):
        """Generate secure password reset token"""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
        return self.password_reset_token
    
    def get_delivery_email(self):
        """Get email for gift delivery (falls back to account email)"""
        return self.gift_delivery_email or self.email
    
    def can_manage_list(self, list_obj):
        """Check if user can manage a list (owns it or is the parent manager)"""
        return list_obj.owner_id == self.id or list_obj.managed_by_id == self.id
    
    def can_see_claims(self, list_obj):
        """Check if user can see claim status on a list (cannot see own/managed lists)"""
        return not self.can_manage_list(list_obj)
    
    def is_child_profile(self):
        """Check if this is a child profile (managed by someone, no email/password)"""
        return self.owned_list and self.owned_list.managed_by_id is not None
    
    def has_managed_children(self):
        """Check if user manages any child profiles"""
        return len(self.managed_lists) > 0
    
    def archive(self, by_user, reason=""):
        """Archive this user"""
        self.is_active = False
        self.archived_at = datetime.utcnow()
        self.archived_by_id = by_user.id
        self.archived_reason = reason
    
    def restore(self):
        """Restore an archived user"""
        self.is_active = True
        self.archived_at = None
        self.archived_by_id = None
        self.archived_reason = None
    
    def __repr__(self):
        return f'<User {self.email}>'


class List(db.Model):
    """Wishlist model"""
    __tablename__ = 'lists'
    
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    managed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # For parent-managed child lists
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    items = db.relationship('Item', backref='list', cascade='all, delete-orphan', order_by='Item.position')
    
    def __repr__(self):
        return f'<List {self.name}>'


class Item(db.Model):
    """Wishlist item model"""
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('lists.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(2000))  # Increased for long URLs with tracking parameters
    price = db.Column(db.Numeric(10, 2))  # Store as decimal for currency
    notes = db.Column(db.Text)  # Only visible to gift-givers
    max_claims = db.Column(db.Integer, default=1, nullable=False)  # 1 = single claim, higher = multiple allowed
    position = db.Column(db.Integer, nullable=False)  # For priority ordering
    received_at = db.Column(db.DateTime)  # NULL = active, has date = received/archived
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    claims = db.relationship('Claim', backref='item', cascade='all, delete-orphan')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def is_received(self):
        """Check if item has been received/archived"""
        return self.received_at is not None
    
    def claim_count(self):
        """Get number of current claims"""
        return len(self.claims)
    
    def is_available(self):
        """Check if item can still be claimed"""
        return self.claim_count() < self.max_claims
    
    def is_claimed_by(self, user):
        """Check if specific user has claimed this item"""
        return any(claim.claimed_by_id == user.id for claim in self.claims)
    
    def get_user_claim(self, user):
        """Get the claim object for a specific user"""
        for claim in self.claims:
            if claim.claimed_by_id == user.id:
                return claim
        return None
    
    def __repr__(self):
        return f'<Item {self.title}>'


class Claim(db.Model):
    """Claim model - represents a user claiming an item to purchase"""
    __tablename__ = 'claims'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    claimed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    claimed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Unique constraint: user can only claim an item once
    __table_args__ = (
        db.UniqueConstraint('item_id', 'claimed_by_id', name='unique_claim_per_user'),
    )
    
    def __repr__(self):
        return f'<Claim item_id={self.item_id} by user_id={self.claimed_by_id}>'


# Import timedelta at the top after datetime
from datetime import timedelta
