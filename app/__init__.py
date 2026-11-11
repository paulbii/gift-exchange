import os
import time
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy.exc import OperationalError
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
# Limits are declared per route; counters live in memory (one gunicorn worker)
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://')

# The database can refuse connections for a few seconds while it starts or
# wakes up; without a retry that fails the whole deploy.
DB_STARTUP_ATTEMPTS = 5
DB_STARTUP_WAIT_SECONDS = 3


def create_app(config_name='default'):
    """Application factory pattern"""
    # Never run production on the public fallback key (sessions would be forgeable)
    if config_name == 'production' and not os.environ.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY environment variable must be set in production.')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    if config_name == 'production':
        # Requests arrive through Railway's proxy. Trust the one address hop it
        # adds so rate limits count per visitor rather than per proxy. Scheme and
        # host are deliberately left alone, so link building and CSRF checks
        # behave exactly as before.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Configure login
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # User loader for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Context processor to inject current year into all templates
    @app.context_processor
    def inject_current_year():
        from datetime import datetime
        return {'current_year': datetime.now().year}

    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)

    from app.webauthn import webauthn_bp
    app.register_blueprint(webauthn_bp)

    # Error pages
    def error_page(status, icon, heading, message):
        return render_template('error.html', status=status, icon=icon,
                               heading=heading, message=message), status

    @app.errorhandler(404)
    def not_found(error):
        return error_page(404, 'bi-compass', "We can't find that page",
                          'The link may be old, or the page may have moved.')

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return error_page(400, 'bi-hourglass-split', 'This page expired',
                          'It was open for a while, so for safety we need you to go back and try that again.')

    @app.errorhandler(429)
    def too_many_requests(error):
        return error_page(429, 'bi-shield-lock', 'Too many attempts',
                          'Please wait a minute and try again.')

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return error_page(500, 'bi-tools', 'Something went wrong',
                          "That's on our end, not yours. Try again in a moment, and tell Paul if it keeps happening.")

    # Create database tables
    with app.app_context():
        for attempt in range(1, DB_STARTUP_ATTEMPTS + 1):
            try:
                db.create_all()
                break
            except OperationalError:
                if attempt == DB_STARTUP_ATTEMPTS:
                    raise
                app.logger.warning('Database not reachable at startup (attempt %d of %d); retrying',
                                   attempt, DB_STARTUP_ATTEMPTS)
                time.sleep(DB_STARTUP_WAIT_SECONDS)

    return app
