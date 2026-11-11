"""
One-off cleanup: find accounts that still have a guessable placeholder password
("temporary" or "placeholder", used for invites and child profiles before
2026-06-11) and replace it with an unguessable random one.

Dry run by default. Against production:

    railway run ./venv/bin/python fix_placeholder_passwords.py           # report only
    railway run ./venv/bin/python fix_placeholder_passwords.py --apply   # fix them

Reads DATABASE_PUBLIC_URL (reachable from a laptop) or DATABASE_URL.
Affected people are not locked out of anything they could legitimately use:
pending invitees get a fresh link from Users > Resend invite, and child
profiles never log in.
"""
import os
import secrets
import sys

from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash

PLACEHOLDERS = ('temporary', 'placeholder')


def main():
    apply = '--apply' in sys.argv
    url = os.environ.get('DATABASE_PUBLIC_URL') or os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('Set DATABASE_PUBLIC_URL or DATABASE_URL (or run via `railway run`).')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    engine = create_engine(url)
    with engine.begin() as conn:
        users = conn.execute(text(
            'SELECT id, name, email, password_hash, invite_token IS NOT NULL AS pending FROM users'
        )).fetchall()

        affected = [u for u in users
                    if any(check_password_hash(u.password_hash, p) for p in PLACEHOLDERS)]

        print(f'Checked {len(users)} accounts; {len(affected)} have a guessable placeholder password.')
        for u in affected:
            kind = 'pending invite' if u.pending else 'child profile / other'
            print(f'  - {u.name} <{u.email}> ({kind})')

        if not affected:
            return
        if not apply:
            print('\nDry run. Re-run with --apply to replace these passwords.')
            return

        for u in affected:
            conn.execute(text('UPDATE users SET password_hash = :h WHERE id = :id'),
                         {'h': generate_password_hash(secrets.token_urlsafe(32)), 'id': u.id})
        print(f'\nReplaced {len(affected)} password(s).')


if __name__ == '__main__':
    main()
