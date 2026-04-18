from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from .admin_core import admin_required
from project_app.utils.db_utils import commit_with_handling
from project_app.forms import EmployeeForm
from project_app.models import Department, Employee, Position, db


def get_position_choices():
    return [(p.id, f"{p.title} ({p.department.name})") for p in Position.query.all()]


def register_employee_routes(admin_bp):
    @admin_bp.route("/employees")
    @admin_required
    def employees():
        search_query = request.args.get("q", "").strip()
        search_terms = [term for term in search_query.split() if term]
        sort = request.args.get("sort", "name")
        direction = request.args.get("direction", "asc")
        if direction not in {"asc", "desc"}:
            direction = "asc"

        sortable_fields = {
            "name": func.lower(Employee.last_name),
            "department": func.lower(func.coalesce(Department.name, "")),
            "position": func.lower(func.coalesce(Position.title, "")),
            "hire_date": Employee.hire_date,
            "status": Employee.is_active,
        }
        sort_column = sortable_fields.get(sort, sortable_fields["name"])
        order_expression = sort_column.desc() if direction == "desc" else sort_column.asc()

        employees_query = Employee.query.outerjoin(Position, Employee.position_id == Position.id).outerjoin(
            Department, Position.department_id == Department.id
        )
        if search_terms:
            for term in search_terms:
                term_lower = term.lower()
                employees_query = employees_query.filter(
                    or_(
                        Employee.last_name.contains(term),
                        Employee.first_name.contains(term),
                        func.coalesce(Employee.middle_name, "").contains(term),
                        func.lower(Employee.email).contains(term_lower),
                    )
                )

        all_employees = employees_query.order_by(order_expression, Employee.last_name.asc(), Employee.first_name.asc()).all()
        return render_template(
            "admin/employees.html",
            employees=all_employees,
            sort=sort,
            direction=direction,
            q=search_query,
        )

    @admin_bp.route("/employee/add", methods=["GET", "POST"])
    @admin_required
    def add_employee():
        form = EmployeeForm()
        form.position_id.choices = get_position_choices()
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.employees")
        if form.validate_on_submit():
            if Employee.query.filter_by(email=form.email.data).first():
                flash(f"Ошибка: Почта {form.email.data} уже используется!", "danger")
                return render_template("admin/add_employee.html", form=form)
            if Employee.query.filter_by(phone=form.phone.data).first():
                flash(f"Ошибка: Телефон {form.phone.data} уже зарегистрирован!", "danger")
                return render_template("admin/add_employee.html", form=form)

            db.session.add(
                Employee(
                    last_name=form.last_name.data,
                    first_name=form.first_name.data,
                    middle_name=form.middle_name.data,
                    email=form.email.data,
                    phone=form.phone.data,
                    hire_date=form.hire_date.data,
                    position_id=form.position_id.data,
                    is_active=form.is_active.data,
                )
            )
            if commit_with_handling("Сотрудник добавлен", "Не удалось сохранить данные сотрудника."):
                return redirect(next_url)
        return render_template("admin/add_employee.html", form=form)

    @admin_bp.route("/employee/edit/<int:emp_id>", methods=["GET", "POST"])
    @admin_required
    def edit_employee(emp_id):
        emp = db.get_or_404(Employee, emp_id)
        form = EmployeeForm(obj=emp)
        form.position_id.choices = get_position_choices()
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.employees")
        if form.validate_on_submit():
            if Employee.query.filter(Employee.email == form.email.data, Employee.id != emp_id).first():
                flash(f"Ошибка: Email {form.email.data} уже занят!", "danger")
                return render_template("admin/add_employee.html", form=form, edit=True)
            if Employee.query.filter(Employee.phone == form.phone.data, Employee.id != emp_id).first():
                flash(f"Ошибка: Телефон {form.phone.data} уже занят!", "danger")
                return render_template("admin/add_employee.html", form=form, edit=True)

            emp.last_name = form.last_name.data
            emp.first_name = form.first_name.data
            emp.middle_name = form.middle_name.data
            emp.email = form.email.data
            emp.phone = form.phone.data
            emp.hire_date = form.hire_date.data
            emp.position_id = form.position_id.data
            emp.is_active = form.is_active.data
            if commit_with_handling("Данные сотрудника обновлены", "Ошибка при сохранении изменений сотрудника."):
                return redirect(next_url)
        return render_template("admin/add_employee.html", form=form, edit=True)

    @admin_bp.route("/employee/delete/<int:emp_id>", methods=["POST"])
    @admin_required
    def delete_employee(emp_id):
        emp = db.get_or_404(Employee, emp_id)
        name = emp.full_name
        db.session.delete(emp)
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.employees")
        if commit_with_handling(f"Сотрудник {name} удален из базы", "Не удалось удалить сотрудника."):
            return redirect(next_url)
        return redirect(next_url)
