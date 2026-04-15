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


def get_department_tree(exclude_id=None):
    parents = Department.query.filter_by(parent_id=None).order_by(Department.name).all()
    choices = [('0', '--- КОРНЕВОЙ ОТДЕЛ ---')]
    for parent in parents:
        if exclude_id and parent.id == exclude_id:
            continue
        choices.append((str(parent.id), f"{parent.name.upper()}"))
        children = parent.sub_departments.order_by(Department.name).all()
        for child in children:
            if exclude_id and child.id == exclude_id:
                continue
            choices.append((str(child.id), f"    - {child.name}"))
    return choices


@admin_bp.route('/departments/add', methods=['GET', 'POST'])
@login_required
def add_department():
    form = DepartmentForm()
    form.parent_id.choices = get_department_tree()
    if form.validate_on_submit():
        duplicate = Department.query.filter_by(name=form.name.data).first()
        if duplicate:
            flash(f'Ошибка: отдел "{form.name.data}" уже существует!', 'danger')
            return render_template('admin/add_departments.html', form=form)
        parent_id = int(form.parent_id.data) if form.parent_id.data != '0' else None
        new_department = Department(name=form.name.data, parent_id=parent_id)
        try:
            db.session.add(new_department)
            db.session.commit()
            flash('Структура обновлена!', 'success')
            return redirect(url_for('admin.departments'))
        except Exception:
            db.session.rollback()
            flash('Произошла ошибка при сохранении в базу данных.', 'danger')
    return render_template('admin/add_departments.html', form=form)


@admin_bp.route('/department/edit/<int:dept_id>', methods=['GET', 'POST'])
@login_required
def edit_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    form = DepartmentForm(obj=dept)
    form.parent_id.choices = get_department_tree(exclude_id=dept_id)

    if form.validate_on_submit():
        duplicate = Department.query.filter(
            Department.name == form.name.data,
            Department.id != dept_id
        ).first()
        if duplicate:
            flash(f'Ошибка: название "{form.name.data}" уже занято другим отделом!', 'danger')
            return render_template('admin/add_departments.html', form=form, edit=True)
        dept.name = form.name.data
        dept.parent_id = int(form.parent_id.data) if form.parent_id.data != '0' else None
        try:
            db.session.commit()
            flash('Отдел обновлен', 'success')
            return redirect(url_for('admin.departments'))
        except Exception:
            db.session.rollback()
            flash('Ошибка при сохранении изменений', 'danger')
    if request.method == 'GET':
        form.parent_id.data = str(dept.parent_id or '0')
    return render_template('admin/add_departments.html', form=form, edit=True)


@admin_bp.route('/departments/<int:dept_id>')
@login_required
def department_detail(dept_id):
    dept = Department.query.get_or_404(dept_id)
    employees = dept.all_employees
    return render_template('admin/department_detail.html', dept=dept, employees=employees)


@admin_bp.route('/department/delete/<int:dept_id>', methods=['POST'])
@login_required
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    flash(f'Отдел {dept.name} и вся его структура удалены', 'success')
    return redirect(url_for('admin.departments'))


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
        if Employee.query.filter_by(email=form.email.data).first():
            flash(f'Ошибка: Почта {form.email.data} уже используется!', 'danger')
            return render_template('admin/add_employee.html', form=form)
        if Employee.query.filter_by(phone=form.phone.data).first():
            flash(f'Ошибка: Телефон {form.phone.data} уже зарегистрирован!', 'danger')
            return render_template('admin/add_employee.html', form=form)
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
        try:
            db.session.add(new_emp)
            db.session.commit()
            flash('Сотрудник добавлен', 'success')
            return redirect(url_for('admin.employees'))
        except Exception:
            db.session.rollback()
            flash('Критическая ошибка базы данных', 'danger')
    return render_template('admin/add_employee.html', form=form)


