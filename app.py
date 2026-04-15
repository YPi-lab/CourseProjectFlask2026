from datetime import timedelta

from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager

from admin import admin_bp
from auth import auth as auth
from main import main as main
from models import db, User

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///job.db'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SECRET_KEY'] = 'aut_pass'

db.init_app(app)
bootstrap = Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

login_manager.login_message = "Для просмотра вакансий необходимо авторизоваться."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(main, url_prefix='/')


def set_admin():
    with app.app_context():
        db.create_all()
        admin_user = User.query.filter_by(username="admin").first()
        if admin_user and not admin_user.is_admin:
            admin_user.is_admin = True
            db.session.commit()


set_admin()

if __name__ == '__main__':
    import os

    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    app.run(HOST, PORT, debug=True)
