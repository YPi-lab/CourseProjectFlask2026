from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user, login_required

from project_app.models import Position, db, ActiveVacancy
from project_app.utils.db_utils import commit_with_handling

main = Blueprint('main', __name__)


def _parse_position_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _handle_vacancy_action(action, position_id):
    if action == 'add':
        if ActiveVacancy.query.filter_by(position_id=position_id).first():
            flash("Эта вакансия уже опубликована.", "warning")
            return
        db.session.add(ActiveVacancy(position_id=position_id))
        commit_with_handling("Вакансия опубликована.", "Не удалось опубликовать вакансию.")
        return

    if action == 'remove':
        vacancy = ActiveVacancy.query.filter_by(position_id=position_id).first()
        if vacancy is None:
            flash("Публикация для этой должности не найдена.", "warning")
            return
        db.session.delete(vacancy)
        commit_with_handling("Вакансия снята с публикации.", "Не удалось снять вакансию.")
        return

    flash("Неизвестное действие для вакансии.", "danger")


@main.route('/')
def home():
    return render_template('index.html')


@main.route('/about')
def about():
    return render_template('about.html')


@main.route('/contact')
def contact():
    return render_template('contacts.html')


@main.route('/products')
def products():
    return render_template('products.html')


@main.route('/services')
def services():
    return render_template('services.html')


@main.route('/vacancies', methods=['GET', 'POST'])
@login_required
def vacancies():
    if request.method == 'POST':
        if not current_user.is_admin:
            abort(403)
        pos_id = _parse_position_id(request.form.get('position_id'))
        action = request.form.get('action')
        if pos_id is None:
            flash("Некорректная должность для операции с вакансией.", "danger")
            return redirect(url_for('main.vacancies'))

        position = db.session.get(Position, pos_id)
        if position is None:
            flash("Выбранная должность не найдена.", "danger")
            return redirect(url_for('main.vacancies'))

        _handle_vacancy_action(action, pos_id)
        return redirect(url_for('main.vacancies'))

    published = ActiveVacancy.query.all()
    published_position_ids = db.session.query(ActiveVacancy.position_id)
    available_positions = (
        Position.query
        .filter(~Position.id.in_(published_position_ids))
        .order_by(Position.title.asc())
        .all()
    )
    return render_template('vacancies.html', published=published, all_positions=available_positions)
