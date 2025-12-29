from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
from app import db
from app.models import User, List, Item, Claim
from app.forms import (LoginForm, RegistrationForm, InviteUserForm, PasswordResetRequestForm,
                       PasswordResetForm, ProfileForm, ChangeEmailForm, ChangePasswordForm,
                       ItemForm, AddChildForm)
from app.email import send_invite_email, send_password_reset_email, send_item_deleted_notification

main = Blueprint('main', __name__)


# ==================== PUBLIC ROUTES ====================

@main.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        flash('Invalid email or password.', 'danger')
    
    return render_template('login.html', form=form)


@main.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@main.route('/register/<token>', methods=['GET', 'POST'])
def register(token):
    """Complete registration from invite token"""
    user = User.query.filter_by(invite_token=token).first()
    
    if not user:
        flash('Invalid or expired invitation link.', 'danger')
        return redirect(url_for('main.index'))
    
    if user.invite_token_expires < datetime.utcnow():
        flash('This invitation has expired. Please request a new one.', 'danger')
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    
    # Pre-populate name field with invited name (GET request only)
    if request.method == 'GET':
        form.name.data = user.name
    
    if form.validate_on_submit():
        user.name = form.name.data
        user.set_password(form.password.data)
        user.invite_token = None
        user.invite_token_expires = None
        
        # Create user's personal list
        user_list = List(
            owner_id=user.id,
            name=f"{user.name}'s List"
        )
        db.session.add(user_list)
        db.session.commit()
        
        login_user(user)
        flash('Welcome! Your account has been created.', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('register.html', form=form, email=user.email, invited_name=user.name)


@main.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            token = user.generate_password_reset_token()
            db.session.commit()
            send_password_reset_email(user, token)
        # Always show success message (don't reveal if email exists)
        flash('If that email is registered, you will receive password reset instructions.', 'info')
        return redirect(url_for('main.login'))
    
    return render_template('forgot_password.html', form=form)


@main.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    user = User.query.filter_by(password_reset_token=token).first()
    
    if not user or user.password_reset_expires < datetime.utcnow():
        flash('Invalid or expired password reset link.', 'danger')
        return redirect(url_for('main.forgot_password'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.session.commit()
        
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('reset_password.html', form=form)


# ==================== DASHBOARD & LISTS ====================

@main.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard showing all family members and their lists"""
    # Get all users who have completed setup (have a password)
    family_members = User.query.filter(User.password_hash.isnot(None)).all()
    
    # Get lists with owner information
    lists = List.query.join(User, List.owner_id == User.id).filter(
        User.password_hash.isnot(None)
    ).all()
    
    return render_template('dashboard.html', family_members=family_members, lists=lists)


@main.route('/my-list')
@login_required
def my_list():
    """View and manage your own list"""
    user_list = current_user.owned_list
    
    if not user_list:
        # Create list if it doesn't exist
        user_list = List(
            owner_id=current_user.id,
            name=f"{current_user.name}'s List"
        )
        db.session.add(user_list)
        db.session.commit()
    
    # Get managed child lists
    managed_lists = List.query.filter_by(managed_by_id=current_user.id).all()
    
    return render_template('my_list.html', list=user_list, managed_lists=managed_lists)


@main.route('/manage-child-list/<int:list_id>')
@login_required
def manage_child_list(list_id):
    """Manage a child's list"""
    child_list = List.query.get_or_404(list_id)
    
    # Check if current user manages this list
    if not current_user.can_manage_list(child_list):
        flash('You do not have permission to manage this list.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Don't allow managing your own list here (use my_list for that)
    if child_list.owner_id == current_user.id:
        return redirect(url_for('main.my_list'))
    
    # Get managed child lists for the sidebar
    managed_lists = List.query.filter_by(managed_by_id=current_user.id).all()
    
    return render_template('my_list.html', list=child_list, managed_lists=managed_lists, is_child_list=True)


@main.route('/list/<int:list_id>')
@login_required
def view_list(list_id):
    """View someone else's list"""
    view_list_obj = List.query.get_or_404(list_id)
    
    # Check if this is the user's own list or a list they manage
    if current_user.can_manage_list(view_list_obj):
        return redirect(url_for('main.my_list'))
    
    # Get filter preference from query string
    show_available_only = request.args.get('available', 'false') == 'true'
    
    items = view_list_obj.items
    if show_available_only:
        # Filter to only show items that can still be claimed
        items = [item for item in items if item.is_available()]
    
    total_items = len(view_list_obj.items)
    shown_items = len(items)
    
    return render_template('view_list.html', 
                         list=view_list_obj, 
                         items=items,
                         show_available_only=show_available_only,
                         total_items=total_items,
                         shown_items=shown_items)


# ==================== ITEM MANAGEMENT ====================

@main.route('/item/add/<int:list_id>', methods=['GET', 'POST'])
@login_required
def add_item(list_id):
    """Add item to a list"""
    list_obj = List.query.get_or_404(list_id)
    
    # Check permission
    if not current_user.can_manage_list(list_obj):
        flash('You do not have permission to add items to this list.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = ItemForm()
    if form.validate_on_submit():
        # Calculate position (append to end)
        max_position = db.session.query(db.func.max(Item.position)).filter_by(list_id=list_id).scalar() or 0
        
        # Determine max_claims
        max_claims_value = 1
        if form.allow_multiple.data:
            max_claims_value = form.max_claims.data if form.max_claims.data else 999
        
        item = Item(
            list_id=list_id,
            title=form.title.data,
            description=form.description.data,
            url=form.url.data,
            price=form.price.data,
            notes=form.notes.data,
            max_claims=max_claims_value,
            position=max_position + 1,
            created_by_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        
        flash('Item added to list!', 'success')
        return redirect(url_for('main.my_list'))
    
    return render_template('item_form.html', form=form, list=list_obj, edit=False)


@main.route('/item/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """Edit an item"""
    item = Item.query.get_or_404(item_id)
    
    # Check permission
    if not current_user.can_manage_list(item.list):
        flash('You do not have permission to edit this item.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = ItemForm(obj=item)
    
    # Pre-populate allow_multiple checkbox
    if request.method == 'GET':
        form.allow_multiple.data = item.max_claims > 1
        if item.max_claims > 1 and item.max_claims < 999:
            form.max_claims.data = item.max_claims
    
    if form.validate_on_submit():
        item.title = form.title.data
        item.description = form.description.data
        item.url = form.url.data
        item.price = form.price.data
        item.notes = form.notes.data
        
        # Update max_claims
        if form.allow_multiple.data:
            item.max_claims = form.max_claims.data if form.max_claims.data else 999
        else:
            item.max_claims = 1
        
        db.session.commit()
        flash('Item updated!', 'success')
        return redirect(url_for('main.my_list'))
    
    return render_template('item_form.html', form=form, list=item.list, edit=True, item=item)


@main.route('/item/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """Delete an item"""
    item = Item.query.get_or_404(item_id)
    
    # Check permission
    if not current_user.can_manage_list(item.list):
        flash('You do not have permission to delete this item.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Notify anyone who claimed this item
    if item.claims:
        send_item_deleted_notification(item)
    
    list_id = item.list_id
    db.session.delete(item)
    db.session.commit()
    
    # Reorder remaining items
    remaining_items = Item.query.filter_by(list_id=list_id).order_by(Item.position).all()
    for idx, remaining_item in enumerate(remaining_items):
        remaining_item.position = idx + 1
    db.session.commit()
    
    flash('Item deleted.', 'success')
    return redirect(url_for('main.my_list'))


@main.route('/item/move/<int:item_id>/<direction>')
@login_required
def move_item(item_id, direction):
    """Move item up or down in priority"""
    item = Item.query.get_or_404(item_id)
    
    # Check permission
    if not current_user.can_manage_list(item.list):
        flash('You do not have permission to reorder this list.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get adjacent item
    if direction == 'up':
        adjacent = Item.query.filter(
            Item.list_id == item.list_id,
            Item.position < item.position
        ).order_by(Item.position.desc()).first()
    elif direction == 'down':
        adjacent = Item.query.filter(
            Item.list_id == item.list_id,
            Item.position > item.position
        ).order_by(Item.position.asc()).first()
    else:
        flash('Invalid direction.', 'danger')
        return redirect(url_for('main.my_list'))
    
    if adjacent:
        # Swap positions
        item.position, adjacent.position = adjacent.position, item.position
        db.session.commit()
    
    return redirect(url_for('main.my_list'))


# ==================== CLAIM MANAGEMENT ====================

@main.route('/claim/<int:item_id>', methods=['POST'])
@login_required
def claim_item(item_id):
    """Claim an item"""
    item = Item.query.get_or_404(item_id)
    
    # Cannot claim from own/managed lists
    if current_user.can_manage_list(item.list):
        flash('You cannot claim items from your own list.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Check if already claimed by this user
    if item.is_claimed_by(current_user):
        flash('You have already claimed this item.', 'info')
        return redirect(url_for('main.view_list', list_id=item.list_id))
    
    # Check if item is still available
    if not item.is_available():
        flash('This item has already been claimed by the maximum number of people.', 'warning')
        return redirect(url_for('main.view_list', list_id=item.list_id))
    
    # Create claim
    claim = Claim(item_id=item_id, claimed_by_id=current_user.id)
    db.session.add(claim)
    db.session.commit()
    
    flash('Item claimed! The list owner cannot see this.', 'success')
    return redirect(url_for('main.view_list', list_id=item.list_id))


@main.route('/unclaim/<int:item_id>', methods=['POST'])
@login_required
def unclaim_item(item_id):
    """Unclaim an item"""
    item = Item.query.get_or_404(item_id)
    claim = item.get_user_claim(current_user)
    
    if not claim:
        flash('You have not claimed this item.', 'warning')
        return redirect(url_for('main.view_list', list_id=item.list_id))
    
    db.session.delete(claim)
    db.session.commit()
    
    flash('Item unclaimed.', 'info')
    return redirect(url_for('main.view_list', list_id=item.list_id))


# ==================== ADMIN FUNCTIONS ====================

@main.route('/admin/invite', methods=['GET', 'POST'])
@login_required
def invite_user():
    """Admin: Invite new family member"""
    if not current_user.is_admin:
        flash('Only administrators can invite new members.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = InviteUserForm()
    invite_url = None  # Will be set after successful invite
    
    if form.validate_on_submit():
        # Create user with invite token
        user = User(
            email=form.email.data.lower(),
            name=form.name.data,  # Pre-populate with invited name (they can change it during registration)
            invited_by_id=current_user.id
        )
        user.set_password('temporary')  # Will be changed during registration
        token = user.generate_invite_token()
        
        db.session.add(user)
        db.session.commit()
        
        # Generate invite URL
        invite_url = url_for('main.register', token=token, _external=True)
        
        # Send invitation email
        send_invite_email(user, token, form.name.data)
        
        flash(f'Invitation sent to {form.email.data}! You can also share the link below.', 'success')
        # Don't redirect - stay on page to show the invite link
    
    return render_template('invite_user.html', form=form, invite_url=invite_url)


# ==================== PROFILE & SETTINGS ====================

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and edit profile"""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.gift_delivery_email = form.gift_delivery_email.data or None
        db.session.commit()
        
        flash('Profile updated!', 'success')
        return redirect(url_for('main.profile'))
    
    return render_template('profile.html', form=form)


@main.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.profile'))
    
    return render_template('change_password.html', form=form)


# ==================== CHILD MANAGEMENT ====================

@main.route('/child/add', methods=['GET', 'POST'])
@login_required
def add_child():
    """Add a child profile"""
    form = AddChildForm()
    
    if form.validate_on_submit():
        # Create a dummy email for the child (will be changed when graduated)
        child_email = f"child_{current_user.id}_{datetime.utcnow().timestamp()}@placeholder.local"
        
        child_user = User(
            email=child_email,
            name=form.name.data
        )
        child_user.set_password('placeholder')  # Will be changed when graduated
        
        db.session.add(child_user)
        db.session.flush()  # Get the child_user.id
        
        # Create child's list, managed by parent
        child_list = List(
            owner_id=child_user.id,
            managed_by_id=current_user.id,
            name=f"{form.name.data}'s List"
        )
        db.session.add(child_list)
        db.session.commit()
        
        flash(f'Child profile created for {form.name.data}!', 'success')
        return redirect(url_for('main.my_list'))
    
    return render_template('add_child.html', form=form)


# Note: Graduate child functionality would go here (convert child to full user)
# This would involve sending an invite email and transferring ownership
