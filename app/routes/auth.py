from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.models.usuario import authenticate, revoke_session
from app.security import login_required
from app.validation import clean_email

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
@bp.route('/login.html', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('main.dashboard'))
    username = ''
    error = None
    status = 200
    if request.method == 'POST':
        username = request.form.get('usuario', '').strip().lower()
        password = request.form.get('contrasena', '')
        remember = request.form.get('recordar') == 'on'
        try:
            clean_email(username)
            if not 1 <= len(password) <= 128:
                raise ValueError('Introduce una contraseña de hasta 128 caracteres.')
        except ValueError as exc:
            error = str(exc)
            status = 400
        if not error:
            token, error = authenticate(username, password, request.remote_addr or 'unknown', remember)
            if token:
                revoke_session(session.get('auth_token'))
                session.clear()
                session['auth_token'] = token
                session.permanent = remember
                return redirect(url_for('main.dashboard'))
            status = 429 if error.startswith('Demasiados') else 401
    response = render_template('login.html', username=username, error=error)
    if status == 429:
        return response, status, {'Retry-After': '900'}
    return response, status


@bp.post('/logout')
@login_required
def logout():
    revoke_session(session.get('auth_token'))
    session.clear()
    flash('Cerraste sesión correctamente.', 'success')
    return redirect(url_for('auth.login'))
