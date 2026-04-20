from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, Email, Regexp, ValidationError


def strip_filter(value):
    return value.strip() if isinstance(value, str) else value


def lower_strip_filter(value):
    return value.strip().lower() if isinstance(value, str) else value


class RuSelectField(SelectField):
    def pre_validate(self, form):
        try:
            super().pre_validate(form)
        except ValidationError as exc:
            raise ValidationError("Выберите корректное значение из списка.") from exc


class RuDateField(DateField):
    def process_formdata(self, valuelist):
        try:
            super().process_formdata(valuelist)
        except ValueError as exc:
            raise ValueError("Введите дату в формате ГГГГ-ММ-ДД.") from exc


class RegisterForm(FlaskForm):
    username = StringField(
        'Логин',
        validators=[
            DataRequired(message="Поле обязательно для заполнения."),
            Length(min=4, max=20, message="Логин должен содержать от 4 до 20 символов."),
        ],
        filters=[strip_filter],
    )
    password = PasswordField('Пароль', validators=[DataRequired(message="Поле обязательно для заполнения."), Length(min=8, max=20, message="Пароль должен содержать от 8 до 20 символов."),
                                                   Regexp(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$',
                                                          message="Пароль должен содержать буквы и цифры")])
    confirm_password = PasswordField('Подтвердите пароль',
                                     validators=[DataRequired(message="Поле обязательно для заполнения."), EqualTo('password', message="Пароли не совпадают")])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(message="Поле обязательно для заполнения.")], filters=[strip_filter])
    password = PasswordField('Пароль', validators=[DataRequired(message="Поле обязательно для заполнения.")])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired(message="Поле обязательно для заполнения.")])
    new_password = PasswordField(
        'Новый пароль',
        validators=[
            DataRequired(message="Поле обязательно для заполнения."),
            Length(min=8, max=20, message="Пароль должен содержать от 8 до 20 символов."),
            Regexp(
                r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$',
                message="Пароль должен содержать буквы и цифры",
            ),
        ],
    )
    confirm_new_password = PasswordField(
        'Подтвердите новый пароль',
        validators=[DataRequired(message="Поле обязательно для заполнения."), EqualTo('new_password', message="Пароли не совпадают")],
    )
    submit = SubmitField('Изменить пароль')


class DeleteAccountForm(FlaskForm):
    password = PasswordField('Пароль для подтверждения', validators=[DataRequired(message="Поле обязательно для заполнения.")])
    submit = SubmitField('Удалить аккаунт')


class DepartmentForm(FlaskForm):
    name = StringField('Название отдела', validators=[DataRequired(message="Поле обязательно для заполнения.")], filters=[strip_filter])
    parent_id = RuSelectField('Родительский отдел', coerce=int, validators=[Optional()])
    submit = SubmitField('Сохранить отдел')


class PositionForm(FlaskForm):
    title = StringField('Название должности', validators=[DataRequired(message="Поле обязательно для заполнения.")], filters=[strip_filter])
    department_id = RuSelectField('Отдел', coerce=int, validators=[DataRequired(message="Поле обязательно для заполнения.")])
    submit = SubmitField('Сохранить должность')


class EmployeeForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(message="Поле обязательно для заполнения.")], filters=[strip_filter])
    first_name = StringField('Имя', validators=[DataRequired(message="Поле обязательно для заполнения.")], filters=[strip_filter])
    middle_name = StringField('Отчество', validators=[Optional()], filters=[strip_filter])
    email = StringField(
        'Эл. почта',
        validators=[
            DataRequired(message="Поле обязательно для заполнения."),
            Email(message="Введите корректный email-адрес."),
        ],
        filters=[lower_strip_filter],
    )
    phone = StringField(
        'Телефон',
        validators=[
            DataRequired(message="Поле обязательно для заполнения."),
            Regexp(
                r'^\+?\d[\d\s\-\(\)]{9,19}$',
                message="Телефон должен содержать только цифры, пробелы, скобки, дефисы и при необходимости знак +",
            ),
        ],
        filters=[strip_filter],
    )

    hire_date = RuDateField('Дата активации', format='%Y-%m-%d', validators=[Optional()])

    position_id = RuSelectField('Должность', coerce=int, validators=[DataRequired(message="Поле обязательно для заполнения.")])
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Сохранить')