@admin_bp.route('/employee/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    form = EmployeeForm(obj=emp)
    form.position_id.choices = [(p.id, f"{p.title} ({p.department.name})") for p in Position.query.all()]
    if form.validate_on_submit():
        if Employee.query.filter(Employee.email == form.email.data, Employee.id != emp_id).first():
            flash(f'Ошибка: Email {form.email.data} уже занят!', 'danger')
            return render_template('admin/add_employee.html', form=form, edit=True)
        if Employee.query.filter(Employee.phone == form.phone.data, Employee.id != emp_id).first():
            flash(f'Ошибка: Телефон {form.phone.data} уже занят!', 'danger')
            return render_template('admin/add_employee.html', form=form, edit=True)
        emp.last_name = form.last_name.data
        emp.first_name = form.first_name.data
        emp.middle_name = form.middle_name.data
        emp.email = form.email.data
        emp.phone = form.phone.data
        emp.position_id = form.position_id.data
        emp.is_active = form.is_active.data
        try:
            db.session.commit()
            flash('Данные сотрудника обновлены', 'success')
            return redirect(url_for('admin.employees'))
        except Exception:
            db.session.rollback()
            flash('Ошибка при сохранении изменений', 'danger')
    return render_template('admin/add_employee.html', form=form, edit=True)


@admin_bp.route('/employee/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    name = emp.full_name
    db.session.delete(emp)
    db.session.commit()
    flash(f'Сотрудник {name} удален из базы', 'success')
    return redirect(request.args.get('next') or url_for('admin.employees'))


@admin_bp.route('/positions')
@login_required
def positions():
    all_positions = Position.query.join(Department).all()
    return render_template('admin/position.html', positions=all_positions)


@admin_bp.route('/positions/add', methods=['GET', 'POST'])
@login_required
def add_position():
    form = PositionForm()
    # Используем иерархию отделов для привязки должности
    # Убираем '0', так как должность обязана быть в отделе
    form.department_id.choices = [(c[0], c[1]) for c in get_department_tree() if c[0] != '0']

    if form.validate_on_submit():
        existing_pos = Position.query.filter_by(
            title=form.title.data,
            department_id=form.department_id.data
        ).first()

        if existing_pos:
            dept_name = dict(form.department_id.choices).get(form.department_id.data)
            flash(f'Ошибка: Должность "{form.title.data}" уже есть в отделе "{dept_name}"!', 'danger')
            return render_template('admin/add_position.html', form=form)

        new_position = Position(
            title=form.title.data,
            department_id=form.department_id.data,
        )
        try:
            db.session.add(new_position)
            db.session.commit()
            flash(f'Должность "{new_position.title}" создана!', 'success')
            return redirect(url_for('admin.positions'))
        except Exception:
            db.session.rollback()
            flash('Ошибка при сохранении в базу данных', 'danger')

    return render_template('admin/add_position.html', form=form)


@admin_bp.route('/position/edit/<int:pos_id>', methods=['GET', 'POST'])
@login_required
def edit_position(pos_id):
    pos = Position.query.get_or_404(pos_id)
    form = PositionForm(obj=pos)
    form.department_id.choices = [(c[0], c[1]) for c in get_department_tree() if c[0] != '0']

    if form.validate_on_submit():
        duplicate = Position.query.filter(
            Position.title == form.title.data,
            Position.department_id == form.department_id.data,
            Position.id != pos_id
        ).first()

        if duplicate:
            dept_name = dict(form.department_id.choices).get(form.department_id.data)
            flash(f'Ошибка: В отделе "{dept_name}" уже существует должность "{form.title.data}"!', 'danger')
            return render_template('admin/add_position.html', form=form, edit=True)

        pos.title = form.title.data
        pos.department_id = form.department_id.data

        try:
            db.session.commit()
            flash(f'Должность "{pos.title}" обновлена', 'success')
            return redirect(url_for('admin.positions'))
        except Exception:
            db.session.rollback()
            flash('Ошибка при обновлении данных', 'danger')

    return render_template('admin/add_position.html', form=form, edit=True)


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
