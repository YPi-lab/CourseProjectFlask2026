from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user, login_required

from project_app.models import Position, db, ActiveVacancy
from project_app.utils.db_utils import commit_with_handling

main = Blueprint('main', __name__)


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
        pos_id_raw = request.form.get('position_id')
        action = request.form.get('action')
        try:
            pos_id = int(pos_id_raw)
        except (TypeError, ValueError):
            flash("Некорректная должность для операции с вакансией.", "danger")
            return redirect(url_for('main.vacancies'))

        position = db.session.get(Position, pos_id)
        if position is None:
            flash("Выбранная должность не найдена.", "danger")
            return redirect(url_for('main.vacancies'))

        if action == 'add':
            if not ActiveVacancy.query.filter_by(position_id=pos_id).first():
                db.session.add(ActiveVacancy(position_id=pos_id))
                commit_with_handling("Вакансия опубликована.", "Не удалось опубликовать вакансию.")
            else:
                flash("Эта вакансия уже опубликована.", "warning")
        elif action == 'remove':
            v = ActiveVacancy.query.filter_by(position_id=pos_id).first()
            if v:
                db.session.delete(v)
                commit_with_handling("Вакансия снята с публикации.", "Не удалось снять вакансию.")
            else:
                flash("Публикация для этой должности не найдена.", "warning")
        else:
            flash("Неизвестное действие для вакансии.", "danger")
        return redirect(url_for('main.vacancies'))

    published = ActiveVacancy.query.all()
    all_positions = Position.query.all()
    return render_template('vacancies.html', published=published, all_positions=all_positions)
