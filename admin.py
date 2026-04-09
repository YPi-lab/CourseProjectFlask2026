from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from forms import DepartmentForm, EmployeeForm, PositionForm
from models import Department, db, Employee, Position, User

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/index')
@login_required
def index():
    stats = {
        'departments_count': Department.query.count(),
        'employee_count': Employee.query.count(),
        'active_count': Employee.query.filter_by(is_active=True).count()
    }
    return render_template('admin/index.html', stats=stats)


@admin_bp.route('/departments')
@login_required
def departments():
    root_department = Department.query.filter_by(parent_id=None).all()
    return render_template('admin/departments.html', departments=root_department)


@admin_bp.route('/departments/add', methods=['GET', 'POST'])
@login_required
def add_department():
    form = DepartmentForm()
    existing_department = Department.query.all()
    choices = [(0, '--Корень--')]
    for d in existing_department:
        choices.append((d.id, d.name))
    form.parent_id.choices = choices
    if form.validate_on_submit():
        new_department = Department(name=form.name.data,
                                    parent_id=form.parent_id.data if form.parent_id.data != 0 else None)
        db.session.add(new_department)
        db.session.commit()
        flash('Структура обновлена!', 'success')
        return redirect(url_for('admin.departments'))
    return render_template('admin/add_departments.html', form=form)


@admin_bp.route('/departments/<int:dept_id>')
@login_required
def department_detail(dept_id):
    dept = Department.query.get_or_404(dept_id)
    employees = dept.all_employees
    return render_template('admin/department_detail.html', dept=dept, employees=employees)


@admin_bp.route('/employees')
@login_required
def employees():
    all_employees = Employee.query.all()
    return render_template('admin/employees.html', employees=all_employees)


@admin_bp.route('/employee/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    form = EmployeeForm()
    form.position_id.choices = [(p.id, f"{p.title} ({p.department.name})") for p in Position.query.all()]

    if form.validate_on_submit():
        new_emp = Employee(
            last_name=form.last_name.data,
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            email=form.email.data,
            phone=form.phone.data,
            hire_date=form.hire_date.data,
            position_id=form.position_id.data,
            is_active=form.is_active.data
        )
        db.session.add(new_emp)
        db.session.commit()
        flash('Сотрудник добавлен', 'success')
        return redirect(url_for('admin.departments'))
    return render_template('admin/add_employee.html', form=form)


@admin_bp.route('/positions')
@login_required
def positions():
    all_positions = Position.query.join(Department).all()
    return render_template('admin/position.html', positions=all_positions)


@admin_bp.route('/positions/add', methods=['GET', 'POST'])
@login_required
def add_position():
    form = PositionForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.all()]

    if form.validate_on_submit():
        new_position = Position(
            title=form.title.data,
            department_id=form.department_id.data,
        )
        db.session.add(new_position)
        db.session.commit()
        flash(f'Должность "{new_position.title}" создана!', 'success')

        next_page = request.args.get('next')
        return redirect(next_page or url_for('admin.positions'))

    return render_template('admin/add_position.html', form=form)


@admin_bp.route('/department/edit/<int:dept_id>', methods=['GET', 'POST'])
@login_required
def edit_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    form = DepartmentForm(obj=dept)
    form.parent_id.choices = [(0, '-- Корень --')] + [(d.id, d.name) for d in
                                                      Department.query.filter(Department.id != dept_id).all()]

    if form.validate_on_submit():
        dept.name = form.name.data
        dept.parent_id = form.parent_id.data if form.parent_id.data != 0 else None
        db.session.commit()
        flash('Отдел обновлен', 'success')
        return redirect(url_for('admin.departments'))
    return render_template('admin/add_departments.html', form=form, edit=True)


@admin_bp.route('/employee/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    form = EmployeeForm(obj=emp)
    form.position_id.choices = [(p.id, f"{p.title} ({p.department.name})") for p in Position.query.all()]

    if form.validate_on_submit():
        emp.last_name = form.last_name.data
        emp.first_name = form.first_name.data
        emp.email = form.email.data
        emp.phone = form.phone.data
        emp.position_id = form.position_id.data
        emp.is_active = form.is_active.data
        db.session.commit()
        flash('Данные сотрудника обновлены', 'success')
        return redirect(request.args.get('next') or url_for('admin.employees'))
    return render_template('admin/add_employee.html', form=form, edit=True)


@admin_bp.route('/department/delete/<int:dept_id>', methods=['POST'])
@login_required
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    flash(f'Отдел {dept.name} и вся его структура удалены', 'success')
    return redirect(url_for('admin.departments'))


@admin_bp.route('/position/delete/<int:pos_id>', methods=['POST'])
@login_required
def delete_position(pos_id):
    pos = Position.query.get_or_404(pos_id)

    affected_employees = Employee.query.filter_by(position_id=pos.id).all()

    for emp in affected_employees:
        emp.position_id = None
        emp.is_active = False

    db.session.delete(pos)
    db.session.commit()
    flash(f'Должность "{pos.title}" удалена. {len(affected_employees)} чел. переведены в архив.', 'warning')
    return redirect(url_for('admin.positions'))


@admin_bp.route('/employee/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    name = emp.full_name
    db.session.delete(emp)
    db.session.commit()
    flash(f'Сотрудник {name} удален из базы', 'success')
    return redirect(request.args.get('next') or url_for('admin.employees'))


@admin_bp.route('/position/edit/<int:pos_id>', methods=['GET', 'POST'])
@login_required
def edit_position(pos_id):
    pos = Position.query.get_or_404(pos_id)
    form = PositionForm(obj=pos)

    form.department_id.choices = [(d.id, d.name) for d in Department.query.all()]

    if form.validate_on_submit():
        pos.title = form.title.data
        pos.department_id = form.department_id.data
        db.session.commit()
        flash(f'Должность "{pos.title}" обновлена', 'success')
        return redirect(url_for('admin.positions'))

    return render_template('admin/add_position.html', form=form, edit=True)


@admin_bp.route('/users')
@login_required
def user_list():
    if not current_user.is_admin:
        abort(403)
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {user.username} удален', 'warning')
    return redirect(url_for('admin.user_list'))


@admin_bp.route('/toggle_admin/<int:user_id>', methods=['POST'])
@login_required
def toggle_admin(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Вы не можете лишить прав администратора самого себя', 'danger')
        return redirect(url_for('admin.user_list'))

    user.is_admin = not user.is_admin
    db.session.commit()

    status = "назначен администратором" if user.is_admin else "лишен прав администратора"
    flash(f'Пользователь {user.username} {status}', 'success')
    return redirect(url_for('admin.user_list'))
