"""Prueba completa opcional con PyMySQL real en una base exclusiva y vacía."""
import os
import secrets

import pytest
from dotenv import dotenv_values

from app import create_app
from app.database.connection import fetch_one, transaction
from app.models import torneo, usuario
from config import Config

pytestmark = pytest.mark.skipif(os.getenv('RUN_MYSQL_TESTS') != '1', reason='Requiere .env.test y RUN_MYSQL_TESTS=1')


def test_real_mysql_registration_bracket_auth_and_rollback():
    values = dotenv_values('.env.test')
    name = values.get('TEST_DB_NAME', '')
    assert name.endswith('_test') and name != Config.DB_NAME, 'Usa una base exclusiva terminada en _test.'
    app = create_app({'TESTING': True, 'APP_ENV': 'development', 'SESSION_COOKIE_SECURE': False,
                      'SECRET_KEY': secrets.token_hex(32),
                      'DB_HOST': values.get('TEST_DB_HOST', '127.0.0.1'),
                      'DB_PORT': int(values.get('TEST_DB_PORT', '3306')),
                      'DB_USER': values.get('TEST_DB_USER', ''),
                      'DB_PASSWORD': values.get('TEST_DB_PASSWORD', ''),
                      'DB_NAME': name, 'DB_SSL_CA': values.get('TEST_DB_SSL_CA', '')})
    with app.app_context():
        result = app.test_cli_runner().invoke(args=['init-db'])
        assert result.exit_code == 0, result.output
        assert fetch_one('SELECT COUNT(*) AS total FROM usuarios')['total'] == 0, 'La base de pruebas debe estar vacía.'
        assert fetch_one('SELECT COUNT(*) AS total FROM inscripciones')['total'] == 0, 'La base de pruebas debe estar vacía.'
        assert fetch_one('SELECT COUNT(*) AS total FROM partidos')['total'] == 0, 'La base de pruebas debe estar vacía.'
        ids = []
        suffix = secrets.token_hex(4)
        username = 'test_' + suffix
        address = 'test-ip-' + suffix
        password = secrets.token_urlsafe(24)
        try:
            user_id = usuario.create_user(username, 'Prueba MySQL', password, 'profesor')
            ids.append(user_id)
            token, error = usuario.authenticate(username, password, address, True)
            assert token and not error
            assert usuario.session_user(token)['id'] == user_id
            usuario.revoke_session(token)
            assert usuario.session_user(token) is None
            for _ in range(5):
                assert usuario.authenticate(username, 'invalid', address)[0] is None
            assert usuario.authenticate(username, password, address)[1].startswith('Demasiados')
            tournament = torneo.get_tournament('futbol')
            tid = tournament['id']
            team_ids = [torneo.register(tid, user_id, f'Equipo {index}', '3 Medio A') for index in range(4)]
            assert len(torneo.registrations(tid)) == 4
            torneo.create_bracket(tid, team_ids)
            matches = {row['fase']: row for row in torneo.matches(tid)}
            torneo.save_winner(tid, matches['semifinal1']['id'], team_ids[0])
            torneo.save_winner(tid, matches['semifinal2']['id'], team_ids[2])
            final = next(m for m in torneo.matches(tid) if m['fase'] == 'final')
            assert (final['equipo_a_id'], final['equipo_b_id']) == (team_ids[0], team_ids[2])
            torneo.save_winner(tid, final['id'], team_ids[0])
            torneo.save_winner(tid, matches['semifinal1']['id'], team_ids[1])
            final = next(m for m in torneo.matches(tid) if m['fase'] == 'final')
            assert final['equipo_a_id'] == team_ids[1] and final['ganador_id'] is None
            with pytest.raises(PermissionError):
                torneo.edit_registration(tid, team_ids[0], {'id': 9999, 'rol': 'estudiante'}, delete=True)
            with pytest.raises(ValueError):
                torneo.edit_registration(tid, team_ids[0], {'id': user_id, 'rol': 'profesor'}, delete=True)
            with pytest.raises(RuntimeError):
                with transaction() as cursor:
                    cursor.execute('UPDATE inscripciones SET curso=%s WHERE id=%s', ('Cambiar', team_ids[0]))
                    raise RuntimeError('Revertir esta transacción')
            assert fetch_one('SELECT curso FROM inscripciones WHERE id=%s', (team_ids[0],))['curso'] == '3 Medio A'
            assert torneo.import_registrations(tid, user_id, [{'nombre': 'Equipo 0', 'curso': '3 Medio A'}]) == 0
        finally:
            # Borra exclusivamente los registros creados por esta prueba.
            with transaction() as cursor:
                for user_id in ids:
                    cursor.execute('DELETE p FROM partidos p JOIN inscripciones i '
                                   'ON i.id=p.equipo_a_id OR i.id=p.equipo_b_id WHERE i.usuario_id=%s', (user_id,))
                    cursor.execute('DELETE FROM inscripciones WHERE usuario_id=%s', (user_id,))
                    cursor.execute('DELETE FROM usuarios WHERE id=%s', (user_id,))
                for key in (usuario.digest('user:' + username), usuario.digest('ip:' + address)):
                    cursor.execute('DELETE FROM login_attempts WHERE attempt_key=%s', (key,))
