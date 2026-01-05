"""
MiKlean - Simple app for small cleaning businesses
"""
from flask import Flask
from .config import Config


def format_time_12hr(time_str):
    """Convert 24-hour time string to 12-hour format."""
    if not time_str:
        return ''
    try:
        # Handle both "HH:MM:SS" and "HH:MM" formats
        time_part = time_str[:5]  # Get "HH:MM"
        hour, minute = map(int, time_part.split(':'))
        period = 'AM' if hour < 12 else 'PM'
        if hour == 0:
            hour = 12
        elif hour > 12:
            hour -= 12
        return f"{hour}:{minute:02d} {period}"
    except:
        return time_str


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register custom Jinja filters
    app.jinja_env.filters['time12'] = format_time_12hr
    
    # Register blueprints
    from .routes import auth, main, clients, estimates, visits, invoices, settings, api, onboarding, help
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(estimates.bp)
    app.register_blueprint(visits.bp)
    app.register_blueprint(invoices.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(onboarding.bp)
    app.register_blueprint(help.bp)
    
    # Register error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)
    
    return app
