from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

from db_utils import commit_with_handling
from forms import RegisterForm, LoginForm
from models import db, User

auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Ошибка: Пользователь с таким логином уже существует!', 'danger')
            return render_template('registration.html', form=form)
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2')
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        if commit_with_handling(
            'Регистрация завершена. Теперь выполните вход в систему.',
            'Не удалось завершить регистрацию пользователя.'
        ):
            return redirect(url_for('auth.login'))
    return render_template('registration.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('main.home'))

        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))
