import argparse
import getpass

from werkzeug.security import generate_password_hash

from project_app import create_app
from project_app.models import User, db

PASSWORD_HASH_METHOD = "pbkdf2"


def parse_args():
    parser = argparse.ArgumentParser(description="Создание администратора для проекта кадрового учета на Flask.")
    parser.add_argument("--username", help="Логин администратора")
    parser.add_argument("--password", help="Пароль администратора")
    return parser.parse_args()


def prompt_if_missing(value, prompt_text, secret=False):
    if value:
        return value
    if secret:
        return getpass.getpass(prompt_text)
    return input(prompt_text).strip()


def validate_username(username):
    if len(username) < 4 or len(username) > 20:
        raise ValueError("Логин должен содержать от 4 до 20 символов.")


def validate_credentials(username, password):
    validate_username(username)
    if len(password) < 8 or len(password) > 20:
        raise ValueError("Пароль должен содержать от 8 до 20 символов.")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise ValueError("Пароль должен содержать и буквы, и цифры.")


def main():
    app = create_app()
    args = parse_args()
    username = prompt_if_missing(args.username, "Логин администратора: ")
    validate_username(username)

    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            if existing_user.is_admin:
                print(f'Пользователь "{username}" уже существует и уже является администратором.')
                return
            existing_user.is_admin = True
            db.session.commit()
            print(f'Пользователь "{username}" успешно назначен администратором.')
            return

        password = prompt_if_missing(args.password, "Пароль администратора: ", secret=True)
        validate_credentials(username, password)

        admin = User(
            username=username,
            password=generate_password_hash(password, method=PASSWORD_HASH_METHOD),
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()
        print(f'Администратор "{username}" успешно создан.')


if __name__ == "__main__":
    main()
