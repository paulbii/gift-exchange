"""Regression tests for the 2026-06 bug-fix pass.

Covers:
1. Promote-child invitation email called with correct arguments
2. Registration does not create a duplicate list for promoted children
3. Invited users / child profiles get unguessable placeholder passwords
4. Restoring a received item preserves its image_url
5. Permanent delete requires the user to be archived first
"""
import os
import tempfile

# Must be set before importing app/config (config reads env at import time)
_db_fd, _db_path = tempfile.mkstemp(suffix='.db')
os.environ['DATABASE_URL'] = 'sqlite:///' + _db_path
os.environ['FLASK_ENV'] = 'development'

import pytest

from app import create_app, db
from app.models import User, List, Item, Claim


@pytest.fixture
def app():
    app = create_app('development')
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def make_admin():
    admin = User(email='admin@example.com', name='Admin', is_admin=True)
    admin.set_password('admin-pass')
    db.session.add(admin)
    db.session.commit()
    admin_list = List(owner_id=admin.id, name="Admin's List")
    db.session.add(admin_list)
    db.session.commit()
    return admin


def login(client, email, password):
    return client.post('/login', data={'email': email, 'password': password},
                       follow_redirects=True)


def make_child(parent):
    """Create a child profile the way the add_child route does."""
    child = User(email=f'child_{parent.id}_test@placeholder.local', name='Kid')
    child.set_password('whatever')
    db.session.add(child)
    db.session.flush()
    child_list = List(owner_id=child.id, managed_by_id=parent.id, name="Kid's List")
    db.session.add(child_list)
    db.session.commit()
    return child


# ---------- Bug 1: promote-child email call ----------

def test_promote_child_sends_invite_email_with_correct_args(app, client, monkeypatch):
    admin = make_admin()
    child = make_child(admin)
    item = Item(list_id=child.owned_list.id, title='Lego set', position=1,
                created_by_id=admin.id)
    db.session.add(item)
    db.session.commit()

    sent = {}

    def fake_send_invite_email(user, token, name):
        sent['user'] = user
        sent['token'] = token
        sent['name'] = name

    import app.routes as routes_module
    monkeypatch.setattr(routes_module, 'send_invite_email', fake_send_invite_email)

    login(client, 'admin@example.com', 'admin-pass')
    resp = client.post(f'/admin/child/{child.id}/promote', data={
        'email': 'kid@example.com',
        'send_invitation': 'y',
    }, follow_redirects=True)

    assert resp.status_code == 200  # no 500 from the old broken call
    assert sent['user'] is child  # a User object, not a string email
    assert sent['token'] == child.invite_token  # the real token, not the name
    assert sent['name'] == 'Kid'


# ---------- Bug 2: no duplicate list on promoted-child registration ----------

def test_promoted_child_registration_keeps_existing_list(app, client, monkeypatch):
    admin = make_admin()
    child = make_child(admin)
    original_list_id = child.owned_list.id
    item = Item(list_id=original_list_id, title='Lego set', position=1,
                created_by_id=admin.id)
    db.session.add(item)
    db.session.commit()

    import app.routes as routes_module
    monkeypatch.setattr(routes_module, 'send_invite_email', lambda *a, **kw: None)

    login(client, 'admin@example.com', 'admin-pass')
    client.post(f'/admin/child/{child.id}/promote', data={
        'email': 'kid@example.com',
        'send_invitation': 'y',
    })
    token = child.invite_token
    client.get('/logout')

    # Child completes registration via the invite link
    resp = client.post(f'/register/{token}', data={
        'name': 'Kid',
        'password': 'new-pass',
        'password2': 'new-pass',
    }, follow_redirects=True)
    assert resp.status_code == 200

    lists = List.query.filter_by(owner_id=child.id).all()
    assert len(lists) == 1, f'expected 1 list, found {len(lists)}'
    assert lists[0].id == original_list_id
    assert len(lists[0].items) == 1  # Lego set survived


