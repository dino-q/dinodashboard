"""
DinoDashboard — Flask Application
"""
import secrets

from flask import Flask

from config import BASE_DIR


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    # Stable secret key per installation (persisted, not hardcoded)
    secret_file = BASE_DIR / ".flask_secret"
    if secret_file.exists():
        app.secret_key = secret_file.read_text().strip()
    else:
        key = secrets.token_hex(32)
        secret_file.write_text(key)
        app.secret_key = key

    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    # Ensure data files exist
    from data import init_data_files
    init_data_files()

    # Register blueprints
    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.api import bp as api_bp
    from routes.admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    # Inject auth helpers into all templates
    from routes.auth import (
        is_logged_in, is_admin, is_editor, is_viewer, current_user,
        is_private_mode, is_registration_open,
    )
    @app.context_processor
    def inject_auth():
        return {
            "is_logged_in": is_logged_in(),
            "is_admin": is_admin(),
            "is_editor": is_editor(),
            "is_viewer": is_viewer(),
            "current_user": current_user(),
            "is_private_mode": is_private_mode(),
            "allow_registration": is_registration_open(),
        }

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=5050)
