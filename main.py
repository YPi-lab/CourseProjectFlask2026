from os import abort

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from models import Position, db, ActiveVacancy

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
    if request.method == 'POST' and current_user.is_admin:
        pos_id = request.form.get('position_id')
        action = request.form.get('action')

        if action == 'add':
            if not ActiveVacancy.query.filter_by(position_id=pos_id).first():
                db.session.add(ActiveVacancy(position_id=pos_id))
        elif action == 'remove':
            v = ActiveVacancy.query.filter_by(position_id=pos_id).first()
            if v: db.session.delete(v)

        db.session.commit()
        return redirect(url_for('main.vacancies'))

    published = ActiveVacancy.query.all()
    all_positions = Position.query.all()
    return render_template('vacancies.html', published=published, all_positions=all_positions)
