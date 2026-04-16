from flask import flash, redirect, render_template, request, url_for

from admin_core import admin_required
from db_utils import commit_with_handling
from forms import DepartmentForm
from models import Department, db


def get_department_tree(exclude_id=None):
    parents = Department.query.filter_by(parent_id=None).order_by(Department.name).all()
    choices = [(0, "--- КОРНЕВОЙ ОТДЕЛ ---")]
    for parent in parents:
        if exclude_id and parent.id == exclude_id:
            continue
        choices.append((parent.id, parent.name.upper()))
        children = parent.sub_departments.order_by(Department.name).all()
        for child in children:
            if exclude_id and child.id == exclude_id:
                continue
            choices.append((child.id, f"    - {child.name}"))
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
        if form.validate_on_submit():
            duplicate = Department.query.filter_by(name=form.name.data).first()
            if duplicate:
                flash(f'Ошибка: отдел "{form.name.data}" уже существует!', "danger")
                return render_template("admin/add_departments.html", form=form)

            db.session.add(Department(name=form.name.data, parent_id=form.parent_id.data or None))
            if commit_with_handling("Структура обновлена!", "Произошла ошибка при сохранении отдела."):
                return redirect(url_for("admin.departments"))
        return render_template("admin/add_departments.html", form=form)

    @admin_bp.route("/department/edit/<int:dept_id>", methods=["GET", "POST"])
    @admin_required
    def edit_department(dept_id):
        dept = Department.query.get_or_404(dept_id)
        form = DepartmentForm(obj=dept)
        form.parent_id.choices = get_department_tree(exclude_id=dept_id)

        if form.validate_on_submit():
            duplicate = Department.query.filter(
                Department.name == form.name.data,
                Department.id != dept_id,
            ).first()
            if duplicate:
                flash(f'Ошибка: название "{form.name.data}" уже занято другим отделом!', "danger")
                return render_template("admin/add_departments.html", form=form, edit=True)

            dept.name = form.name.data
            dept.parent_id = form.parent_id.data or None
            if commit_with_handling("Отдел обновлен", "Ошибка при сохранении изменений отдела."):
                return redirect(url_for("admin.departments"))

        if request.method == "GET":
            form.parent_id.data = dept.parent_id or 0
        return render_template("admin/add_departments.html", form=form, edit=True)

    @admin_bp.route("/departments/<int:dept_id>")
    @admin_required
    def department_detail(dept_id):
        dept = Department.query.get_or_404(dept_id)
        employees = dept.all_employees
        return render_template("admin/department_detail.html", dept=dept, employees=employees)

    @admin_bp.route("/department/delete/<int:dept_id>", methods=["POST"])
    @admin_required
    def delete_department(dept_id):
        dept = Department.query.get_or_404(dept_id)
        dept_name = dept.name
        db.session.delete(dept)
        if commit_with_handling(
            f"Отдел {dept_name} и вся его структура удалены",
            "Не удалось удалить отдел.",
        ):
            return redirect(url_for("admin.departments"))
        return redirect(url_for("admin.departments"))
