from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from .admin_core import admin_required
from project_app.utils.db_utils import commit_with_handling
from project_app.utils.request_utils import get_next_url
from project_app.forms import EmployeeForm
from project_app.models import Department, Employee, Position, db

PER_PAGE_OPTIONS = {5, 10, 15, 30, 35}
DEFAULT_PER_PAGE = 5


def get_position_choices(department_id=None):
    query = Position.query
    if department_id:
        query = query.filter_by(department_id=department_id)
    return [(p.id, f"{p.title} ({p.department.name})") for p in query.all()]


def _render_employee_form(form, edit=False):
    return render_template("admin/add_employee.html", form=form, edit=edit)


def _is_unique_employee_contact(form, employee_id=None):
    email_exists = Employee.query.filter(Employee.email == form.email.data, Employee.id != employee_id).first()
    if email_exists:
        message = "занят!" if employee_id else "уже используется!"
        flash(f"Ошибка: Почта {form.email.data} {message}", "danger")
        return False

    phone_exists = Employee.query.filter(Employee.phone == form.phone.data, Employee.id != employee_id).first()
    if phone_exists:
        message = "занят!" if employee_id else "уже зарегистрирован!"
        flash(f"Ошибка: Телефон {form.phone.data} {message}", "danger")
        return False

    return True


def _apply_employee_form(employee, form):
    employee.last_name = form.last_name.data
    employee.first_name = form.first_name.data
    employee.middle_name = form.middle_name.data
    employee.email = form.email.data
    employee.phone = form.phone.data
    employee.hire_date = form.hire_date.data
    employee.position_id = form.position_id.data
    employee.is_active = form.is_active.data


def register_employee_routes(admin_bp):
    @admin_bp.route("/employees")
    @admin_required
    def employees():
        search_query = request.args.get("q", "").strip()
        search_terms = [term for term in search_query.split() if term]
        sort = request.args.get("sort", "name")
        direction = request.args.get("direction", "asc")
        page = request.args.get("page", default=1, type=int)
        per_page = request.args.get("per_page", default=DEFAULT_PER_PAGE, type=int)
        if not page or page < 1:
            page = 1
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
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

        base_query = Employee.query.outerjoin(Position, Employee.position_id == Position.id).outerjoin(
            Department, Position.department_id == Department.id
        )
        if search_terms:
            for term in search_terms:
                term_lower = term.lower()
                base_query = base_query.filter(
                    or_(
                        Employee.last_name.contains(term),
                        Employee.first_name.contains(term),
                        func.coalesce(Employee.middle_name, "").contains(term),
                        func.lower(Employee.email).contains(term_lower),
                    )
                )

        total_employees = base_query.with_entities(func.count(func.distinct(Employee.id))).scalar() or 0
        total_pages = max((total_employees - 1) // per_page + 1, 1)
        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page
        all_employees = (
            base_query
            .order_by(order_expression, Employee.last_name.asc(), Employee.first_name.asc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return render_template(
            "admin/employees.html",
            employees=all_employees,
            total_employees=total_employees,
            sort=sort,
            direction=direction,
            q=search_query,
            page=page,
            total_pages=total_pages,
            per_page=per_page,
        )

    @admin_bp.route("/employee/add", methods=["GET", "POST"])
    @admin_required
    def add_employee():
        dept_id = request.args.get("dept_id", type=int)
        form = EmployeeForm()
        form.position_id.choices = get_position_choices(dept_id)
        next_val = request.args.get("next") or request.form.get("next")
        if next_val:
            next_url = next_val
        elif dept_id:
            next_url = url_for("admin.department_detail", dept_id=dept_id)
        else:
            next_url = url_for("admin.employees")

        if request.method == "GET" and dept_id and form.position_id.choices:
            default_position = (
                Position.query
                .filter_by(department_id=dept_id)
                .order_by(Position.title.asc())
                .first()
            )
            if default_position and any(choice_id == default_position.id for choice_id, _ in form.position_id.choices):
                form.position_id.data = default_position.id

        if form.validate_on_submit():
            if not _is_unique_employee_contact(form):
                return _render_employee_form(form)

            employee = Employee()
            _apply_employee_form(employee, form)
            db.session.add(employee)
            if commit_with_handling("Сотрудник добавлен", "Не удалось сохранить данные сотрудника."):
                return redirect(next_url)
        return _render_employee_form(form)

    @admin_bp.route("/employee/edit/<int:emp_id>", methods=["GET", "POST"])
    @admin_required
    def edit_employee(emp_id):
        emp = db.get_or_404(Employee, emp_id)
        form = EmployeeForm(obj=emp)
        form.position_id.choices = get_position_choices()
        next_url = get_next_url("admin.employees")
        if form.validate_on_submit():
            if not _is_unique_employee_contact(form, employee_id=emp_id):
                return _render_employee_form(form, edit=True)

            _apply_employee_form(emp, form)
            if commit_with_handling("Данные сотрудника обновлены", "Ошибка при сохранении изменений сотрудника."):
                return redirect(next_url)
        return _render_employee_form(form, edit=True)

    @admin_bp.route("/employee/delete/<int:emp_id>", methods=["POST"])
    @admin_required
    def delete_employee(emp_id):
        emp = db.get_or_404(Employee, emp_id)
        name = emp.full_name
        db.session.delete(emp)
        next_url = get_next_url("admin.employees")
        if commit_with_handling(f"Сотрудник {name} удален из базы", "Не удалось удалить сотрудника."):
            return redirect(next_url)
        return redirect(next_url)
