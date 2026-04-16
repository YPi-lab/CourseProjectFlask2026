from flask import flash, redirect, render_template, url_for

from admin_core import admin_required
from admin_department_routes import get_department_tree
from db_utils import commit_with_handling
from forms import PositionForm
from models import Department, Employee, Position, db


def get_department_choices():
    return [(choice_id, label) for choice_id, label in get_department_tree() if choice_id != 0]


def register_position_routes(admin_bp):
    @admin_bp.route("/positions")
    @admin_required
    def positions():
        all_positions = Position.query.join(Department).all()
        return render_template("admin/position.html", positions=all_positions)

    @admin_bp.route("/positions/add", methods=["GET", "POST"])
    @admin_required
    def add_position():
        form = PositionForm()
        form.department_id.choices = get_department_choices()

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
                return redirect(url_for("admin.positions"))

        return render_template("admin/add_position.html", form=form)

    @admin_bp.route("/position/edit/<int:pos_id>", methods=["GET", "POST"])
    @admin_required
    def edit_position(pos_id):
        pos = Position.query.get_or_404(pos_id)
        form = PositionForm(obj=pos)
        form.department_id.choices = get_department_choices()

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
                return redirect(url_for("admin.positions"))

        return render_template("admin/add_position.html", form=form, edit=True)

    @admin_bp.route("/position/delete/<int:pos_id>", methods=["POST"])
    @admin_required
    def delete_position(pos_id):
        pos = Position.query.get_or_404(pos_id)
        affected_employees = Employee.query.filter_by(position_id=pos.id).all()
        for emp in affected_employees:
            emp.position_id = None
            emp.is_active = False

        pos_title = pos.title
        db.session.delete(pos)
        if commit_with_handling(
            f'Должность "{pos_title}" удалена. {len(affected_employees)} чел. переведены в архив.',
            "Не удалось удалить должность.",
            category="warning",
        ):
            return redirect(url_for("admin.positions"))
        return redirect(url_for("admin.positions"))
