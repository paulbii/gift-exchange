"""Parents can shop their own child's list; move-to-top reordering."""
import html
import os
import tempfile

if 'DATABASE_URL' not in os.environ:
    _db_fd, _db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DATABASE_URL'] = 'sqlite:///' + _db_path
os.environ['FLASK_ENV'] = 'development'

import pytest

from app import create_app, db
from app.models import User, List, Item, Claim, utcnow
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
    monkeypatch.setattr(routes, 'fetch_image_from_url', lambda url: None)
    monkeypatch.setattr(routes, 'send_item_deleted_notification', lambda *a, **k: None)


def make_user(email, name, managed_by=None):
    user = User(email=email, name=name)
    user.set_password('password1')
    db.session.add(user)
    db.session.flush()
    db.session.add(List(owner_id=user.id, name=f"{name}'s List", managed_by_id=managed_by))
    db.session.commit()
    return user


def make_item(owner, title, position, received=False):
    item = Item(list_id=owner.owned_list.id, title=title, position=position,
                created_by_id=owner.id, received_at=utcnow() if received else None)
    db.session.add(item)
    db.session.commit()
    return item


def login(client, email):
    return client.post('/login', data={'email': email, 'password': 'password1'})


CLAIMED_BADGE = 'class="status-badge claimed"'


def page_of(resp):
    return html.unescape(resp.data.decode())


# ==================== PARENT SHOPPING ====================

@pytest.fixture
def family(app):
    parent = make_user('p@example.com', 'Parent')
    kid = make_user('child_1@placeholder.local', 'Kid', managed_by=parent.id)
    aunt = make_user('aunt@example.com', 'Aunt')
    return parent, kid, aunt


def test_parent_can_open_shopping_view_of_child_list(client, family):
    parent, kid, aunt = family
    lego = make_item(kid, 'Lego set', 1)
    make_item(kid, 'Puzzle', 2)
    db.session.add(Claim(item_id=lego.id, claimed_by_id=aunt.id))
    db.session.commit()
    login(client, 'p@example.com')
    resp = client.get(f'/list/{kid.owned_list.id}')
    assert resp.status_code == 200
    page = page_of(resp)
    assert CLAIMED_BADGE in page      # sees that the Lego is taken
    assert "I'll Get This!" in page   # and can claim the puzzle
    assert 'Aunt' not in page         # but not who claimed it
    assert f'/manage-child-list/{kid.owned_list.id}' in page  # way back to managing


def test_parent_can_claim_and_unclaim_on_child_list(client, family):
    parent, kid, aunt = family
    lego = make_item(kid, 'Lego set', 1)
    login(client, 'p@example.com')
    resp = client.post(f'/claim/{lego.id}')
    assert resp.headers['Location'].endswith(f'/list/{kid.owned_list.id}')
    assert Claim.query.filter_by(item_id=lego.id, claimed_by_id=parent.id).count() == 1
    client.post(f'/unclaim/{lego.id}')
    assert Claim.query.count() == 0


def test_parent_claim_on_child_list_shows_in_my_claims(client, family):
    parent, kid, aunt = family
    lego = make_item(kid, 'Lego set', 1)
    login(client, 'p@example.com')
    client.post(f'/claim/{lego.id}')
    assert 'Lego set' in page_of(client.get('/my-claims'))


def test_manage_view_of_child_list_still_hides_claims_but_links_to_shop(client, family):
    parent, kid, aunt = family
    lego = make_item(kid, 'Lego set', 1)
    db.session.add(Claim(item_id=lego.id, claimed_by_id=aunt.id))
    db.session.commit()
    login(client, 'p@example.com')
    page = page_of(client.get(f'/manage-child-list/{kid.owned_list.id}'))
    assert CLAIMED_BADGE not in page and 'Already Claimed' not in page
    assert f'/list/{kid.owned_list.id}' in page


def test_owner_still_cannot_see_or_claim_own_list(client, family):
    parent, kid, aunt = family
    mine = make_item(parent, 'Dutch oven', 1)
    db.session.add(Claim(item_id=mine.id, claimed_by_id=aunt.id))
    db.session.commit()
    login(client, 'p@example.com')
    resp = client.get(f'/list/{parent.owned_list.id}')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/my-list')
    other = make_item(parent, 'Socks', 2)
    client.post(f'/claim/{other.id}')
    assert Claim.query.filter_by(claimed_by_id=parent.id).count() == 0
    my_list = page_of(client.get('/my-list'))
    assert CLAIMED_BADGE not in my_list and 'Already Claimed' not in my_list


def test_dashboard_offers_parent_both_manage_and_shop(client, family):
    parent, kid, aunt = family
    login(client, 'p@example.com')
    page = page_of(client.get('/dashboard'))
    assert f'/manage-child-list/{kid.owned_list.id}' in page
    assert f'/list/{kid.owned_list.id}' in page


# ==================== MOVE TO TOP ====================

def test_move_to_top(client, app):
    ann = make_user('a@example.com', 'Ann')
    make_item(ann, 'one', 1)
    make_item(ann, 'old', 2, received=True)
    make_item(ann, 'two', 3)
    three = make_item(ann, 'three', 4)
    login(client, 'a@example.com')
    resp = client.post(f'/item/move/{three.id}/top')
    assert resp.headers['Location'].endswith('/my-list')
    db.session.expire_all()
    active = [i.title for i in ann.owned_list.items if not i.is_received()]
    assert active == ['three', 'one', 'two']
    positions = [i.position for i in ann.owned_list.items]
    assert len(set(positions)) == len(positions)  # no duplicate positions


def test_move_to_top_requires_permission(client, app):
    ann = make_user('a@example.com', 'Ann')
    make_user('b@example.com', 'Bob')
    make_item(ann, 'one', 1)
    two = make_item(ann, 'two', 2)
    login(client, 'b@example.com')
    client.post(f'/item/move/{two.id}/top')
    db.session.expire_all()
    assert [i.title for i in ann.owned_list.items] == ['one', 'two']


def test_move_to_top_button_only_from_third_item_down(client, app):
    ann = make_user('a@example.com', 'Ann')
    items = [make_item(ann, f'item {n}', n) for n in (1, 2, 3)]
    login(client, 'a@example.com')
    page = page_of(client.get('/my-list'))
    assert f'/item/move/{items[2].id}/top' in page
    assert f'/item/move/{items[1].id}/top' not in page
    assert f'/item/move/{items[0].id}/top' not in page
