"""
WebAuthn / Passkey routes for passwordless authentication.

Provides four JSON API endpoints:
  - Registration options (generate challenge)
  - Registration verify (store new credential)
  - Login options (generate challenge)
  - Login verify (authenticate and log in)

Plus a management endpoint to delete stored passkeys.
"""

import base64
from flask import Blueprint, request, jsonify, session, current_app, url_for
from flask_login import login_user, current_user, login_required
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AuthenticatorAttestationResponse,
    AuthenticationCredential,
    AuthenticatorAssertionResponse,
)
from webauthn.helpers import base64url_to_bytes
from app import db
from app.models import User, WebAuthnCredential

webauthn_bp = Blueprint('webauthn', __name__, url_prefix='/webauthn')


# ---------- helpers ----------

def _rp_id():
    return current_app.config['WEBAUTHN_RP_ID']


def _rp_name():
    return current_app.config['WEBAUTHN_RP_NAME']


def _origin():
    return current_app.config['WEBAUTHN_ORIGIN']


def _user_id_bytes(user):
    """Convert integer user id to bytes for WebAuthn user handle."""
    return str(user.id).encode('utf-8')


def _b64url_decode(value):
    """Decode a base64url string to bytes, handling missing padding."""
    return base64url_to_bytes(value)


# ==================== REGISTRATION (add a passkey) ====================

@webauthn_bp.route('/register/options', methods=['POST'])
@login_required
def register_options():
    """Generate registration options for the current logged-in user."""
    user = current_user

    # Exclude credentials the user already registered
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=cred.credential_id)
        for cred in user.webauthn_credentials
    ]

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=_user_id_bytes(user),
        user_name=user.email,
        user_display_name=user.name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store the challenge in session so we can verify it later
    session['webauthn_register_challenge'] = base64.b64encode(options.challenge).decode('utf-8')

    return jsonify({"publicKey": options_to_json(options)}), 200


@webauthn_bp.route('/register/verify', methods=['POST'])
@login_required
def register_verify():
    """Verify the registration response and store the new credential."""
    user = current_user
    data = request.get_json()

    challenge_b64 = session.pop('webauthn_register_challenge', None)
    if not challenge_b64:
        return jsonify({'error': 'No registration challenge in session. Please try again.'}), 400

    expected_challenge = base64.b64decode(challenge_b64)

    try:
        cred_data = data['credential']

        # Build the structured RegistrationCredential object
        credential = RegistrationCredential(
            id=cred_data['id'],
            raw_id=_b64url_decode(cred_data['rawId']),
            response=AuthenticatorAttestationResponse(
                client_data_json=_b64url_decode(cred_data['response']['clientDataJSON']),
                attestation_object=_b64url_decode(cred_data['response']['attestationObject']),
            ),
            type='public-key',
        )

        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_origin=_origin(),
            expected_rp_id=_rp_id(),
        )
    except Exception as e:
        return jsonify({'error': f'Verification failed: {str(e)}'}), 400

    # Store credential
    device_name = data.get('device_name', 'My Passkey')
    new_cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        device_name=device_name[:100],
    )
    db.session.add(new_cred)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Passkey registered.'}), 200


# ==================== AUTHENTICATION (sign in with passkey) ====================

@webauthn_bp.route('/login/options', methods=['POST'])
def login_options():
    """Generate authentication options.

    If an email is provided, we scope to that user's credentials.
    Otherwise we allow discoverable credentials (resident keys).
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    allow_credentials = []
    if email:
        user = User.query.filter_by(email=email, is_active=True).first()
        if user:
            allow_credentials = [
                PublicKeyCredentialDescriptor(id=cred.credential_id)
                for cred in user.webauthn_credentials
            ]
            if not allow_credentials:
                return jsonify({'error': 'No passkeys registered for this account.'}), 404

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    session['webauthn_login_challenge'] = base64.b64encode(options.challenge).decode('utf-8')

    return jsonify({"publicKey": options_to_json(options)}), 200


@webauthn_bp.route('/login/verify', methods=['POST'])
def login_verify():
    """Verify the authentication response and log the user in."""
    data = request.get_json()

    challenge_b64 = session.pop('webauthn_login_challenge', None)
    if not challenge_b64:
        return jsonify({'error': 'No login challenge in session. Please try again.'}), 400

    expected_challenge = base64.b64decode(challenge_b64)

    try:
        cred_data = data['credential']

        # Find the credential in our database by raw_id
        raw_id_bytes = _b64url_decode(cred_data['rawId'])
        stored_cred = WebAuthnCredential.query.filter_by(credential_id=raw_id_bytes).first()
        if not stored_cred:
            return jsonify({'error': 'Passkey not recognized.'}), 400

        user = stored_cred.user
        if not user.is_active:
            return jsonify({'error': 'This account has been archived.'}), 403

        # Build user_handle if present
        user_handle = None
        if cred_data['response'].get('userHandle'):
            user_handle = _b64url_decode(cred_data['response']['userHandle'])

        # Build the structured AuthenticationCredential object
        credential = AuthenticationCredential(
            id=cred_data['id'],
            raw_id=raw_id_bytes,
            response=AuthenticatorAssertionResponse(
                client_data_json=_b64url_decode(cred_data['response']['clientDataJSON']),
                authenticator_data=_b64url_decode(cred_data['response']['authenticatorData']),
                signature=_b64url_decode(cred_data['response']['signature']),
                user_handle=user_handle,
            ),
            type='public-key',
        )

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_origin=_origin(),
            expected_rp_id=_rp_id(),
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.sign_count,
        )
    except Exception as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 400

    # Update sign count to detect cloned authenticators
    stored_cred.sign_count = verification.new_sign_count
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'success': True, 'redirect': url_for('main.dashboard')}), 200


# ==================== MANAGEMENT ====================

@webauthn_bp.route('/delete/<int:credential_id>', methods=['POST'])
@login_required
def delete_credential(credential_id):
    """Delete a stored passkey."""
    cred = WebAuthnCredential.query.get_or_404(credential_id)

    if cred.user_id != current_user.id:
        return jsonify({'error': 'Not your credential.'}), 403

    db.session.delete(cred)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Passkey removed.'}), 200


@webauthn_bp.route('/dismiss-prompt', methods=['POST'])
@login_required
def dismiss_prompt():
    """Dismiss the passkey setup banner on the dashboard."""
    current_user.passkey_prompt_dismissed = True
    db.session.commit()
    return jsonify({'success': True}), 200
