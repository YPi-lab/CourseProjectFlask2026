from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from project_app.utils.db_utils import commit_with_handling
from project_app.forms import ChangePasswordForm, DeleteAccountForm, RegisterForm, LoginForm
from project_app.models import db, User

auth = Blueprint('auth', __name__)
PASSWORD_HASH_METHOD = "pbkdf2"


def get_account_forms():
    return ChangePasswordForm(), DeleteAccountForm()


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Ошибка: Пользователь с таким логином уже существует!', 'danger')
            return render_template('registration.html', form=form)
        hashed_password = generate_password_hash(form.password.data, method=PASSWORD_HASH_METHOD)
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


@auth.route('/account', methods=['GET'])
@login_required
def account():
    password_form, delete_form = get_account_forms()
    return render_template('account.html', password_form=password_form, delete_form=delete_form)


@auth.route('/account/password', methods=['POST'])
@login_required
def change_password():
    password_form, delete_form = get_account_forms()
    if not password_form.validate_on_submit():
        return render_template('account.html', password_form=password_form, delete_form=delete_form)

    user = current_user._get_current_object()
    if not check_password_hash(user.password, password_form.current_password.data):
        flash("Текущий пароль указан неверно.", "danger")
        return redirect(url_for('auth.account'))

    if check_password_hash(user.password, password_form.new_password.data):
        flash("Новый пароль должен отличаться от текущего.", "warning")
        return redirect(url_for('auth.account'))

    user.password = generate_password_hash(password_form.new_password.data, method=PASSWORD_HASH_METHOD)
    commit_with_handling("Пароль успешно изменен.", "Не удалось изменить пароль.")
    return redirect(url_for('auth.account'))


@auth.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    delete_form = DeleteAccountForm()
    if not delete_form.validate_on_submit():
        password_form, _ = get_account_forms()
        return render_template('account.html', password_form=password_form, delete_form=delete_form)

    user = current_user._get_current_object()
    if not check_password_hash(user.password, delete_form.password.data):
        flash("Неверный пароль. Удаление аккаунта отменено.", "danger")
        return redirect(url_for('auth.account'))

    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash("Нельзя удалить последнего администратора в системе.", "danger")
        return redirect(url_for('auth.account'))

    db.session.delete(user)
    if commit_with_handling("Аккаунт удален.", "Не удалось удалить аккаунт.", category="warning"):
        logout_user()
        return redirect(url_for('auth.login'))
    return redirect(url_for('auth.account'))
