import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def postgres_url(url):
    """Normalize a Postgres URL for SQLAlchemy.

    Railway/Render hand out postgres://, which SQLAlchemy rejects. We also name
    the psycopg2 driver explicitly: it is the one in requirements.txt, and
    SQLAlchemy 2.1 changed the default for bare postgresql:// to psycopg (v3).
    """
    if not url:
        return url
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg2://' + url[len(prefix):]
    return url


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # Email is sent through the SendGrid HTTP API; app/email.py reads
    # SENDGRID_API_KEY (or MAIL_PASSWORD) and MAIL_DEFAULT_SENDER from the environment.
    
    # App configuration
    APP_NAME = os.environ.get('APP_NAME', 'Power Family Wishlist')

    # WebAuthn / Passkey configuration
    WEBAUTHN_RP_ID = os.environ.get('WEBAUTHN_RP_ID', 'localhost')
    WEBAUTHN_RP_NAME = os.environ.get('WEBAUTHN_RP_NAME', 'Power Family Wishlist')
    WEBAUTHN_ORIGIN = os.environ.get('WEBAUTHN_ORIGIN', 'http://localhost:5000')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    RATELIMIT_ENABLED = False  # no login throttling while developing or testing
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'dev.db')


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = postgres_url(os.environ.get('DATABASE_URL'))


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
