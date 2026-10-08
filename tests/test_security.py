from unittest.mock import Mock

from app.database.connection import SupabaseError
import pytest

from app import create_app
from app.models import torneo
from app.validation import clean_text
from tests.conftest import STUDENT, csrf_token


@pytest.mark.parametrize('path', ['/dashboard', '/dashboard-profesor.html', '/dashboard-estudiante.html',
    '/torneos/futbol', '/profesor-voleibol.html', '/estudiante-basketball.html', '/confirmacion.html'])
def test_pages_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert '/login' in response.location


def test_login_csrf_and_hash_authentication(client, monkeypatch):
    authenticate = Mock(return_value=('new-session', None))
    monkeypatch.setattr('app.routes.auth.authenticate', authenticate)
    assert client.post('/login', data={'usuario': 'profesor@example.test', 'contrasena': 'password'}).status_code == 400
    authenticate.assert_not_called()
    token = csrf_token(client)
    response = client.post('/login', data={'csrf_token': token, 'usuario': 'PROFESOR@EXAMPLE.TEST', 'contrasena': 'password', 'recordar': 'on'})
    assert response.status_code == 302
    authenticate.assert_called_once_with('profesor@example.test', 'password', '127.0.0.1', True)
    assert 'HttpOnly' in response.headers['Set-Cookie'] and 'SameSite=Lax' in response.headers['Set-Cookie']
    with client.session_transaction() as session:
        assert session['auth_token'] == 'new-session' and session.permanent


def test_logout_revokes_session(signed_client, monkeypatch):
    revoke = Mock()
    monkeypatch.setattr('app.routes.auth.revoke_session', revoke)
    token = csrf_token(signed_client, '/dashboard')
    assert signed_client.get('/logout').status_code == 405
    assert signed_client.post('/logout', data={'csrf_token': token}).status_code == 302
    revoke.assert_called_once_with('test-session')
    with signed_client.session_transaction() as session:
        assert 'auth_token' not in session


def test_student_cannot_write_results_or_open_professor_pages(signed_client, monkeypatch):
    monkeypatch.setattr('app.security.session_user', lambda token: STUDENT.copy())
    token = csrf_token(signed_client, '/dashboard')
    assert signed_client.get('/dashboard-profesor.html').status_code == 403
    assert signed_client.get('/profesor-futbol.html').status_code == 403
    assert signed_client.post('/torneos/futbol/llaves', data={'csrf_token': token}).status_code == 403
    assert signed_client.post('/torneos/futbol/partidos/1', data={'csrf_token': token, 'ganador': '1'}).status_code == 403


def test_student_only_sees_own_edit_controls(signed_client, monkeypatch):
    monkeypatch.setattr('app.security.session_user', lambda token: STUDENT.copy())
    html = signed_client.get('/torneos/futbol').get_data(as_text=True)
    assert 'id="edit-1"' in html and 'id="edit-2"' not in html
    assert 'Guardar resultado' not in html and 'Guardar llaves' not in html


def test_database_failure_is_503_and_static_stays_available(client, monkeypatch):
    monkeypatch.setattr('app.routes.auth.authenticate', Mock(side_effect=SupabaseError(503)))
    token = csrf_token(client)
    response = client.post('/login', data={'csrf_token': token, 'usuario': 'profesor@example.test', 'contrasena': 'pw'})
    assert response.status_code == 503
    assert b'private detail' not in response.data
    with client.session_transaction() as session:
        session['auth_token'] = 'test'
    monkeypatch.setattr('app.security.session_user', Mock(side_effect=SupabaseError(503)))
    assert client.get('/dashboard').status_code == 503
    assert client.get('/static/css/app.css').status_code == 200


def test_html_escapes_account_name(signed_client, monkeypatch):
    monkeypatch.setattr('app.security.session_user', lambda token: {'id': 1, 'rol': 'profesor', 'nombre': '<script>alert(1)</script>'})
    html = signed_client.get('/dashboard').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_login_lockout_returns_retry_header(client, monkeypatch):
    monkeypatch.setattr('app.routes.auth.authenticate', Mock(return_value=(None, 'Demasiados intentos. Espera 15 minutos.')))
    token = csrf_token(client)
    response = client.post('/login', data={'csrf_token': token, 'usuario': 'profesor@example.test', 'contrasena': 'bad'})
    assert response.status_code == 429 and response.headers['Retry-After'] == '900'


def test_registration_confirmation_requires_saved_action(signed_client, monkeypatch):
    register = Mock(return_value=3)
    monkeypatch.setattr(torneo, 'register', register)
    assert signed_client.get('/confirmacion.html').status_code == 302
    token = csrf_token(signed_client, '/torneos/futbol')
    response = signed_client.post('/torneos/futbol/inscripciones', data={'csrf_token': token, 'nombre': 'Los Pumas', 'curso': '3° A'})
    assert response.status_code == 302 and '/confirmacion.html' in response.location
    register.assert_called_once_with(1, 1, 'Los Pumas', '3° A')
    assert signed_client.get('/confirmacion.html').status_code == 200
    assert signed_client.get('/confirmacion.html').status_code == 302


@pytest.mark.parametrize('value', ["Robert'); DROP TABLE usuarios;--", '<script>alert(1)</script>', 'x', 'A' * 61])
def test_registration_validation_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        clean_text(value, 'Equipo', 60)


def test_supabase_rejects_plain_http():
    with pytest.raises(RuntimeError, match='HTTPS'):
        create_app({'SECRET_KEY': 'x' * 64, 'APP_ENV': 'development', 'SUPABASE_URL': 'http://example.org'})


def test_production_requires_secure_cookies():
    with pytest.raises(RuntimeError, match='COOKIE_SECURE'):
        create_app({'SECRET_KEY': 'x' * 64, 'APP_ENV': 'production', 'SESSION_COOKIE_SECURE': False})


def test_headers_and_missing_paths(client):
    response = client.get('/login')
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.get('/no-existe').status_code == 404


def test_professor_can_create_tournament_and_student_is_blocked(signed_client, monkeypatch):
    manage=Mock(return_value=10)
    monkeypatch.setattr(torneo,'manage_tournament',manage)
    token=csrf_token(signed_client,'/dashboard')
    form={'csrf_token':token,'nombre':'Ajedrez Primavera','slug':'ajedrez-primavera',
          'modalidad':'individual','fecha_limite':'2026-12-31','abiertas':'on'}
    response=signed_client.post('/torneos/administrar',data=form)
    assert response.status_code==302 and '/torneos/ajedrez-primavera' in response.location
    manage.assert_called_once_with('Ajedrez Primavera','ajedrez-primavera','individual','2026-12-31',True,None)
    monkeypatch.setattr('app.security.session_user',lambda token:STUDENT.copy())
    assert signed_client.post('/torneos/administrar',data=form).status_code==403
    assert manage.call_count==1
