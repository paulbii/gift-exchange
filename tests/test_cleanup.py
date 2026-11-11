"""Tests for the 2026-11 cleanup pass: error pages, email failure messages,
startup database retry, login rate limiting."""
import html
import os
import tempfile

if 'DATABASE_URL' not in os.environ:
    _db_fd, _db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DATABASE_URL'] = 'sqlite:///' + _db_path
os.environ['FLASK_ENV'] = 'development'

import pytest
from sqlalchemy.exc import OperationalError

import app as app_module
from app import create_app, db, limiter
from app.models import User, List
import app.routes as routes


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


def make_user(email, name, password='password1', admin=False, managed_by=None):
    user = User(email=email, name=name, is_admin=admin)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(List(owner_id=user.id, name=f"{name}'s List", managed_by_id=managed_by))
    db.session.commit()
    return user


def login(client, email, password='password1'):
    return client.post('/login', data={'email': email, 'password': password})


# ==================== ERROR PAGES ====================

def test_404_page_is_branded(app, client):
    resp = client.get('/no-such-page')
    assert resp.status_code == 404
    page = html.unescape(resp.data.decode())
    assert 'Power Family Wishlist' in page
    assert "can't find that page" in page


def test_500_page_is_branded(app, client):
    app.config['PROPAGATE_EXCEPTIONS'] = False

    @app.route('/boom')
    def boom():
        raise RuntimeError('kaboom')

    resp = client.get('/boom')
    assert resp.status_code == 500
    page = html.unescape(resp.data.decode())
    assert 'Power Family Wishlist' in page
    assert 'Something went wrong' in page
    assert 'kaboom' not in page


def test_csrf_failure_shows_friendly_page(app, client):
    app.config['WTF_CSRF_ENABLED'] = True
    resp = client.post('/logout')
    assert resp.status_code == 400
    page = html.unescape(resp.data.decode())
    assert 'Power Family Wishlist' in page
    assert 'page expired' in page.lower()


# ==================== EMAIL FAILURE MESSAGES ====================

def test_invite_flash_admits_email_failure(app, client, monkeypatch):
    make_user('admin@example.com', 'Admin', admin=True)
    monkeypatch.setattr(routes, 'send_invite_email', lambda *a, **k: False)
    login(client, 'admin@example.com')
    page = html.unescape(client.post('/admin/invite', data={'name': 'Sue', 'email': 'sue@example.com'}).data.decode())
    assert 'Invitation sent' not in page
    assert "couldn't be sent" in page
    assert '/register/' in page  # link still offered


def test_invite_flash_confirms_when_email_sent(app, client, monkeypatch):
    make_user('admin@example.com', 'Admin', admin=True)
    monkeypatch.setattr(routes, 'send_invite_email', lambda *a, **k: True)
    login(client, 'admin@example.com')
    page = html.unescape(client.post('/admin/invite', data={'name': 'Sue', 'email': 'sue@example.com'}).data.decode())
    assert 'Invitation sent' in page


def test_resend_flash_admits_email_failure(app, client, monkeypatch):
    make_user('admin@example.com', 'Admin', admin=True)
    sue = User(email='sue@example.com', name='Sue')
    sue.set_password('unguessable-placeholder')
    sue.generate_invite_token()
    db.session.add(sue)
    db.session.commit()
    monkeypatch.setattr(routes, 'send_invite_email', lambda *a, **k: False)
    login(client, 'admin@example.com')
    page = html.unescape(client.post(f'/admin/users/{sue.id}/resend-invite', follow_redirects=True).data.decode())
    assert 'New invitation sent' not in page
    assert "couldn't be sent" in page


def test_promote_flash_admits_email_failure(app, client, monkeypatch):
    admin = make_user('admin@example.com', 'Admin', admin=True)
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=admin.id)
    monkeypatch.setattr(routes, 'send_invite_email', lambda *a, **k: False)
    login(client, 'admin@example.com')
    page = html.unescape(client.post(f'/admin/child/{kid.id}/promote',
                       data={'email': 'kid@example.com', 'send_invitation': 'y'},
                       follow_redirects=True).data.decode())
    assert 'Invitation email sent' not in page
    assert "couldn't be sent" in page


def test_send_functions_report_result(app, monkeypatch):
    import app.email as email_mod
    user = User(email='x@example.com', name='X')
    for result in (True, False):
        monkeypatch.setattr(email_mod, 'send_email', lambda *a, **k: result)
        with app.test_request_context():
            assert email_mod.send_invite_email(user, 'tok', 'X') is result
            assert email_mod.send_password_reset_email(user, 'tok') is result


# ==================== STARTUP DATABASE RETRY ====================

def test_startup_retries_until_database_is_reachable(monkeypatch):
    calls = {'n': 0}
    real_create_all = db.create_all

    def flaky_create_all(*a, **k):
        calls['n'] += 1
        if calls['n'] < 3:
            raise OperationalError('SELECT 1', {}, Exception('Connection refused'))
        return real_create_all(*a, **k)

    monkeypatch.setattr(db, 'create_all', flaky_create_all)
    monkeypatch.setattr(app_module.time, 'sleep', lambda s: None)
    create_app('development')
    assert calls['n'] == 3


def test_startup_gives_up_after_repeated_failures(monkeypatch):
    def dead_create_all(*a, **k):
        raise OperationalError('SELECT 1', {}, Exception('Connection refused'))

    monkeypatch.setattr(db, 'create_all', dead_create_all)
    monkeypatch.setattr(app_module.time, 'sleep', lambda s: None)
    with pytest.raises(OperationalError):
        create_app('development')


# ==================== RATE LIMITING ====================

@pytest.fixture
def rate_limited(monkeypatch):
    """Turn throttling on (as in production) for the app this test builds.

    Listed before `app`/`client` in a test's arguments so it applies first.
    """
    from config import DevelopmentConfig
    monkeypatch.setattr(DevelopmentConfig, 'RATELIMIT_ENABLED', True)
    yield
    limiter.reset()


def test_login_attempts_are_rate_limited(rate_limited, app, client):
    make_user('a@example.com', 'Ann')
    statuses = [client.post('/login', data={'email': 'a@example.com', 'password': 'wrong-password'}).status_code
                for _ in range(12)]
    assert statuses[:10] == [200] * 10
    assert statuses[10:] == [429, 429]
    page = html.unescape(client.post('/login', data={'email': 'a@example.com', 'password': 'wrong-password'}).data.decode())
    assert 'Too many attempts' in page


def test_login_page_view_is_not_rate_limited(rate_limited, app, client):
    assert [client.get('/login').status_code for _ in range(15)] == [200] * 15


def test_forgot_password_is_rate_limited(rate_limited, app, client, monkeypatch):
    monkeypatch.setattr(routes, 'send_password_reset_email', lambda *a, **k: True)
    statuses = [client.post('/forgot-password', data={'email': 'nobody@example.com'}).status_code
                for _ in range(7)]
    assert 429 in statuses and statuses[:5] == [302] * 5


def test_rate_limiting_is_off_in_development_by_default(app, client):
    make_user('a@example.com', 'Ann')
    statuses = {client.post('/login', data={'email': 'a@example.com', 'password': 'wrong-password'}).status_code
                for _ in range(15)}
    assert statuses == {200}


# ==================== HOUSEKEEPING ====================

def test_no_utcnow_deprecation_warnings(app, client, recwarn):
    user = make_user('a@example.com', 'Ann')
    user.generate_invite_token()
    user.archive(by_user=user)
    db.session.commit()
    assert not [w for w in recwarn.list if 'utcnow' in str(w.message)]
