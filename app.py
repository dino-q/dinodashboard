"""
DinoDashboard — Flask Application
"""
import os
import secrets

# 本機開發：從 .env 讀 SUPABASE_URL / SUPABASE_SECRET_KEY / FLASK_SECRET_KEY
# 線上（Render）：直接走 os.environ，python-dotenv 不存在也沒關係
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask

from config import BASE_DIR


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Secret key 來源（優先順序）：
    #   1. FLASK_SECRET_KEY 環境變數（Render 上用這個）
    #   2. 本機 .flask_secret 檔（開發環境，git 有 ignore）
    #   3. 隨機產生（每次重啟都會變；Render 上 session 會失效，不要走到這步）
    env_key = os.environ.get("FLASK_SECRET_KEY")
    if env_key:
        app.secret_key = env_key
    else:
        secret_file = BASE_DIR / ".flask_secret"
        if secret_file.exists():
            app.secret_key = secret_file.read_text().strip()
        else:
            key = secrets.token_hex(32)
            try:
                secret_file.write_text(key)
            except OSError:
                # 雲端環境檔案系統唯讀，不寫檔
                pass
            app.secret_key = key

    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

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


# WSGI 進入點（gunicorn / Render 用）
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5050)
