from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.services.admin_service import AdminService
from app.services.reporting_service import ReportingService

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/admin')
@admin_required
def console():
    users = AdminService.list_users()
    transactions = AdminService.get_all_transactions()
    report = ReportingService.generate_admin_report()
    return render_template(
        'admin/console.html',
        users=users, transactions=transactions, report=report,
    )


@admin_bp.route('/admin/disable/<int:user_id>', methods=['POST'])
@admin_required
def disable_user(user_id):
    try:
        AdminService.disable_user(current_user.id, user_id)
        flash('User disabled.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.console'))


@admin_bp.route('/admin/enable/<int:user_id>', methods=['POST'])
@admin_required
def enable_user(user_id):
    try:
        AdminService.enable_user(current_user.id, user_id)
        flash('User enabled.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.console'))


@admin_bp.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    new_password = request.form.get('new_password', '')
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('admin.console'))
    try:
        AdminService.reset_password(current_user.id, user_id, new_password)
        flash('Password reset successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.console'))
