from datetime import datetime
import pytest

from app import create_app
from app.models import torneo

USER = {'id': 1, 'username': 'profesor', 'nombre': 'Andrea Torres', 'rol': 'profesor'}
STUDENT = {'id': 2, 'username': 'estudiante', 'nombre': 'Martín Pérez', 'rol': 'estudiante'}
TOURNAMENTS = [
    {'id': 1, 'slug': 'futbol', 'nombre': 'Fútbol', 'equipos': 4, 'completados': 2},
    {'id': 2, 'slug': 'basketball', 'nombre': 'Básquetbol', 'equipos': 0, 'completados': 0},
    {'id': 3, 'slug': 'voleibol', 'nombre': 'Voleibol', 'equipos': 0, 'completados': 0},
]
TEAMS = [
    {'id': index, 'torneo_id': 1, 'usuario_id': 2 if index == 1 else 1,
     'nombre': name, 'curso': course, 'creador': 'Andrea Torres',
     'created_at': datetime(2026, 10, 7, 12)}
    for index, (name, course) in enumerate([
        ('Los Cóndores', '3° Medio A'), ('Atlético Escolar', '2° Medio B'),
        ('Los Pumas', '4° Medio A'), ('Deportivo Norte', '3° Medio B')], 1)
]
MATCHES = [
    {'id': 1, 'fase': 'semifinal1', 'equipo_a_id': 1, 'equipo_b_id': 2,
     'equipo_a': 'Los Cóndores', 'equipo_b': 'Atlético Escolar', 'ganador_id': 1, 'ganador': 'Los Cóndores'},
    {'id': 2, 'fase': 'semifinal2', 'equipo_a_id': 3, 'equipo_b_id': 4,
     'equipo_a': 'Los Pumas', 'equipo_b': 'Deportivo Norte', 'ganador_id': 4, 'ganador': 'Deportivo Norte'},
    {'id': 3, 'fase': 'final', 'equipo_a_id': 1, 'equipo_b_id': 4,
     'equipo_a': 'Los Cóndores', 'equipo_b': 'Deportivo Norte', 'ganador_id': None, 'ganador': None},
]


@pytest.fixture
def app(monkeypatch):
    # Dobles exclusivamente en pruebas; la aplicación real sólo utiliza PyMySQL.
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-' * 8,
                      'DB_HOST': '127.0.0.1', 'SESSION_COOKIE_SECURE': False,
                      'APP_ENV': 'development', 'TRUSTED_HOSTS': ['localhost', '127.0.0.1']})
    monkeypatch.setattr('app.security.session_user', lambda token: USER.copy() if token else None)
    monkeypatch.setattr(torneo, 'list_tournaments', lambda: TOURNAMENTS)
    monkeypatch.setattr(torneo, 'get_tournament', lambda slug: next((t for t in TOURNAMENTS if t['slug'] == slug), None))
    monkeypatch.setattr(torneo, 'registrations', lambda tid: TEAMS if tid == 1 else [])
    monkeypatch.setattr(torneo, 'matches', lambda tid: MATCHES if tid == 1 else [])
    monkeypatch.setattr(torneo, 'recent_registrations', lambda user: [
        dict(t, deporte='Fútbol', slug='futbol') for t in TEAMS if user['rol'] == 'profesor' or t['usuario_id'] == user['id']])
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed_client(client):
    with client.session_transaction() as session:
        session['auth_token'] = 'test-session'
    return client


def csrf_token(client, url='/login'):
    import re
    response = client.get(url)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, response.get_data(as_text=True)
    return match.group(1)
