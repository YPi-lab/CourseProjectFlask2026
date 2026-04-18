from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, Email, Regexp


def strip_filter(value):
    return value.strip() if isinstance(value, str) else value


def lower_strip_filter(value):
    return value.strip().lower() if isinstance(value, str) else value


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=20)], filters=[strip_filter])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=8, max=20),
                                                   Regexp(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$',
                                                          message="Пароль должен содержать буквы и цифры")])
    confirm_password = PasswordField('Подтвердите пароль',
                                     validators=[DataRequired(), EqualTo('password', message="Пароли не совпадают")])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()], filters=[strip_filter])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField(
        'Новый пароль',
        validators=[
            DataRequired(),
            Length(min=8, max=20),
            Regexp(
                r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$',
                message="Пароль должен содержать буквы и цифры",
            ),
        ],
    )
    confirm_new_password = PasswordField(
        'Подтвердите новый пароль',
        validators=[DataRequired(), EqualTo('new_password', message="Пароли не совпадают")],
    )
    submit = SubmitField('Изменить пароль')


class DeleteAccountForm(FlaskForm):
    password = PasswordField('Пароль для подтверждения', validators=[DataRequired()])
    submit = SubmitField('Удалить аккаунт')


class DepartmentForm(FlaskForm):
    name = StringField('Название отдела', validators=[DataRequired()], filters=[strip_filter])
    parent_id = SelectField('Родительский отдел', coerce=int, validators=[Optional()])
    submit = SubmitField('Сохранить отдел')


class PositionForm(FlaskForm):
    title = StringField('Название должности', validators=[DataRequired()], filters=[strip_filter])
    department_id = SelectField('Отдел', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить должность')


class EmployeeForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired()], filters=[strip_filter])
    first_name = StringField('Имя', validators=[DataRequired()], filters=[strip_filter])
    middle_name = StringField('Отчество', validators=[Optional()], filters=[strip_filter])
    email = StringField('Эл. почта', validators=[DataRequired(), Email()], filters=[lower_strip_filter])
    phone = StringField(
        'Телефон',
        validators=[
            DataRequired(),
            Regexp(
                r'^\+?\d[\d\s\-\(\)]{9,19}$',
                message="Телефон должен содержать только цифры, пробелы, скобки, дефисы и при необходимости знак +",
            ),
        ],
        filters=[strip_filter],
    )

    hire_date = DateField('Дата активации', format='%Y-%m-%d', validators=[Optional()])

    position_id = SelectField('Должность', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Сохранить')
