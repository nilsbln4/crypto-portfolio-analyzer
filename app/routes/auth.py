import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.services.auth_service import AuthService, AuthError

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        user = AuthService.authenticate(email, password)
        if user:
            login_user(user)
            logger.info('Login success: %s (IP: %s)', email, request.remote_addr)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        logger.warning('Login failure: %s (IP: %s)', email, request.remote_addr)
        flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        try:
            user = AuthService.register(email, password)
            login_user(user)
            return redirect(url_for('dashboard.index'))
        except AuthError as e:
            flash(str(e), 'error')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info('Logout: %s', current_user.email)
    logout_user()
    return redirect(url_for('auth.login'))
