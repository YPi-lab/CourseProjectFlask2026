import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from project_app.admin import admin_bp
from project_app.auth import auth
from project_app.main import main
from project_app.models import User, db


def create_app(test_config=None):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///job.db",
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    Bootstrap5(app)
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Для доступа к внутренним разделам необходимо выполнить вход."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(main, url_prefix="/")

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    return app


def init_database(app):
    with app.app_context():
        db.create_all()
