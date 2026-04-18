from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from .admin_core import admin_required
from .admin_department_routes import get_department_tree
from project_app.utils.db_utils import commit_with_handling
from project_app.forms import PositionForm
from project_app.models import ActiveVacancy, Department, Employee, Position, db


def get_department_choices():
    return [(choice_id, label) for choice_id, label in get_department_tree() if choice_id != 0]


def register_position_routes(admin_bp):
    @admin_bp.route("/positions")
    @admin_required
    def positions():
        search_query = request.args.get("q", "").strip()
        search_terms = [term for term in search_query.split() if term]
        sort = request.args.get("sort", "title")
        direction = request.args.get("direction", "asc")
        if direction not in {"asc", "desc"}:
            direction = "asc"

        sortable_fields = {
            "title": func.lower(Position.title),
            "department": func.lower(Department.name),
            "employees": func.count(Employee.id),
        }
        sort_column = sortable_fields.get(sort, sortable_fields["title"])
        order_expression = sort_column.desc() if direction == "desc" else sort_column.asc()

        positions_query = Position.query.join(Department).outerjoin(Employee, Employee.position_id == Position.id)
        if search_terms:
            for term in search_terms:
                term_lower = term.lower()
                positions_query = positions_query.filter(
                    or_(
                        Position.title.contains(term),
                        Department.name.contains(term),
                        func.lower(Position.title).contains(term_lower),
                        func.lower(Department.name).contains(term_lower),
                    )
                )

        all_positions = positions_query.group_by(Position.id, Department.id).order_by(order_expression, Position.title.asc()).all()
        return render_template(
            "admin/position.html",
            positions=all_positions,
            sort=sort,
            direction=direction,
            q=search_query,
        )

    @admin_bp.route("/positions/add", methods=["GET", "POST"])
    @admin_required
    def add_position():
        form = PositionForm()
        form.department_id.choices = get_department_choices()
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.positions")

        if form.validate_on_submit():
            existing_pos = Position.query.filter_by(
                title=form.title.data,
                department_id=form.department_id.data,
            ).first()
            if existing_pos:
                dept_name = dict(form.department_id.choices).get(form.department_id.data)
                flash(f'Ошибка: Должность "{form.title.data}" уже есть в отделе "{dept_name}"!', "danger")
                return render_template("admin/add_position.html", form=form)

            db.session.add(Position(title=form.title.data, department_id=form.department_id.data))
            if commit_with_handling(
                f'Должность "{form.title.data}" создана!',
                "Ошибка при сохранении должности.",
            ):
                return redirect(next_url)

        return render_template("admin/add_position.html", form=form)

    @admin_bp.route("/position/edit/<int:pos_id>", methods=["GET", "POST"])
    @admin_required
    def edit_position(pos_id):
        pos = db.get_or_404(Position, pos_id)
        form = PositionForm(obj=pos)
        form.department_id.choices = get_department_choices()
        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.positions")

        if form.validate_on_submit():
            duplicate = Position.query.filter(
                Position.title == form.title.data,
                Position.department_id == form.department_id.data,
                Position.id != pos_id,
            ).first()
            if duplicate:
                dept_name = dict(form.department_id.choices).get(form.department_id.data)
                flash(f'Ошибка: В отделе "{dept_name}" уже существует должность "{form.title.data}"!', "danger")
                return render_template("admin/add_position.html", form=form, edit=True)

            pos.title = form.title.data
            pos.department_id = form.department_id.data
            if commit_with_handling(
                f'Должность "{pos.title}" обновлена',
                "Ошибка при обновлении должности.",
            ):
                return redirect(next_url)

        return render_template("admin/add_position.html", form=form, edit=True)

    @admin_bp.route("/position/delete/<int:pos_id>", methods=["POST"])
    @admin_required
    def delete_position(pos_id):
        pos = db.get_or_404(Position, pos_id)
        affected_employees = Employee.query.filter_by(position_id=pos.id).all()
        active_vacancies = ActiveVacancy.query.filter_by(position_id=pos.id).all()
        for emp in affected_employees:
            emp.position_id = None
            emp.is_active = False
        for vacancy in active_vacancies:
            db.session.delete(vacancy)

        next_url = request.args.get("next") or request.form.get("next") or url_for("admin.positions")
        pos_title = pos.title
        db.session.delete(pos)
        if commit_with_handling(
            f'Должность "{pos_title}" удалена. {len(affected_employees)} чел. переведены в архив.',
            "Не удалось удалить должность.",
            category="warning",
        ):
            return redirect(next_url)
        return redirect(next_url)
