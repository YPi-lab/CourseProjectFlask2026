from flask import render_template

from .admin_core import admin_required
from project_app.models import Department, Employee


def register_dashboard_routes(admin_bp):
    @admin_bp.route("/index")
    @admin_required
    def index():
        stats = {
            "departments_count": Department.query.count(),
            "employee_count": Employee.query.count(),
            "active_count": Employee.query.filter_by(is_active=True).count(),
        }
        return render_template("admin/index.html", stats=stats)