def test_fresh_invitee_registration_creates_list(app, client, monkeypatch):
    admin = make_admin()
    import app.routes as routes_module
    monkeypatch.setattr(routes_module, 'send_invite_email', lambda *a, **kw: None)

    login(client, 'admin@example.com', 'admin-pass')
    client.post('/admin/invite', data={'name': 'Sarah', 'email': 'sarah@example.com'})
    client.get('/logout')

    user = User.query.filter_by(email='sarah@example.com').one()
    client.post(f'/register/{user.invite_token}', data={
        'name': 'Sarah', 'password': 'pw', 'password2': 'pw',
    })
    assert List.query.filter_by(owner_id=user.id).count() == 1


# ---------- Bug 3: no guessable placeholder passwords ----------

def test_pending_invitee_cannot_log_in_with_temporary(app, client, monkeypatch):
    make_admin()
    import app.routes as routes_module
    monkeypatch.setattr(routes_module, 'send_invite_email', lambda *a, **kw: None)

    login(client, 'admin@example.com', 'admin-pass')
    client.post('/admin/invite', data={'name': 'Sarah', 'email': 'sarah@example.com'})
    client.get('/logout')

    resp = login(client, 'sarah@example.com', 'temporary')
    assert b'Invalid email or password' in resp.data

    pending = User.query.filter_by(email='sarah@example.com').one()
    assert not pending.check_password('temporary')


def test_child_profile_has_no_guessable_password(app, client):
    admin = make_admin()
    login(client, 'admin@example.com', 'admin-pass')
    client.post('/child/add', data={'name': 'Junior'})

    child = User.query.filter_by(name='Junior').one()
    assert not child.check_password('placeholder')


# ---------- Bug 4: restore keeps image_url ----------

def test_restore_item_preserves_image_url(app, client):
    from datetime import datetime
    admin = make_admin()
    item = Item(list_id=admin.owned_list.id, title='Coffee roaster', position=1,
                image_url='https://example.com/roaster.jpg',
                received_at=datetime.utcnow(), created_by_id=admin.id)
    db.session.add(item)
    db.session.commit()

    login(client, 'admin@example.com', 'admin-pass')
    resp = client.post(f'/item/restore/{item.id}', data={
        'title': 'Coffee roaster',
        'image_url': 'https://example.com/roaster.jpg',
    }, follow_redirects=True)
    assert resp.status_code == 200

    restored = Item.query.filter_by(title='Coffee roaster', received_at=None).one()
    assert restored.image_url == 'https://example.com/roaster.jpg'


# ---------- Bug 5: delete requires archived ----------

def test_delete_active_user_is_blocked(app, client, monkeypatch):
    admin = make_admin()
    import app.routes as routes_module
    monkeypatch.setattr(routes_module, 'send_invite_email', lambda *a, **kw: None)

    target = User(email='victim@example.com', name='Victim')
    target.set_password('pw')
    db.session.add(target)
    db.session.commit()
    target_id = target.id

    login(client, 'admin@example.com', 'admin-pass')
    resp = client.post(f'/admin/users/{target_id}/delete', data={
        'admin_password': 'admin-pass',
        'confirm_email': 'victim@example.com',
    }, follow_redirects=True)

    assert b'must be archived' in resp.data
    assert db.session.get(User, target_id) is not None  # still exists


def test_delete_archived_user_still_works(app, client):
    admin = make_admin()
    target = User(email='victim@example.com', name='Victim')
    target.set_password('pw')
    target.archive(by_user=admin)
    db.session.add(target)
    db.session.commit()
    target_id = target.id

    login(client, 'admin@example.com', 'admin-pass')
    client.post(f'/admin/users/{target_id}/delete', data={
        'admin_password': 'admin-pass',
        'confirm_email': 'victim@example.com',
    }, follow_redirects=True)

    assert db.session.get(User, target_id) is None
