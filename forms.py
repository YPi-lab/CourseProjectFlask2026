from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired, Length, EqualTo, Optional, Email


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class DepartmentForm(FlaskForm):
    name = StringField('Название отдела', validators=[DataRequired()])
    parent_id = SelectField('Родительский отдел', coerce=int, validators=[Optional()])
    submit = SubmitField('Сохранить отдел')


class PositionForm(FlaskForm):
    title = StringField('Название должности', validators=[DataRequired()])
    department_id = SelectField('Отдел', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить должность')


class EmployeeForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    middle_name = StringField('Отчество', validators=[Optional()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Телефон', validators=[DataRequired()])

    hire_date = DateField('Дата активации', format='%Y-%m-%d', validators=[Optional()])

    position_id = SelectField('Должность', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Активен', default=True)
    submit = SubmitField('Сохранить')
