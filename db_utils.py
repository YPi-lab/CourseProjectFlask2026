from flask import current_app, flash
from sqlalchemy.exc import SQLAlchemyError

from models import db


def commit_with_handling(success_message=None, error_message="Ошибка при сохранении данных.", category="success"):
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(error_message)
        flash(error_message, "danger")
        return False

    if success_message:
        flash(success_message, category)
    return True
