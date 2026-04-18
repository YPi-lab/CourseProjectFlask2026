from flask import flash, redirect, render_template, request, url_for

from .admin_core import admin_required
from project_app.utils.db_utils import commit_with_handling
from project_app.forms import DepartmentForm
from project_app.models import ActiveVacancy, Department, Employee, Position, db


def iter_department_tree(department):
    yield department
    for child in department.sub_departments.order_by(Department.name).all():
        yield from iter_department_tree(child)


def get_descendant_ids(department):
    descendant_ids = set()
    for child in department.sub_departments.order_by(Department.name).all():
        descendant_ids.add(child.id)
        descendant_ids.update(get_descendant_ids(child))
    return descendant_ids


def build_department_choices(items, choices, excluded_ids=None, depth=0):
    excluded_ids = excluded_ids or set()
    for item in items:
        if item.id in excluded_ids:
            continue
        prefix = "    " * depth
        choices.append((item.id, f"{prefix}{item.name}" if prefix else item.name))
        build_department_choices(
            item.sub_departments.order_by(Department.name).all(),
            choices,
            excluded_ids=excluded_ids,
            depth=depth + 1,
        )


def get_department_tree(exclude_id=None, excluded_ids=None):
    parents = Department.query.filter_by(parent_id=None).order_by(Department.name).all()
    choices = [(0, "— Корневой отдел —")]
    ids_to_exclude = set(excluded_ids or [])
    if exclude_id:
        ids_to_exclude.add(exclude_id)
    build_department_choices(parents, choices, excluded_ids=ids_to_exclude)
    return choices


def register_department_routes(admin_bp):
    @admin_bp.route("/departments")
    @admin_required
    def departments():
        root_department = Department.query.filter_by(parent_id=None).all()
        return render_template("admin/departments.html", departments=root_department)

    @admin_bp.route("/departments/add", methods=["GET", "POST"])
    @admin_required
    def add_department():
        form = DepartmentForm()
        form.parent_id.choices = get_department_tree()
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.departments")
        if form.validate_on_submit():
            duplicate = Department.query.filter_by(name=form.name.data).first()
            if duplicate:
                flash(f'Ошибка: отдел "{form.name.data}" уже существует!', "danger")
                return render_template("admin/add_departments.html", form=form)

            db.session.add(Department(name=form.name.data, parent_id=form.parent_id.data or None))
            if commit_with_handling("Структура обновлена!", "Произошла ошибка при сохранении отдела."):
                return redirect(next_url)
        return render_template("admin/add_departments.html", form=form)

    @admin_bp.route("/department/edit/<int:dept_id>", methods=["GET", "POST"])
    @admin_required
    def edit_department(dept_id):
        dept = db.get_or_404(Department, dept_id)
        form = DepartmentForm(obj=dept)
        descendant_ids = get_descendant_ids(dept)
        form.parent_id.choices = get_department_tree(exclude_id=dept_id, excluded_ids=descendant_ids)
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.departments")

        if form.validate_on_submit():
            duplicate = Department.query.filter(
                Department.name == form.name.data,
                Department.id != dept_id,
            ).first()
            if duplicate:
                flash(f'Ошибка: название "{form.name.data}" уже занято другим отделом!', "danger")
                return render_template("admin/add_departments.html", form=form, edit=True)
            if form.parent_id.data in descendant_ids:
                flash("Нельзя назначить дочерний отдел родительским для своего предка.", "danger")
                return render_template("admin/add_departments.html", form=form, edit=True)

            dept.name = form.name.data
            dept.parent_id = form.parent_id.data or None
            if commit_with_handling("Отдел обновлен", "Ошибка при сохранении изменений отдела."):
                return redirect(next_url)

        if request.method == "GET":
            form.parent_id.data = dept.parent_id or 0
        return render_template("admin/add_departments.html", form=form, edit=True)

    @admin_bp.route("/departments/<int:dept_id>")
    @admin_required
    def department_detail(dept_id):
        dept = db.get_or_404(Department, dept_id)
        employees = dept.all_employees
        return render_template("admin/department_detail.html", dept=dept, employees=employees)

    @admin_bp.route("/department/delete/<int:dept_id>", methods=["POST"])
    @admin_required
    def delete_department(dept_id):
        dept = db.get_or_404(Department, dept_id)
        dept_name = dept.name
        department_ids = [item.id for item in iter_department_tree(dept)]
        affected_vacancies = ActiveVacancy.query.join(ActiveVacancy.position).filter(
            Position.department_id.in_(department_ids)
        ).all()
        affected_employees = Employee.query.join(Employee.position).filter(
            Position.department_id.in_(department_ids)
        ).all()
        for vacancy in affected_vacancies:
            db.session.delete(vacancy)
        for emp in affected_employees:
            emp.position_id = None
            emp.is_active = False
        db.session.delete(dept)
        if commit_with_handling(
            f"Отдел {dept_name} и вся его структура удалены. {len(affected_employees)} чел. переведены в архив.",
            "Не удалось удалить отдел.",
            category="warning",
        ):
            return redirect(url_for("admin.departments"))
        return redirect(url_for("admin.departments"))
