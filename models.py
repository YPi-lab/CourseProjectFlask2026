from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    has_completed_survey = db.Column(db.Boolean, default=False)


class Department(db.Model):
    __tablename__ = 'department'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    sub_departments = db.relationship(
        'Department',
        backref=db.backref('parent', remote_side=[id]),
        cascade="all, delete-orphan",  # Теперь удаление предка удалит всех потомков
        lazy='dynamic'
    )
    positions = db.relationship('Position', backref='department', cascade="all,delete-orphan", lazy='select')

    def __repr__(self):
        return f'<Department {self.name}>'

    @property
    def all_employees(self):
        employees_list = []
        for pos in self.positions:
            active_emps = pos.employees.filter_by(is_active=True).all()
            employees_list.extend(active_emps)
        return employees_list


class Position(db.Model):
    __tablename__ = 'position'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)

    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)

    employees = db.relationship('Employee', backref='position', lazy='dynamic')

    def __repr__(self):
        return f'<Position {self.title}>'


class Employee(db.Model):
    __tablename__ = 'employee'
    id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    middle_name = db.Column(db.String(150))

    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(150), unique=True, nullable=False)

    hire_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    position_id = db.Column(db.Integer, db.ForeignKey('position.id'), nullable=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name} {self.middle_name or ''}".strip()

    def __repr__(self):
        return f'<Employee {self.last_name}>'
