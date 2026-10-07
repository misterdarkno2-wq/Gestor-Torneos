from functools import wraps

from flask import abort, g, redirect, request, session, url_for
from flask_wtf import CSRFProtect

from app.models.usuario import session_user

csrf = CSRFProtect()


def load_user():
    if request.endpoint == 'static':
        g.user = None
        return
    g.user = session_user(session.get('auth_token'))
    if not g.user and session.get('auth_token'):
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


def professor_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user['rol'] != 'profesor':
            abort(403)
        return view(*args, **kwargs)
    return wrapped
