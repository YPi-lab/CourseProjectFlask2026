from .admin_core import admin_bp, admin_required
from .admin_dashboard_routes import register_dashboard_routes
from .admin_department_routes import register_department_routes
from .admin_employee_routes import register_employee_routes
from .admin_position_routes import register_position_routes
from .admin_user_routes import register_user_routes

register_dashboard_routes(admin_bp)
register_department_routes(admin_bp)
register_employee_routes(admin_bp)
register_position_routes(admin_bp)
register_user_routes(admin_bp)

__all__ = ["admin_bp", "admin_required"]
