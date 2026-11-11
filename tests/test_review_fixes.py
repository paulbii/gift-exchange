"""Regression tests for the 2026-11 review pass (security + bug fixes + new pages)."""
import os
import tempfile
from datetime import datetime, timedelta

# Must be set before importing app/config (config reads env at import time)
if 'DATABASE_URL' not in os.environ:
    _db_fd, _db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DATABASE_URL'] = 'sqlite:///' + _db_path
os.environ['FLASK_ENV'] = 'development'

import pytest
from sqlalchemy import event

from app import create_app, db
from app.models import User, List, Item, Claim
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


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Never hit the network from tests."""
    monkeypatch.setattr(routes, 'fetch_image_from_url', lambda url: None)
    monkeypatch.setattr(routes, 'send_invite_email', lambda *a, **k: None)
    monkeypatch.setattr(routes, 'send_password_reset_email', lambda *a, **k: None)
    monkeypatch.setattr(routes, 'send_item_deleted_notification', lambda *a, **k: None)


def make_user(email, name, password='password1', admin=False, managed_by=None):
    user = User(email=email, name=name, is_admin=admin)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(List(owner_id=user.id, name=f"{name}'s List", managed_by_id=managed_by))
    db.session.commit()
    return user


def make_item(owner, title, position, created_by=None, received=False, **kw):
    item = Item(list_id=owner.owned_list.id, title=title, position=position,
                created_by_id=(created_by or owner).id,
                received_at=datetime.utcnow() if received else None, **kw)
    db.session.add(item)
    db.session.commit()
    return item


def login(client, email, password='password1'):
    return client.post('/login', data={'email': email, 'password': password})


# ==================== SECURITY ====================

def test_login_next_rejects_external_redirect(app, client):
    make_user('a@example.com', 'Ann')
    resp = client.post('/login?next=https://evil.example/phish',
                       data={'email': 'a@example.com', 'password': 'password1'})
    assert resp.headers['Location'].endswith('/dashboard')


def test_login_next_allows_local_path(app, client):
    make_user('a@example.com', 'Ann')
    resp = client.post('/login?next=/profile',
                       data={'email': 'a@example.com', 'password': 'password1'})
    assert resp.headers['Location'].endswith('/profile')


@pytest.mark.parametrize('bad_url', [
    'javascript://example.com/%0Aalert(1)',
    'ftp://example.com/file',
    'data://example.com/x',
])
def test_item_url_must_be_http(app, client, bad_url):
    ann = make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    client.post(f'/item/add/{ann.owned_list.id}', data={'title': 'x', 'url': bad_url})
    assert Item.query.count() == 0
    client.post(f'/item/add/{ann.owned_list.id}', data={'title': 'x', 'image_url': bad_url})
    assert Item.query.count() == 0


def test_item_url_accepts_https(app, client):
    ann = make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    client.post(f'/item/add/{ann.owned_list.id}',
                data={'title': 'x', 'url': 'https://example.com/p/1'})
    assert Item.query.one().url == 'https://example.com/p/1'


def test_csrf_blocks_tokenless_post(app, client):
    app.config['WTF_CSRF_ENABLED'] = True
    ann = make_user('a@example.com', 'Ann')
    item = make_item(ann, 'x', 1)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(ann.id)
        sess['_fresh'] = True
    resp = client.post(f'/item/delete/{item.id}')
    assert resp.status_code == 400
    assert Item.query.count() == 1


def test_move_and_logout_are_post_only(app, client):
    ann = make_user('a@example.com', 'Ann')
    item = make_item(ann, 'x', 1)
    login(client, 'a@example.com')
    assert client.get(f'/item/move/{item.id}/up').status_code == 405
    assert client.get('/logout').status_code == 405
    assert client.post('/logout').status_code == 302
    assert client.get('/dashboard').status_code == 302  # logged out


def test_short_password_rejected(app, client):
    ann = make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    client.post('/change-password', data={'current_password': 'password1',
                                          'new_password': 'abc', 'new_password2': 'abc'})
    db.session.expire_all()
    assert ann.check_password('password1')


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError):
        create_app('production')


def test_fetch_product_image_endpoint_removed(app, client):
    make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    assert client.post('/fetch-product-image', json={'url': 'http://example.com'}).status_code == 404


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/admin',
    'http://localhost:5000/',
    'http://169.254.169.254/latest/meta-data/',
    'http://10.0.0.5/',
    'http://[::1]/',
])
def test_image_fetch_refuses_private_addresses(url):
    from app.routes import _is_public_http_url
    assert _is_public_http_url(url) is False


def test_passkey_options_do_not_reveal_accounts(app, client):
    make_user('a@example.com', 'Ann')
    known = client.post('/webauthn/login/options', json={'email': 'a@example.com'})
    unknown = client.post('/webauthn/login/options', json={'email': 'nobody@example.com'})
    assert known.status_code == unknown.status_code == 200


def test_invite_email_escapes_name(app, monkeypatch):
    import app.email as email_mod
    sent = {}
    monkeypatch.setattr(email_mod, 'send_email',
                        lambda subject, recipients, text_body, html_body=None: sent.update(html=html_body))
    user = User(email='x@example.com', name='<b>Eve</b>')
    with app.test_request_context():
        email_mod.send_invite_email(user, 'tok', '<b>Eve</b>')
    assert '<b>Eve</b>' not in sent['html']
    assert '&lt;b&gt;Eve&lt;/b&gt;' in sent['html']


# ==================== BUGS ====================

def test_delete_user_who_created_items_on_another_list(app, client):
    """With FKs enforced (as on Postgres) this used to raise IntegrityError."""
    engine = db.engine

    def fk_on(dbapi_con, _rec):
        dbapi_con.execute('PRAGMA foreign_keys=ON')

    event.listen(engine, 'connect', fk_on)
    engine.dispose()
    try:
        admin = make_user('admin@example.com', 'Admin', admin=True)
        parent = make_user('p@example.com', 'Parent')
        kid = make_user('kid@example.com', 'Kid')  # already promoted
        item = make_item(kid, 'Lego', 1, created_by=parent)
        parent.archive(by_user=admin)
        db.session.commit()
        login(client, 'admin@example.com')
        resp = client.post(f'/admin/users/{parent.id}/delete',
                           data={'admin_password': 'password1', 'confirm_email': 'p@example.com'})
        assert resp.status_code == 302
        assert User.query.filter_by(email='p@example.com').first() is None
        db.session.expire_all()
        assert Item.query.get(item.id).created_by_id == kid.id
    finally:
        db.session.remove()
        event.remove(engine, 'connect', fk_on)
        engine.dispose()


def test_child_list_actions_return_to_child_list(app, client):
    parent = make_user('p@example.com', 'Parent')
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=parent.id)
    child_url = f'/manage-child-list/{kid.owned_list.id}'
    login(client, 'p@example.com')

    resp = client.post(f'/item/add/{kid.owned_list.id}', data={'title': 'Lego'})
    assert resp.headers['Location'].endswith(child_url)
    item = Item.query.one()

    resp = client.post(f'/item/edit/{item.id}', data={'title': 'Lego 2'})
    assert resp.headers['Location'].endswith(child_url)
    resp = client.post(f'/item/move/{item.id}/up')
    assert resp.headers['Location'].endswith(child_url)
    resp = client.get(f'/list/{kid.owned_list.id}')
    assert resp.headers['Location'].endswith(child_url)
    resp = client.post(f'/item/mark-received/{item.id}')
    assert resp.headers['Location'].endswith(child_url)
    resp = client.post(f'/item/delete/{item.id}')
    assert resp.headers['Location'].endswith(child_url)


def test_own_list_actions_still_return_to_my_list(app, client):
    ann = make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    resp = client.post(f'/item/add/{ann.owned_list.id}', data={'title': 'x'})
    assert resp.headers['Location'].endswith('/my-list')


def test_move_skips_received_items(app, client):
    ann = make_user('a@example.com', 'Ann')
    make_item(ann, 'one', 1)
    make_item(ann, 'two', 2, received=True)
    three = make_item(ann, 'three', 3)
    login(client, 'a@example.com')
    client.post(f'/item/move/{three.id}/up')
    db.session.expire_all()
    active = [i.title for i in ann.owned_list.items if not i.is_received()]
    assert active == ['three', 'one']


def test_allow_multiple_blank_means_unlimited_and_field_not_prefilled(app, client):
    ann = make_user('a@example.com', 'Ann')
    login(client, 'a@example.com')
    page = client.get(f'/item/add/{ann.owned_list.id}').data.decode()
    field = page[page.index('name="max_claims"') - 200: page.index('name="max_claims"') + 200]
    assert 'value="1"' not in field
    client.post(f'/item/add/{ann.owned_list.id}',
                data={'title': 'Gift card', 'allow_multiple': 'y', 'max_claims': ''})
    assert Item.query.one().max_claims == 999


def test_edit_unlimited_item_shows_blank_max(app, client):
    ann = make_user('a@example.com', 'Ann')
    item = make_item(ann, 'Gift card', 1, max_claims=999)
    login(client, 'a@example.com')
    page = client.get(f'/item/edit/{item.id}').data.decode()
    assert 'value="999"' not in page


def test_changed_url_refetches_image(app, client, monkeypatch):
    ann = make_user('a@example.com', 'Ann')
    item = make_item(ann, 'x', 1, url='https://a.example.com/1',
                     image_url='https://a.example.com/old.jpg')
    monkeypatch.setattr(routes, 'fetch_image_from_url', lambda url: 'https://b.example.com/new.jpg')
    login(client, 'a@example.com')
    # browser submits the prefilled (unchanged) image field
    client.post(f'/item/edit/{item.id}', data={'title': 'x', 'url': 'https://b.example.com/2',
                                               'image_url': 'https://a.example.com/old.jpg'})
    db.session.expire_all()
    assert item.image_url == 'https://b.example.com/new.jpg'


def test_changed_url_keeps_manually_changed_image(app, client, monkeypatch):
    ann = make_user('a@example.com', 'Ann')
    item = make_item(ann, 'x', 1, url='https://a.example.com/1',
                     image_url='https://a.example.com/old.jpg')
    monkeypatch.setattr(routes, 'fetch_image_from_url', lambda url: 'https://b.example.com/new.jpg')
    login(client, 'a@example.com')
    client.post(f'/item/edit/{item.id}', data={'title': 'x', 'url': 'https://b.example.com/2',
                                               'image_url': 'https://c.example.com/mine.jpg'})
    db.session.expire_all()
    assert item.image_url == 'https://c.example.com/mine.jpg'


def test_dashboard_count_excludes_received(app, client):
    ann = make_user('a@example.com', 'Ann')
    make_user('b@example.com', 'Bob')
    make_item(ann, 'old', 1, received=True)
    make_item(ann, 'new', 2)
    login(client, 'b@example.com')
    page = client.get('/dashboard').data.decode()
    assert '1 item' in page and '2 items' not in page


def test_cannot_claim_received_item(app, client):
    ann = make_user('a@example.com', 'Ann')
    make_user('b@example.com', 'Bob')
    item = make_item(ann, 'old', 1, received=True)
    login(client, 'b@example.com')
    client.post(f'/claim/{item.id}')
    assert Claim.query.count() == 0


def test_admin_cannot_open_adult_list_in_manage_view(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    login(client, 'admin@example.com')
    assert client.get(f'/manage-child-list/{bob.owned_list.id}').status_code == 302


def test_password_reset_clears_pending_invite(app, client):
    user = User(email='sue@example.com', name='Sue')
    user.set_password('unguessable-placeholder')
    user.generate_invite_token()
    token = user.generate_password_reset_token()
    db.session.add(user)
    db.session.commit()
    client.post(f'/reset-password/{token}', data={'password': 'password1', 'password2': 'password1'})
    db.session.expire_all()
    assert user.invite_token is None


# ==================== INVITES ====================

def _pending(email='sue@example.com', name='Sue', expired=False):
    user = User(email=email, name=name)
    user.set_password('unguessable-placeholder')
    user.generate_invite_token()
    if expired:
        user.invite_token_expires = datetime.utcnow() - timedelta(hours=1)
    db.session.add(user)
    db.session.commit()
    return user


def test_resend_invite_issues_fresh_token_and_emails(app, client, monkeypatch):
    make_user('admin@example.com', 'Admin', admin=True)
    sue = _pending(expired=True)
    old_token = sue.invite_token
    sent = {}
    monkeypatch.setattr(routes, 'send_invite_email',
                        lambda user, token, name: sent.update(email=user.email, token=token))
    login(client, 'admin@example.com')
    resp = client.post(f'/admin/users/{sue.id}/resend-invite', follow_redirects=True)
    db.session.expire_all()
    assert sue.invite_token != old_token
    assert sue.invite_token_expires > datetime.utcnow()
    assert sent == {'email': 'sue@example.com', 'token': sue.invite_token}
    assert f'/register/{sue.invite_token}'.encode() in resp.data  # link shown to admin


def test_resend_invite_requires_admin_and_pending_user(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    bob = make_user('b@example.com', 'Bob')
    sue = _pending()
    token = sue.invite_token
    login(client, 'b@example.com')
    client.post(f'/admin/users/{sue.id}/resend-invite')
    db.session.expire_all()
    assert sue.invite_token == token
    client.post('/logout')
    login(client, 'admin@example.com')
    client.post(f'/admin/users/{bob.id}/resend-invite')
    db.session.expire_all()
    assert bob.invite_token is None


def test_user_management_marks_pending_invites(app, client):
    make_user('admin@example.com', 'Admin', admin=True)
    _pending(expired=True)
    login(client, 'admin@example.com')
    page = client.get('/admin/users').data.decode()
    assert 'Invite expired' in page
    assert 'Resend invite' in page


def test_promote_without_email_shows_link(app, client):
    admin = make_user('admin@example.com', 'Admin', admin=True)
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=admin.id)
    login(client, 'admin@example.com')
    resp = client.post(f'/admin/child/{kid.id}/promote',
                       data={'email': 'kid@example.com'}, follow_redirects=True)
    db.session.expire_all()
    assert f'/register/{kid.invite_token}'.encode() in resp.data


# ==================== MY CLAIMS ====================

def test_my_claims_lists_only_my_active_claims(app, client):
    ann = make_user('a@example.com', 'Ann')
    bob = make_user('b@example.com', 'Bob')
    carl = make_user('c@example.com', 'Carl')
    mine = make_item(ann, 'Dutch oven', 1, price=89.99)
    theirs = make_item(ann, 'Wool socks', 2)
    done = make_item(ann, 'Already given', 3, received=True)
    db.session.add_all([Claim(item_id=mine.id, claimed_by_id=bob.id),
                        Claim(item_id=theirs.id, claimed_by_id=carl.id),
                        Claim(item_id=done.id, claimed_by_id=bob.id)])
    db.session.commit()
    login(client, 'b@example.com')
    page = client.get('/my-claims').data.decode()
    assert 'Dutch oven' in page
    assert 'Wool socks' not in page
    assert 'Already given' not in page
    assert 'Ann' in page


def test_my_claims_requires_login(app, client):
    assert client.get('/my-claims').status_code == 302


def test_unclaim_from_my_claims_returns_there(app, client):
    ann = make_user('a@example.com', 'Ann')
    bob = make_user('b@example.com', 'Bob')
    item = make_item(ann, 'Dutch oven', 1)
    db.session.add(Claim(item_id=item.id, claimed_by_id=bob.id))
    db.session.commit()
    login(client, 'b@example.com')
    resp = client.post(f'/unclaim/{item.id}', data={'next': 'claims'})
    assert resp.headers['Location'].endswith('/my-claims')
    assert Claim.query.count() == 0


# ==================== DEPLOYMENT ====================

@pytest.mark.parametrize('given,expected', [
    ('postgres://u:p@host:5432/db', 'postgresql+psycopg2://u:p@host:5432/db'),
    ('postgresql://u:p@host:5432/db', 'postgresql+psycopg2://u:p@host:5432/db'),
    ('postgresql+psycopg2://u:p@host/db', 'postgresql+psycopg2://u:p@host/db'),
    ('sqlite:///dev.db', 'sqlite:///dev.db'),
    (None, None),
])
def test_postgres_url_names_the_installed_driver(given, expected):
    from config import postgres_url
    assert postgres_url(given) == expected


def test_production_database_url_uses_psycopg2():
    """The driver SQLAlchemy picks must be the one requirements.txt installs."""
    from sqlalchemy.engine import make_url
    from config import postgres_url
    assert make_url(postgres_url('postgres://u:p@host/db')).get_dialect().driver == 'psycopg2'
