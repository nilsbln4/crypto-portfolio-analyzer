from functools import wraps

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.services.reporting_service import ReportingService

reporting_bp = Blueprint('reporting', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


@reporting_bp.route('/reports')
@login_required
def index():
    report = ReportingService.generate_user_report(current_user.id)
    admin_report = None
    if current_user.is_admin():
        admin_report = ReportingService.generate_admin_report()
    return render_template(
        'reporting/index.html', report=report, admin_report=admin_report,
    )
