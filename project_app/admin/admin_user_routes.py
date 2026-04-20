from flask import flash, redirect, render_template, url_for
from flask_login import current_user

from .admin_core import admin_required
from project_app.utils.db_utils import commit_with_handling
from project_app.models import User, db


def register_user_routes(admin_bp):
    @admin_bp.route("/users")
    @admin_required
    def user_list():
        users = User.query.all()
        return render_template("admin/users.html", users=users)

    @admin_bp.route("/delete_user/<int:user_id>", methods=["POST"])
    @admin_required
    def delete_user(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            flash("Нельзя удалить текущего администратора из своей сессии.", "danger")
            return redirect(url_for("admin.user_list"))

        username = user.username
        db.session.delete(user)
        if commit_with_handling(f"Пользователь {username} удален", "Не удалось удалить пользователя.", category="warning"):
            return redirect(url_for("admin.user_list"))
        return redirect(url_for("admin.user_list"))

    @admin_bp.route("/toggle_admin/<int:user_id>", methods=["POST"])
    @admin_required
    def toggle_admin(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            flash("Вы не можете лишить прав администратора самого себя", "danger")
            return redirect(url_for("admin.user_list"))

        user.is_admin = not user.is_admin
        status = "назначен администратором" if user.is_admin else "лишен прав администратора"
        if commit_with_handling(f"Пользователь {user.username} {status}", "Не удалось изменить роль пользователя."):
            return redirect(url_for("admin.user_list"))
        return redirect(url_for("admin.user_list"))
