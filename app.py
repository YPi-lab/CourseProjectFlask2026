import os
from datetime import timedelta

from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from admin import admin_bp
from auth import auth as auth
from main import main as main
from models import db, User

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///job.db'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bootstrap = Bootstrap5(app)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

login_manager.login_message = "Для доступа к внутренним разделам необходимо выполнить вход."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(main, url_prefix='/')


@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.exception("Внутренняя ошибка приложения: %s", error)
    return render_template("errors/500.html"), 500


def init_database():
    with app.app_context():
        db.create_all()


init_database()

if __name__ == '__main__':
    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    debug = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    app.run(HOST, PORT, debug=debug)
