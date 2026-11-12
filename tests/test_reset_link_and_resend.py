"""Admin-created password reset links, and sending email through Resend."""
import html
import os
import re
import tempfile

if 'DATABASE_URL' not in os.environ:
    _db_fd, _db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DATABASE_URL'] = 'sqlite:///' + _db_path
os.environ['FLASK_ENV'] = 'development'

import pytest

from app import create_app, db
from app.models import User, List, utcnow
import app.email as email_mod


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


def make_user(email, name, admin=False, managed_by=None):
    user = User(email=email, name=name, is_admin=admin)
    user.set_password('password1')
    db.session.add(user)
    db.session.flush()
    db.session.add(List(owner_id=user.id, name=f"{name}'s List", managed_by_id=managed_by))
    db.session.commit()
    return user


def login(client, email, password='password1'):
    return client.post('/login', data={'email': email, 'password': password})


# ==================== ADMIN RESET LINK ====================

def test_admin_creates_reset_link_that_works(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    login(client, 'admin@example.com')
    resp = client.post(f'/admin/users/{bob.id}/reset-link')
    assert resp.status_code == 200
    page = html.unescape(resp.data.decode())
    db.session.expire_all()
    assert bob.password_reset_token
    assert bob.password_reset_expires > utcnow()
    assert f'/reset-password/{bob.password_reset_token}' in page
    assert 'Bob' in page

    # The link lets Bob set a new password without any email
    client.post('/logout')
    client.post(f'/reset-password/{bob.password_reset_token}',
                data={'password': 'brand-new-pass', 'password2': 'brand-new-pass'})
    assert login(client, 'b@example.com', 'brand-new-pass').headers['Location'].endswith('/dashboard')


def test_reset_link_not_shown_on_ordinary_page_load(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    login(client, 'admin@example.com')
    client.post(f'/admin/users/{bob.id}/reset-link')
    assert '/reset-password/' not in client.get('/admin/users').data.decode()


def test_reset_link_requires_admin(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    make_user('c@example.com', 'Carl')
    login(client, 'c@example.com')
    resp = client.post(f'/admin/users/{bob.id}/reset-link')
    assert resp.status_code == 302
    db.session.expire_all()
    assert bob.password_reset_token is None


def test_reset_link_refused_for_accounts_that_cannot_use_one(app, client):
    admin = make_user('admin@example.com', 'Admin', admin=True)
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=admin.id)
    pending = make_user('p@example.com', 'Pending')
    pending.generate_invite_token()
    archived = make_user('z@example.com', 'Zed')
    archived.archive(by_user=admin)
    db.session.commit()
    login(client, 'admin@example.com')
    for user in (kid, pending, archived):
        client.post(f'/admin/users/{user.id}/reset-link')
        db.session.expire_all()
        assert user.password_reset_token is None, user.name


def test_users_page_offers_reset_link_only_where_it_applies(app, client):
    admin = make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=admin.id)
    pending = make_user('p@example.com', 'Pending')
    pending.generate_invite_token()
    db.session.commit()
    login(client, 'admin@example.com')
    page = client.get('/admin/users').data.decode()
    assert f'/admin/users/{bob.id}/reset-link' in page
    assert f'/admin/users/{kid.id}/reset-link' not in page
    assert f'/admin/users/{pending.id}/reset-link' not in page


# ==================== EMAIL PROVIDERS ====================

class FakeResponse:
    def __init__(self, status_code, text=''):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def outbox(monkeypatch):
    class Outbox(list):
        pass

    calls = Outbox()

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({'url': url, 'headers': headers, 'json': json})
        return FakeResponse(fake_post.status)

    fake_post.status = 200
    monkeypatch.setattr(email_mod.requests, 'post', fake_post)
    for var in ('RESEND_API_KEY', 'SENDGRID_API_KEY', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER'):
        monkeypatch.delenv(var, raising=False)
    calls.set_status = lambda s: setattr(fake_post, 'status', s)
    return calls


def test_resend_is_used_when_its_key_is_set(app, outbox, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 're_test')
    monkeypatch.setenv('MAIL_PASSWORD', 'SG.old')   # old key still around; Resend wins
    monkeypatch.setenv('MAIL_DEFAULT_SENDER', 'Wishlist <wishlist@example.com>')
    with app.app_context():
        assert email_mod.send_email('Hi', 'a@example.com', 'text body', '<p>html body</p>') is True
    call = outbox[0]
    assert call['url'] == 'https://api.resend.com/emails'
    assert call['headers']['Authorization'] == 'Bearer re_test'
    assert call['json'] == {'from': 'Wishlist <wishlist@example.com>', 'to': ['a@example.com'],
                            'subject': 'Hi', 'text': 'text body', 'html': '<p>html body</p>'}


def test_resend_failure_is_reported(app, outbox, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 're_test')
    outbox.set_status(403)
    with app.app_context():
        assert email_mod.send_email('Hi', 'a@example.com', 'text') is False


def test_sendgrid_still_used_without_a_resend_key(app, outbox, monkeypatch):
    monkeypatch.setenv('MAIL_PASSWORD', 'SG.old')
    outbox.set_status(202)
    with app.app_context():
        assert email_mod.send_email('Hi', 'a@example.com', 'text') is True
    assert outbox[0]['url'] == 'https://api.sendgrid.com/v3/mail/send'


def test_no_keys_means_no_send(app, outbox):
    with app.app_context():
        assert email_mod.send_email('Hi', 'a@example.com', 'text') is False
    assert outbox == []
