import unittest
from pathlib import Path

from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

from admin import admin_bp
from auth import auth
from main import main
from models import User, Department, db


def create_test_app():
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    db.init_app(app)
    Bootstrap5(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    app.jinja_env.globals["csrf_token"] = lambda: "test-token"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(main, url_prefix="/")
    return app


class FlaskProjectTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_test_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all(
                [
                    User(
                        username="admin_user",
                        password=generate_password_hash("Admin123", method="pbkdf2"),
                        is_admin=True,
                    ),
                    User(
                        username="simple_user",
                        password=generate_password_hash("User12345", method="pbkdf2"),
                        is_admin=False,
                    ),
                ]
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, username, password):
        return self.client.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def test_public_pages_are_available(self):
        for route in ["/", "/about", "/contact", "/products", "/services", "/auth/login", "/auth/register"]:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, route)

    def test_vacancies_requires_authentication(self):
        response = self.client.get("/vacancies")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_error_pages_are_available(self):
        response_404 = self.client.get("/missing-page")
        self.assertEqual(response_404.status_code, 404)

        self.login("simple_user", "User12345")
        response_403 = self.client.get("/admin/index")
        self.assertEqual(response_403.status_code, 403)

    def test_regular_user_cannot_access_admin_panel(self):
        self.login("simple_user", "User12345")
        response = self.client.get("/admin/index")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_admin_panel(self):
        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/index")
        self.assertEqual(response.status_code, 200)

    def test_root_department_saved_with_null_parent(self):
        self.login("admin_user", "Admin123")
        self.client.post(
            "/admin/departments/add",
            data={"name": "Разработка", "parent_id": 0},
            follow_redirects=True,
        )
        with self.app.app_context():
            department = Department.query.filter_by(name="Разработка").first()
            self.assertIsNotNone(department)
            self.assertIsNone(department.parent_id)


if __name__ == "__main__":
    unittest.main()
