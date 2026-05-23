import unittest

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from project_app import create_app
from project_app.models import ActiveVacancy, User, Department, Position, Employee, db


def create_test_app():
    app = create_app(
        {
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    app.jinja_env.globals["csrf_token"] = lambda: "test-token"
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

    def test_login_redirects_to_safe_next_url(self):
        response = self.client.post(
            "/auth/login?next=/vacancies",
            data={"username": "simple_user", "password": "User12345"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/vacancies"))

    def test_login_ignores_external_next_url(self):
        response = self.client.post(
            "/auth/login?next=https://evil.example/phish",
            data={"username": "simple_user", "password": "User12345"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/"))

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

    def test_duplicate_department_is_not_created(self):
        with self.app.app_context():
            db.session.add(Department(name="Разработка"))
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/departments/add",
            data={"name": "Разработка", "parent_id": 0},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже существует", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertEqual(Department.query.filter_by(name="Разработка").count(), 1)

    def test_department_name_is_trimmed_on_create(self):
        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/departments/add",
            data={"name": "  Разработка  ", "parent_id": 0},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            department = Department.query.filter_by(name="Разработка").first()
            self.assertIsNotNone(department)
            self.assertEqual(Department.query.count(), 1)

    def test_add_department_respects_next_redirect(self):
        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/departments/add?next=/admin/positions/add",
            data={"name": "Разработка", "parent_id": 0},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/positions/add"))

    def test_edit_department_rejects_duplicate_name_and_keeps_original(self):
        with self.app.app_context():
            root = Department(name="Разработка")
            child = Department(name="Backend", parent=root)
            sibling = Department(name="Аналитика")
            db.session.add_all([root, child, sibling])
            db.session.commit()
            child_id = child.id
            root_id = root.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/department/edit/{child_id}",
            data={"name": "Аналитика", "parent_id": 0},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже занято другим отделом", response.get_data(as_text=True).lower())

        with self.app.app_context():
            unchanged_child = db.session.get(Department, child_id)
            self.assertEqual(unchanged_child.name, "Backend")
            self.assertEqual(unchanged_child.parent_id, root_id)

    def test_employee_search_works_by_keywords(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            db.session.add_all(
                [
                    Employee(
                        last_name="Иванов",
                        first_name="Петр",
                        middle_name="Сергеевич",
                        email="p.ivanov@example.com",
                        phone="+79990000001",
                        position_id=position.id,
                        is_active=True,
                    ),
                    Employee(
                        last_name="Сидоров",
                        first_name="Антон",
                        middle_name="Ильич",
                        email="anton@example.com",
                        phone="+79990000002",
                        position_id=position.id,
                        is_active=True,
                    ),
                ]
            )
            db.session.commit()

        self.login("admin_user", "Admin123")

        response = self.client.get("/admin/employees?q=Иванов+Петр")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Иванов Петр Сергеевич".encode("utf-8"), response.data)
        self.assertNotIn("Сидоров Антон Ильич".encode("utf-8"), response.data)

    def test_position_search_works_by_keywords(self):
        with self.app.app_context():
            development = Department(name="Разработка")
            analytics = Department(name="Аналитика")
            db.session.add_all([development, analytics])
            db.session.flush()

            db.session.add_all(
                [
                    Position(title="Backend Developer", department_id=development.id),
                    Position(title="System Analyst", department_id=analytics.id),
                ]
            )
            db.session.commit()

        self.login("admin_user", "Admin123")

        response = self.client.get("/admin/positions?q=Backend+Разработка")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Backend Developer".encode("utf-8"), response.data)
        self.assertNotIn("System Analyst".encode("utf-8"), response.data)

    def test_positions_filter_form_preserves_per_page(self):
        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/positions?per_page=35")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="per_page" value="35"', response.data)
        self.assertIn(b'name="page" value="1"', response.data)

    def test_employees_filter_form_preserves_per_page(self):
        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/employees?per_page=35")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="per_page" value="35"', response.data)
        self.assertIn(b'name="page" value="1"', response.data)

    def test_positions_filter_form_preserves_current_page(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()
            for idx in range(1, 12):
                db.session.add(Position(title=f"Должность {idx:02d}", department_id=department.id))
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/positions?page=2&per_page=10")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="page" value="2"', response.data)

    def test_employees_filter_form_preserves_current_page(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            for idx in range(1, 12):
                db.session.add(
                    Employee(
                        last_name=f"Сотрудник{idx:02d}",
                        first_name="Тест",
                        middle_name=None,
                        email=f"employee-filter-page-{idx}@example.com",
                        phone=f"+79991111{idx:03d}",
                        position_id=position.id,
                        is_active=True,
                    )
                )
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/employees?page=2&per_page=10")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="page" value="2"', response.data)

    def test_duplicate_position_in_same_department_is_not_created(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            db.session.add(Position(title="Backend Developer", department_id=department.id))
            db.session.commit()
            department_id = department.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/positions/add",
            data={"title": "Backend Developer", "department_id": department_id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже есть в отделе", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertEqual(Position.query.filter_by(title="Backend Developer", department_id=department_id).count(), 1)

    def test_position_title_is_trimmed_on_create(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.commit()
            department_id = department.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/positions/add",
            data={"title": "  Backend Developer  ", "department_id": department_id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            position = Position.query.filter_by(title="Backend Developer", department_id=department_id).first()
            self.assertIsNotNone(position)

    def test_edit_position_rejects_duplicate_in_same_department(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            first_position = Position(title="Backend Developer", department_id=department.id)
            second_position = Position(title="System Analyst", department_id=department.id)
            db.session.add_all([first_position, second_position])
            db.session.commit()
            department_id = department.id
            second_position_id = second_position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/position/edit/{second_position_id}",
            data={"title": "Backend Developer", "department_id": department_id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже существует должность", response.get_data(as_text=True).lower())

        with self.app.app_context():
            unchanged_position = db.session.get(Position, second_position_id)
            self.assertEqual(unchanged_position.title, "System Analyst")

    def test_add_position_respects_next_redirect(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.commit()
            department_id = department.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/positions/add?next=/admin/employee/add",
            data={"title": "Backend Developer", "department_id": department_id},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/employee/add"))

    def test_edit_missing_position_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/position/edit/999999")
        self.assertEqual(response.status_code, 404)

    def test_department_delete_moves_employees_out_of_staff(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            employee = Employee(
                last_name="Иванов",
                first_name="Петр",
                middle_name="Сергеевич",
                email="archive-test@example.com",
                phone="+79990000003",
                position_id=position.id,
                is_active=True,
            )
            db.session.add(employee)
            db.session.commit()

            dept_id = department.id
            employee_id = employee.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/department/delete/{dept_id}",
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            updated_employee = db.session.get(Employee, employee_id)
            self.assertIsNotNone(updated_employee)
            self.assertIsNone(updated_employee.position_id)
            self.assertFalse(updated_employee.is_active)

    def test_duplicate_employee_email_is_not_created(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            db.session.add(
                Employee(
                    last_name="Иванов",
                    first_name="Петр",
                    middle_name="Сергеевич",
                    email="duplicate@example.com",
                    phone="+79990000100",
                    position_id=position.id,
                    is_active=True,
                )
            )
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add",
            data={
                "last_name": "Сидоров",
                "first_name": "Антон",
                "middle_name": "Ильич",
                "email": "duplicate@example.com",
                "phone": "+79990000101",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже используется", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertEqual(Employee.query.filter_by(email="duplicate@example.com").count(), 1)

    def test_employee_email_is_normalized_to_lowercase(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add",
            data={
                "last_name": "Иванов",
                "first_name": "Петр",
                "middle_name": "Сергеевич",
                "email": "  TEST.USER@EXAMPLE.COM  ",
                "phone": "+79990000120",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            employee = Employee.query.filter_by(phone="+79990000120").first()
            self.assertIsNotNone(employee)
            self.assertEqual(employee.email, "test.user@example.com")

    def test_edit_employee_rejects_duplicate_phone(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            first_employee = Employee(
                last_name="Иванов",
                first_name="Петр",
                middle_name="Сергеевич",
                email="first@example.com",
                phone="+79990000110",
                position_id=position.id,
                is_active=True,
            )
            second_employee = Employee(
                last_name="Сидоров",
                first_name="Антон",
                middle_name="Ильич",
                email="second@example.com",
                phone="+79990000111",
                position_id=position.id,
                is_active=True,
            )
            db.session.add_all([first_employee, second_employee])
            db.session.commit()
            first_employee_id = first_employee.id
            second_employee_id = second_employee.id
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/employee/edit/{second_employee_id}",
            data={
                "last_name": "Сидоров",
                "first_name": "Антон",
                "middle_name": "Ильич",
                "email": "second@example.com",
                "phone": "+79990000110",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("телефон", response.get_data(as_text=True).lower())
        self.assertIn("занят", response.get_data(as_text=True).lower())

        with self.app.app_context():
            unchanged_employee = db.session.get(Employee, second_employee_id)
            self.assertEqual(unchanged_employee.phone, "+79990000111")
            self.assertIsNotNone(db.session.get(Employee, first_employee_id))

    def test_add_employee_rejects_invalid_phone_format(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add",
            data={
                "last_name": "Иванов",
                "first_name": "Петр",
                "middle_name": "Сергеевич",
                "email": "phone-check@example.com",
                "phone": "abc123",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("телефон должен содержать только цифры", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertIsNone(Employee.query.filter_by(email="phone-check@example.com").first())

    def test_add_employee_rejects_invalid_email_format(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add",
            data={
                "last_name": "Иванов",
                "first_name": "Петр",
                "middle_name": "Сергеевич",
                "email": "invalid-email",
                "phone": "+79990000121",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("введите корректный email-адрес", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertIsNone(Employee.query.filter_by(phone="+79990000121").first())

    def test_add_employee_rejects_invalid_position_choice(self):
        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add",
            data={
                "last_name": "Иванов",
                "first_name": "Петр",
                "middle_name": "Сергеевич",
                "email": "invalid-position@example.com",
                "phone": "+79990000112",
                "hire_date": "2026-04-18",
                "position_id": 999999,
                "is_active": "y",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("выберите корректное значение из списка", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertIsNone(Employee.query.filter_by(email="invalid-position@example.com").first())

    def test_add_employee_respects_next_redirect(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/admin/employee/add?next=/admin/departments",
            data={
                "last_name": "Иванов",
                "first_name": "Петр",
                "middle_name": "Сергеевич",
                "email": "next-redirect@example.com",
                "phone": "+79990000113",
                "hire_date": "2026-04-18",
                "position_id": position_id,
                "is_active": "y",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/departments"))

    def test_add_employee_prefills_position_from_department_query_param(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            other_department = Department(name="Аналитика")
            db.session.add(other_department)
            db.session.flush()

            first_position = Position(title="Backend Developer", department_id=department.id)
            second_position = Position(title="System Analyst", department_id=other_department.id)
            db.session.add_all([first_position, second_position])
            db.session.commit()
            department_id = department.id
            first_position_id = first_position.id

        self.login("admin_user", "Admin123")
        response = self.client.get(f"/admin/employee/add?dept_id={department_id}")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn(f'selected value="{first_position_id}"', page_text)

    def test_edit_missing_employee_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/employee/edit/999999")
        self.assertEqual(response.status_code, 404)

    def test_department_all_employees_includes_subdepartments(self):
        with self.app.app_context():
            root = Department(name="Разработка")
            child = Department(name="Backend", parent=root)
            db.session.add_all([root, child])
            db.session.flush()

            position = Position(title="Backend Developer", department_id=child.id)
            db.session.add(position)
            db.session.flush()

            employee = Employee(
                last_name="Иванов",
                first_name="Петр",
                middle_name="Сергеевич",
                email="nested-employee@example.com",
                phone="+79990000004",
                position_id=position.id,
                is_active=True,
            )
            db.session.add(employee)
            db.session.commit()

            refreshed_root = db.session.get(Department, root.id)
            self.assertEqual(len(refreshed_root.all_employees), 1)

    def test_department_detail_is_paginated_with_default_five_rows(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            for idx in range(1, 12):
                db.session.add(
                    Employee(
                        last_name=f"Сотрудник{idx:02d}",
                        first_name="Тест",
                        middle_name=None,
                        email=f"department-page-{idx}@example.com",
                        phone=f"+79990101{idx:03d}",
                        position_id=position.id,
                        is_active=True,
                    )
                )
            db.session.commit()
            dept_id = department.id

        self.login("admin_user", "Admin123")
        first_page = self.client.get(f"/admin/departments/{dept_id}")
        self.assertEqual(first_page.status_code, 200)
        self.assertIn("Сотрудник01 Тест".encode("utf-8"), first_page.data)
        self.assertNotIn("Сотрудник06 Тест".encode("utf-8"), first_page.data)

        second_page = self.client.get(f"/admin/departments/{dept_id}?page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertIn("Сотрудник06 Тест".encode("utf-8"), second_page.data)

    def test_departments_tree_shows_only_active_employees(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            db.session.add_all(
                [
                    Employee(
                        last_name="Активный",
                        first_name="Сотрудник",
                        middle_name=None,
                        email="active-list@example.com",
                        phone="+79990000130",
                        position_id=position.id,
                        is_active=True,
                    ),
                    Employee(
                        last_name="Неактивный",
                        first_name="Сотрудник",
                        middle_name=None,
                        email="inactive-list@example.com",
                        phone="+79990000131",
                        position_id=position.id,
                        is_active=False,
                    ),
                ]
            )
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/departments")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn("Активный Сотрудник", page_text)
        self.assertNotIn("Неактивный Сотрудник", page_text)

    def test_vacancy_publication_ignores_duplicate_publish(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        first_response = self.client.post(
            "/vacancies",
            data={"position_id": position_id, "action": "add"},
            follow_redirects=True,
        )
        second_response = self.client.post(
            "/vacancies",
            data={"position_id": position_id, "action": "add"},
            follow_redirects=True,
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(ActiveVacancy.query.filter_by(position_id=position_id).count(), 1)

    def test_position_uniqueness_is_enforced_at_database_level(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            db.session.add(Position(title="Backend Developer", department_id=department.id))
            db.session.commit()

            db.session.add(Position(title="Backend Developer", department_id=department.id))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_active_vacancy_uniqueness_is_enforced_at_database_level(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            db.session.add(ActiveVacancy(position_id=position.id))
            db.session.commit()

            db.session.add(ActiveVacancy(position_id=position.id))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_vacancies_page_shows_empty_state(self):
        self.login("simple_user", "User12345")
        response = self.client.get("/vacancies")
        self.assertEqual(response.status_code, 200)
        self.assertIn("открытых вакансий нет", response.get_data(as_text=True).lower())

    def test_vacancies_page_shows_published_positions(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            first_position = Position(title="Backend Developer", department_id=department.id)
            second_position = Position(title="QA Engineer", department_id=department.id)
            db.session.add_all([first_position, second_position])
            db.session.flush()

            db.session.add_all(
                [
                    ActiveVacancy(position_id=first_position.id),
                    ActiveVacancy(position_id=second_position.id),
                ]
            )
            db.session.commit()

        self.login("simple_user", "User12345")
        response = self.client.get("/vacancies")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn("Backend Developer", page_text)
        self.assertIn("QA Engineer", page_text)
        self.assertIn("Разработка", page_text)

    def test_vacancies_publish_form_shows_only_unpublished_positions(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            published_position = Position(title="Backend Developer", department_id=department.id)
            available_position = Position(title="QA Engineer", department_id=department.id)
            db.session.add_all([published_position, available_position])
            db.session.flush()
            published_position_id = published_position.id
            available_position_id = available_position.id

            db.session.add(ActiveVacancy(position_id=published_position.id))
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/vacancies")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn('<option value="%d">' % available_position_id, page_text)
        self.assertNotIn('<option value="%d">' % published_position_id, page_text)

    def test_vacancy_publication_rejects_invalid_position(self):
        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/vacancies",
            data={"position_id": 999999, "action": "add"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("должность не найдена", response.get_data(as_text=True).lower())

    def test_vacancy_publication_rejects_unknown_action(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/vacancies",
            data={"position_id": position_id, "action": "archive"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("неизвестное действие", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertEqual(ActiveVacancy.query.filter_by(position_id=position_id).count(), 0)

    def test_regular_user_cannot_manage_vacancies_via_post(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.commit()
            position_id = position.id

        self.login("simple_user", "User12345")
        response = self.client.post(
            "/vacancies",
            data={"position_id": position_id, "action": "add"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 403)

        with self.app.app_context():
            self.assertIsNone(ActiveVacancy.query.filter_by(position_id=position_id).first())

    def test_position_delete_removes_active_vacancy(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            vacancy = ActiveVacancy(position_id=position.id)
            db.session.add(vacancy)
            db.session.commit()

            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/position/delete/{position_id}",
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(ActiveVacancy.query.filter_by(position_id=position_id).first())

    def test_delete_missing_department_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.post("/admin/department/delete/999999", data={})
        self.assertEqual(response.status_code, 404)

    def test_delete_missing_position_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.post("/admin/position/delete/999999", data={})
        self.assertEqual(response.status_code, 404)

    def test_delete_missing_employee_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.post("/admin/employee/delete/999999", data={})
        self.assertEqual(response.status_code, 404)

    def test_delete_missing_user_returns_404(self):
        self.login("admin_user", "Admin123")
        response = self.client.post("/admin/delete_user/999999", data={})
        self.assertEqual(response.status_code, 404)

    def test_employee_list_ignores_invalid_sort_direction(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            db.session.add(
                Employee(
                    last_name="Иванов",
                    first_name="Петр",
                    middle_name="Сергеевич",
                    email="sort-test@example.com",
                    phone="+79990000102",
                    position_id=position.id,
                    is_active=True,
                )
            )
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/employees?sort=status&direction=sideways")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Иванов Петр Сергеевич".encode("utf-8"), response.data)

    def test_employee_list_is_paginated_by_ten_rows(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            position = Position(title="Backend Developer", department_id=department.id)
            db.session.add(position)
            db.session.flush()

            for idx in range(1, 12):
                db.session.add(
                    Employee(
                        last_name=f"Сотрудник{idx:02d}",
                        first_name="Тест",
                        middle_name=None,
                        email=f"employee-page-{idx}@example.com",
                        phone=f"+79990001{idx:03d}",
                        position_id=position.id,
                        is_active=True,
                    )
                )
            db.session.commit()

        self.login("admin_user", "Admin123")
        first_page = self.client.get("/admin/employees?page=1&per_page=10")
        self.assertEqual(first_page.status_code, 200)
        self.assertIn("Сотрудник01 Тест".encode("utf-8"), first_page.data)
        self.assertNotIn("Сотрудник11 Тест".encode("utf-8"), first_page.data)

        second_page = self.client.get("/admin/employees?page=2&per_page=10")
        self.assertEqual(second_page.status_code, 200)
        self.assertIn("Сотрудник11 Тест".encode("utf-8"), second_page.data)

    def test_position_list_ignores_invalid_sort_direction(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            db.session.add(Position(title="Backend Developer", department_id=department.id))
            db.session.commit()

        self.login("admin_user", "Admin123")
        response = self.client.get("/admin/positions?sort=department&direction=sideways")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Backend Developer".encode("utf-8"), response.data)

    def test_position_list_is_paginated_by_ten_rows(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            db.session.add(department)
            db.session.flush()

            for idx in range(1, 12):
                db.session.add(Position(title=f"Должность {idx:02d}", department_id=department.id))
            db.session.commit()

        self.login("admin_user", "Admin123")
        first_page = self.client.get("/admin/positions?page=1&per_page=10")
        self.assertEqual(first_page.status_code, 200)
        self.assertIn("Должность 01".encode("utf-8"), first_page.data)
        self.assertNotIn("Должность 11".encode("utf-8"), first_page.data)

        second_page = self.client.get("/admin/positions?page=2&per_page=10")
        self.assertEqual(second_page.status_code, 200)
        self.assertIn("Должность 11".encode("utf-8"), second_page.data)

    def test_department_delete_removes_active_vacancies_in_structure(self):
        with self.app.app_context():
            department = Department(name="Разработка")
            child_department = Department(name="Backend", parent=department)
            db.session.add_all([department, child_department])
            db.session.flush()

            position = Position(title="Backend Developer", department_id=child_department.id)
            db.session.add(position)
            db.session.flush()

            vacancy = ActiveVacancy(position_id=position.id)
            db.session.add(vacancy)
            db.session.commit()

            dept_id = department.id
            position_id = position.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/department/delete/{dept_id}",
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(ActiveVacancy.query.filter_by(position_id=position_id).first())

    def test_department_cannot_be_moved_under_its_child(self):
        with self.app.app_context():
            root = Department(name="Разработка")
            child = Department(name="Backend", parent=root)
            db.session.add_all([root, child])
            db.session.commit()
            root_id = root.id
            child_id = child.id

        self.login("admin_user", "Admin123")
        form_response = self.client.get(f"/admin/department/edit/{root_id}")
        self.assertEqual(form_response.status_code, 200)
        self.assertNotIn("Backend".encode("utf-8"), form_response.data)

        response = self.client.post(
            f"/admin/department/edit/{root_id}",
            data={"name": "Разработка", "parent_id": child_id},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            updated_root = db.session.get(Department, root_id)
            self.assertIsNone(updated_root.parent_id)

    def test_user_can_change_password(self):
        self.login("simple_user", "User12345")

        response = self.client.post(
            "/auth/account/password",
            data={
                "current_password": "User12345",
                "new_password": "NewUser123",
                "confirm_new_password": "NewUser123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        self.client.get("/auth/logout", follow_redirects=True)
        self.login("simple_user", "User12345")
        old_password_access = self.client.get("/vacancies")
        self.assertEqual(old_password_access.status_code, 302)
        self.assertIn("/auth/login", old_password_access.location)

        self.login("simple_user", "NewUser123")
        new_password_access = self.client.get("/vacancies")
        self.assertEqual(new_password_access.status_code, 200)

    def test_user_cannot_change_password_with_wrong_current_password(self):
        self.login("simple_user", "User12345")

        response = self.client.post(
            "/auth/account/password",
            data={
                "current_password": "WrongPassword",
                "new_password": "NewUser123",
                "confirm_new_password": "NewUser123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("текущий пароль указан неверно", response.get_data(as_text=True).lower())

        self.client.get("/auth/logout", follow_redirects=True)
        self.login("simple_user", "NewUser123")
        denied_access = self.client.get("/vacancies")
        self.assertEqual(denied_access.status_code, 302)
        self.assertIn("/auth/login", denied_access.location)

        self.login("simple_user", "User12345")
        restored_access = self.client.get("/vacancies")
        self.assertEqual(restored_access.status_code, 200)

    def test_user_can_delete_own_account(self):
        self.login("simple_user", "User12345")
        response = self.client.post(
            "/auth/account/delete",
            data={"password": "User12345"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            deleted_user = User.query.filter_by(username="simple_user").first()
            self.assertIsNone(deleted_user)

    def test_cannot_delete_last_admin_account(self):
        self.login("admin_user", "Admin123")
        response = self.client.post(
            "/auth/account/delete",
            data={"password": "Admin123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("последнего администратора".encode("utf-8"), response.data)

        with self.app.app_context():
            admin_user = User.query.filter_by(username="admin_user").first()
            self.assertIsNotNone(admin_user)

    def test_registration_trims_username_and_preserves_uniqueness(self):
        response = self.client.post(
            "/auth/register",
            data={
                "username": "  simple_user  ",
                "password": "User12345",
                "confirm_password": "User12345",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("уже существует", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertEqual(User.query.filter_by(username="simple_user").count(), 1)

    def test_registration_rejects_password_without_digits(self):
        response = self.client.post(
            "/auth/register",
            data={
                "username": "new_user",
                "password": "Password",
                "confirm_password": "Password",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("пароль должен содержать буквы и цифры", response.get_data(as_text=True).lower())

        with self.app.app_context():
            self.assertIsNone(User.query.filter_by(username="new_user").first())

    def test_change_password_rejects_password_without_letters(self):
        self.login("simple_user", "User12345")
        response = self.client.post(
            "/auth/account/password",
            data={
                "current_password": "User12345",
                "new_password": "12345678",
                "confirm_new_password": "12345678",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("пароль должен содержать буквы и цифры", response.get_data(as_text=True).lower())

        self.client.get("/auth/logout", follow_redirects=True)
        self.login("simple_user", "12345678")
        denied_access = self.client.get("/vacancies")
        self.assertEqual(denied_access.status_code, 302)
        self.assertIn("/auth/login", denied_access.location)

    def test_admin_cannot_revoke_own_admin_rights(self):
        self.login("admin_user", "Admin123")
        with self.app.app_context():
            admin_user = User.query.filter_by(username="admin_user").first()
            admin_id = admin_user.id

        response = self.client.post(
            f"/admin/toggle_admin/{admin_id}",
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("не можете лишить прав администратора самого себя", response.get_data(as_text=True).lower())

        with self.app.app_context():
            refreshed_admin = db.session.get(User, admin_id)
            self.assertTrue(refreshed_admin.is_admin)

    def test_admin_cannot_delete_current_session_user_from_admin_list(self):
        self.login("admin_user", "Admin123")
        with self.app.app_context():
            admin_user = User.query.filter_by(username="admin_user").first()
            admin_id = admin_user.id

        response = self.client.post(
            f"/admin/delete_user/{admin_id}",
            data={},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("нельзя удалить текущего администратора", response.get_data(as_text=True).lower())

        with self.app.app_context():
            refreshed_admin = db.session.get(User, admin_id)
            self.assertIsNotNone(refreshed_admin)



    def test_add_employee_filters_positions_by_department(self):
        with self.app.app_context():
            dept1 = Department(name="Dept 1")
            dept2 = Department(name="Dept 2")
            db.session.add_all([dept1, dept2])
            db.session.flush()

            pos1 = Position(title="Pos 1", department_id=dept1.id)
            pos2 = Position(title="Pos 2", department_id=dept2.id)
            db.session.add_all([pos1, pos2])
            db.session.commit()
            
            dept1_id = dept1.id
            pos1_id = pos1.id
            pos2_id = pos2.id

        self.login("admin_user", "Admin123")
        
        # When dept_id is provided, only positions from that department should be in choices
        response = self.client.get(f"/admin/employee/add?dept_id={dept1_id}")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn(f'value="{pos1_id}"', page_text)
        self.assertNotIn(f'value="{pos2_id}"', page_text)
        
        # When dept_id is NOT provided, all positions should be in choices
        response = self.client.get("/admin/employee/add")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn(f'value="{pos1_id}"', page_text)
        self.assertIn(f'value="{pos2_id}"', page_text)


    def test_add_employee_from_department_redirects_back_to_department(self):
        with self.app.app_context():
            dept = Department(name="Redirect Dept")
            db.session.add(dept)
            db.session.flush()
            pos = Position(title="Redirect Pos", department_id=dept.id)
            db.session.add(pos)
            db.session.commit()
            dept_id = dept.id
            pos_id = pos.id

        self.login("admin_user", "Admin123")
        response = self.client.post(
            f"/admin/employee/add?dept_id={dept_id}",
            data={
                "last_name": "Redirect",
                "first_name": "Test",
                "email": "redirect@example.com",
                "phone": "+79991234567",
                "position_id": pos_id,
                "is_active": "y",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/admin/departments/{dept_id}", response.location)
if __name__ == "__main__":
    unittest.main()
